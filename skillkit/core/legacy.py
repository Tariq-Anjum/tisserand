"""Limited stdlib reader for legacy `manifest.yaml` files (spec 11.1).

Reads only the known shape: top-level scalar / list / one-level-map keys,
plain or single/double-quoted scalars, folded plain continuation lines.
Anything else raises LegacyYamlError (anchors, flow collections, block
scalars, comments, unknown keys, ...). This is not a general YAML parser.
"""
import re

SCALARS = frozenset(("id", "name", "type", "category", "activation", "risk",
                     "summary", "notes", "description"))
LISTS = frozenset(("capabilities", "requires", "conflicts"))
MAPS = {
    "upstream": frozenset(("repo", "license", "ref", "verified_on",
                           "verified_version", "package")),
    "install": frozenset(("kind", "command", "note", "package")),
}
_TOP = re.compile(r"^([a-z_]+):(?: (.*))?$")
_SUB = re.compile(r"^  ([a-z_]+):(?: (.*))?$")
_ITEM = re.compile(r"^(?:  )?- (.+)$")
_BAD_START = "&*!|>[{%@`#"


class LegacyYamlError(Exception):
    pass


def _scalar(text, where):
    text = text.strip()
    if not text:
        raise LegacyYamlError("%s: empty value" % where)
    if text[0] == "'":
        if len(text) < 2 or text[-1] != "'":
            raise LegacyYamlError("%s: unterminated quoted scalar" % where)
        inner = text[1:-1]
        if "'" in inner.replace("''", ""):
            raise LegacyYamlError("%s: unsupported quoting" % where)
        return inner.replace("''", "'")
    if text[0] == '"':
        inner = text[1:-1]
        if len(text) < 2 or text[-1] != '"' or "\\" in inner or '"' in inner:
            raise LegacyYamlError("%s: unsupported double-quoted scalar" % where)
        return inner
    if text[0] in _BAD_START:
        raise LegacyYamlError("%s: unsupported scalar syntax" % where)
    if ": " in text or " #" in text or text.endswith(":"):
        raise LegacyYamlError("%s: unsupported plain scalar" % where)
    return text


def parse(text):
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    out = {}
    i, n = 0, len(lines)

    def gather(start, min_indent):
        """Collect folded continuation lines (indent >= min_indent)."""
        parts, j = [], start
        while j < n and lines[j].startswith(" " * min_indent) and lines[j].strip():
            parts.append(lines[j].strip())
            j += 1
        return parts, j

    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m = _TOP.match(line)
        if not m:
            raise LegacyYamlError("line %d: unsupported syntax" % (i + 1))
        key, rest = m.group(1), m.group(2)
        if key in out:
            raise LegacyYamlError("line %d: duplicate key '%s'" % (i + 1, key))
        i += 1
        if key in LISTS:
            if rest == "[]":
                out[key] = []
            elif rest is None:
                items = []
                while i < n:
                    im = _ITEM.match(lines[i])
                    if not im:
                        break
                    items.append(_scalar(im.group(1), "line %d" % (i + 1)))
                    i += 1
                out[key] = items
            else:
                raise LegacyYamlError("line %d: unsupported list syntax" % i)
        elif key in MAPS:
            if rest == "{}":
                out[key] = {}
            elif rest is None:
                sub = {}
                while i < n:
                    sm = _SUB.match(lines[i])
                    if not sm:
                        break
                    sk, sv = sm.group(1), sm.group(2)
                    if sk not in MAPS[key]:
                        raise LegacyYamlError("line %d: unknown key '%s.%s'" % (i + 1, key, sk))
                    if sk in sub:
                        raise LegacyYamlError("line %d: duplicate key '%s.%s'" % (i + 1, key, sk))
                    if sv is None:
                        raise LegacyYamlError("line %d: nested values unsupported" % (i + 1))
                    first, i = i, i + 1
                    extra, i = gather(i, 4)
                    if extra and sv[0] in "'\"":
                        raise LegacyYamlError("line %d: multi-line quoted scalar" % (first + 1))
                    sub[sk] = _scalar(" ".join([sv.strip()] + extra), "line %d" % (first + 1))
                out[key] = sub
            else:
                raise LegacyYamlError("line %d: unsupported map syntax" % i)
        elif key in SCALARS:
            if rest is None:
                raise LegacyYamlError("line %d: empty value for '%s'" % (i, key))
            extra, j = gather(i, 1)
            if extra and rest[0] in "'\"":
                raise LegacyYamlError("line %d: multi-line quoted scalar" % i)
            out[key] = _scalar(" ".join([rest.strip()] + extra), "line %d" % i)
            i = j
        else:
            raise LegacyYamlError("line %d: unknown key '%s'" % (i, key))
    return out
