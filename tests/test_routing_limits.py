"""Authoring limits, closed vocabulary and requires-target rules."""
import unittest

from tests.helpers import TempCase, findings_of

TOML = "skills/alpha-research/capability.toml"
ANCHOR = 'requires = ["delta-dep"]'


def strs(n, width=8):
    return "[" + ", ".join('"%s"' % (chr(97 + i) * width) for i in range(n)) + "]"


class RoutingLimitTests(TempCase):
    def routing(self, extra, old=ANCHOR, new=None):
        root = self.copy_fixture("good")
        self.edit(root, TOML, old, (new or old) + "\n" + extra)
        return root

    def hits(self, root, rule):
        code, found = findings_of(root)
        return code, [f for f in found if f["rule"] == rule and f["severity"] == "error"]

    def test_within_limits_is_clean(self):
        root = self.routing("intents = %s\nphrases = %s\nexclusions = %s" % (strs(4, 32), strs(4, 32), strs(2, 24)))
        self.assertEqual(self.hits(root, "routing-limit")[1], [])

    def test_item_count_limits(self):
        for key, n in (("intents", 5), ("phrases", 5), ("exclusions", 3)):
            root = self.routing("%s = %s" % (key, strs(n)))
            code, hits = self.hits(root, "routing-limit")
            self.assertEqual(code, 1, key)
            self.assertEqual(len(hits), 1, key)
            self.assertIn(key, hits[0]["msg"])

    def test_composes_with_limit(self):
        root = self.copy_fixture("good")
        self.edit(root, TOML, 'composes_with = ["beta-explicit"]',
                  'composes_with = ["beta-explicit", "delta-dep", "gamma-manual"]')
        code, hits = self.hits(root, "routing-limit")
        self.assertEqual(code, 1)
        self.assertIn("composes_with", hits[0]["msg"])

    def test_alias_limits(self):
        root = self.copy_fixture("good")
        self.edit(root, 'skills/alpha-research/capability.toml', 'aliases = ["alpha-lookup"]',
                  'aliases = ["aa-one", "aa-two", "aa-three"]')
        code, hits = self.hits(root, "routing-limit")
        self.assertEqual(code, 1)
        self.assertIn("aliases has 3", hits[0]["msg"])
        root = self.copy_fixture("good")
        self.edit(root, 'skills/alpha-research/capability.toml', 'aliases = ["alpha-lookup"]',
                  'aliases = ["%s"]' % ("a" * 33))
        self.assertEqual(len(self.hits(root, "routing-limit")[1]), 1)

    def test_string_length_limits(self):
        for key, width, ok in (("intents", 32, True), ("intents", 33, False), ("phrases", 33, False),
                               ("exclusions", 24, True), ("exclusions", 25, False)):
            root = self.routing("%s = [\"%s\"]" % (key, "x" * width))
            hits = self.hits(root, "routing-limit")[1]
            self.assertEqual(bool(hits), not ok, (key, width))

    def test_explicit_vocab_for_platforms_and_artifacts(self):
        root = self.routing('platforms = ["linux", "macos"]\nartifacts = ["code", "pdf"]')
        self.assertEqual(self.hits(root, "routing-vocab")[1], [])
        for key, bad in (("platforms", "plan9"), ("artifacts", "docx")):
            root = self.routing('%s = ["%s"]' % (key, bad))
            code, hits = self.hits(root, "routing-vocab")
            self.assertEqual(code, 1)
            self.assertIn(bad, hits[0]["msg"])

    def test_vocab_file_missing_fails_closed_only_when_used(self):
        root = self.copy_fixture("good")
        (root / "policy" / "routing-vocab.toml").unlink()
        self.assertEqual(self.hits(root, "routing-vocab")[1], [])
        self.edit(root, TOML, ANCHOR, ANCHOR + '\nplatforms = ["linux"]')
        self.assertEqual(len(self.hits(root, "routing-vocab")[1]), 1)

    def test_malformed_vocab_file(self):
        root = self.copy_fixture("good")
        (root / "policy" / "routing-vocab.toml").write_text('[platforms]\nallow = []\n', encoding="utf-8")
        code, found = findings_of(root)
        self.assertEqual(code, 1)
        self.assertIn("policy-parse", {f["rule"] for f in found})

    def test_requires_target_must_exist(self):
        root = self.copy_fixture("good")
        self.edit(root, TOML, ANCHOR, 'requires = ["no-such-capability"]')
        code, hits = self.hits(root, "ref-unknown")
        self.assertEqual(code, 1)
        self.assertIn("requires", hits[0]["msg"])

    def test_requires_target_must_not_be_explicit(self):
        root = self.copy_fixture("good")
        self.edit(root, TOML, ANCHOR, 'requires = ["beta-explicit"]')
        code, hits = self.hits(root, "requires-explicit")
        self.assertEqual(code, 1)
        self.assertEqual(len(hits), 1)
        self.assertIn("beta-explicit", hits[0]["msg"])

    def test_composes_with_an_explicit_capability_is_allowed(self):
        code, found = findings_of(self.copy_fixture("good"))  # alpha composes_with beta-explicit
        self.assertNotIn("requires-explicit", {f["rule"] for f in found})


if __name__ == "__main__":
    unittest.main()
