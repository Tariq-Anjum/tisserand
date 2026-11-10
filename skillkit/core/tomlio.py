"""Thin wrapper over the stdlib TOML reader plus a raw-text marker scan."""
import tomllib


class TomlError(Exception):
    pass


def loads(text):
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise TomlError(str(exc)) from None


def table_has_marker(text, table, marker):
    """True if `[table]` carries `# marker` on its line or on the line before.

    The TOML parser drops comments, so the unreviewed-placeholder marker
    (spec 11.2) is detected from the raw text.
    """
    lines = text.split("\n")
    header = "[" + table + "]"
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith(header):
            continue
        rest = stripped[len(header):]
        if "#" in rest and marker in rest.split("#", 1)[1]:
            return True
        if i > 0:
            prev = lines[i - 1].strip()
            if prev.startswith("#") and marker in prev:
                return True
    return False
