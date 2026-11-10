"""Generator: authored files -> registry/{catalog,index,graph,manifest.lock}.json
plus the D6 compat outputs (see compat.py).

Pure build step (`build`) plus explicit IO helpers (`drift`, `write_outputs`).
Outputs are deterministic: sorted keys, no timestamps, no absolute paths.
"""
import json
import os
from pathlib import Path

from . import compat, credits, jsonout, migrations, model, rules, schemacheck, tomlio
from .model import finding, sha256, sort_findings

REGISTRY_DIR = "registry"
PATHS = {
    "catalog": REGISTRY_DIR + "/catalog.json",
    "index": REGISTRY_DIR + "/index.json",
    "graph": REGISTRY_DIR + "/graph.json",
    "lock": REGISTRY_DIR + "/manifest.lock.json",
}
INDEX_BUDGET = 16834  # bytes; frozen from the P0 baseline (spec 3)
# Conditional fallback (router-v2 section 1, amendment 9): 20 480 B, usable only after a
# measured S7 miss and while the model read surface stays <= ROUTER_SURFACE_BUDGET.
INDEX_BUDGET_FALLBACK = 20480
INDEX_BUDGET_MISS = "skillkit/core/index-budget-miss.json"
INDEX_SCHEMA = 2
# Router read surface (spec 8): INDEX.md alone and INDEX.md + the meta category.
ROUTER_INDEX_BUDGET = 1795
ROUTER_SURFACE_BUDGET = 2909
INDEX_FIELDS = ("id", "type", "category", "activation", "risk", "description")
UNROUTABLE = frozenset(("manual", "dependency"))
# Optional index keys (router-v2 section 1): emitted only when non-empty / non-default.
INDEX_LISTS = ("aliases", "phrases", "requires", "composes_with", "conflicts_with", "artifacts", "platforms")
INDEX_ROUTING_ONLY = ("intents", "exclusions")


class Result:
    def __init__(self, repo, findings, outputs):
        self.repo = repo
        self.findings = findings
        self.outputs = outputs  # {relpath: bytes} or None when the model is invalid

    @property
    def errors(self):
        return [f for f in self.findings if f["severity"] == "error"]


def evaluate(root, with_drift=True, sources_root=None, provenance_mode='public', evidence_map=None):
    repo = model.load(root)
    for name in model.SCHEMA_NAMES:
        repo.schema(name)
    findings = list(repo.findings)
    findings += rules.run(repo)
    from . import taskbuild
    task_assets, task_findings, task_inputs = taskbuild.load(repo, sources_root, provenance_mode, evidence_map)
    findings += task_findings
    repo.files.update(task_inputs)
    try:
        aliases = {a: c.id for c in repo.caps if c.ok for a in c.raw.get("aliases", [])}
        migrations.load(repo.root, {c.id for c in repo.caps}, aliases)
        if (repo.root / migrations.PATH).exists():
            repo.read_text(migrations.PATH)
    except (ValueError, OSError, UnicodeError, tomlio.TomlError) as exc:
        findings.append(finding("", "migrations", "error", migrations.PATH, str(exc)))
    for path in sorted((repo.root / "sources").glob("*")):
        if path.is_file() and path.suffix in (".md", ".toml"):
            repo.read_text(path.relative_to(repo.root).as_posix())
    try:
        credits.build([dict(model.normalize(c), path=c.doc_path) for c in repo.caps if c.ok],
                      {p: b for p, b in repo.files.items() if p.startswith("sources/")})
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        findings.append(finding("", "provenance-notices", "error", credits.NOTICES, str(exc)))
    outputs = None
    if not any(f["severity"] == "error" for f in findings):
        objs, outputs = build(repo, task_assets)
        findings += validate_outputs(repo, objs)
        surface_findings = router_surface(outputs)
        budget = INDEX_BUDGET
        if not surface_findings and recorded_index_miss(repo.root):
            budget = INDEX_BUDGET_FALLBACK
        index_size = len(outputs[PATHS["index"]])
        if index_size > budget:
            findings.append(finding("", "index-budget", "error", PATHS["index"],
                                    "%d bytes exceeds the %d byte budget" % (index_size, budget)))
        findings += surface_findings
        if with_drift:
            findings += drift(repo.root, outputs)
    return Result(repo, sort_findings(findings), outputs)


def recorded_index_miss(root):
    """A missing or invalid measured-miss record never enables the fallback."""
    try:
        record = json.loads((Path(root) / INDEX_BUDGET_MISS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (isinstance(record, dict)
            and record.get("budget_bytes") == INDEX_BUDGET
            and type(record.get("measured_bytes")) is int
            and record["measured_bytes"] > INDEX_BUDGET
            and isinstance(record.get("evidence"), str)
            and bool(record["evidence"].strip()))


def _without_install_notes(entry):
    """Catalog copy of an entry minus the free-text install note (the legacy
    compat files still carry it; the machine registry does not)."""
    install = (entry.get("manifest") or {}).get("install")
    if not isinstance(install, dict) or "note" not in install:
        return entry
    slim = dict(entry)
    slim["manifest"] = dict(entry["manifest"])
    slim["manifest"]["install"] = {k: v for k, v in install.items() if k != "note"}
    return slim


def index_row(e):
    """registry/index.json entry for a normalised capability (schema 2). Optional
    keys are omitted when empty; `name` only when it differs from `id`; `routable`
    only as false."""
    r = e["routing"]
    row = {k: e[k] for k in INDEX_FIELDS}
    row.update(provides=r["provides"], path=e["path"])
    if e["name"] != e["id"]:
        row["name"] = e["name"]
    for key in INDEX_ROUTING_ONLY:
        if r[key]:
            row[key] = list(r[key])
    for key in INDEX_LISTS:
        value = e["aliases"] if key == "aliases" else r[key]
        if value:
            row[key] = list(value)
    if e["activation"] in UNROUTABLE:
        row["routable"] = False
    return row


def build(repo, task_assets=None):
    """Return ({name: object}, {relpath: bytes}) for every generated file."""
    caps = sorted((c for c in repo.caps if c.ok), key=lambda c: c.id)
    entries, index = [], []
    graph_edges = set()
    for c in caps:
        e = model.normalize(c)
        if c.is_pointer:
            e["path"] = c.doc_path
            e["body_bytes"] = 0
            e["sha256"] = c.sha_toml
            e["manifest_sha256"] = c.sha_doc
            e["manifest"] = {k: v for k, v in sorted(c.manifest.items())
                             if k in ("upstream", "install", "summary", "notes")}
        else:
            e["path"] = c.doc_path
            e["body_bytes"] = c.size_doc
            e["sha256"] = c.sha_doc
        entries.append(e)
        r = e["routing"]
        index.append(index_row(e))
        for rel in rules.RELATIONS:
            for target in r[rel]:
                graph_edges.add((e["id"], rel, target))
    objs = {
        "catalog": {"schema": 1, "capabilities": [_without_install_notes(e) for e in entries]},
        "index": {"schema": INDEX_SCHEMA, "capabilities": index},
        "graph": {
            "nodes": [c.id for c in caps],
            "edges": [{"from": a, "rel": rel, "to": b} for a, rel, b in sorted(graph_edges, key=lambda t: (t[0], t[1], t[2]))],
        },
    }
    outputs = {PATHS[k]: jsonout.encode(v) for k, v in objs.items() if k != "index"}
    outputs[PATHS["index"]] = jsonout.encode_inline_lists(objs["index"])
    outputs.update(compat.build(entries))
    outputs.update(credits.build(entries, {p: b for p, b in repo.files.items() if p.startswith("sources/")}))
    if task_assets is not None:
        from . import taskbuild
        outputs.update(taskbuild.outputs(task_assets))
        linked = outputs[compat.INDEX_MD] + taskbuild.RATING_LINK.encode("utf-8")
        if len(linked) <= ROUTER_INDEX_BUDGET and len(linked) + len(outputs.get("categories/meta.md", b"")) <= ROUTER_SURFACE_BUDGET:
            outputs[compat.INDEX_MD] = linked
    inputs = {}
    for c in caps:
        inputs[c.toml_path] = c.sha_toml
        inputs[c.doc_path] = c.sha_doc
    for rel, data in list(repo.files.items()) + list(repo.schema_inputs.items()):
        if rel.startswith(("policy/", "schema/", "taxonomy/", "ratings/", "sources/", migrations.PATH)):
            inputs[rel] = sha256(data)
    objs["lock"] = {
        "inputs": dict(sorted(inputs.items())),
        "outputs": {p: sha256(b) for p, b in sorted(outputs.items())},
    }
    outputs[PATHS["lock"]] = jsonout.encode(objs["lock"])
    return objs, outputs


def router_surface(outputs):
    index = len(outputs.get(compat.INDEX_MD, b""))
    meta = len(outputs.get(compat.CATEGORY_DIR + "/meta.md", b""))
    out = []
    if index > ROUTER_INDEX_BUDGET:
        out.append(finding("", "router-surface", "error", compat.INDEX_MD,
                           "%d bytes exceeds the %d byte budget" % (index, ROUTER_INDEX_BUDGET)))
    if index + meta > ROUTER_SURFACE_BUDGET:
        out.append(finding("", "router-surface", "error", compat.INDEX_MD,
                           "INDEX.md + meta category is %d bytes, over the %d byte budget"
                           % (index + meta, ROUTER_SURFACE_BUDGET)))
    return out


def validate_outputs(repo, objs):
    out = []
    for name in ("catalog", "index", "graph", "lock"):
        schema = repo.schema(name)
        if schema is None:
            continue
        for ptr, msg in schemacheck.validate(objs[name], schema):
            out.append(finding("", "schema.generated", "error", PATHS[name], "%s: %s" % (ptr or "/", msg)))
    return out


def drift(root, outputs):
    out = []
    for rel in sorted(outputs):
        path = Path(root) / rel
        try:
            current = path.read_bytes()
        except FileNotFoundError:
            out.append(finding("", "generated-missing", "error", rel, "generated file is missing; run gen"))
            continue
        except OSError as exc:
            out.append(finding("", "read-error", "error", rel, "cannot read: %s" % type(exc).__name__))
            continue
        if current != outputs[rel]:
            out.append(finding("", "generated-drift", "error", rel,
                               "differs from regeneration (hand edit or stale); run gen"))
    # A category whose last member was retired is no longer generated; a
    # leftover file would advertise retired assets through dangling links.
    category_dir = Path(root) / compat.CATEGORY_DIR
    if any(rel.startswith(compat.CATEGORY_DIR + "/") for rel in outputs) and category_dir.is_dir():
        for path in sorted(category_dir.glob("*.md")):
            rel = "%s/%s" % (compat.CATEGORY_DIR, path.name)
            if rel not in outputs:
                out.append(finding("", "generated-stale", "error", rel,
                                   "generated category no longer produced; delete it"))
    return out


def write_outputs(root, outputs):
    """Write only files whose bytes differ. Returns the written paths."""
    written = []
    for rel in sorted(outputs):
        path = Path(root) / rel
        if Path(rel).is_absolute() or ".." in Path(rel).parts or any(p.is_symlink() for p in (path, *path.parents) if p != Path(root).parent):
            raise OSError("refusing generated output through symlink or unsafe path")
        try:
            if path.read_bytes() == outputs[rel]:
                continue
        except FileNotFoundError:
            pass
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        if tmp.is_symlink():
            raise OSError("refusing generated temporary output through symlink")
        tmp.write_bytes(outputs[rel])
        os.replace(tmp, path)
        written.append(rel)
    return written
