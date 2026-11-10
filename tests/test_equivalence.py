"""`check` must reject every defect the retired validate.py / _validate.py could report.

Each case mutates a throw-away copy of the real repository and asserts that
`check` exits 1 with the expected rule (the unmodified copy must pass).
"""
import re
import shutil
import unittest
from pathlib import Path

from tests.helpers import TempCase, findings_of, registered_sources_root

REPO = Path(__file__).resolve().parents[1]
SKIP = shutil.ignore_patterns(".git", ".venv", "__pycache__", "*.pyc")


def _sub(pattern, repl, flags=re.M):
    def apply(text):
        new, n = re.subn(pattern, repl, text, count=1, flags=flags)
        assert n == 1, pattern
        return new
    return apply


# (case name, file, transformation, expected rule). Old check in comments.
CASES = (
    ("missing-dmi", "skills/research-first/SKILL.md", _sub(r"^disable-model-invocation: .*\n", ""), "schema.frontmatter"),
    ("bad-id", "skills/research-first/capability.toml", _sub(r'^id = "research-first"', 'id = "Research_First"'), "id-dir-mismatch"),
    ("unknown-requires", "skills/research-first/capability.toml", _sub(r"^\[cost\]", 'requires = ["no-such-id"]\n\n[cost]'), "ref-unknown"),
    ("unknown-conflicts", "skills/research-first/capability.toml", _sub(r"^\[cost\]", 'conflicts_with = ["no-such-id"]\n\n[cost]'), "ref-unknown"),
    ("second-always", "skills/bounded-plan/capability.toml", _sub(r'^activation = "contextual"', 'activation = "always"'), "always-unique"),
    ("no-always", "skills/skill-router/capability.toml", _sub(r'^activation = "always"', 'activation = "contextual"'), "always-unique"),
    ("missing-quick-index", "skills/research-first/SKILL.md", _sub(r"^## Quick Index$", "## Overview"), "body-structure"),
    ("description-too-long", "skills/research-first/SKILL.md", _sub(r"^description: .*$", "description: " + "x" * 1100), "schema.frontmatter"),
    ("name-too-long", "skills/research-first/SKILL.md", _sub(r"^name: .*$", "name: " + "n" * 65), "schema.frontmatter"),
    ("no-frontmatter", "skills/research-first/SKILL.md", _sub(r"\A---\n(?:.*\n)*?---\n", ""), "frontmatter.parse"),
    ("missing-provenance", "skills/research-first/capability.toml", _sub(r"^\[provenance\]\n(?:.*\n?)*\Z", ""), "schema.capability"),
    ("missing-category", "skills/research-first/capability.toml", _sub(r"^category = .*\n", ""), "schema.capability"),
    ("missing-capabilities", "skills/research-first/capability.toml", _sub(r"^provides = .*\n", ""), "schema.capability"),
    ("missing-risk", "skills/research-first/capability.toml", _sub(r"^risk = .*\n", ""), "schema.capability"),
    ("manifest-missing-summary", "workflows/bmad/manifest.yaml", _sub(r"^summary:.*\n(?:  .*\n)*", ""), "manifest-missing-field"),
    ("manifest-missing-install", "workflows/bmad/manifest.yaml", _sub(r"^install:\n(?:  .*\n)*", ""), "manifest-missing-field"),
    ("guidance-missing-provenance", "guidance/synthetic-guidance/capability.toml", _sub(r"^\[provenance\]\n(?:.*\n?)*\Z", ""), "schema.capability"),
    ("generated-hand-edit", "catalog.yaml", lambda t: t + "# edited\n", "generated-drift"),
)


class OldValidatorEquivalence(TempCase):
    def setUp(self):
        super().setUp()
        self.sources_root = registered_sources_root(self)

    def copy_repo(self):
        dest = self.tmp / "repo"
        shutil.copytree(REPO, dest, ignore=SKIP)
        return dest

    def test_unmodified_copy_passes(self):
        code, found = findings_of(self.copy_repo(), self.sources_root)
        self.assertEqual((code, [f for f in found if f["severity"] == "error"]), (0, []))

    def test_each_old_failure_mode_is_rejected(self):
        for name, rel, mutate, rule in CASES:
            with self.subTest(case=name):
                root = self.tmp / name
                shutil.copytree(REPO, root, ignore=SKIP)
                if name == "guidance-missing-provenance":
                    # Synthetic guidance preserves the retired validator case.
                    guidance = root / "guidance/synthetic-guidance"
                    guidance.mkdir(parents=True)
                    (guidance / "capability.toml").write_text(
                        'schema = 1\nid = "synthetic-guidance"\nkind = "judgment"\n'
                        'type = "guidance"\ncategory = "engineering"\nactivation = "contextual"\n'
                        'risk = "low"\nversion = "0.1.0"\n'
                        '[routing]\nprovides = ["synthetic"]\n'
                        '[cost]\nlatency = "low"\n'
                        '[provenance]\norigin = "original"\nlicense = "MIT"\n')
                    (guidance / "GUIDANCE.md").write_text('# Synthetic guidance\n\nLocal fixture.\n')
                path = root / rel
                path.write_text(mutate(path.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
                code, found = findings_of(root, self.sources_root)
                errors = {f["rule"] for f in found if f["severity"] == "error"}
                self.assertEqual(code, 1, name)
                self.assertIn(rule, errors, name)

    def test_missing_files_are_rejected(self):
        for name, rel, rule in (("missing-toml", "skills/research-first/capability.toml", "capability-missing"),
                                ("missing-skill-md", "skills/research-first/SKILL.md", "doc-missing"),
                                ("missing-manifest", "workflows/bmad/manifest.yaml", "doc-missing")):
            with self.subTest(case=name):
                root = self.tmp / name
                shutil.copytree(REPO, root, ignore=SKIP)
                (root / rel).unlink()
                code, found = findings_of(root, self.sources_root)
                self.assertEqual(code, 1, name)
                self.assertIn(rule, {f["rule"] for f in found if f["severity"] == "error"}, name)


if __name__ == "__main__":
    unittest.main()
