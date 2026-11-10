"""Legacy writer contracts exercised only in marked disposable roots."""
import fcntl
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseWriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='writer-tests-', dir='/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        (self.base / '.writer-test-root').write_text('disposable test only\n')
        self.repo = self.base / 'source'
        self.repo.mkdir()
        shutil.copytree(ROOT / 'scripts', self.repo / 'scripts',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        self.runtime = self.base / 'runtime'
        self.runtime.mkdir()
        self.home = self.base / 'home'
        self.home.mkdir()
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(('AI_', 'SKILLKIT_', 'PYTHON'))}
        self.env.update(AI_TOOLS_ROOT=str(self.runtime), HOME=str(self.home),
                        PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(self.repo / 'scripts'))

    def run_writer(self, *args):
        self.assertTrue((self.base / '.writer-test-root').is_file())
        return subprocess.run(args, cwd=self.repo, env=self.env, text=True,
                              capture_output=True, timeout=15)

    def snapshot(self):
        result = {}
        for path in sorted(self.base.rglob('*')):
            if path.name == '.activation.lock':
                continue
            rel = path.relative_to(self.base).as_posix()
            result[rel] = (('link', os.readlink(path)) if path.is_symlink() else
                           ('dir',) if path.is_dir() else ('file', path.read_bytes()))
        return result

    def assert_refused(self, command, reason):
        before = self.snapshot()
        result = self.run_writer(*command)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(reason, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_release_layout_refuses_every_entry_before_mutation(self):
        layouts = ('skills/current', 'skills/releases', '.activation/transaction',
                   '.activation/preparing')
        commands = (
            (sys.executable, 'scripts/system_link.py'),
            (sys.executable, 'scripts/installer.py', 'sample'),
            (sys.executable, 'scripts/_install.py', 'sample'),
            (sys.executable, '-c', 'from _bootstrap import ensure_yaml; ensure_yaml()'),
            (sys.executable, '-c', 'import _lib'),
            (sys.executable, 'scripts/resolve.py', 'sample'),
            ('bash', 'scripts/install.sh', '--system', 'sample'),
            ('bash', 'scripts/install.sh', 'sample'),
            ('bash', 'scripts/sync.sh'),
            ('bash', 'scripts/uninstall.sh', 'sample'),
            ('bash', 'scripts/doctor.sh'),
            ('bash', 'scripts/python.sh', '-c', 'raise RuntimeError("executed")'),
            ('bash', 'scripts/update.sh'),
        )
        # A Git checkout marker makes an unguarded sync attempt observable.
        (self.repo / '.git').mkdir()
        for layout in layouts:
            marker = self.runtime / layout
            marker.parent.mkdir(parents=True, exist_ok=True)
            if layout.endswith('current'):
                marker.symlink_to('missing-release')
            else:
                marker.mkdir()
            for command in commands:
                with self.subTest(layout=layout, command=command):
                    self.assert_refused(command, 'release layout active')
            marker.unlink() if marker.is_symlink() else marker.rmdir()

    def test_uninstall_validates_entire_request_before_removal(self):
        installed = self.runtime / 'skills/installed/sample'
        installed.mkdir(parents=True)
        (installed / 'keep').write_text('preserved')
        for bad in ('', '../sample', '/sample', 'nested/sample', '--all', '.', 'a b'):
            with self.subTest(bad=bad):
                self.assert_refused(('bash', 'scripts/uninstall.sh', 'sample', bad),
                                    'invalid id')

    def test_lock_contention_refuses_shell_and_python_writers(self):
        with (self.runtime / '.activation.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for command in (('bash', 'scripts/uninstall.sh', 'sample'),
                            (sys.executable, 'scripts/installer.py', 'sample')):
                with self.subTest(command=command):
                    self.assert_refused(command, 'activation lock busy')

    def test_guards_inherit_lock_and_allow_repeated_calls(self):
        code = ('from release_guard import guard; import os, subprocess, sys; '
                'guard(os.environ["AI_TOOLS_ROOT"]); guard(os.environ["AI_TOOLS_ROOT"]); '
                'subprocess.run([sys.executable, "-c", '
                '"from release_guard import guard; import os; guard(os.environ[\'AI_TOOLS_ROOT\'])"], '
                'close_fds=False, check=True); print("inherited")')
        result = self.run_writer('bash', '-c',
            'source scripts/release_guard.sh; source scripts/release_guard.sh; exec "$@"',
            'writer-test', sys.executable, '-c', code)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('inherited', result.stdout)
        with (self.runtime / '.activation.lock').open('r') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_lock_symlink_and_indirect_layout_refused(self):
        outside = self.base / 'sentinel'
        outside.write_text('unchanged')
        markers = (self.runtime / '.activation.lock', self.runtime / 'skills',
                   self.runtime / 'skills/installed')
        for marker in markers:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.symlink_to(outside)
            for command in (('bash', 'scripts/uninstall.sh', 'sample'),
                            (sys.executable, 'scripts/installer.py', 'sample')):
                with self.subTest(marker=marker.name, command=command):
                    reason = ('explicit real' if marker.name == '.activation.lock'
                              else 'indirect skills')
                    self.assert_refused(command, reason)
            marker.unlink()

    def test_runtime_must_be_real_existing_directory(self):
        self.runtime.rmdir()
        for indirect in (False, True):
            if indirect:
                self.runtime.symlink_to(self.home, target_is_directory=True)
            for command in (('bash', 'scripts/uninstall.sh', 'sample'),
                            (sys.executable, 'scripts/installer.py', 'sample')):
                with self.subTest(indirect=indirect, command=command):
                    self.assert_refused(command, 'explicit real')
            if indirect:
                self.runtime.unlink()

    def test_flat_layout_link_and_uninstall_preserve_behavior(self):
        installed = self.runtime / 'skills/installed/sample'
        installed.mkdir(parents=True)
        (installed / 'SKILL.md').write_text('# Sample\n')
        result = self.run_writer(sys.executable, 'scripts/system_link.py', 'sample')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        links = [p for p in self.home.rglob('sample') if p.is_symlink()]
        self.assertTrue(links)
        for link in links:
            self.assertEqual(link.resolve(), installed)
        unrelated = links.pop()
        unrelated.unlink()
        unrelated.symlink_to(self.repo)
        result = self.run_writer('bash', 'scripts/uninstall.sh', 'sample')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(installed.exists())
        self.assertTrue(unrelated.is_symlink())
        self.assertEqual(unrelated.resolve(), self.repo)
        self.assertTrue(all(not link.is_symlink() for link in links))

    @unittest.skipUnless(importlib.util.find_spec('yaml'), 'installer requires PyYAML')
    def test_flat_layout_install_link_and_uninstall_preserve_behavior(self):
        # Relocating a venv interpreter loses its original package context.
        # Keep the real dependency local to this disposable import root.
        package = next(iter(importlib.util.find_spec('yaml').submodule_search_locations))
        shutil.copytree(package, self.repo / 'scripts/yaml',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        source = self.repo / 'skills/sample'
        source.mkdir(parents=True)
        (source / 'SKILL.md').write_text('# Sample\n')
        (self.repo / 'catalog.yaml').write_text(
            'skills:\n- id: sample\n  type: skill\n  path: skills/sample/SKILL.md\n  requires: []\n')
        for name in ('INDEX.md', 'capabilities.md'):
            (self.repo / name).write_text('sample\n')
        (self.repo / 'categories').mkdir()
        python = self.repo / '.venv/bin/python'
        python.parent.mkdir(parents=True)
        python.symlink_to(sys.executable)
        result = self.run_writer('bash', 'scripts/install.sh', '--system', 'sample')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        installed = self.runtime / 'skills/installed/sample'
        self.assertEqual((installed / 'SKILL.md').read_bytes(), (source / 'SKILL.md').read_bytes())
        self.assertTrue((self.runtime / 'skills/state/install-manifest.yaml').is_file())
        self.assertEqual((self.runtime / 'skills/catalog.yaml').resolve(), self.repo / 'catalog.yaml')
        links = [p for p in self.home.rglob('sample') if p.is_symlink()]
        self.assertTrue(links)
        for link in links:
            self.assertEqual(link.resolve(), installed)
        unrelated = links.pop()
        unrelated.unlink()
        unrelated.symlink_to(source)
        result = self.run_writer('bash', 'scripts/uninstall.sh', 'sample')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(installed.exists())
        self.assertTrue(unrelated.is_symlink())
        self.assertEqual(unrelated.resolve(), source)
        self.assertTrue(all(not link.is_symlink() for link in links))
