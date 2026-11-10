"""Neutrality, privacy and portability lints (manifest spec 5, 11.8).

The scratch repos use synthetic terms ("zorblax", "Quux") so no real host
name appears in this file. Strings the privacy lint looks for are assembled
at run time so this file stays clean under that same lint.
"""
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from skillkit.core import baseline, globs
from tests.helpers import FIXTURES, TempCase, run, registered_sources_root

REPO = Path(__file__).resolve().parents[1]
SLASH = "/"
HOME_PATH = SLASH + "ho" + "me" + SLASH + "someone"
MNT_PATH = SLASH + "m" + "nt" + SLASH + "data"
TILDE_PATH = "~" + SLASH + ".config"
AT = "@"
SECRET_VALUE = "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5"

TERMS = """\
[[terms]]
term = "zorblax"
mode = "word-ci"

[[terms]]
term = "Quux"
mode = "word-cs"
"""
ZONES = """\
[[zone]]
name = "exempt"
globs = ["adapters/**", "policy/**"]

[[zone]]
name = "hard"
globs = ["core/**"]

[[zone]]
name = "ratchet"
globs = ["skills/**"]
"""


class LintCase(TempCase):
    def repo(self, files=None, terms=True, zones=True):
        root = self.tmp / ("r%d" % getattr(self, "_k", 0))
        self._k = getattr(self, "_k", 0) + 1
        root.mkdir()
        base = {}
        if terms:
            base["policy/neutrality-terms.toml"] = TERMS
        if zones:
            base["policy/neutrality-zones.toml"] = ZONES
        base.update(files or {})
        for rel, text in base.items():
            self.put(root, rel, text)
        return root

    def put(self, root, rel, text):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)

    def lint(self, root, which, *extra):
        code, out, err = run("lint", which, "--root", str(root), "--format", "json", *extra)
        return code, (json.loads(out) if out.strip() else None), err

    def rules(self, doc):
        return sorted(f["rule"] for f in doc["findings"])

    def baseline(self, root, name):
        return json.loads((root / baseline.rel_path(name)).read_text(encoding="utf-8"))


class NeutralityTests(LintCase):
    def test_hard_zone_hit_is_an_error(self):
        root = self.repo({"core/mod.txt": "uses zorblax here\n"})
        code, doc, _ = self.lint(root, "neutrality")
        self.assertEqual(code, 1)
        self.assertEqual(self.rules(doc), ["lint-neutrality-hard"])
        self.assertIn("line 1", doc["findings"][0]["msg"])

    def test_clean_tree_is_green(self):
        root = self.repo({"core/mod.txt": "nothing here\n", "skills/a.md": "plain\n"})
        code, doc, _ = self.lint(root, "neutrality")
        self.assertEqual((code, doc["findings"]), (0, []))

    def test_ratchet_rise_equal_and_fall(self):
        root = self.repo({"skills/a.md": "zorblax and ZORBLAX\n"})
        self.put(root, "policy/neutrality-baseline.json", '{"counts":{"skills/a.md":2},"raises":[],"waivers":{}}')
        self.assertEqual(self.lint(root, "neutrality")[0], 0)  # unchanged: silent
        self.put(root, "skills/a.md", "zorblax\n")
        self.assertEqual(self.lint(root, "neutrality")[1]["findings"], [])  # fall: free
        self.put(root, "skills/a.md", "zorblax zorblax zorblax\n")
        code, doc, _ = self.lint(root, "neutrality")
        self.assertEqual((code, self.rules(doc)), (1, ["lint-neutrality-ratchet"]))

    def test_unlisted_text_defaults_to_ratchet_and_binary_is_ignored(self):
        root = self.repo({"other/notes.txt": "zorblax\n"})
        self.put(root, "other/blob.bin", b"zorblax\x00\x01")
        code, doc, _ = self.lint(root, "neutrality")
        self.assertEqual(code, 1)
        paths = [f["path"] for f in doc["findings"]]
        self.assertEqual(paths, ["other/notes.txt"])

    def test_exempt_zone_is_not_checked(self):
        root = self.repo({"adapters/h/x.md": "zorblax Quux\n"})
        self.assertEqual(self.lint(root, "neutrality")[0], 0)

    def test_modes_and_word_boundaries(self):
        root = self.repo({"skills/a.md": "Quux quux zorblaxes zorblax-2 Zorblax\n"})
        code, doc, _ = self.lint(root, "neutrality")
        self.assertEqual(doc["stats"]["neutrality"]["ratchet_hits"], 3)  # Quux, zorblax-2, Zorblax

    def test_waiver_suppresses_and_is_counted(self):
        root = self.repo({"skills/a.md": "zorblax <!-- neutral-ok: host integration notes -->\n"})
        self.put(root, "policy/neutrality-baseline.json", '{"counts":{},"raises":[],"waivers":{"skills/a.md":1}}')
        code, doc, _ = self.lint(root, "neutrality")
        self.assertEqual(code, 0)
        self.assertEqual(self.rules(doc), ["lint-neutrality-waivers"])
        self.assertEqual([f["severity"] for f in doc["findings"]], ["info"])
        self.assertEqual(doc["stats"]["neutrality"]["waivers"], 1)

    def test_waiver_count_has_its_own_ratchet(self):
        root = self.repo({"skills/a.md": "zorblax neutral-ok: host integration notes\n"})
        self.put(root, "policy/neutrality-baseline.json", '{"counts":{},"raises":[],"waivers":{}}')
        code, doc, _ = self.lint(root, "neutrality")
        self.assertEqual((code, "lint-neutrality-waiver-ratchet" in self.rules(doc)), (1, True))
        self.put(root, "policy/neutrality-baseline.json", '{"counts":{},"raises":[],"waivers":{"skills/a.md":1}}')
        self.assertEqual(self.lint(root, "neutrality")[0], 0)

    def test_short_waiver_reason_is_rejected(self):
        root = self.repo({"skills/a.md": "zorblax neutral-ok: nope\n"})
        code, doc, _ = self.lint(root, "neutrality")
        self.assertEqual(code, 1)
        self.assertIn("lint-neutrality-waiver", self.rules(doc))
        self.assertIn("lint-neutrality-ratchet", self.rules(doc))  # the hit still counts

    def test_waiver_not_honoured_in_hard_zone(self):
        root = self.repo({"core/a.md": "zorblax neutral-ok: a perfectly long reason\n"})
        code, doc, _ = self.lint(root, "neutrality")
        self.assertEqual((code, self.rules(doc)), (1, ["lint-neutrality-hard"]))

    def test_provenance_table_of_a_manifest_is_exempt(self):
        text = '[routing]\nprovides = ["x"]\n\n[provenance]\nsource = "zorblax upstream"\n\n[cost]\nnote = "zorblax"\n'
        root = self.repo({"skills/a/capability.toml": text})
        code, doc, _ = self.lint(root, "neutrality")
        self.assertEqual(doc["stats"]["neutrality"]["ratchet_hits"], 1)  # only the [cost] line

    def test_unconfigured_neutrality(self):
        root = self.repo({"skills/a.md": "zorblax\n"}, terms=False)
        self.assertEqual(run("lint", "neutrality", "--root", str(root))[0], 2)
        # ... but check on a valid repo without the policy file does not fail on it
        good = self.copy_fixture("good")
        self.assertEqual(run("check", "--root", str(good))[0], 0)

    def test_bad_policy_is_reported(self):
        root = self.repo({"policy/neutrality-terms.toml": '[[terms]]\nterm = "x"\nmode = "regex"\n'})
        code, doc, _ = self.lint(root, "neutrality")
        self.assertEqual((code, self.rules(doc)), (1, ["lint-policy"]))


class BaselineTests(LintCase):
    def test_initial_generation_records_no_raises(self):
        root = self.repo({"skills/a.md": "zorblax zorblax\n"})
        code, doc, _ = self.lint(root, "neutrality", "--update-baseline")
        self.assertEqual(code, 0)
        self.assertEqual(self.baseline(root, "neutrality"),
                         {"counts": {"skills/a.md": 2}, "raises": [], "waivers": {}})
        self.assertEqual(self.lint(root, "neutrality")[0], 0)

    def test_raise_needs_allow_raise_and_is_recorded(self):
        root = self.repo({"skills/a.md": "zorblax\n"})
        self.lint(root, "neutrality", "--update-baseline")
        before = (root / baseline.rel_path("neutrality")).read_bytes()
        self.put(root, "skills/a.md", "zorblax zorblax zorblax\n")
        code, doc, _ = self.lint(root, "neutrality", "--update-baseline")
        self.assertEqual(code, 1)
        self.assertTrue(doc["refused"])
        self.assertEqual(doc["raises"], [{"path": "skills/a.md", "from": 1, "to": 3}])
        self.assertEqual((root / baseline.rel_path("neutrality")).read_bytes(), before)  # untouched
        with mock.patch.object(baseline, "today", return_value="2026-11-05"):
            code, doc, _ = self.lint(root, "neutrality", "--update-baseline", "--allow-raise", "new integration notes")
        self.assertEqual(code, 0)
        data = self.baseline(root, "neutrality")
        self.assertEqual(data["counts"], {"skills/a.md": 3})
        self.assertEqual(data["raises"], [{"date": "2026-11-05", "path": "skills/a.md", "from": 1, "to": 3,
                                           "reason": "new integration notes"}])
        code, doc, _ = self.lint(root, "neutrality")
        self.assertEqual(code, 0)
        self.assertEqual([f["rule"] for f in doc["findings"]], ["lint-neutrality-raises"])  # info only

    def test_lowering_is_free_and_zero_counts_are_dropped(self):
        root = self.repo({"skills/a.md": "zorblax zorblax\n", "skills/b.md": "zorblax\n"})
        self.lint(root, "neutrality", "--update-baseline")
        self.put(root, "skills/a.md", "zorblax\n")
        self.put(root, "skills/b.md", "clean\n")
        self.assertEqual(self.lint(root, "neutrality", "--update-baseline")[0], 0)
        self.assertEqual(self.baseline(root, "neutrality")["counts"], {"skills/a.md": 1})

    def test_new_file_with_hits_counts_as_a_raise(self):
        root = self.repo({"skills/a.md": "zorblax\n"})
        self.lint(root, "neutrality", "--update-baseline")
        self.put(root, "skills/new.md", "zorblax\n")
        code, doc, _ = self.lint(root, "neutrality", "--update-baseline")
        self.assertEqual((code, doc["raises"]), (1, [{"path": "skills/new.md", "from": 0, "to": 1}]))

    def test_flag_validation(self):
        root = self.repo()
        self.assertEqual(run("lint", "neutrality", "--root", str(root), "--allow-raise", "long enough reason")[0], 2)
        self.assertEqual(run("lint", "neutrality", "--root", str(root), "--update-baseline", "--allow-raise", "short")[0], 2)
        self.assertEqual(run("lint", "portability", "--root", str(root), "--update-baseline")[0], 2)
        self.assertEqual(run("lint", "bogus", "--root", str(root))[0], 2)

    def test_malformed_baseline_is_an_error(self):
        root = self.repo({"policy/neutrality-baseline.json": '{"counts":{"a":0},"raises":[]}'})
        code, doc, _ = self.lint(root, "neutrality")
        self.assertEqual((code, self.rules(doc)), (1, ["lint-baseline"]))

    def test_baseline_files_are_canonical_json(self):
        from skillkit.core import jsonout
        for name in ("neutrality", "privacy"):
            text = (REPO / baseline.rel_path(name)).read_text(encoding="utf-8")
            self.assertEqual(text, jsonout.dumps(json.loads(text)), name)


class PrivacyTests(LintCase):
    def test_each_kind_is_detected(self):
        lines = [
            "path " + HOME_PATH,
            "path " + MNT_PATH,
            "path " + TILDE_PATH,
            "mail someone" + AT + "corp.io",
            "host 10.1" + ".2.3",
            "token = " + SECRET_VALUE,
            "key AK" + "IA" + "ABCDEFGHIJKLMNOP",
        ]
        root = self.repo({"notes.md": "\n".join(lines) + "\n"})
        code, doc, _ = self.lint(root, "privacy")
        self.assertEqual(code, 1)
        stats = doc["stats"]["privacy"]
        self.assertEqual(stats["hits"], 8)  # the token line also trips the prefix pattern
        self.assertEqual(sorted(stats["hits_by_kind"]),
                         ["email", "home-path", "ipv4", "mnt-path", "secret-assignment", "secret-prefix", "tilde-dotpath"])

    def test_messages_never_echo_the_matched_text(self):
        root = self.repo({"notes.md": "token = %s\nsomeone%scorp.io\n" % (SECRET_VALUE, AT)})
        _, doc, _ = self.lint(root, "privacy")
        blob = json.dumps(doc)
        self.assertNotIn(SECRET_VALUE, blob)
        self.assertNotIn("corp.io", blob)

    def test_allowed_and_non_findings(self):
        lines = [
            "noreply" + AT + "corp.io",
            "dev" + AT + "example.com",
            "bind 127.0.0.1 and 192.0.2.7 and 203.0.113.9",
            "version 1.2.3.4.5",
            "pkg" + AT + "1.2.3",
            "token: ${{ value }}",
            "relative src" + SLASH + "ho" + "me" + SLASH + "page",
        ]
        root = self.repo({"notes.md": "\n".join(lines) + "\n",
                          "policy/privacy-allow.toml": (REPO / "policy/privacy-allow.toml").read_text(encoding="utf-8")})
        code, doc, _ = self.lint(root, "privacy")
        self.assertEqual((code, doc["findings"]), (0, []))

    def test_privacy_allow_file_globs(self):
        root = self.repo({"gen/out.md": HOME_PATH + "\n", "keep/x.md": HOME_PATH + "\n"})
        self.put(root, "policy/privacy-allow.toml", '[files]\nallow = ["gen/**"]\n')
        _, doc, _ = self.lint(root, "privacy")
        self.assertEqual([f["path"] for f in doc["findings"]], ["keep/x.md"])

    def test_new_file_must_be_clean_and_ratchet_holds(self):
        root = self.repo({"old.md": HOME_PATH + "\n"})
        self.lint(root, "privacy", "--update-baseline")
        self.assertEqual(self.lint(root, "privacy")[0], 0)
        self.put(root, "new.md", HOME_PATH + "\n")
        self.assertEqual(self.lint(root, "privacy")[0], 1)
        self.put(root, "new.md", "clean\n")
        self.put(root, "old.md", HOME_PATH + "\n" + MNT_PATH + "\n")
        code, doc, _ = self.lint(root, "privacy", "--update-baseline")
        self.assertEqual((code, doc["refused"]), (1, True))
        code, doc, _ = self.lint(root, "privacy", "--update-baseline", "--allow-raise", "documented path examples")
        self.assertEqual(code, 0)
        self.assertEqual(self.baseline(root, "privacy")["raises"][0]["path"], "old.md")

    def test_denylist(self):
        root = self.repo({"a.md": "owner is zebra-user here\n"})
        deny = self.tmp / "deny.txt"
        deny.write_text("# local only\n\nzebra-user\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"SKILLKIT_PRIVACY_DENYLIST": str(deny)}):
            code, doc, _ = self.lint(root, "privacy")
        self.assertEqual((code, self.rules(doc)), (1, ["lint-privacy-denylist"]))
        self.assertNotIn("zebra-user", json.dumps(doc))
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SKILLKIT_PRIVACY_DENYLIST", None)
            self.assertEqual(self.lint(root, "privacy")[0], 0)  # unset: pattern-only
        with mock.patch.dict(os.environ, {"SKILLKIT_PRIVACY_DENYLIST": str(self.tmp / "missing.txt")}):
            code, doc, _ = self.lint(root, "privacy")
        self.assertEqual((code, self.rules(doc)), (0, ["lint-privacy-denylist"]))  # unreadable: warning
        self.assertEqual(doc["findings"][0]["severity"], "warn")


class PortabilityTests(LintCase):
    def test_case_collision(self):
        root = self.repo({"docs/Readme.md": "a\n", "docs/readme.md": "b\n"})
        _, doc, _ = self.lint(root, "portability")
        self.assertEqual(self.rules(doc), ["lint-portability-case-collision"] * 2)

    def test_directory_case_collision(self):
        root = self.repo({"Dir/a.txt": "a\n", "dir/b.txt": "b\n"})
        _, doc, _ = self.lint(root, "portability")
        self.assertEqual({f["path"] for f in doc["findings"]}, {"Dir", "dir"})

    def test_reserved_names_and_trailing_dot(self):
        root = self.repo({"data/con.txt": "a\n", "aux/ok.txt": "b\n", "fine/Com1": "c\n", "x/note.": "d\n"})
        _, doc, _ = self.lint(root, "portability")
        self.assertEqual(sorted(f["path"] for f in doc["findings"]), ["aux", "data/con.txt", "fine/Com1", "x/note."])

    def test_long_path(self):
        rel = "/".join(["d" * 50] * 4) + "/f.txt"
        root = self.repo({rel: "x\n"})
        _, doc, _ = self.lint(root, "portability")
        self.assertEqual(self.rules(doc), ["lint-portability-path-length"])

    def test_crlf(self):
        root = self.repo({"a.md": b"one\r\ntwo\r\n", "b.md": "fine\n"})
        _, doc, _ = self.lint(root, "portability")
        self.assertEqual([(f["rule"], f["path"]) for f in doc["findings"]], [("lint-portability-crlf", "a.md")])

    def test_core_import_rule(self):
        bad = {
            "skillkit/core/a.py": "import subprocess\n",
            "skillkit/core/b.py": "from subprocess import run\n",
            "skillkit/core/c.py": "import os\nos.system('x')\n",
            "skillkit/core/d.py": "import shutil\nshutil.which('x')\n",
            "skillkit/core/e.py": "from shutil import which\n",
            "skillkit/core/f.py": "from os import system\n",
            "skillkit/core/ok.py": "import os\nimport shutil\nos.path.join('a')\nshutil.copy\n",
            "skillkit/adapters/h.py": "import subprocess\n",
        }
        root = self.repo(bad)
        code, doc, _ = self.lint(root, "portability")
        self.assertEqual(code, 1)
        self.assertEqual(sorted(f["path"] for f in doc["findings"]), sorted(
            "skillkit/core/%s.py" % x for x in "abcdef"))
        self.assertTrue(all(f["rule"] == "lint-portability-core-import" for f in doc["findings"]))

    def test_clean_tree(self):
        root = self.repo({"a.md": "x\n", "skillkit/core/ok.py": "import json\n"})
        self.assertEqual(self.lint(root, "portability")[1]["findings"], [])


class ScanTests(LintCase):
    def test_excludes_from_policy_and_fixed_dirs(self):
        root = self.repo({
            "build/out.txt": "zorblax\n", "keep/in.txt": "zorblax\n", "a/__pycache__/x.txt": "zorblax\n",
            ".git/config": "zorblax\n", "policy/scan.toml": 'exclude = ["build/"]\n'})
        self.put(root, "policy/neutrality-zones.toml", '[[zone]]\nname = "exempt"\nglobs = ["policy/**"]\n')
        _, doc, _ = self.lint(root, "neutrality")
        self.assertEqual([f["path"] for f in doc["findings"]], ["keep/in.txt"])

    def test_glob_semantics(self):
        g = globs.GlobSet(["skills/**", "*.md", "a/**/z.txt", "x?[ab]"])
        for rel in ("skills/a/b.md", "skills/x", "top.md", "a/z.txt", "a/b/c/z.txt", "xqa"):
            self.assertTrue(g.match(rel), rel)
        for rel in ("skill/x", "dir/top.md", "a/z.txtx", "xqc"):
            self.assertFalse(g.match(rel), rel)
        ex = globs.Excludes(["# c", "build/", "*.py[cod]", "/top.tmp", "a/b"])
        self.assertTrue(ex.excluded("build", True))
        self.assertFalse(ex.excluded("build", False))
        self.assertTrue(ex.excluded("pkg/build/x", False))
        self.assertTrue(ex.excluded("m/n.pyc", False))
        self.assertTrue(ex.excluded("top.tmp", False))
        self.assertFalse(ex.excluded("d/top.tmp", False))
        self.assertTrue(ex.excluded("a/b/c.txt", False))
        self.assertFalse(ex.excluded("z/a/b", False))

    def test_scan_policy_covers_the_repo_ignore_file(self):
        import tomllib
        listed = tomllib.loads((REPO / "policy/scan.toml").read_text(encoding="utf-8"))["exclude"]
        for line in (REPO / ".gitignore").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                self.assertIn(line, listed)


class WiringTests(LintCase):
    def test_check_runs_the_lints_and_no_lint_skips_them(self):
        root = self.copy_fixture("good")
        self.put(root, "NOTES.md", "see " + HOME_PATH + "\n")
        code, out, _ = run("check", "--root", str(root), "--format", "json")
        self.assertEqual(code, 1)
        self.assertIn("lint-privacy-ratchet", {f["rule"] for f in json.loads(out)["findings"]})
        self.assertEqual(run("check", "--root", str(root), "--no-lint")[0], 0)

    def test_check_reports_hard_zone_and_portability_findings(self):
        root = self.copy_fixture("good")
        self.put(root, "policy/neutrality-terms.toml", TERMS)
        self.put(root, "policy/neutrality-zones.toml", '[[zone]]\nname = "hard"\nglobs = ["skills/**"]\n')
        self.put(root, "skills/alpha-research/extra.md", "zorblax\n")
        self.put(root, "skills/alpha-research/Extra.md", "ok\n")
        code, out, _ = run("check", "--root", str(root), "--format", "json")
        rules = {f["rule"] for f in json.loads(out)["findings"]}
        self.assertTrue({"lint-neutrality-hard", "lint-portability-case-collision"} <= rules)
        self.assertEqual(code, 1)

    def test_lint_is_deterministic(self):
        for which in ("neutrality", "privacy", "portability"):
            a = run("lint", which, "--root", str(REPO), "--format", "json")
            b = run("lint", which, "--root", str(REPO), "--format", "json")
            self.assertEqual(a, b, which)
        a = run("check", "--root", str(REPO), "--format", "json")
        b = run("check", "--root", str(REPO), "--format", "json")
        self.assertEqual(a, b)

    def test_real_repo_is_green_against_its_baselines(self):
        sources_root = registered_sources_root(self)
        code, out, _ = run("check", "--root", str(REPO), "--format", "json",
                         "--sources-root", str(sources_root))
        doc = json.loads(out)
        self.assertEqual(code, 0, [f for f in doc["findings"] if f["severity"] == "error"])
        self.assertEqual(doc["summary"]["error"], 0)
        for which in ("neutrality", "privacy", "portability"):
            code, out, _ = run("lint", which, "--root", str(REPO), "--format", "json")
            self.assertEqual(code, 0, which)
            self.assertEqual([f for f in json.loads(out)["findings"] if f["severity"] == "error"], [], which)

    def test_real_repo_has_no_hard_zone_neutrality_hits(self):
        _, out, _ = run("lint", "neutrality", "--root", str(REPO), "--format", "json")
        self.assertEqual(json.loads(out)["stats"]["neutrality"]["hard_hits"], 0)

    def test_lint_does_not_modify_the_tree(self):
        root = self.copy_fixture("good")
        before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
        run("check", "--root", str(root), "--no-cache")
        run("lint", "privacy", "--root", str(root), "--no-cache")
        self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()})


if __name__ == "__main__":
    unittest.main()
