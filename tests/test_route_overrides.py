"""Named-capability detector: golden cases for matching, shadowing, negation,
the invocation-cue rule for explicit single-token names, unroutable entries,
determinism and parameter validation."""
import unittest
from collections import namedtuple

from skillkit.core import lexical
from skillkit.core.route import overrides
from skillkit.core.route.overrides import find_overrides

STOP = frozenset(("the", "a", "an", "and", "or", "to", "of", "me", "it", "is", "in", "on", "for", "with", "do", "not"))

ENTRIES = (
    {"id": "caveman", "name": "Caveman", "activation": "explicit"},
    {"id": "grill-me", "name": "grill-me", "activation": "explicit"},
    {"id": "grill-with-docs", "name": "grill-with-docs", "activation": "explicit"},
    {"id": "handoff", "activation": "explicit"},
    {"id": "terse-output", "name": "Terse Output", "activation": "explicit", "aliases": ["short mode", "brief"]},
    {"id": "bmad", "name": "BMAD", "activation": "contextual", "aliases": ["agile method"]},
    {"id": "docs-flow", "name": "Docs Flow", "activation": "contextual"},
    {"id": "docs-flow-extended", "name": "Docs Flow Extended", "activation": "contextual"},
    {"id": "manual-tool", "name": "Manual Tool", "activation": "manual", "routable": False},
    {"id": "ok", "name": "OK", "activation": "contextual"},
)


def detect(task, entries=ENTRIES, **kw):
    return find_overrides(task, entries, stopwords=STOP, **kw)


def ids(result):
    return [i for i, _p in result.named]


class MatchTests(unittest.TestCase):
    def test_id_name_and_alias_match_on_word_boundaries(self):
        self.assertEqual(ids(detect("please explain the bmad approach")), ["bmad"])
        self.assertEqual(ids(detect("try the agile method here")), ["bmad"])
        self.assertEqual(ids(detect("switch on terse output")), ["terse-output"])
        self.assertEqual(ids(detect("Terse-Output now")), ["terse-output"])

    def test_no_substring_matches(self):
        self.assertEqual(ids(detect("bmadly written bmad2 notes")), [])
        self.assertEqual(ids(detect("a handoffs list")), [])
        self.assertEqual(detect("nothing relevant at all"), ((), frozenset(), ()))

    def test_positions_and_ordering(self):
        r = detect("docs flow then bmad")
        self.assertEqual(r.named, (("docs-flow", 0), ("bmad", 3)))
        r = detect("bmad then docs flow")
        self.assertEqual(r.named, (("bmad", 0), ("docs-flow", 2)))

    def test_longer_match_of_another_entry_shadows_shorter(self):
        # "docs flow extended" names the longer entry only
        self.assertEqual(ids(detect("run docs flow extended")), ["docs-flow-extended"])
        self.assertEqual(ids(detect("run docs flow")), ["docs-flow"])
        # grill-with-docs contains neither another entry's phrase nor a clash
        self.assertEqual(ids(detect("grill-with-docs")), ["grill-with-docs"])

    def test_same_start_ties_sort_longer_phrase_first_then_id(self):
        entries = ({"id": "alpha", "name": "alpha beta", "aliases": ["alpha"], "activation": "contextual"},
                   {"id": "zulu", "name": "alpha", "activation": "contextual"})
        r = detect("alpha beta", entries)
        self.assertEqual([i for i, _p in r.named], ["alpha"])  # zulu's span is inside alpha's longer span

    def test_all_stopword_and_short_single_token_phrases_are_dropped(self):
        entries = ({"id": "the", "name": "The", "activation": "contextual"},
                   {"id": "to-do", "name": "to do", "activation": "contextual"},
                   {"id": "to-docs", "name": "to docs", "activation": "contextual"},
                   {"id": "ok", "name": "OK", "activation": "contextual"})
        self.assertEqual(detect("the ok list", entries).named, ())
        self.assertEqual(detect("a to do list", entries).named, ())  # every word is a stopword
        self.assertEqual(ids(detect("a to docs list", entries)), ["to-docs"])  # partly stopwords is fine

    def test_one_entry_with_several_matching_phrases_is_named_once(self):
        r = detect("bmad is the agile method")
        self.assertEqual(ids(r), ["bmad"])
        self.assertEqual(r.named[0][1], 0)

    def test_query_forms(self):
        Q = namedtuple("Q", "words")
        words = lexical.words("use caveman")
        for q in ("use caveman", words, tuple(words), Q(words)):
            self.assertEqual(ids(find_overrides(q, ENTRIES, stopwords=STOP)), ["caveman"])


class CueTests(unittest.TestCase):
    def test_explicit_single_token_needs_an_invocation_cue(self):
        self.assertEqual(ids(detect("a caveman lived in a cave")), [])
        self.assertEqual(ids(detect("caveman")), [])
        self.assertEqual(ids(detect("I wrote a handoff note for the team")), [])

    def test_cue_before_within_two_tokens(self):
        self.assertEqual(ids(detect("use caveman")), ["caveman"])
        self.assertEqual(ids(detect("please run the handoff")), ["handoff"])
        self.assertEqual(ids(detect("activate caveman now")), ["caveman"])
        self.assertEqual(ids(detect("run now and handoff")), [])  # cue three tokens away

    def test_cue_after_must_be_adjacent(self):
        self.assertEqual(ids(detect("caveman mode please")), ["caveman"])
        self.assertEqual(ids(detect("the handoff skill")), ["handoff"])
        self.assertEqual(ids(detect("handoff the skill")), [])

    def test_multi_token_explicit_names_need_no_cue(self):
        self.assertEqual(ids(detect("grill me")), ["grill-me"])
        self.assertEqual(ids(detect("terse output")), ["terse-output"])

    def test_non_explicit_single_token_needs_no_cue(self):
        self.assertEqual(ids(detect("bmad")), ["bmad"])

    def test_custom_cues(self):
        params = overrides.default_params()
        params["invoke_before"] = ["engage"]
        self.assertEqual(ids(detect("engage caveman", params=params)), ["caveman"])
        self.assertEqual(ids(detect("use caveman", params=params)), [])


class NegationTests(unittest.TestCase):
    def test_negation_cues(self):
        for task in ("without caveman", "no caveman", "dont use caveman", "don't use caveman", "do not use caveman",
                     "never use caveman", "stop using caveman", "skip caveman"):
            r = detect(task)
            self.assertEqual(r.negated, frozenset({"caveman"}), task)
            self.assertEqual(r.named, (), task)

    def test_one_bridge_token_is_allowed(self):
        self.assertEqual(detect("do not use the caveman").negated, frozenset({"caveman"}))
        self.assertEqual(detect("without any bmad").negated, frozenset({"bmad"}))
        self.assertEqual(detect("without using bmad").negated, frozenset({"bmad"}))

    def test_two_bridge_tokens_are_too_far(self):
        r = detect("without the a bmad")
        self.assertEqual(r.negated, frozenset())
        self.assertEqual(ids(r), ["bmad"])

    def test_non_bridge_word_breaks_the_negation(self):
        r = detect("without some bmad")
        self.assertEqual(r.negated, frozenset())
        self.assertEqual(ids(r), ["bmad"])

    def test_negation_applies_without_an_invocation_cue(self):
        self.assertEqual(detect("without handoff").negated, frozenset({"handoff"}))

    def test_negated_wins_over_positive_mention_of_the_same_id(self):
        r = detect("use bmad but without bmad")
        self.assertEqual(r.negated, frozenset({"bmad"}))
        self.assertEqual(r.named, ())

    def test_negation_is_per_id(self):
        r = detect("use bmad without docs flow")
        self.assertEqual(ids(r), ["bmad"])
        self.assertEqual(r.negated, frozenset({"docs-flow"}))

    def test_negation_must_end_immediately_before(self):
        self.assertEqual(ids(detect("no thanks, bmad please")), ["bmad"])
        self.assertEqual(detect("bmad without").negated, frozenset())

    def test_shadowed_match_is_not_negated(self):
        r = detect("without docs flow extended")
        self.assertEqual(r.negated, frozenset({"docs-flow-extended"}))


class UnroutableTests(unittest.TestCase):
    def test_unroutable_named_is_reported_separately(self):
        r = detect("open manual tool")
        self.assertEqual(r.named, ())
        self.assertEqual(r.unroutable_named, ("manual-tool",))

    def test_unroutable_negated(self):
        r = detect("no manual tool")
        self.assertEqual(r.unroutable_named, ())
        self.assertEqual(r.negated, frozenset({"manual-tool"}))


class ParamsAndDeterminismTests(unittest.TestCase):
    def test_default_params_validate_and_are_copies(self):
        p = overrides.default_params()
        self.assertIs(overrides.validate_params(p), p)
        p["bridge"].append("x")
        self.assertNotIn("x", overrides.default_params()["bridge"])

    def test_bad_params_rejected(self):
        good = overrides.default_params()
        for bad in (None, {}, dict(good, extra=["x"]), dict(good, bridge=[]), dict(good, bridge="the"),
                    dict(good, bridge=[""]), dict(good, bridge=[3])):
            with self.assertRaises(overrides.OverrideParamsError):
                find_overrides("x", ENTRIES, params=bad) if bad is not None else overrides.validate_params(bad)

    def test_deterministic_and_input_order_independent(self):
        task = "use caveman and handoff skill, without bmad, then docs flow"
        first = detect(task)
        self.assertEqual(first, detect(task))
        self.assertEqual(first, detect(task, tuple(reversed(ENTRIES))))
        self.assertEqual(ids(first), ["caveman", "handoff", "docs-flow"])
        self.assertEqual(first.negated, frozenset({"bmad"}))

    def test_inputs_are_not_mutated(self):
        entries = [dict(e) for e in ENTRIES]
        params = overrides.default_params()
        find_overrides("use caveman", entries, params=params, stopwords=STOP)
        self.assertEqual(entries, [dict(e) for e in ENTRIES])
        self.assertEqual(params, overrides.default_params())


if __name__ == "__main__":
    unittest.main()
