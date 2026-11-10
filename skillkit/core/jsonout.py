"""Deterministic JSON serialisation for generated files (spec D2)."""
import json


def dumps(obj):
    """UTF-8-safe text, sorted keys, 2-space indent, LF, trailing newline."""
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def encode(obj):
    return dumps(obj).encode("utf-8")


def _inline(value):
    return "[" + ", ".join(json.dumps(v, ensure_ascii=False) for v in value) + "]"


def _render(obj, level):
    pad = "  " * (level + 1)
    if isinstance(obj, dict) and obj:
        body = ",\n".join("%s%s: %s" % (pad, json.dumps(k, ensure_ascii=False), _render(obj[k], level + 1))
                          for k in sorted(obj))
        return "{\n%s\n%s}" % (body, "  " * level)
    if isinstance(obj, list) and obj:
        if all(isinstance(v, str) for v in obj):
            return _inline(obj)
        body = ",\n".join(pad + _render(v, level + 1) for v in obj)
        return "[\n%s\n%s]" % (body, "  " * level)
    return json.dumps(obj, ensure_ascii=False)


def dumps_inline_lists(obj):
    """Like `dumps`, but a non-empty list made only of strings is written on one
    line (`"phrases": ["a", "b"]`). Used for registry/index.json only; every other
    generated JSON keeps `dumps`. Output equals `dumps` when no such list exists."""
    return _render(obj, 0) + "\n"


def encode_inline_lists(obj):
    return dumps_inline_lists(obj).encode("utf-8")
