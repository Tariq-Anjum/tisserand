"""Repository file scan shared by the lints (spec 5.1-5.3).

Which files are scanned (decision, spec 5.3): the core may not spawn
processes, so it cannot ask a VCS for the tracked-file list. Instead the
working tree is walked and everything matching the gitignore-style list in
`policy/scan.toml` (plus the fixed VCS/bytecode dirs below) is skipped. A
test keeps that list in step with the repository's own ignore file, so the
walk sees the tracked files plus any not-yet-committed ones, which is the
conservative direction for a lint.
"""
import os
from pathlib import Path

from . import tomlio
from .globs import Excludes
from .model import finding

ALWAYS_EXCLUDED = (".git", "__pycache__", ".cache")
MAX_BYTES = 4 * 1024 * 1024
SNIFF = 8192
SCAN_POLICY = "policy/scan.toml"


class ScannedFile:
    __slots__ = ("rel", "raw", "text")

    def __init__(self, rel, raw, text):
        self.rel = rel
        self.raw = raw
        self.text = text  # decoded str, or None for binary / oversized files


class Scan:
    """Walks the tree once; lazily exposes policy files and file contents."""

    def __init__(self, root):
        self.root = Path(root)
        self.findings = []
        self._policy = {}
        self._files = None

    # ---------------------------------------------------------------- policy
    def policy(self, name):
        """Parsed `policy/<name>` TOML, or None when absent or invalid
        (invalid also records an error finding once)."""
        if name in self._policy:
            return self._policy[name]
        rel = "policy/" + name
        data = None
        path = self.root / rel
        if path.is_file():
            try:
                data = tomlio.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError) as exc:
                self.findings.append(finding("", "lint-policy", "error", rel,
                                             "cannot read: %s" % type(exc).__name__))
            except tomlio.TomlError as exc:
                self.findings.append(finding("", "lint-policy", "error", rel, str(exc)))
        self._policy[name] = data
        return data

    def has_policy(self, name):
        return (self.root / "policy" / name).is_file()

    # ----------------------------------------------------------------- files
    def _excludes(self):
        patterns = []
        data = self.policy("scan.toml")
        if data is not None:
            listed = data.get("exclude", [])
            if isinstance(listed, list) and all(isinstance(x, str) for x in listed):
                patterns = listed
            else:
                self.findings.append(finding("", "lint-policy", "error", SCAN_POLICY,
                                             "'exclude' must be an array of strings"))
        return Excludes(patterns)

    def files(self):
        """All non-excluded files, sorted by path."""
        if self._files is None:
            excludes = self._excludes()
            out = []
            self._walk(self.root, "", excludes, out)
            out.sort(key=lambda f: f.rel)
            self._files = out
        return self._files

    def _walk(self, directory, prefix, excludes, out):
        try:
            entries = sorted(os.scandir(directory), key=lambda e: e.name)
        except OSError as exc:
            self.findings.append(finding("", "lint-scan", "error", prefix.rstrip("/") or ".",
                                         "cannot list directory: %s" % type(exc).__name__))
            return
        for entry in entries:
            rel = prefix + entry.name
            if entry.is_symlink():
                continue
            is_dir = entry.is_dir(follow_symlinks=False)
            if entry.name in ALWAYS_EXCLUDED or excludes.excluded(rel, is_dir):
                continue
            if is_dir:
                self._walk(entry.path, rel + "/", excludes, out)
            elif entry.is_file(follow_symlinks=False):
                out.append(self._read(rel, entry.path))

    def _read(self, rel, path):
        try:
            with open(path, "rb") as fh:
                raw = fh.read(MAX_BYTES + 1)
        except OSError as exc:
            self.findings.append(finding("", "lint-scan", "error", rel,
                                         "cannot read: %s" % type(exc).__name__))
            return ScannedFile(rel, b"", None)
        if len(raw) > MAX_BYTES or b"\0" in raw[:SNIFF]:
            return ScannedFile(rel, raw, None)
        try:
            return ScannedFile(rel, raw, raw.decode("utf-8"))
        except UnicodeDecodeError:
            return ScannedFile(rel, raw, None)

    def text_files(self):
        return [f for f in self.files() if f.text is not None]

    def cached(self, name, file, compute, policies=(), extra=""):
        """Per-file analysis hook; the optional IO cache lives outside core."""
        return compute()
