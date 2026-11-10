"""Synthetic golden cases only: no benchmark corpus or evidence access."""
import copy
import unittest
from pathlib import Path
from unittest import mock

from skillkit.core import lexical
from skillkit.core.route import compose, eligible, normalize, overrides, plan, score
from skillkit.core.route.params import ParamsError, params_sha256, validate_params
from tests.route_fixtures import parameters

STOP = frozenset(("a", "the", "and", "of", "to", "with", "use"))


def entry(ident, **kw):
    return dict({"id": ident, "type": "skill", "activation": "contextual",
                 "description": "", "intents": [], "provides": []}, **kw)


def params():
    return validate_params(parameters())


def route(task, entries, p=None, ctx=None, trace=False):
    p = p or params()
    return plan.make_plan(task, ctx or plan.Ctx(), plan.build_index(entries, STOP, p), p, trace)


class NormalizeTests(unittest.TestCase):
    def test_words_terms_key(self):
        q = normalize.normalize("The DOGS, and policies! dogs", STOP, True)
        self.assertEqual(q.words, ("the", "dogs", "and", "policies", "dogs"))
        self.assertEqual(q.terms, ("dog", "policy"))
        self.assertEqual(q.key, "the dogs and policies dogs")
        self.assertEqual(normalize.normalize("DOGS", STOP, False).terms, ("dogs",))


class ParamsTests(unittest.TestCase):
    def test_defaults_identity_and_copies(self):
        p = params()
        self.assertEqual(p["weights"], dict(intent=3.0, phrase=4.0, provides=1.0,
                                             bm25=2.0, excl=2.0, named=1000.0))
        self.assertEqual(p["compose"], dict(max_supporting=2, max_depth=3))
        self.assertEqual(params_sha256(p), lexical.params_sha256(p))
        q = validate_params(p)
        q["overrides"]["bridge"].append("another")
        self.assertNotEqual(q, p)

    def test_closed_schema_types_and_ranges(self):
        for path, value in ((["schema"], True), (["extra"], 1), (["tokens", "stem"], 1),
                            (["weights", "named"], 99), (["weights", "excl"], -1),
                            (["weights", "intent"], float("inf")),
                            (["bm25", "b"], 1.1), (["bm25", "k1"], float("nan")),
                            (["decision", "delta"], 2), (["decision", "tau_s"], -1),
                            (["compose", "max_supporting"], 5), (["compose", "max_depth"], -1),
                            (["identity", "version"], "2"), (["overrides", "bridge"], [])):
            p = params()
            table = p if len(path) == 1 else p[path[0]]
            table[path[-1]] = value
            with self.subTest(path=path, value=value), self.assertRaises(ParamsError):
                validate_params(p)
        p = params()
        del p["decision"]["tau"]
        with self.assertRaises(ParamsError):
            validate_params(p)


class EligibilityTests(unittest.TestCase):
    def test_first_hit_and_context_filters(self):
        entries = [entry("router", activation="always", routable=False),
                   entry("manual", activation="manual"), entry("hidden", routable=False),
                   entry("exp", activation="explicit", platforms=["linux"]),
                   entry("plat", platforms=["linux"], artifacts=["code"]),
                   entry("art", artifacts=["code"]), entry("ok")]
        ov = overrides.Overrides((), frozenset(("router", "hidden", "exp")), ())
        got = eligible.filter_eligible(entries, ov, eligible.Ctx({"windows"}, {"text"}))
        self.assertEqual(got.ids, ("ok",))
        self.assertEqual(got.excluded, {"router": "router_self", "manual": "unroutable",
                                      "hidden": "unroutable", "exp": "named_negative:exp",
                                      "plat": "platform_mismatch", "art": "artifact_mismatch"})
        self.assertIn("plat", eligible.filter_eligible(entries, ov, eligible.Ctx()).ids)


class ScoreTests(unittest.TestCase):
    def test_feature_golden(self):
        p = params()
        e = entry("alpha", intents=["walking dogs"], provides=["dog-care"],
                  phrases=["the dogs"], exclusions=["dogs", "dogs walking", "dogs"])
        m = score.build_model([e], STOP, p)
        q = normalize.normalize("the dogs walking", STOP, True)
        self.assertEqual(score.features(q, m, e),
                         dict(intent=1.0, phrase=1.0, provides=0.5, bm25=0.0, excl=2.0))
        ov = overrides.Overrides((), frozenset(), ())
        scored = score.score_all(q, m, {"alpha": e}, eligible.Eligibility(("alpha",), {}), ov, p)
        self.assertEqual(scored[0].total, 3.5)

    def test_description_only_idf_and_explicit_documents(self):
        p = params()
        a = entry("secret", activation="explicit", description="dogs walking", intents=["unique"])
        b = entry("normal", description="dogs")
        excluded = entry("router", activation="always", description="unique")
        m = score.build_model([a, b, excluded], STOP, p)
        expected = lexical.Model([dict(a, intents=[], activation="contextual"), b], STOP,
                                 dict(p["bm25"], stem=True, norm="query"),
                                 {f: float(f == "description") for f in lexical.FIELDS})
        self.assertEqual(set(m.bm25.idf), {"dog", "walk"})
        q = normalize.normalize("dogs walking", STOP, True)
        self.assertEqual(score.features(q, m, a)["bm25"], round(dict(expected.rank(q.key)[0])["secret"], 6))

    def test_ties_and_zero_drop(self):
        p = params()
        p["decision"]["delta"] = 0.0
        entries = [entry("zulu", intents=["repair"]), entry("alpha", intents=["repair"])]
        got = route("repair", entries, p, trace=True)
        self.assertEqual(got["primary"], "alpha")
        self.assertEqual([s["id"] for s in got["trace"]["candidates"]], ["alpha", "zulu"])
        self.assertEqual(route("unknown", entries)["reasons"], ["no_candidate"])


class ComposeTests(unittest.TestCase):
    def test_required_topology_guidance_and_staged(self):
        entries = [entry("alpha", requires=["beta", "guide"]),
                   entry("beta", requires=["base"], routable=False, activation="dependency"),
                   entry("base", routable=False), entry("guide", type="guidance", routable=False)]
        got = route("alpha", entries)
        self.assertEqual((got["primary"], got["supporting"], got["reference"], got["mode"]),
                         ("alpha", ["base", "beta"], ["guide"], "staged"))

    def test_forward_reverse_gain_cap_and_reference(self):
        p = params()
        p["compose"]["max_supporting"] = 1
        entries = [entry("alpha", intents=["repair"], composes_with=["beta", "same", "guide"]),
                   entry("beta", intents=["deploy"]),
                   entry("reverse", intents=["publish"], composes_with=["alpha"]),
                   entry("same", intents=["repair"]),
                   entry("guide", type="guidance", intents=["safety"])]
        got = route("alpha repair deploy publish safety", entries, p)
        self.assertEqual(got["supporting"], ["beta"])
        self.assertEqual(got["reference"], ["guide"])
        self.assertEqual(got["mode"], "parallel")
        got = route("alpha publish", entries, p)
        self.assertEqual(got["supporting"], ["reverse"])

    def test_named_bypass_gain_and_threshold(self):
        p = params()
        p["decision"]["tau_s"] = 10000.0
        got = route("use beta then alpha", [entry("alpha"), entry("beta")], p)
        self.assertEqual((got["primary"], got["supporting"]), ("beta", ["alpha"]))
        self.assertIn("named_multi", got["reasons"])

    def test_conflicts_primary_named_score_and_id(self):
        entries = [entry("alpha", composes_with=["beta", "zulu", "charlie"]),
                   entry("beta", intents=["deploy"], conflicts_with=["zulu"]),
                   entry("zulu", intents=["publish"]),
                   entry("charlie", intents=["audit"], conflicts_with=["alpha"])]
        p = params()
        p["compose"]["max_supporting"] = 4
        got = route("alpha deploy publish audit", entries, p)
        self.assertEqual(got["supporting"], ["beta"])
        self.assertIn("conflict_dropped:zulu", got["reasons"])
        self.assertIn("conflict_dropped:charlie", got["reasons"])

    def test_invalid_graphs(self):
        for entries, code in (([entry("alpha", requires=["missing"])], "unknown_id"),
                              ([entry("alpha", requires=["beta"]), entry("beta", requires=["alpha"])], "cycle"),
                              ([entry("alpha", requires=["beta"], conflicts_with=["beta"]), entry("beta")], "conflict_requires")):
            with self.subTest(code=code):
                got = route("alpha", entries)
                self.assertTrue(got["abstain"])
                self.assertIn("plan_invalid:" + code, got["reasons"])
        p = params()
        p["compose"]["max_depth"] = 0
        self.assertIn("plan_invalid:requires_depth", route("alpha", [entry("alpha", requires=["beta"]), entry("beta")], p)["reasons"])

    def test_dropped_composition_prunes_its_orphaned_dependencies(self):
        entries = [entry("alpha", intents=["repair"], composes_with=["beta"]),
                   entry("beta", intents=["deploy"], requires=["base"], conflicts_with=["alpha"]),
                   entry("base", activation="dependency", routable=False, conflicts_with=["alpha"])]
        got = route("alpha deploy", entries)
        self.assertEqual((got["primary"], got["supporting"], got["mode"]), ("alpha", [], None))
        self.assertIn("conflict_dropped:beta", got["reasons"])
        self.assertNotIn("requires_added:base", got["reasons"])

    def test_negated_requirement_abstains_as_conflicting_requirement(self):
        got = route("alpha without beta", [entry("alpha", requires=["beta"]), entry("beta")])
        self.assertEqual((got["primary"], got["supporting"], got["abstain"]), (None, [], True))
        self.assertIn("plan_invalid:conflict_requires", got["reasons"])

    def test_b_dropped_roots_do_not_keep_each_others_requirements(self):
        entries = [entry("alpha", composes_with=["beta", "gamma"]),
                   entry("beta", intents=["deploy"], requires=["gamma"], conflicts_with=["alpha"]),
                   entry("gamma", intents=["publish"], phrases=["publish"], conflicts_with=["alpha"])]
        got = route("alpha deploy publish", entries)
        self.assertFalse(got["abstain"])
        self.assertEqual((got["primary"], got["supporting"], got["mode"]), ("alpha", [], None))
        self.assertIn("conflict_dropped:beta", got["reasons"])
        self.assertIn("conflict_dropped:gamma", got["reasons"])
        self.assertNotIn("requires_added:gamma", got["reasons"])

    def test_c_composed_requirement_of_primary_does_not_block_root_drop(self):
        entries = [entry("alpha", composes_with=["charlie", "delta"]),
                   entry("charlie", intents=["deploy"], requires=["alpha"]),
                   entry("delta", intents=["publish"], conflicts_with=["alpha"])]
        got = route("alpha deploy publish", entries)
        self.assertFalse(got["abstain"])
        self.assertEqual((got["primary"], got["supporting"]), ("alpha", ["charlie"]))
        self.assertIn("conflict_dropped:delta", got["reasons"])

    def test_d_surviving_root_requirement_still_conflicts_with_primary(self):
        entries = [entry("alpha", composes_with=["beta", "gamma"]),
                   entry("beta", intents=["deploy"], requires=["gamma"]),
                   entry("gamma", intents=["publish"], phrases=["publish"], conflicts_with=["alpha"])]
        got = route("alpha deploy publish", entries)
        self.assertTrue(got["abstain"])
        self.assertIn("plan_invalid:conflict_requires", got["reasons"])
        self.assertNotIn("conflict_dropped:gamma", got["reasons"])


class PlanTests(unittest.TestCase):
    def test_all_abstentions_and_confidence(self):
        entries = [entry("alpha", intents=["repair"]), entry("beta", intents=["repair"])]
        for task, code in ((" !!! ", "empty_task"), ("unknown", "no_candidate"), ("repair", "low_margin")):
            got = route(task, entries)
            self.assertEqual((got["primary"], got["supporting"], got["reference"], got["mode"], got["confidence"]),
                             (None, [], [], None, 0.0))
            self.assertIn(code, got["reasons"])
        p = params()
        p["decision"]["tau"] = 100.0
        self.assertEqual(route("repair", entries, p)["reasons"], ["below_tau"])
        self.assertEqual(route("alpha", entries, p)["confidence"], 1.0)
        self.assertEqual(route("repair", entries[:1])["confidence"], 1.0)

    def test_negation_explicit_and_ineligible_named(self):
        entries = [entry("quiet", activation="explicit", intents=["concise"]),
                   entry("alpha", intents=["repair"], platforms=["linux"]),
                   entry("beta", intents=["repair"]), entry("manual", routable=False)]
        self.assertTrue(route("concise", entries)["abstain"])
        self.assertEqual(route("use quiet", entries)["primary"], "quiet")
        self.assertIn("named_negative:quiet", route("use quiet without quiet", entries)["reasons"])
        got = route("alpha repair manual", entries, ctx=plan.Ctx({"windows"}), trace=True)
        self.assertEqual(got["primary"], "beta")
        self.assertIn("named_unroutable:manual", got["reasons"])
        self.assertEqual(got["trace"]["excluded"]["alpha"], "platform_mismatch")
        self.assertIn("named_ineligible", got["trace"]["reasons"])

    def test_reason_cap_keeps_abstention_and_soft_exclusions_are_trace_only(self):
        entries = [entry("item-%02d" % i) for i in range(20)]
        got = route(" ".join("without " + e["id"] for e in entries), entries)
        self.assertEqual(len(got["reasons"]), 12)
        self.assertEqual(got["reasons"], sorted(got["reasons"]))
        self.assertIn("no_candidate", got["reasons"])
        got = route("alpha repair", [entry("alpha", intents=["repair"], exclusions=["repair"])], trace=True)
        self.assertIn("exclusion_hit:alpha", got["trace"]["reasons"])
        self.assertNotIn("exclusion_hit:alpha", got["reasons"])
        self.assertNotIn("alpha", got["trace"]["excluded"])

    def test_synthetic_registry_surface_plans_are_compact(self):
        entries = [entry("synthetic-capability-%02d" % i, intents=["repair code"],
                         activation="explicit" if i % 3 == 0 else "contextual") for i in range(32)]
        p = params()
        index = plan.build_index(entries, STOP, p)
        tasks = ["", " ".join("use " + e["id"] for e in entries),
                 " ".join("without " + e["id"] for e in entries)]
        tasks += ["use " + e["id"] for e in entries]
        for task in tasks:
            with self.subTest(task=task):
                got = plan.make_plan(task, plan.Ctx(), index, p)
                self.assertLessEqual(len(plan.encode(got)), 1024)
                self.assertEqual(plan.encode(got), plan.encode(plan.make_plan(task, plan.Ctx(), index, p)))

    def test_pure_deterministic_and_compact(self):
        p = params()
        entries = [entry("alpha", intents=["repair"]), entry("beta", intents=["publish"])]
        saved = copy.deepcopy((entries, p))
        with mock.patch("builtins.open", side_effect=AssertionError("unexpected I/O")), \
                mock.patch.object(Path, "read_bytes", side_effect=AssertionError("unexpected I/O")):
            index = plan.build_index(entries, STOP, p)
            a = plan.make_plan("repair", plan.Ctx(), index, p)
            b = plan.make_plan("repair", plan.Ctx(), index, p)
        self.assertEqual(plan.encode(a), plan.encode(b))
        self.assertEqual(plan.encode(a), b'{"abstain":false,"confidence":1.0,"mode":null,"primary":"alpha","reasons":[],"reference":[],"router":"router-v2/1","schema":1,"supporting":[]}\n')
        self.assertLessEqual(len(plan.encode(a)), 1024)
        self.assertEqual((entries, p), saved)
        self.assertEqual(a, route("repair", list(reversed(entries)), p))
        self.assertNotIn("trace", a)
        p["decision"]["tau"] = 2.0
        with self.assertRaises(ValueError):
            plan.make_plan("repair", plan.Ctx(), index, p)


class ViewTests(unittest.TestCase):
    def test_explicit_reference_is_not_a_supporting_violation(self):
        from skillkit.core.route.views import explicit_violation
        by_id = {"alpha": {"activation": "contextual"}, "guide": {"activation": "explicit"}}
        case = {"expect": {"primary": "alpha"}, "tags": []}
        got = {"primary": "alpha", "supporting": [], "reference": ["guide"]}
        self.assertFalse(explicit_violation(case, got, by_id))
        got["supporting"] = ["guide"]
        self.assertTrue(explicit_violation(case, got, by_id))


if __name__ == "__main__":
    unittest.main()
