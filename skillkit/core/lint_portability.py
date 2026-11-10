"""Portability lints (spec 5.3). All findings are errors; there is no baseline.

- case-insensitive path collisions
- Windows-reserved names and trailing dot/space in any path component
- repo-relative paths longer than MAX_PATH characters
- CRLF line endings in text files
- the core package must not use process spawning or executable lookup
  (`subprocess`, `os.system`, `shutil.which`); adapters may.
"""
import ast

from .model import finding
from .rules import WINDOWS_RESERVED

LINT = "portability"
MAX_PATH = 200
CORE_DIR = "skillkit/core/"
FORBIDDEN_IMPORTS = frozenset(("subprocess",))
FORBIDDEN_ATTRS = frozenset((("os", "system"), ("shutil", "which")))
FORBIDDEN_FROM = {"os": frozenset(("system",)), "shutil": frozenset(("which",))}


def _components(rel):
    return rel.split("/")


def _reserved(part):
    stem = part.split(".", 1)[0].lower()
    return stem in WINDOWS_RESERVED or part.endswith((".", " "))


def run(scan, root=None):
    out = []
    files = scan.files()
    seen = {}
    dirs = set()
    for f in files:
        parts = _components(f.rel)
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
    for rel in sorted(dirs) + [f.rel for f in files]:
        low = rel.lower()
        seen.setdefault(low, []).append(rel)
    for low in sorted(seen):
        names = sorted(set(seen[low]))
        if len(names) > 1:
            for rel in names:
                out.append(finding("", "lint-portability-case-collision", "error", rel,
                                   "path collides case-insensitively with: %s"
                                   % ", ".join(n for n in names if n != rel)))
    for rel in sorted(dirs.union(f.rel for f in files)):
        last = _components(rel)[-1]
        if _reserved(last):
            out.append(finding("", "lint-portability-reserved-name", "error", rel,
                               "'%s' is a reserved or non-portable name on some platforms" % last))
        if len(rel) > MAX_PATH and rel not in dirs:  # a long directory implies long file paths
            out.append(finding("", "lint-portability-path-length", "error", rel,
                               "path is %d characters, limit %d" % (len(rel), MAX_PATH)))
    for f in files:
        if f.text is not None:
            out.extend(scan.cached(LINT, f, lambda: _file_findings(f)))
    return _dedupe(out), None, True


def _file_findings(f):
    out = []
    if "\r" in f.text:
        out.append(finding("", "lint-portability-crlf", "error", f.rel,
                           "contains carriage returns; commit LF line endings"))
    if f.rel.startswith(CORE_DIR) and f.rel.endswith(".py"):
        out.extend(_core_imports(f))
    return out


def _key(f):
    return (f["path"], f["rule"], f["id"], f["msg"])


def _dedupe(items):
    seen, out = set(), []
    for f in items:
        k = _key(f)
        if k not in seen:
            seen.add(k)
            out.append(f)
    return out


def _core_imports(f):
    if not any(word in f.text for word in ("subprocess", "system", "which")):
        return []  # cheap prefilter: nothing to parse
    try:
        tree = ast.parse(f.text)
    except SyntaxError:
        return [finding("", "lint-portability-core-import", "error", f.rel, "cannot parse for import check")]
    out = []
    for node in ast.walk(tree):
        bad = None
        if isinstance(node, ast.Import):
            bad = next((a.name for a in node.names if a.name.split(".")[0] in FORBIDDEN_IMPORTS), None)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            top = node.module.split(".")[0]
            if top in FORBIDDEN_IMPORTS:
                bad = node.module
            elif top in FORBIDDEN_FROM:
                bad = next(("%s.%s" % (top, a.name) for a in node.names if a.name in FORBIDDEN_FROM[top]), None)
        elif (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
              and (node.value.id, node.attr) in FORBIDDEN_ATTRS):
            bad = "%s.%s" % (node.value.id, node.attr)
        if bad:
            out.append(finding("", "lint-portability-core-import", "error", f.rel,
                               "line %d: core must not use %s (adapters may)" % (node.lineno, bad)))
    return out
