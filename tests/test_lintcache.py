"""Per-file lint cache equivalence and invalidation on synthetic roots."""
import json
from unittest import mock

from skillkit import lintcache
from skillkit.core import lints
from tests.test_lints import LintCase, HOME_PATH
from tests.helpers import run


class LintCacheTests(LintCase):
    def cached(self, root, which=lints.LINTS):
        scan = lintcache.CachedScan(root)
        result = lints.run(root, which, scan=scan)
        scan.save()
        return result, scan

    def test_cold_warm_uncached_findings_and_stats_identical(self):
        root = self.repo({"core/a.txt": "zorblax\n", "other/b.txt": HOME_PATH,
                          "skillkit/core/bad.py": "import subprocess\r\n"})
        expected = lints.run(root)
        cold, a = self.cached(root)
        warm, b = self.cached(root)
        self.assertEqual((cold, warm), (expected, expected))
        self.assertGreater(a.misses, 0)
        self.assertEqual(b.misses, 0)
        self.assertGreater(b.hits, 0)

    def test_only_changed_file_or_relevant_policy_keys_invalidate(self):
        root = self.repo({"a.txt": "plain", "b.txt": "plain"})
        self.put(root, "policy/scan.toml", 'exclude = [".cache/"]')
        self.cached(root)
        self.put(root, "a.txt", "changed")
        _, changed = self.cached(root)
        self.assertEqual(changed.misses, 3)  # one key in each lint
        self.put(root, "policy/privacy-allow.toml", '[email]\nallow = ["test.invalid"]')
        _, policy = self.cached(root)
        # The new file is scanned by all lints; only privacy's other keys miss.
        self.assertEqual(policy.misses, len(policy.files()) + 2)
        self.assertEqual(self.cached(root)[1].misses, 0)

    def test_cross_file_collisions_and_baselines_always_recompute(self):
        root = self.repo({"A.txt": "zorblax"})
        self.put(root, "policy/scan.toml", 'exclude = [".cache/"]')
        self.cached(root)
        self.put(root, "a.txt", "plain")
        self.put(root, "policy/neutrality-baseline.json",
                 '{"counts":{"A.txt":1},"waivers":{},"raises":[]}')
        result, _ = self.cached(root)
        self.assertEqual(result, lints.run(root))
        rules = [f["rule"] for f in result[0]]
        self.assertIn("lint-portability-case-collision", rules)
        self.assertNotIn("lint-neutrality-ratchet", rules)

    def test_denylist_contents_invalidate_privacy_without_caching_literals(self):
        root = self.repo({"a.txt": "unique-local-value"})
        self.put(root, "policy/scan.toml", 'exclude = [".cache/"]')
        deny = self.tmp / "deny.txt"
        deny.write_text("unmatched")
        with mock.patch.dict("os.environ", {"SKILLKIT_PRIVACY_DENYLIST": str(deny)}):
            self.cached(root)
            deny.write_text("unique-local-value")
            result, scan = self.cached(root)
            self.assertEqual(result, lints.run(root))
            self.assertEqual(scan.misses, len(scan.text_files()))
            self.assertIn("lint-privacy-denylist", [f["rule"] for f in result[0]])
        self.assertNotIn("unique-local-value", (root / lintcache.CACHE_PATH).read_text())

    def test_corrupt_cache_is_a_miss_and_no_cache_bypasses_read_and_write(self):
        root = self.repo({"a.txt": "zorblax"})
        self.put(root, "policy/scan.toml", 'exclude = [".cache/"]')
        expected, _ = self.cached(root)
        path = root / lintcache.CACHE_PATH
        path.write_text("{broken")
        self.assertEqual(self.cached(root)[0], expected)
        before = path.read_bytes()
        with mock.patch.object(lintcache, "CachedScan", side_effect=AssertionError("cache used")):
            for cmd in (("lint", "neutrality"), ("check",)):
                code, out, _ = run(*cmd, "--root", str(root), "--no-cache", "--format", "json")
                self.assertIn(code, (0, 1))
                self.assertTrue(json.loads(out))
        self.assertEqual(path.read_bytes(), before)

    def test_cache_io_failure_is_optional(self):
        root = self.repo({"a.txt": "plain"})
        self.put(root, ".cache", "not a directory")
        self.assertEqual(lintcache.run(root), lints.run(root))
