"""Small glob matcher for repo-relative '/' paths (stdlib `re` only).

Supported: `*` (no '/'), `?`, `[set]`, `**/` (zero or more directories) and
a trailing `/**` or bare `**` (everything below). Used for lint zones, file
allowlists and scan exclusions.
"""
import re


def _translate(pattern):
    out, i, n = [], 0, len(pattern)
    while i < n:
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "[":
            j = pattern.find("]", i + 2)
            if j == -1:
                out.append(re.escape(c))
                i += 1
            else:
                body = pattern[i + 1:j]
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append("[" + body.replace("\\", "\\\\") + "]")
                i = j + 1
        else:
            out.append(re.escape(c))
            i += 1
    return "".join(out)


def compile_glob(pattern):
    """Anchored matcher for a repo-relative glob."""
    return re.compile(_translate(pattern.lstrip("/")) + r"\Z", re.S)


class GlobSet:
    """Ordered list of globs; `match(rel)` is true if any glob matches."""

    def __init__(self, patterns):
        self.patterns = tuple(patterns)
        self._rx = [compile_glob(p) for p in self.patterns]

    def match(self, rel):
        return any(rx.match(rel) for rx in self._rx)


class Excludes:
    """gitignore-style exclusion list (documented subset).

    `name/` matches directories only; a pattern without '/' matches a path
    component at any depth; a pattern containing '/' (or starting with '/')
    is anchored at the root. No negation. Blank lines and '#' comments are
    ignored.
    """

    def __init__(self, patterns):
        self._rules = []
        for raw in patterns:
            p = raw.strip()
            if not p or p.startswith("#") or p.startswith("!"):
                continue
            dir_only = p.endswith("/")
            p = p.rstrip("/")
            anchored = p.startswith("/") or "/" in p
            self._rules.append((compile_glob(p), dir_only, anchored))

    def excluded(self, rel, is_dir):
        parts = rel.split("/")
        for i in range(len(parts)):
            sub_is_dir = is_dir or i < len(parts) - 1
            sub = "/".join(parts[:i + 1])
            for rx, dir_only, anchored in self._rules:
                if dir_only and not sub_is_dir:
                    continue
                target = sub if anchored else parts[i]
                if rx.match(target):
                    return True
        return False
