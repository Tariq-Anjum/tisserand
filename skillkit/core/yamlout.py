"""Minimal block-style YAML writer for compat outputs (spec D6).

Strings are always double-quoted (JSON string syntax is valid YAML), no
anchors, no flow collections except the empty `[]` / `{}`. Keys are sorted
unless `sort_keys=False`.
"""
import json


def _scalar(value):
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise TypeError("unsupported YAML value: %s" % type(value).__name__)


def _emit(value, indent, lines, sort_keys):
    pad = "  " * indent
    if isinstance(value, dict):
        if not value:
            lines.append(pad + "{}")
            return
        keys = sorted(value) if sort_keys else list(value)
        for key in keys:
            item = value[key]
            head = pad + _scalar(str(key)) + ":"
            if isinstance(item, (dict, list)) and item:
                lines.append(head)
                _emit(item, indent + 1, lines, sort_keys)
            elif isinstance(item, dict):
                lines.append(head + " {}")
            elif isinstance(item, list):
                lines.append(head + " []")
            else:
                lines.append(head + " " + _scalar(item))
    elif isinstance(value, list):
        if not value:
            lines.append(pad + "[]")
            return
        for item in value:
            if isinstance(item, (dict, list)) and item:
                sub = []
                _emit(item, indent + 1, sub, sort_keys)
                first = sub[0].lstrip(" ")
                lines.append(pad + "- " + first)
                lines.extend(sub[1:])
            elif isinstance(item, dict):
                lines.append(pad + "- {}")
            elif isinstance(item, list):
                lines.append(pad + "- []")
            else:
                lines.append(pad + "- " + _scalar(item))
    else:
        lines.append(pad + _scalar(value))


def dumps(obj, sort_keys=True):
    lines = []
    _emit(obj, 0, lines, sort_keys)
    return "\n".join(lines) + "\n"
