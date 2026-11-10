"""Loading: discover capabilities, parse authored files, schema-validate.

Authority per field follows spec 1.3 / 11.1. Findings are plain dicts
`{"id","rule","severity","path","msg"}`; paths are repo-relative with '/'.
"""
import hashlib
import json
import re
from pathlib import Path

from . import frontmatter, legacy, schemacheck, tomlio

# (type, directory, primary document)
TYPE_DIRS = (
    ("skill", "skills", "SKILL.md"),
    ("guidance", "guidance", "GUIDANCE.md"),
    ("workflow", "workflows", "manifest.yaml"),
    ("plugin", "plugins", "manifest.yaml"),
)
SCHEMA_NAMES = ("capability", "frontmatter", "catalog", "index", "graph", "lock")
DEFAULT_LICENSES = ("Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "CC0-1.0",
                    "ISC", "MIT", "Unlicense")
BUNDLED_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schema"


def finding(cap_id, rule, severity, path, msg):
    return {"id": cap_id, "rule": rule, "severity": severity, "path": path, "msg": msg}


def sort_findings(items):
    return sorted(items, key=lambda f: (f["path"], f["rule"], f["id"], f["msg"]))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _fmt(ptr, msg):
    return "%s: %s" % (ptr or "/", msg)


class Capability:
    def __init__(self, type_, dir_name, dir_rel, doc_name):
        self.type = type_
        self.dir_name = dir_name
        self.dir_rel = dir_rel
        self.toml_path = dir_rel + "/capability.toml"
        self.doc_path = dir_rel + "/" + doc_name
        self.raw = None          # parsed capability.toml
        self.toml_text = ""
        self.frontmatter = None  # skills only
        self.body_text = ""
        self.manifest = None     # workflow/plugin only
        self.sha_toml = None
        self.sha_doc = None
        self.size_doc = 0
        self.ok = False

    @property
    def id(self):
        raw = self.raw if isinstance(self.raw, dict) else {}
        value = raw.get("id")
        return value if isinstance(value, str) else self.dir_name

    @property
    def is_pointer(self):
        return self.type in ("workflow", "plugin")


class Repo:
    def __init__(self, root):
        self.root = Path(root)
        self.caps = []
        self.files = {}        # rel path -> raw bytes of every authored input
        self.findings = []
        self.schemas = {}      # name -> dict, or None when unusable
        self.schema_inputs = {}  # "schema/<name>.schema.json" -> bytes
        self.licenses = set(DEFAULT_LICENSES)
        self.vocab = None      # {"platforms": set, "artifacts": set} from policy/routing-vocab.toml

    def add(self, *args):
        self.findings.append(finding(*args))

    def read_text(self, rel, cap_id=""):
        """Read a UTF-8 text file once; record bytes; None on failure."""
        try:
            data = (self.root / rel).read_bytes()
            text = data.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            self.add(cap_id, "read-error", "error", rel, "cannot read as UTF-8: %s" % type(exc).__name__)
            return None
        self.files[rel] = data
        return text

    def schema(self, name):
        if name in self.schemas:
            return self.schemas[name]
        fname = name + ".schema.json"
        local = self.root / "schema" / fname
        path = local if local.is_file() else BUNDLED_SCHEMA_DIR / fname
        rel = "schema/" + fname
        result = None
        try:
            data = path.read_bytes()
            obj = json.loads(data.decode("utf-8"))
            self.schema_inputs[rel] = data
            problems = schemacheck.check_schema(obj)
            if problems:
                for ptr, msg in problems:
                    self.add("", "schema.unsupported", "error", rel, _fmt(ptr, msg))
            else:
                result = obj
        except (OSError, ValueError) as exc:
            self.add("", "schema.unreadable", "error", rel, "cannot load schema: %s" % type(exc).__name__)
        self.schemas[name] = result
        return result


def load(root):
    repo = Repo(root)
    _load_policy(repo)
    for type_, dirname, doc in TYPE_DIRS:
        base = repo.root / dirname
        if not base.is_dir():
            continue
        for entry in sorted(p.name for p in base.iterdir() if p.is_dir() and not p.name.startswith(".")):
            rel = dirname + "/" + entry
            has_toml = (base / entry / "capability.toml").is_file()
            has_doc = (base / entry / doc).is_file()
            if not has_toml and not has_doc:
                continue
            cap = Capability(type_, entry, rel, doc)
            repo.caps.append(cap)
            if not has_toml:
                repo.add(entry, "capability-missing", "error", cap.toml_path, "capability.toml not found")
                continue
            if not has_doc:
                repo.add(entry, "doc-missing", "error", cap.doc_path, "%s not found" % doc)
            _load_cap(repo, cap, has_doc)
    return repo


def _load_policy(repo):
    pdir = repo.root / "policy"
    if not pdir.is_dir():
        return
    for name in sorted(p.name for p in pdir.glob("*.toml")):
        rel = "policy/" + name
        text = repo.read_text(rel)
        if text is None:
            continue
        if name == "routing-vocab.toml":
            _load_vocab(repo, rel, text)
            continue
        if name != "licenses.toml":
            continue
        try:
            data = tomlio.loads(text)
        except tomlio.TomlError as exc:
            repo.add("", "policy-parse", "error", rel, str(exc))
            continue
        allow = data.get("allow")
        if not isinstance(allow, list) or not all(isinstance(x, str) for x in allow):
            repo.add("", "policy-parse", "error", rel, "'allow' must be an array of strings")
            continue
        repo.licenses = set(allow)


VOCAB_KEYS = ("platforms", "artifacts")
_VOCAB_VALUE = re.compile(r"^[a-z0-9-]+$")


def _load_vocab(repo, rel, text):
    try:
        data = tomlio.loads(text)
    except tomlio.TomlError as exc:
        repo.add("", "policy-parse", "error", rel, str(exc))
        return
    vocab = {}
    for key in VOCAB_KEYS:
        table = data.get(key)
        allow = table.get("allow") if isinstance(table, dict) else None
        if not isinstance(allow, list) or not allow or not all(
                isinstance(x, str) and _VOCAB_VALUE.match(x) for x in allow):
            repo.add("", "policy-parse", "error", rel,
                     "[%s] 'allow' must be a non-empty array of [a-z0-9-] strings" % key)
            return
        vocab[key] = set(allow)
    repo.vocab = vocab


def _load_cap(repo, cap, has_doc):
    ok = True
    text = repo.read_text(cap.toml_path, cap.dir_name)
    if text is None:
        return
    cap.toml_text = text
    cap.sha_toml = sha256(repo.files[cap.toml_path])
    try:
        cap.raw = tomlio.loads(text)
    except tomlio.TomlError as exc:
        repo.add(cap.dir_name, "toml-parse", "error", cap.toml_path, str(exc))
        return
    cschema = repo.schema("capability")
    if cschema is None:
        ok = False
    else:
        for ptr, msg in schemacheck.validate(cap.raw, cschema):
            repo.add(cap.id, "schema.capability", "error", cap.toml_path, _fmt(ptr, msg))
            ok = False
    if has_doc:
        if cap.type in ("workflow", "plugin"):
            ok = _load_manifest(repo, cap) and ok
        else:
            ok = _load_doc(repo, cap) and ok
    else:
        ok = False
    cap.ok = ok


def _load_doc(repo, cap):
    ok = True
    text = repo.read_text(cap.doc_path, cap.id)
    if text is None:
        return False
    data = repo.files[cap.doc_path]
    cap.sha_doc = sha256(data)
    cap.size_doc = len(data)
    if cap.type != "skill":
        return True  # GUIDANCE.md frontmatter is not parsed (name/description live in the toml)
    fm, errors, body_start = frontmatter.parse(text)
    for e in errors:
        repo.add(cap.id, "frontmatter.parse", "error", cap.doc_path, e)
        ok = False
    if fm is not None:
        fschema = repo.schema("frontmatter")
        if fschema is None:
            ok = False
        else:
            for ptr, msg in schemacheck.validate(fm, fschema):
                repo.add(cap.id, "schema.frontmatter", "error", cap.doc_path, _fmt(ptr, msg))
                ok = False
        cap.frontmatter = fm
    cap.body_text = text
    return ok


def _load_manifest(repo, cap):
    text = repo.read_text(cap.doc_path, cap.id)
    if text is None:
        return False
    cap.sha_doc = sha256(repo.files[cap.doc_path])
    cap.size_doc = 0  # pointer entries carry no loadable body
    try:
        cap.manifest = legacy.parse(text)
    except legacy.LegacyYamlError as exc:
        repo.add(cap.id, "manifest.parse", "error", cap.doc_path, str(exc))
        return False
    return True


# ------------------------------------------------------------------ normalise
_ROUTING_LISTS = ("provides", "intents", "phrases", "exclusions", "artifacts",
                  "platforms", "requires", "composes_with", "conflicts_with")
_ACCESS = ("fs", "network", "shell", "secrets", "privilege")


def normalize(cap):
    """Apply spec defaults; return the catalog entry (without generated
    path/body_bytes/sha fields, which generate.py adds)."""
    raw = cap.raw
    routing = dict(raw.get("routing", {}))
    for key in _ROUTING_LISTS:
        routing.setdefault(key, [])
    access = dict(raw.get("access", {}))
    for key in _ACCESS:
        access.setdefault(key, "none")
    cost = dict(raw.get("cost", {}))
    cost.setdefault("latency", "low")
    prov = dict(raw.get("provenance", {}))
    for key in ("source", "ref", "adaptation"):
        prov.setdefault(key, "")
    entry = {
        "id": raw["id"],
        "type": raw["type"],
        "kind": raw["kind"],
        "category": raw["category"],
        "activation": raw["activation"],
        "risk": raw["risk"],
        "priority": raw.get("priority", "normal"),
        "aliases": list(raw.get("aliases", [])),
        "routing": routing,
        "cost": cost,
        "access": access,
        "provenance": prov,
    }
    if "version" in raw:
        entry["version"] = raw["version"]
    if cap.type == "skill":
        entry["name"] = cap.frontmatter["name"]
        entry["description"] = cap.frontmatter["description"]
        entry["disable-model-invocation"] = cap.frontmatter["disable-model-invocation"]
    else:
        entry["name"] = raw["name"]
        entry["description"] = raw["description"]
    return entry
