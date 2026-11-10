"""Optional, bounded decision cache at the router I/O boundary."""
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from .core.route import normalize, plan
from .core.route.params import ROUTER_NAME, ROUTER_VERSION

LIMIT = 1000
_ENTRY_PATH = re.compile(r"\A([0-9a-f]{2})/([0-9a-f]{64})\.json\Z")


def directory(root, option):
    value = option if option is not None else os.environ.get("SKILLKIT_CACHE_DIR")
    if not value:
        return None
    if value.startswith("~"):
        raise ValueError("cache path must not use home expansion")
    path, root = Path(value).resolve(), Path(root).resolve()
    if path == root or root in path.parents:
        allowed = root / ".cache"
        if path == allowed or allowed not in path.parents:
            raise ValueError("cache inside repository must be under .cache/")
    return path


def key(task, ctx, index, params, registry_hash, stopwords_hash, rung_sha256=None):
    q = normalize.normalize(task, index.stopwords, params["tokens"]["stem"])
    parts = [q.key, registry_hash, ROUTER_NAME + "/" + ('2' if rung_sha256 is not None else ROUTER_VERSION),
             index.params_sha256, stopwords_hash, json.dumps([sorted(ctx.platforms), sorted(ctx.artifacts)],
                                                             ensure_ascii=False, separators=(",", ":"))]
    if rung_sha256 is not None:
        parts.append(rung_sha256)
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _read_entry(path, digest, router_version=None):
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        result = obj["plan"]
        if obj["key"] != digest or obj["plan_sha256"] != hashlib.sha256(plan.encode(result)).hexdigest():
            return None
        allowed = {ROUTER_NAME + '/' + router_version} if router_version else {ROUTER_NAME + '/1', ROUTER_NAME + '/2'}
        if not isinstance(result, dict) or result.get("router") not in allowed:
            return None
        return result
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        return None


def get(directory, digest, router_version=ROUTER_VERSION):
    return _read_entry(directory / digest[:2] / (digest + ".json"), digest, router_version)


def put(directory, digest, result):
    path = directory / digest[:2] / (digest + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    obj = {"key": digest, "plan": result, "plan_sha256": hashlib.sha256(plan.encode(result)).hexdigest()}
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    fd, temp = tempfile.mkstemp(prefix=".route-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    entries = []
    for candidate in directory.glob("[0-9a-f][0-9a-f]/*.json"):
        relative = candidate.relative_to(directory).as_posix()
        match = _ENTRY_PATH.fullmatch(relative)
        if not match or match.group(1) != match.group(2)[:2]:
            continue
        if _read_entry(candidate, match.group(2)) is None:
            continue
        try:
            entries.append((candidate.stat().st_mtime_ns, str(candidate.relative_to(directory)), candidate))
        except FileNotFoundError:
            pass
    for _, _, candidate in sorted(entries)[:max(0, len(entries) - LIMIT)]:
        candidate.unlink(missing_ok=True)
