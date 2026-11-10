"""Mutation tests: each starts from a copy of the good fixture."""
import unittest

from tests.helpers import TempCase, findings_of, rules_of, run


class RuleTests(TempCase):
    def mutated(self, rel, old, new):
        root = self.copy_fixture("good")
        self.edit(root, rel, old, new)
        return root

    def assertReports(self, root, rule, code=1):
        got_code, rules = rules_of(root)
        self.assertIn(rule, rules)
        self.assertEqual(got_code, code)

    def test_missing_capability_toml(self):
        root = self.copy_fixture("good")
        (root / "skills/delta-dep/capability.toml").unlink()
        self.assertReports(root, "capability-missing")

    def test_doc_missing(self):
        root = self.copy_fixture("good")
        (root / "skills/delta-dep/SKILL.md").unlink()
        self.assertReports(root, "doc-missing")

    def test_toml_parse_error(self):
        self.assertReports(self.mutated("skills/delta-dep/capability.toml", 'schema = 1', 'schema = '), "toml-parse")

    def test_unknown_toml_key(self):
        self.assertReports(self.mutated("skills/delta-dep/capability.toml", 'schema = 1', 'schema = 1\nbogus = 1'),
                           "schema.capability")

    def test_type_dir_mismatch(self):
        self.assertReports(self.mutated("skills/delta-dep/capability.toml", 'type = "skill"', 'type = "guidance"\nname = "n"\ndescription = "d"'),
                           "type-dir-mismatch")

    def test_unknown_frontmatter_key(self):
        root = self.mutated("skills/delta-dep/SKILL.md", "---\nname:", "---\nid: x\nname:")
        self.assertReports(root, "frontmatter.parse")

    def test_crlf_frontmatter(self):
        root = self.copy_fixture("good")
        path = root / "skills/delta-dep/SKILL.md"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        self.assertReports(root, "frontmatter.parse")

    def test_description_too_long(self):
        root = self.mutated("skills/delta-dep/SKILL.md", "description: Fixture skill delta-dep.",
                            "description: " + "x" * 1025)
        self.assertReports(root, "schema.frontmatter")

    def test_name_too_long(self):
        root = self.mutated("skills/delta-dep/SKILL.md", "name: delta-dep", "name: " + "x" * 65)
        self.assertReports(root, "schema.frontmatter")

    def test_activation_dmi_both_directions(self):
        root = self.mutated("skills/delta-dep/SKILL.md", "disable-model-invocation: false", "disable-model-invocation: true")
        self.assertReports(root, "activation-dmi")
        root2 = self.mutated("skills/beta-explicit/SKILL.md", "disable-model-invocation: true", "disable-model-invocation: false")
        self.assertReports(root2, "activation-dmi")

    def test_every_activation_value_is_covered(self):
        for act, dmi in (("always", "true"), ("contextual", "true"), ("dependency", "true"),
                         ("explicit", "false"), ("manual", "false")):
            with self.subTest(activation=act):
                root = self.copy_fixture("good", dest=self.tmp / ("x-" + act))
                self.edit(root, "skills/delta-dep/capability.toml", 'activation = "dependency"', 'activation = "%s"' % act)
                self.edit(root, "skills/delta-dep/SKILL.md", "disable-model-invocation: false", "disable-model-invocation: " + dmi)
                _, found = findings_of(root)
                self.assertIn("activation-dmi", {f["rule"] for f in found})

    def test_body_structure(self):
        root = self.mutated("skills/delta-dep/SKILL.md", "## Quick Index", "## Overview")
        self.assertReports(root, "body-structure")

    def test_quick_index_after_100_lines(self):
        root = self.mutated("skills/delta-dep/SKILL.md", "## Quick Index", "\n" * 100 + "## Quick Index")
        self.assertReports(root, "body-structure")

    def test_router_missing(self):
        root = self.copy_fixture("good")
        self.edit(root, "skills/skill-router/capability.toml", 'activation = "always"', 'activation = "contextual"')
        self.assertReports(root, "always-unique")

    def test_requires_cycle(self):
        root = self.mutated("skills/delta-dep/capability.toml", 'provides = ["helper-work"]',
                            'provides = ["helper-work"]\nrequires = ["alpha-research"]')
        _, found = findings_of(root)
        cyc = [f for f in found if f["rule"] == "requires-cycle"]
        self.assertEqual(len(cyc), 1)
        self.assertIn("alpha-research -> delta-dep", cyc[0]["msg"])

    def test_self_reference(self):
        root = self.mutated("skills/delta-dep/capability.toml", 'provides = ["helper-work"]',
                            'provides = ["helper-work"]\nrequires = ["delta-dep"]')
        _, rules = rules_of(root)
        self.assertEqual([r for r in rules if r.startswith("ref-") or r == "requires-cycle"], ["ref-self"])

    def test_requires_conflicts_overlap(self):
        root = self.mutated("skills/alpha-research/capability.toml", 'composes_with = ["beta-explicit"]',
                            'composes_with = ["beta-explicit"]\nconflicts_with = ["delta-dep"]')
        self.assertReports(root, "requires-conflicts-overlap")

    def test_asymmetric_conflict_is_warning_not_failure(self):
        root = self.mutated("skills/gamma-manual/capability.toml", 'conflicts_with = ["beta-explicit"]', 'conflicts_with = []')
        self.assertEqual(run("gen", "--root", str(root))[0], 0)  # warnings do not block generation
        code, found = findings_of(root)
        self.assertEqual(code, 0)
        self.assertIn(("conflict-asymmetric", "warn"), {(f["rule"], f["severity"]) for f in found})

    def test_license_allowlist_and_waiver(self):
        root = self.mutated("skills/alpha-research/capability.toml", 'license = "MIT"', 'license = "GPL-3.0-only"')
        self.assertReports(root, "license-not-allowed")
        self.edit(root, "skills/alpha-research/capability.toml", 'license = "GPL-3.0-only"',
                  'license = "GPL-3.0-only"\nlicense_waiver = "owner accepted for fixture"')
        self.assertEqual(rules_of(root)[0], 1)  # generated files now stale, but no license finding
        self.assertNotIn("license-not-allowed", rules_of(root)[1])

    def test_derived_requires_http_source_url(self):
        root = self.mutated("skills/alpha-research/capability.toml", 'source = "https://example.org/upstream/alpha"',
                            'source = "upstream/alpha"')
        self.assertReports(root, "provenance-source-url")
        self.assertNotIn("provenance-source-url", rules_of(self.copy_fixture("good"))[1])

    def test_derived_requires_pinned_hex_ref_and_adaptation(self):
        for old, new in (('ref = "abcdef1234567"', 'ref = "main"'), ('ref = "abcdef1234567"', 'ref = "abc12"'),
                         ('ref = "abcdef1234567"', 'ref = ""'),
                         ('adaptation = "Rewritten for the fixture registry."', 'adaptation = ""')):
            with self.subTest(new=new):
                root = self.mutated("skills/alpha-research/capability.toml", old, new)
                self.assertReports(root, "schema.capability")

    def test_unverified_license_is_a_single_warning_listing_the_entries(self):
        root = self.copy_fixture("good")
        for cap in ("alpha-research", "delta-dep"):
            self.edit(root, "skills/%s/capability.toml" % cap, 'license = "MIT"', 'license = "LicenseRef-unverified"'
                      + ('\nlicense_waiver = "owner will verify upstream"' if cap == "alpha-research" else ""))
        code, found = findings_of(root)
        hits = [f for f in found if f["rule"] == "license-unverified"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["severity"], "warn")
        self.assertIn("alpha-research, delta-dep", hits[0]["msg"])
        self.assertIn("2 capabilities", hits[0]["msg"])
        self.assertNotIn("license-not-allowed", {f["rule"] for f in found})  # waiver covers the derived one

    def test_unverified_license_on_derived_without_waiver_is_an_error_too(self):
        root = self.mutated("skills/alpha-research/capability.toml", 'license = "MIT"', 'license = "LicenseRef-unverified"')
        _, rules = rules_of(root)
        self.assertIn("license-not-allowed", rules)
        self.assertIn("license-unverified", rules)

    def test_license_default_allowlist_without_policy_file(self):
        root = self.mutated("skills/alpha-research/capability.toml", 'license = "MIT"', 'license = "GPL-3.0-only"')
        (root / "policy" / "licenses.toml").unlink()
        self.assertReports(root, "license-not-allowed")

    def test_reserved_names_and_alias_collision(self):
        root = self.copy_fixture("good")
        (root / "skills/delta-dep").rename(root / "skills/aux")
        self.edit(root, "skills/aux/capability.toml", 'id = "delta-dep"', 'id = "aux"')
        self.edit(root, "skills/alpha-research/capability.toml", '"delta-dep"', '"aux"')
        self.assertReports(root, "id-reserved")
        root2 = self.mutated("skills/delta-dep/capability.toml", 'schema = 1', 'schema = 1\naliases = ["beta-explicit"]')
        self.assertReports(root2, "alias-collision")

    def test_duplicate_id_across_types(self):
        root = self.copy_fixture("good")
        self.edit(root, "guidance/eta-guidance/capability.toml", 'id = "eta-guidance"', 'id = "delta-dep"')
        _, rules = rules_of(root)
        self.assertIn("id-duplicate", rules)
        self.assertIn("id-dir-mismatch", rules)

    def test_skill_toml_must_not_carry_name(self):
        self.assertReports(self.mutated("skills/delta-dep/capability.toml", 'schema = 1', 'schema = 1\nname = "x"'),
                           "authority-split")

    def test_non_skill_requires_name_and_description(self):
        root = self.mutated("guidance/eta-guidance/capability.toml", 'name = "eta-guidance"\n', '')
        self.assertReports(root, "schema.capability")

    def test_manifest_drift_and_missing_field(self):
        root = self.mutated("workflows/theta-flow/manifest.yaml", "risk: low", "risk: high")
        self.assertReports(root, "manifest-drift")
        root2 = self.mutated("workflows/theta-flow/manifest.yaml", "capabilities:\n- fixture-workflow", "capabilities:\n- other")
        self.assertReports(root2, "manifest-drift")
        root3 = self.mutated("workflows/theta-flow/manifest.yaml", "summary: Fixture workflow pointer.\n", "")
        self.assertReports(root3, "manifest-missing-field")

    def test_manifest_shape_errors_are_findings(self):
        root = self.mutated("workflows/theta-flow/manifest.yaml", "id: theta-flow", "id: &anchor theta-flow")
        self.assertReports(root, "manifest.parse")

    def test_derived_requires_pinned_ref_hex(self):
        root = self.mutated("skills/alpha-research/capability.toml", 'ref = "abcdef1234567"', 'ref = "main"')
        self.assertReports(root, "schema.capability")

    def test_bad_date(self):
        root = self.mutated("skills/delta-dep/capability.toml", 'verified = "2026-11-05"', 'verified = "yesterday"')
        self.assertReports(root, "schema.capability")

    def test_info_findings_do_not_fail(self):
        code, found = findings_of(self.copy_fixture("good"))
        self.assertEqual(code, 0)
        self.assertEqual(sorted(f["rule"] for f in found), ["provenance-not-cleared"] * 8 + ["todo-intent", "unpinned-ref", "unreviewed-access"])
        self.assertTrue(all(f["severity"] == "info" for f in found))

    def test_policy_parse_error(self):
        root = self.mutated("policy/licenses.toml", "allow = [", "allow = 5 #")
        self.assertReports(root, "policy-parse")


if __name__ == "__main__":
    unittest.main()
