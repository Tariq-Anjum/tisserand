import hashlib
import json
import os
import time
import unittest
from unittest.mock import patch
from pathlib import Path

from skillkit.core import generate, jsonout
from tests.helpers import FIXTURES, TempCase, findings_of, run

REGISTRY = ("catalog.json", "graph.json", "index.json", "manifest.lock.json")


def tree_hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(root).rglob("*")) if p.is_file()}


class GenerateTests(TempCase):
    def test_gen_then_check_clean(self):
        root = self.copy_fixture("good", keep_registry=False)
        self.assertEqual(run("gen", "--check", "--root", str(root))[0], 1)  # missing outputs
        self.assertFalse((root / "registry").exists())  # --check wrote nothing
        self.assertFalse((root / "INDEX.md").exists())
        code, out, _ = run("gen", "--root", str(root))
        self.assertEqual(code, 0)
        self.assertIn("14 file(s) written", out)
        self.assertEqual(run("gen", "--check", "--root", str(root))[0], 0)
        self.assertEqual(run("check", "--root", str(root))[0], 0)

    def test_idempotent_second_run_writes_nothing(self):
        root = self.copy_fixture("good", keep_registry=False)
        run("gen", "--root", str(root))
        first = tree_hashes(root)
        stamp = {p: p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()}
        time.sleep(0.01)
        code, out, _ = run("gen", "--root", str(root))
        self.assertEqual(code, 0)
        self.assertIn("0 file(s) written", out)
        self.assertEqual(tree_hashes(root), first)
        self.assertEqual({p: p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()}, stamp)

    def test_fresh_copy_determinism(self):
        a = self.copy_fixture("good", dest=self.tmp / "one" / "repo", keep_registry=False)
        b = self.copy_fixture("good", dest=self.tmp / "other-name" / "nested" / "copy", keep_registry=False)
        os.utime(b / "skills" / "skill-router" / "SKILL.md", (1, 1))  # different mtimes must not matter
        run("gen", "--root", str(a))
        run("gen", "--root", str(b))
        self.assertEqual(tree_hashes(a), tree_hashes(b))

    def test_committed_fixture_registry_is_current(self):
        root = self.copy_fixture("good")
        self.assertEqual(run("gen", "--check", "--root", str(root))[0], 0)
        code, out, _ = run("gen", "--root", str(root))
        self.assertIn("0 file(s) written", out)
        self.assertEqual(tree_hashes(root), tree_hashes(FIXTURES / "good"))

    def test_hand_edit_is_drift(self):
        root = self.copy_fixture("good")
        (root / "registry" / "index.json").write_text("{}\n", encoding="utf-8")
        code, found = findings_of(root)
        self.assertEqual(code, 1)
        self.assertEqual([(f["rule"], f["path"]) for f in found if f["severity"] == "error"],
                         [("generated-drift", "registry/index.json")])

    def test_leftover_category_is_stale(self):
        root = self.copy_fixture("good")
        (root / "categories" / "retired.md").write_text("# Retired\n", encoding="utf-8")
        code, found = findings_of(root)
        self.assertEqual(code, 1)
        self.assertEqual([(f["rule"], f["path"]) for f in found if f["severity"] == "error"],
                         [("generated-stale", "categories/retired.md")])
        (root / "categories" / "retired.md").unlink()
        self.assertEqual(run("check", "--root", str(root))[0], 0)

    def test_input_change_is_drift_until_regenerated(self):
        root = self.copy_fixture("good")
        self.edit(root, "skills/beta-explicit/SKILL.md", "Fixture skill", "Changed fixture skill")
        self.assertEqual(run("check", "--root", str(root))[0], 1)
        self.assertEqual(run("gen", "--root", str(root))[0], 0)
        self.assertEqual(run("check", "--root", str(root))[0], 0)

    def test_gen_refuses_invalid_model(self):
        root = self.copy_fixture("bad-id")
        code, out, _ = run("gen", "--root", str(root))
        self.assertEqual(code, 1)
        self.assertFalse((root / "registry").exists())

    def test_output_properties(self):
        root = self.copy_fixture("good")
        cat = json.loads((root / "registry" / "catalog.json").read_text(encoding="utf-8"))
        ids = [e["id"] for e in cat["capabilities"]]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), 8)
        for name in REGISTRY:
            data = (root / "registry" / name).read_bytes()
            self.assertTrue(data.endswith(b"\n") and not data.endswith(b"\n\n"))
            self.assertNotIn(b"\r", data)
            text = data.decode("utf-8")
            for needle in (str(root), "/" + "home" + "/", "/" + "mnt" + "/", "\\"):
                self.assertNotIn(needle, text, (name, needle))
            want = (jsonout.dumps_inline_lists if name == "index.json" else jsonout.dumps)(json.loads(text))
            self.assertEqual(text, want)
        by_id = {e["id"]: e for e in cat["capabilities"]}
        pointer = by_id["theta-flow"]
        self.assertEqual(pointer["path"], "workflows/theta-flow/manifest.yaml")
        self.assertNotIn("note", pointer["manifest"]["install"])  # free-text install notes stay out of the catalog
        self.assertIn("Pointer only; the note continues on a second line.",
                      (root / "catalog.yaml").read_text(encoding="utf-8"))  # compat file keeps them
        self.assertIn("manifest_sha256", pointer)
        skill_bytes = (root / "skills/alpha-research/SKILL.md").read_bytes()
        self.assertEqual(by_id["alpha-research"]["sha256"], hashlib.sha256(skill_bytes).hexdigest())
        self.assertEqual(by_id["alpha-research"]["body_bytes"], len(skill_bytes))

    def test_index_routable_and_graph(self):
        root = self.copy_fixture("good")
        index = json.loads((root / "registry" / "index.json").read_text(encoding="utf-8"))
        routable = {e["id"]: e.get("routable", True) for e in index["capabilities"]}
        self.assertEqual(routable["gamma-manual"], False)
        self.assertEqual(routable["delta-dep"], False)
        self.assertEqual(routable["beta-explicit"], True)
        self.assertEqual(routable["skill-router"], True)
        graph = json.loads((root / "registry" / "graph.json").read_text(encoding="utf-8"))
        edges = [(e["from"], e["rel"], e["to"]) for e in graph["edges"]]
        self.assertEqual(edges, sorted(edges))
        self.assertIn(("alpha-research", "requires", "delta-dep"), edges)
        self.assertIn(("beta-explicit", "conflicts_with", "gamma-manual"), edges)
        self.assertEqual(graph["nodes"], sorted(graph["nodes"]))

    def test_lock_covers_inputs_and_outputs(self):
        root = self.copy_fixture("good")
        lock = json.loads((root / "registry" / "manifest.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(lock["outputs"]), sorted(
            ["CREDITS.md", "THIRD_PARTY_NOTICES", "registry/catalog.json", "registry/graph.json", "registry/index.json", "INDEX.md", "capabilities.md",
             "catalog.yaml", "guidance/INDEX.md"] + ["categories/%s.md" % c for c in ("meta", "research", "routing", "testing")]))
        for rel, digest in lock["inputs"].items():
            if not rel.startswith("schema/"):  # schemas may come from the bundled directory
                self.assertEqual(digest, hashlib.sha256((root / rel).read_bytes()).hexdigest(), rel)
        for expected in ("skills/skill-router/capability.toml", "skills/skill-router/SKILL.md",
                         "guidance/eta-guidance/GUIDANCE.md", "workflows/theta-flow/manifest.yaml",
                         "policy/licenses.toml", "schema/capability.schema.json"):
            self.assertIn(expected, lock["inputs"])

    def test_write_outputs_only_when_bytes_differ(self):
        root = self.copy_fixture("good")
        result = generate.evaluate(root, with_drift=False)
        self.assertEqual(generate.write_outputs(root, result.outputs), [])
        (root / "registry" / "graph.json").unlink()
        self.assertEqual(generate.write_outputs(root, result.outputs), ["registry/graph.json"])


if __name__ == "__main__":
    unittest.main()


class IndexSchema2Tests(TempCase):
    def index(self, root):
        return json.loads((root / "registry" / "index.json").read_text(encoding="utf-8"))

    def test_schema_2_omits_empty_and_default_keys(self):
        root = self.copy_fixture("good")
        index = self.index(root)
        self.assertEqual(index["schema"], 2)
        by_id = {e["id"]: e for e in index["capabilities"]}
        alpha = by_id["alpha-research"]
        self.assertEqual(alpha["aliases"], ["alpha-lookup"])
        self.assertEqual(alpha["requires"], ["delta-dep"])
        self.assertEqual(alpha["composes_with"], ["beta-explicit"])
        for key in ("intents", "exclusions", "phrases", "routable", "name", "platforms", "artifacts",
                    "conflicts_with"):
            self.assertNotIn(key, alpha)
        self.assertIs(by_id["gamma-manual"]["routable"], False)
        for e in index["capabilities"]:
            for key in ("intents", "exclusions", "aliases", "phrases", "requires", "composes_with",
                        "conflicts_with", "artifacts", "platforms"):
                self.assertTrue(e.get(key, ["x"]), (e["id"], key))  # never present-but-empty
            self.assertNotEqual(e.get("routable"), True)

    def test_name_only_when_it_differs_and_new_fields_flow(self):
        root = self.copy_fixture("good")
        self.edit(root, "skills/alpha-research/capability.toml",
                  'requires = ["delta-dep"]',
                  'requires = ["delta-dep"]\nintents = ["find sources"]\nphrases = ["look it up"]\n'
                  'exclusions = ["write code"]\nartifacts = ["document"]\nplatforms = ["linux"]')
        code, out, _ = run("gen", "--root", str(root))
        self.assertEqual(code, 0, out)
        by_id = {e["id"]: e for e in self.index(root)["capabilities"]}
        a = by_id["alpha-research"]
        self.assertEqual((a["intents"], a["phrases"], a["exclusions"], a["artifacts"], a["platforms"]),
                         (["find sources"], ["look it up"], ["write code"], ["document"], ["linux"]))
        self.assertEqual(by_id["beta-explicit"]["conflicts_with"], ["gamma-manual"])
        text = (root / "registry" / "index.json").read_text(encoding="utf-8")
        self.assertIn('"phrases": ["look it up"]', text)

    def test_index_is_valid_against_schema_and_fixture_is_current(self):
        root = self.copy_fixture("good")
        self.assertEqual(run("gen", "--check", "--root", str(root))[0], 0)

    def test_budget_is_an_error_without_a_record(self):
        root = self.copy_fixture("good")
        old = generate.INDEX_BUDGET
        generate.INDEX_BUDGET = 100
        try:
            code, found = findings_of(root)
        finally:
            generate.INDEX_BUDGET = old
        self.assertEqual(code, 1)
        self.assertIn(("index-budget", "error"), {(f["rule"], f["severity"]) for f in found})
        self.assertEqual(generate.INDEX_BUDGET, 16834)
        self.assertEqual(generate.INDEX_BUDGET_FALLBACK, 20480)

    def test_recorded_fallback_and_surface_boundaries(self):
        root = self.copy_fixture("good")
        record = root / "skillkit/core/index-budget-miss.json"
        record.parent.mkdir(parents=True)
        miss = {"budget_bytes": 16834, "measured_bytes": 17011,
                "evidence": "ev:report:s3-install"}
        objs, original = generate.build(generate.model.load(root))
        for recorded in (False, True):
            if recorded:
                record.write_text(json.dumps(miss), encoding="utf-8")
            for size in (16834, 16835, 20480, 20481):
                for index, meta in ((1795, 1114), (1796, 0), (1795, 1115)):
                    with self.subTest(recorded=recorded, size=size, index=index, meta=meta):
                        outputs = dict(original)
                        outputs[generate.PATHS["index"]] = b"x" * size
                        outputs["INDEX.md"] = b"x" * index
                        outputs["categories/meta.md"] = b"x" * meta
                        with patch.object(generate, "build", return_value=(objs, outputs)):
                            result = generate.evaluate(root, with_drift=False)
                        surface_ok = index <= 1795 and index + meta <= 2909
                        cap = 20480 if recorded and surface_ok else 16834
                        rules = {f["rule"] for f in result.errors}
                        self.assertEqual("index-budget" in rules, size > cap)
                        self.assertEqual("router-surface" in rules, not surface_ok)
                        self.assertEqual(bool(result.errors), size > cap or not surface_ok)

    def test_invalid_miss_records_keep_original_cap(self):
        root = self.copy_fixture("good")
        record = root / "skillkit/core/index-budget-miss.json"
        record.parent.mkdir(parents=True)
        objs, outputs = generate.build(generate.model.load(root))
        outputs[generate.PATHS["index"]] = b"x" * 17011
        for raw in ('{', '[]', '{}',
                    '{"budget_bytes":16834,"measured_bytes":16834,"evidence":"report"}',
                    '{"budget_bytes":1,"measured_bytes":17011,"evidence":"report"}',
                    '{"budget_bytes":16834,"measured_bytes":17011,"evidence":""}',
                    '{"budget_bytes":16834,"measured_bytes":"17011","evidence":"report"}'):
            with self.subTest(raw=raw):
                record.write_text(raw, encoding="utf-8")
                with patch.object(generate, "build", return_value=(objs, outputs)):
                    result = generate.evaluate(root, with_drift=False)
                self.assertIn("index-budget", {f["rule"] for f in result.errors})

    def test_index_schema_rejects_old_and_malformed_rows(self):
        from skillkit.core import schemacheck
        schema = json.loads((Path(__file__).resolve().parents[1] / "schema" / "index.schema.json").read_text(encoding="utf-8"))
        good = self.index(self.copy_fixture("good"))
        self.assertEqual(schemacheck.validate(good, schema), [])
        old = dict(good, schema=1)
        self.assertTrue(schemacheck.validate(old, schema))
        for key, value in (("routable", True), ("phrases", []), ("aliases", ["Not An Id"]), ("bogus", 1)):
            bad = json.loads(json.dumps(good))
            bad["capabilities"][0][key] = value
            self.assertTrue(schemacheck.validate(bad, schema), key)
