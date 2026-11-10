"""Optional content-addressed per-file lint memoization, outside the core.

File bytes are still read on every run. Baselines and cross-file checks are
never cached. Cache IO errors are misses, and --no-cache bypasses this module.
"""
import hashlib
import json
import os
import tempfile
from pathlib import Path

from .core import lints
from .core.scan import Scan

LINT_VERSION = 1
CACHE_PATH = ".cache/skillkit/lint-v%d.json" % LINT_VERSION


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


class CachedScan(Scan):
    def __init__(self, root):
        super().__init__(root)
        self.path = Path(root) / CACHE_PATH
        self.hits = self.misses = 0
        self._fingerprints, self._digests = {}, {}
        self._entries = {}
        try:
            doc = json.loads(self.path.read_bytes())
            if doc["version"] == LINT_VERSION and isinstance(doc["entries"], dict):
                self._entries = doc["entries"]
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def _policy_hash(self, policies, extra):
        identity = (policies, extra)
        if identity not in self._fingerprints:
            hashes = []
            for name in policies:
                try:
                    raw = (self.root / "policy" / name).read_bytes()
                except OSError:
                    raw = b""
                hashes.append((name, _sha(raw)))
            # Local denylist contents affect identity without being persisted.
            self._fingerprints[identity] = _sha(_encode([hashes, _sha(extra.encode("utf-8"))]))
        return self._fingerprints[identity]

    def cached(self, name, file, compute, policies=(), extra=""):
        slot = name + ":" + file.rel
        if file.rel not in self._digests:
            self._digests[file.rel] = _sha(file.raw)
        key = _sha(_encode([self._digests[file.rel], self._policy_hash(policies, extra), LINT_VERSION]))
        entry = self._entries.get(slot)
        if isinstance(entry, dict) and entry.get("key") == key:
            result = entry.get("result")
            if entry.get("result_sha256") == _sha(_encode(result)):
                self.hits += 1
                return result
        self.misses += 1
        result = compute()
        self._entries[slot] = {"key": key, "result": result, "result_sha256": _sha(_encode(result))}
        return result

    def save(self):
        # Preserve other lint namespaces when a single lint is requested; prune
        # removed files. Never retain a stale result for an analysed slot.
        paths = {f.rel for f in self.files()}
        entries = {k: v for k, v in self._entries.items() if k.partition(":")[2] in paths}
        raw = _encode({"version": LINT_VERSION, "entries": entries}) + b"\n"
        temporary = None
        try:
            if self.path.is_file() and self.path.read_bytes() == raw:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=self.path.parent, delete=False) as fh:
                temporary = fh.name
                fh.write(raw)
            os.replace(temporary, self.path)
        except OSError:
            pass
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass


def run(root, which=lints.LINTS):
    scan = CachedScan(root)
    result = lints.run(root, which, scan=scan)
    scan.save()
    return result
