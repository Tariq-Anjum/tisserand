"""CLI integration against an isolated, synthetic input surface."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skillkit import cli
from skillkit.core.route import plan
from tests.route_fixtures import parameters, params_text

ROOT = Path(__file__).resolve().parents[1]


class RouteCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for directory in ("registry", "policy"):
            (self.root / directory).mkdir(parents=True)
        entries = [{"id": "alpha", "activation": "contextual", "type": "skill",
                    "intents": ["repair code"], "platforms": ["linux"], "artifacts": ["code"]},
                   {"id": "quiet", "activation": "explicit", "type": "skill", "intents": ["concise"]}]
        (self.root / "registry/index.json").write_text(json.dumps({"schema": 2, "capabilities": entries}), encoding="utf-8")
        (self.root / "policy/router-params.toml").write_text(params_text(parameters()), encoding="utf-8")
        (self.root / "policy/stopwords.txt").write_text("the\nand\nuse\n", encoding="utf-8")

    def test_export_surface_without_benchmark_directory(self):
        self.assertFalse((self.root / "bench").exists())
        code, out, err = self.run_cli("repair code")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out)["primary"], "alpha")
        (self.root / "registry/manifest.lock.json").write_text("synthetic lock")
        cached = self.run_cli("--cache-dir", str(self.root / ".cache/router"), "repair code")
        self.assertEqual(cached, (code, out, err))

    def run_cli(self, *args, stdin=""):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), mock.patch("sys.stdin", io.StringIO(stdin)):
            code = cli.main(["route", "--root", str(self.root), *args])
        return code, out.getvalue(), err.getvalue()

    def test_json_stdin_trace_text_and_context(self):
        code, out, err = self.run_cli("repair code")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out)["primary"], "alpha")
        self.assertEqual(out.encode(), plan.encode(json.loads(out)))
        self.assertEqual(self.run_cli("-", stdin="repair code")[1], out)
        got = json.loads(self.run_cli("--trace", "repair code")[1])
        self.assertEqual(got["trace"]["query_terms"], ["code", "repair"])
        self.assertEqual(self.run_cli("--format", "text", "use quiet")[1].splitlines()[0], "primary: quiet")
        for options in (("--platform", "windows"), ("--artifact", "image")):
            self.assertTrue(json.loads(self.run_cli(*options, "repair code")[1])["abstain"])
        self.assertFalse(json.loads(self.run_cli("--platform", "windows", "--platform", "linux", "repair code")[1])["abstain"])

    def test_errors_are_exit_two_and_abstain_is_zero(self):
        for args in ((), ("--format", "xml", "task"), ("x" * 8001,),
                     ("--cache-dir", "~" + "/unused", "repair"), ("--params", "missing.toml", "task")):
            with self.subTest(args=args):
                self.assertEqual(self.run_cli(*args)[0], 2)
        self.assertEqual(self.run_cli("-", stdin="é" * 4001)[0], 2)
        self.assertEqual(self.run_cli("é" * 4000)[0], 0)
        self.assertEqual(self.run_cli("unrelated task")[0], 0)
        (self.root / "policy/router-params.toml").write_text("schema = 1\n", encoding="utf-8")
        self.assertEqual(self.run_cli("repair code")[0], 2)

    def test_input_surface_only_no_writes(self):
        seen = []
        original = Path.read_bytes
        def read(path):
            seen.append(path.relative_to(self.root).as_posix())
            return original(path)
        with mock.patch.object(Path, "read_bytes", read), \
                mock.patch.object(Path, "write_bytes", side_effect=AssertionError("write")), \
                mock.patch.object(Path, "write_text", side_effect=AssertionError("write")):
            self.assertEqual(self.run_cli("repair code")[0], 0)
        self.assertEqual(sorted(seen), ["policy/router-params.toml", "policy/stopwords.txt", "registry/index.json"])

    def subprocess(self, seed, *args, data=None):
        env = dict(os.environ, PYTHONHASHSEED=str(seed))
        return subprocess.run([sys.executable, "-m", "skillkit", "route", "--root", str(self.root), *args],
                              cwd=ROOT, env=env, input=data, capture_output=True)

    def test_hashseed_determinism(self):
        for task in ("repair code", "use quiet", "without alpha", "", "unknown"):
            first = self.subprocess(0, "--trace", task)
            second = self.subprocess(1, "--trace", task)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual((first.returncode, first.stdout, first.stderr),
                             (second.returncode, second.stdout, second.stderr))

    def test_binary_stdin_limit_and_invalid_utf8(self):
        self.assertEqual(self.subprocess(0, "-", data=b"repair code").returncode, 0)
        for data in (b"\xff", b"x" * 8001):
            proc = self.subprocess(0, "-", data=data)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(proc.stdout, b"")

    def test_route_imports_no_bench_or_lint_modules(self):
        code = """import sys
from skillkit.cli import main
assert main(['route', '--root', sys.argv[1], 'repair code']) == 0
assert not any('bench' in n or 'lint' in n for n in sys.modules if n.startswith('skillkit.'))
"""
        proc = subprocess.run([sys.executable, "-c", code, str(self.root)], cwd=ROOT,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
