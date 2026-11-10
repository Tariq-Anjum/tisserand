import json
import unittest

from skillkit.core import jsonout
from tests.helpers import FIXTURES, TempCase, findings_of, run, rules_of

# fixture -> rule that must be reported (in addition to the golden comparison)
EXPECTED_RULE = {
    "bad-missing-dmi": "schema.frontmatter",
    "bad-id": "schema.capability",
    "bad-unknown-requires": "ref-unknown",
    "bad-second-always": "always-unique",
    "bad-derived-no-sha": "schema.capability",
    "bad-case-collision": "id-case-collision",
    "bad-schema-keyword": "schema.unsupported",
    "bad-activation-dmi": "activation-dmi",
}


def repository_fixtures():
    # Rung data is protocol/vector support, not a repository under validation.
    # Keep discovering unknown repository fixtures so a missing golden fails.
    return sorted(p for p in FIXTURES.iterdir() if p.is_dir() and p.name != 'rung')


class GoldenTests(unittest.TestCase):
    def test_every_fixture_has_a_golden(self):
        names = [p.name for p in repository_fixtures()]
        self.assertEqual(names, sorted(["good"] + list(EXPECTED_RULE)))

    def test_findings_match_golden(self):
        for path in repository_fixtures():
            with self.subTest(fixture=path.name):
                golden = json.loads((path / "findings.json").read_text(encoding="utf-8"))
                code, got = findings_of(path)
                self.assertEqual(got, golden)
                has_error = any(f["severity"] == "error" for f in got)
                self.assertEqual(code, 1 if has_error else 0)

    def test_golden_files_are_canonical_json(self):
        for path in repository_fixtures():
            text = (path / "findings.json").read_text(encoding="utf-8")
            self.assertEqual(text, jsonout.dumps(json.loads(text)), path.name)

    def test_bad_fixtures_report_their_rule(self):
        for name, rule in EXPECTED_RULE.items():
            with self.subTest(fixture=name):
                code, rules = rules_of(FIXTURES / name)
                self.assertEqual(code, 1)
                self.assertIn(rule, rules)

    def test_good_fixture_is_clean(self):
        code, got = findings_of(FIXTURES / "good")
        self.assertEqual(code, 0)
        self.assertEqual({f["severity"] for f in got}, {"info"})

    def test_findings_are_sorted(self):
        for path in repository_fixtures():
            _, got = findings_of(path)
            keys = [(f["path"], f["rule"], f["id"], f["msg"]) for f in got]
            self.assertEqual(keys, sorted(keys), path.name)

    def test_fixtures_not_modified_by_check(self):
        before = {p: p.read_bytes() for p in (FIXTURES / "good").rglob("*") if p.is_file()}
        run("check", "--root", str(FIXTURES / "good"), "--no-cache")
        after = {p: p.read_bytes() for p in (FIXTURES / "good").rglob("*") if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
