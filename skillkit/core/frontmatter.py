"""Strict SKILL.md frontmatter parser (spec section 2).

Exactly the keys name, description, disable-model-invocation; one per line as
`key: value`. No nesting, no multi-line values, no anchors, no escapes.
"""
import re

ALLOWED_KEYS = ("name", "description", "disable-model-invocation")
_LINE = re.compile(r"^([a-z-]+): (.*)$")


def _value(raw):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    if raw == "true":
        return True
    if raw == "false":
        return False
    return raw


def _needs_quotes(raw):
    """True when an unquoted value would not be a plain YAML scalar (strict YAML parsers reject it)."""
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return False
    return ": " in raw or " #" in raw or raw.endswith(":") or (raw[:1] in tuple("[]{}&*!|>%@`,'\"#"))


def parse(text):
    """Return (data, errors, body_start) where body_start is the 0-based line
    index of the first line after the closing delimiter."""
    if "\r" in text:
        return None, ["CRLF line endings are not allowed"], 0
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        return None, ["first line must be '---'"], 0
    end = None
    for i in range(1, len(lines)):
        if lines[i] == "---":
            end = i
            break
    if end is None:
        return None, ["frontmatter is not closed with '---'"], 0
    data = {}
    errors = []
    for offset, line in enumerate(lines[1:end], start=2):
        m = _LINE.match(line)
        if not m:
            errors.append("line %d: expected 'key: value'" % offset)
            continue
        key, raw = m.group(1), m.group(2)
        if key not in ALLOWED_KEYS:
            errors.append("line %d: unknown key '%s'" % (offset, key))
        elif key in data:
            errors.append("line %d: duplicate key '%s'" % (offset, key))
        elif _needs_quotes(raw):
            errors.append("line %d: value for '%s' must be quoted (contains ': ', ' #' or a leading YAML indicator)" % (offset, key))
        else:
            data[key] = _value(raw)
    if errors:
        return None, errors, end + 1
    return data, [], end + 1
