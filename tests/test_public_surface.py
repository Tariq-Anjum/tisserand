"""The public checker and router operate without optional corpus tooling."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PublicSurfaceTests(unittest.TestCase):
    def test_route_and_help_without_optional_tooling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('skillkit', 'policy', 'registry'):
                shutil.copytree(ROOT / name, root / name,
                                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            # Remove only optional implementation modules from the scratch copy.
            (root / 'skillkit/benchcli.py').unlink(missing_ok=True)
            (root / 'skillkit/core/bench.py').unlink(missing_ok=True)
            for args in (['--help'], ['route', '--format', 'json', 'use fault-loop']):
                result = subprocess.run([sys.executable, '-m', 'skillkit', *args],
                                        cwd=root, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                if args[0] == 'route':
                    self.assertEqual(json.loads(result.stdout)['primary'], 'fault-loop')

    def test_missing_optional_seal_reader_does_not_disable_other_checks(self):
        from unittest import mock
        from skillkit import cli
        from tests.helpers import TempCase, run
        fixture = TempCase()
        fixture.setUp()
        try:
            root = fixture.copy_fixture('good')
            original = cli.importlib.util.find_spec
            with mock.patch.object(cli.importlib.util, 'find_spec',
                                   side_effect=lambda name: None if name.endswith('.bench') else original(name)):
                code, out, err = run('check', '--root', str(root), '--format', 'json')
                self.assertEqual(code, 0, out + err)
                (root / 'registry/index.json').write_text('{}')
                code, out, err = run('check', '--root', str(root), '--format', 'json')
                self.assertEqual(code, 1, out + err)
                self.assertIn('generated-drift', out)
        finally:
            fixture.doCleanups()
