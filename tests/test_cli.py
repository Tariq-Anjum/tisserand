import json
import itertools
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import FIXTURES, TempCase, run

REPO = Path(__file__).resolve().parents[1]


class CliTests(TempCase):
    def test_fast_check_matches_argparse(self):
        from skillkit.cli import _fast_check, _parser
        parser = _parser("check")
        options = [("--no-lint",), ("--no-cache",), ("--format=json",),
                   ("--root", "repo with spaces")]
        for n in range(len(options) + 1):
            for chosen in itertools.permutations(options, n):
                argv = ["check", *(s for flags in chosen for s in flags)]
                self.assertEqual(vars(_fast_check(argv)), vars(parser.parse_args(argv)), argv)
        for flags in (("--format", "json", "--format", "text"),
                      ("--root=", "--root=-dash"),
                      ("--root", "a", "--root=b", "--no-lint", "--no-lint")):
            argv = ["check", *flags]
            self.assertEqual(vars(_fast_check(argv)), vars(parser.parse_args(argv)))

    def test_fast_check_falls_back_for_help_errors_and_abbreviations(self):
        from skillkit.cli import _fast_check
        for flags in (("--help",), ("--no-li",), ("--roo=repo",), ("--format",),
                      ("--format=xml",), ("--root", "--no-cache"), ("--",),
                      ("extra",), ("--no-cache=true",)):
            self.assertIsNone(_fast_check(["check", *flags]))
        self.assertIsNone(_fast_check(["gen"]))
        self.assertIsNone(_fast_check([]))
        self.assertEqual(run("check", "--help")[0], 0)
        self.assertEqual(run("check", "--roo", str(FIXTURES / "good"))[0], 0)

    def test_fast_and_general_check_dispatch_identically(self):
        for flags in ((), ("--no-lint",), ("--format", "json", "--no-cache")):
            argv = ("check", "--root", str(FIXTURES / "bad-id"), *flags)
            fast = run(*argv)
            with mock.patch("skillkit.cli._fast_check", return_value=None):
                self.assertEqual(run(*argv), fast)

    def test_check_fast_path_avoids_parser_and_heavy_command_imports(self):
        from skillkit.cli import main
        with mock.patch("skillkit.cli._parser", side_effect=AssertionError("slow path")), \
                mock.patch("skillkit.cli._check", return_value=0):
            self.assertEqual(main(["check", "--no-lint", "--root", str(FIXTURES / "good")]), 0)
        code = ("import sys; from skillkit.cli import main; "
                "assert main(['check','--no-lint','--root',sys.argv[1]]) == 0; "
                "assert not ({'argparse','skillkit.benchcli','skillkit.routecli',"
                "'skillkit.core.lints'} & set(sys.modules))")
        proc = subprocess.run([sys.executable, "-c", code, str(FIXTURES / "good")],
                              cwd=REPO, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_parser_lint_choices_match_registered_lints(self):
        from skillkit.cli import _parser
        from skillkit.core import lints
        parser = _parser("lint")
        for which in lints.LINTS + ("commits",):
            self.assertEqual(parser.parse_args(["lint", which]).which, which)

    def test_exit_codes(self):
        self.assertEqual(run("check", "--root", str(FIXTURES / "good"))[0], 0)
        self.assertEqual(run("check", "--root", str(FIXTURES / "bad-id"))[0], 1)
        self.assertEqual(run("check", "--root", str(self.tmp / "missing"))[0], 2)
        self.assertEqual(run("check", "--format", "xml")[0], 2)
        self.assertEqual(run("bogus")[0], 2)
        self.assertEqual(run()[0], 2)

    def test_lint_subcommand_runs(self):
        code, out, err = run("lint", "portability", "--root", str(FIXTURES / "good"))
        self.assertEqual((code, err), (0, ""))
        self.assertIn("0 error(s)", out)
        self.assertEqual(run("lint", "bogus")[0], 2)
        self.assertEqual(run("lint")[0], 2)

    def test_json_format(self):
        code, out, _ = run("check", "--root", str(FIXTURES / "bad-id"), "--format", "json")
        doc = json.loads(out)
        self.assertEqual(sorted(doc), ["findings", "provenance", "provenance_complete", "summary"])
        self.assertEqual(doc["summary"], {"error": 2, "info": 1, "warn": 0})
        for f in doc["findings"]:
            self.assertEqual(sorted(f), ["id", "msg", "path", "rule", "severity"])

    def test_text_format_has_no_absolute_paths(self):
        _, out, _ = run("check", "--root", str(FIXTURES / "bad-id"))
        self.assertNotIn(str(FIXTURES), out)
        self.assertIn("skills/bad-id/capability.toml: error [id-dir-mismatch]", out)

    def test_env_root(self):
        with mock.patch.dict(os.environ, {"SKILLKIT_ROOT": str(FIXTURES / "good")}):
            self.assertEqual(run("check")[0], 0)
        with mock.patch.dict(os.environ, {"SKILLKIT_ROOT": str(FIXTURES / "bad-id")}):
            self.assertEqual(run("check")[0], 1)
            self.assertEqual(run("check", "--root", str(FIXTURES / "good"))[0], 0)  # flag wins

    def test_gen_json_lists_written(self):
        root = self.copy_fixture("good", keep_registry=False)
        code, out, _ = run("gen", "--root", str(root), "--format", "json")
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)["written"]), 14)

    def test_module_entry_point_in_subprocess(self):
        env = {k: v for k, v in os.environ.items() if k != "SKILLKIT_ROOT"}
        proc = subprocess.run([sys.executable, "-m", "skillkit", "check", "--root", str(FIXTURES / "good")],
                              cwd=REPO, env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        proc = subprocess.run([sys.executable, "-m", "skillkit", "lint"], cwd=REPO, env=env,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
