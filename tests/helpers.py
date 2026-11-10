import contextlib
import io
import json
import os
import tomllib
import shutil
import tempfile
import unittest
from pathlib import Path

from skillkit import cli

FIXTURES = Path(__file__).resolve().parent / "fixtures"
# Generated outputs of the fixture repos (registry JSON plus the D6 compat files).
GENERATED = ("CREDITS.md", "THIRD_PARTY_NOTICES", "registry", "catalog.yaml", "INDEX.md", "capabilities.md", "categories", "guidance/INDEX.md")


def run(*argv):
    """Run the CLI in-process; return (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


def registered_sources_root(test):
    """Find the registered local reference tree, or skip real-repo checks."""
    repo = Path(__file__).resolve().parents[1]
    registry = tomllib.loads((repo / 'sources/idea-cards.toml').read_text())
    refs = {rel for card in registry.get('card', []) for rel in card.get('records', [])}
    candidates = []
    if os.environ.get('SKILLKIT_SOURCES_ROOT'):
        candidates.append(Path(os.environ['SKILLKIT_SOURCES_ROOT']))
    for root in candidates:
        if refs and all((root / rel).is_file() for rel in refs):
            return root
    test.skipTest('registered provenance reference tree unavailable; set SKILLKIT_SOURCES_ROOT')


def findings_of(root, sources_root=None):
    extra = () if sources_root is None else ('--sources-root', str(sources_root))
    code, out, _ = run("check", "--root", str(root), "--format", "json", "--no-cache", *extra)
    return code, json.loads(out)["findings"]


def rules_of(root):
    code, found = findings_of(root)
    return code, sorted({f["rule"] for f in found})


class TempCase(unittest.TestCase):
    """Base class with a scratch directory and fixture-copy helper."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def copy_fixture(self, name="good", dest=None, keep_registry=True):
        self._n = getattr(self, "_n", 0) + 1
        dest = Path(dest) if dest else self.tmp / ("%s-%d" % (name, self._n))
        shutil.copytree(FIXTURES / name, dest)
        if not keep_registry:
            for rel in GENERATED:
                target = dest / rel
                if target.is_dir():
                    shutil.rmtree(target, ignore_errors=True)
                else:
                    target.unlink(missing_ok=True)
        return dest

    def edit(self, root, rel, old, new):
        path = Path(root) / rel
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
