"""Cross-field rules (spec 1.4, 11.1, 11.3). Pure: Repo in, findings out."""
from . import tomlio
from .model import finding, normalize

ROUTER_ID = "skill-router"
WINDOWS_RESERVED = frozenset(
    ["con", "prn", "aux", "nul"]
    + ["com%d" % i for i in range(1, 10)]
    + ["lpt%d" % i for i in range(1, 10)]
)
UNVERIFIED_LICENSE = "LicenseRef-unverified"
UNPINNED_REFS = frozenset(("main", "master", "HEAD"))
RELATIONS = ("requires", "composes_with", "conflicts_with")
# Authoring limits that keep registry/index.json inside its byte budget (router-v2
# section 1): item counts per list, characters per string.
MAX_ITEMS = (("intents", 4), ("phrases", 4), ("exclusions", 2), ("composes_with", 2), ("aliases", 2))
MAX_CHARS = (("intents", 32), ("phrases", 32), ("exclusions", 24), ("aliases", 32))
VOCAB_PATH = "policy/routing-vocab.toml"
# manifest.yaml key -> accessor into the normalised capability entry
MANIFEST_DUPLICATES = (
    ("id", lambda e: e["id"]),
    ("name", lambda e: e["name"]),
    ("type", lambda e: e["type"]),
    ("category", lambda e: e["category"]),
    ("activation", lambda e: e["activation"]),
    ("risk", lambda e: e["risk"]),
    ("description", lambda e: e["description"]),
)


def run(repo):
    out = []
    add = lambda *a: out.append(finding(*a))
    parsed = [c for c in repo.caps if isinstance(c.raw, dict)]
    known_ids = {c.id for c in parsed}

    # ---- identity rules (apply even when other validation failed) --------
    groups = {}
    for c in parsed:
        groups.setdefault(c.id.lower(), []).append(c)
        if c.id != c.dir_name:
            add(c.id, "id-dir-mismatch", "error", c.toml_path,
                "id '%s' != directory name '%s'" % (c.id, c.dir_name))
        if c.raw.get("type") != c.type and "type" in c.raw:
            add(c.id, "type-dir-mismatch", "error", c.toml_path,
                "type '%s' does not match its directory (expected '%s')" % (c.raw["type"], c.type))
        for label in {c.id, c.dir_name}:
            low = label.lower()
            if low in WINDOWS_RESERVED or label.endswith((".", " ")):
                add(c.id, "id-reserved", "error", c.toml_path,
                    "'%s' is a reserved or non-portable name" % label)
    for low in sorted(groups):
        members = groups[low]
        if len(members) < 2:
            continue
        exact = len({m.id for m in members}) == 1
        rule = "id-duplicate" if exact else "id-case-collision"
        names = ", ".join(sorted(m.toml_path for m in members))
        for m in members:
            add(m.id, rule, "error", m.toml_path, "id collides with another capability (%s)" % names)

    alias_owner = {}
    for c in parsed:
        for a in c.raw.get("aliases", []) if isinstance(c.raw.get("aliases"), list) else []:
            if not isinstance(a, str):
                continue
            if a in known_ids or (a in alias_owner and alias_owner[a] != c.id):
                add(c.id, "alias-collision", "error", c.toml_path,
                    "alias '%s' collides with an id or another alias" % a)
            alias_owner.setdefault(a, c.id)

    # ---- activation=always uniqueness ------------------------------------
    always = [c for c in parsed if c.raw.get("activation") == "always"]
    for c in always:
        if c.id != ROUTER_ID:
            add(c.id, "always-unique", "error", c.toml_path,
                "only '%s' may have activation=always" % ROUTER_ID)
    if not any(c.id == ROUTER_ID for c in always):
        add("", "always-unique", "error", ".",
            "exactly one capability must have activation=always and it must be '%s'" % ROUTER_ID)

    # ---- per-capability rules (valid shape only) -------------------------
    valid = [c for c in repo.caps if c.ok]
    unverified = []
    by_id = {x.id: x for x in parsed}
    for c in valid:
        entry = normalize(c)
        raw = c.raw
        routing = entry["routing"]
        if c.type == "skill":
            if "name" in raw or "description" in raw:
                add(c.id, "authority-split", "error", c.toml_path,
                    "name/description belong in SKILL.md frontmatter for skills")
            dmi = c.frontmatter["disable-model-invocation"]
            want = entry["activation"] in ("explicit", "manual")
            if dmi != want:
                add(c.id, "activation-dmi", "error", c.doc_path,
                    "activation=%s requires disable-model-invocation: %s" %
                    (entry["activation"], "true" if want else "false"))
            lines = c.body_text.splitlines()
            title = next((i for i, l in enumerate(lines) if l.startswith("# ")), None)
            quick = next((i for i, l in enumerate(lines) if l == "## Quick Index"), None)
            if title is None or quick is None or quick <= title or quick >= 100:
                add(c.id, "body-structure", "error", c.doc_path,
                    "'# Title' then '## Quick Index' required within the first 100 lines")
        prov = entry["provenance"]
        if prov["license"].startswith(UNVERIFIED_LICENSE):
            unverified.append(c.id)
        if prov["origin"] == "derived":
            # source/ref/adaptation presence and the hex ref are enforced by
            # the capability schema; the URL shape and the licence gate are here.
            if not prov["source"].startswith(("https://", "http://")):
                add(c.id, "provenance-source-url", "error", c.toml_path,
                    "derived entries need an http(s) source URL")
            if prov["license"] not in repo.licenses and not prov.get("license_waiver"):
                add(c.id, "license-not-allowed", "error", c.toml_path,
                    "license '%s' is not allowlisted and has no license_waiver" % prov["license"])
        for rel in RELATIONS:
            for target in routing[rel]:
                if target == c.id:
                    add(c.id, "ref-self", "error", c.toml_path, "%s references itself" % rel)
                elif target not in known_ids:
                    add(c.id, "ref-unknown", "error", c.toml_path,
                        "%s references unknown id '%s'" % (rel, target))
        for target in routing["requires"]:
            other = by_id.get(target)
            if other is not None and other is not c and other.raw.get("activation") == "explicit":
                add(c.id, "requires-explicit", "error", c.toml_path,
                    "requires target '%s' has activation=explicit and cannot be pulled in as a dependency" % target)
        _routing_limits(c, entry, repo, add)
        for target in sorted(set(routing["requires"]) & set(routing["conflicts_with"])):
            add(c.id, "requires-conflicts-overlap", "error", c.toml_path,
                "'%s' is in both requires and conflicts_with" % target)
        for target in routing["conflicts_with"]:
            other = by_id.get(target)
            if other is not None and other is not c:
                back = other.raw.get("routing", {}).get("conflicts_with", [])
                if c.id not in back:
                    add(c.id, "conflict-asymmetric", "warn", c.toml_path,
                        "conflicts_with '%s' but '%s' does not list '%s'" % (target, target, c.id))
        if c.is_pointer:
            _manifest_rules(c, entry, add)
        if not routing["intents"]:
            add(c.id, "todo-intent", "info", c.toml_path, "routing.intents is empty (placeholder)")
        if tomlio.table_has_marker(c.toml_text, "access", "unreviewed"):
            add(c.id, "unreviewed-access", "info", c.toml_path, "[access] values are marked unreviewed")

    if unverified:
        add("", "license-unverified", "warn", "policy/licenses.toml",
            "%d capabilit%s carry %s (owner action: verify the upstream licence and set an SPDX id): %s"
            % (len(unverified), "y" if len(unverified) == 1 else "ies", UNVERIFIED_LICENSE,
               ", ".join(sorted(unverified))))

    # ---- requires graph must be acyclic ----------------------------------
    graph = {c.id: sorted(set(t for t in c.raw.get("routing", {}).get("requires", []) if t in known_ids and t != c.id))
             for c in valid}
    for comp in _cycles(graph):
        first = sorted(comp)[0]
        owner = next(c for c in valid if c.id == first)
        add(first, "requires-cycle", "error", owner.toml_path,
            "requires cycle: %s" % " -> ".join(sorted(comp)))
    return out


def _routing_limits(c, entry, repo, add):
    values = dict(entry["routing"], aliases=entry["aliases"])
    for key, limit in MAX_ITEMS:
        if len(values[key]) > limit:
            add(c.id, "routing-limit", "error", c.toml_path,
                "%s has %d items, the limit is %d" % (key, len(values[key]), limit))
    for key, limit in MAX_CHARS:
        for item in values[key]:
            if len(item) > limit:
                add(c.id, "routing-limit", "error", c.toml_path,
                    "%s entry '%s' is %d characters, the limit is %d" % (key, item, len(item), limit))
    for key in ("platforms", "artifacts"):
        if not values[key]:
            continue
        if repo.vocab is None:
            add(c.id, "routing-vocab", "error", c.toml_path,
                "%s is set but %s is missing or unusable" % (key, VOCAB_PATH))
            continue
        for item in values[key]:
            if item not in repo.vocab[key]:
                add(c.id, "routing-vocab", "error", c.toml_path,
                    "%s value '%s' is not in the closed vocabulary (%s)" % (key, item, VOCAB_PATH))


def _manifest_rules(c, entry, add):
    m = c.manifest
    for key in ("upstream", "install", "summary"):
        if not m.get(key):
            add(c.id, "manifest-missing-field", "error", c.doc_path, "manifest.yaml is missing '%s'" % key)
    for key, getter in MANIFEST_DUPLICATES:
        if key in m and m[key] != getter(entry):
            add(c.id, "manifest-drift", "error", c.doc_path,
                "'%s' differs from capability.toml" % key)
    routing = entry["routing"]
    for key, expected in (("capabilities", routing["provides"]),
                          ("requires", routing["requires"]),
                          ("conflicts", routing["conflicts_with"])):
        if key in m and sorted(m[key]) != sorted(expected):
            add(c.id, "manifest-drift", "error", c.doc_path,
                "'%s' differs from capability.toml" % key)
    ref = m.get("upstream", {}).get("ref")
    if ref in UNPINNED_REFS:
        add(c.id, "unpinned-ref", "info", c.doc_path, "upstream ref '%s' is not pinned" % ref)


def _cycles(graph):
    """Return strongly connected components that contain a cycle (Tarjan)."""
    index, low, on, stack, out = {}, {}, set(), [], []
    counter = [0]

    def visit(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in graph.get(v, ()):
            if w not in graph:
                continue
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1 or v in graph.get(v, ()):
                out.append(comp)

    for v in sorted(graph):
        if v not in index:
            visit(v)
    return sorted(out, key=lambda comp: sorted(comp))
