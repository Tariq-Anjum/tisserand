"""Ratchet baselines for the neutrality and privacy lints (spec 5.1, 11.8).

File: `policy/<lint>-baseline.json` =
    {"counts": {path: n}, "raises": [{"date","path","from","to","reason"}]}
The neutrality baseline also carries "waivers": {path: n} (its own ratchet).
Counts may fall freely; a rise is refused unless `--allow-raise "<reason>"`
is given, which appends a `raises` entry.
"""
import datetime
import json
import os
from pathlib import Path

from . import jsonout

MIN_REASON = 8
RAISE_KEYS = ("date", "path", "from", "to", "reason")


def rel_path(lint):
    return "policy/%s-baseline.json" % lint


def today():
    return datetime.date.today().isoformat()


def empty(extra_maps=()):
    data = {"counts": {}, "raises": []}
    for key in extra_maps:
        data[key] = {}
    return data


def load(root, lint, extra_maps=()):
    """Return (data, existed, problems). A missing file is an empty baseline."""
    path = Path(root) / rel_path(lint)
    if not path.is_file():
        return empty(extra_maps), False, []
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return empty(extra_maps), True, ["cannot parse baseline: %s" % type(exc).__name__]
    problems = []
    if not isinstance(obj, dict):
        return empty(extra_maps), True, ["baseline must be an object"]
    data = empty(extra_maps)
    for key in ("counts",) + tuple(extra_maps):
        value = obj.get(key, {})
        if not isinstance(value, dict) or not all(
                isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool) and v >= 1
                for k, v in value.items()):
            problems.append("'%s' must map paths to positive integers" % key)
        else:
            data[key] = dict(value)
    raises = obj.get("raises", [])
    if not isinstance(raises, list) or not all(
            isinstance(r, dict) and sorted(r) == sorted(RAISE_KEYS) for r in raises):
        problems.append("'raises' must be a list of {%s} objects" % ",".join(RAISE_KEYS))
    else:
        data["raises"] = raises
    unknown = sorted(set(obj) - {"counts", "raises"} - set(extra_maps))
    if unknown:
        problems.append("unknown key(s): %s" % ", ".join(unknown))
    return data, True, problems


def exceeded(counts, allowed):
    """[(path, allowed, now)] for every path whose count rose above baseline."""
    return [(p, allowed.get(p, 0), n) for p, n in sorted(counts.items()) if n > allowed.get(p, 0)]


def build_update(old, existed, maps, reason, extra_maps=()):
    """New baseline data from current `maps` ({"counts": {...}, ...}).

    Returns (data, rises). `rises` = [(label, from, to)] needed; when
    non-empty and `reason` is falsy the caller must refuse to write. A
    baseline that did not exist yet is initialised without raises.
    """
    data = empty(extra_maps)
    data["raises"] = list(old["raises"])
    rises = []
    for key in ("counts",) + tuple(extra_maps):
        now = {p: n for p, n in sorted(maps.get(key, {}).items()) if n > 0}
        data[key] = now
        if existed:
            prefix = "" if key == "counts" else key + ":"
            for path, was, n in exceeded(now, old[key]):
                rises.append((prefix + path, was, n))
    if rises and reason:
        stamp = today()
        for label, was, n in rises:
            data["raises"].append({"date": stamp, "path": label, "from": was, "to": n, "reason": reason})
    return data, rises


def write(root, lint, data):
    path = Path(root) / rel_path(lint)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(jsonout.encode(data))
    os.replace(tmp, path)
    return rel_path(lint)
