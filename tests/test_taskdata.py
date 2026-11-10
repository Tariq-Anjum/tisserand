"""Synthetic contracts; never read the benchmark corpus."""
import copy
import json
import unittest

from skillkit.core import schemacheck
from tests.helpers import TempCase, run


def taxonomy():
    return {
        'version': 'tt-1.0.0', 'revision': 2, 'cue_file': 'cues.toml',
        'artifacts': ['code', 'agent', 'none'], 'conditions': ['long_running'],
        'stage_order': ['plan', 'implement', 'any'],
        'type': [
            {'id': 'plan', 'order': 1, 'stage': 'plan', 'artifact_default': 'code',
             'definition': 'Order agreed work', 'not_this': [{'to': 'debug', 'when': 'a failure'}]},
            {'id': 'debug', 'order': 2, 'stage': 'implement', 'artifact_default': 'code',
             'definition': 'Diagnose a failure', 'not_this': []},
            {'id': 'unclear', 'order': 3, 'stage': 'any', 'artifact_default': 'none',
             'definition': 'Abstain', 'not_this': []}],
        'tie_break': [{'pair': ['plan', 'debug'], 'choose': 'plan'}],
        'unclear': {'U1': 'no outcome', 'U2': 'state-changing split', 'U3': 'missing object'}}


def cues():
    return {'version': 'cues-1', 'tt': 'tt-1.0.0', 'artifact_order': ['agent', 'code'],
            'artifact': {'agent': ['skill', 'SKILL.md'], 'code': ['module', '*.py']},
            'steps': {'plan': ['make a plan'], 'debug': ['diagnose the failure']},
            'conditions': {'long_running': ['long running']}}


def rubric():
    return {'version': 'rb-1.0.0', 'tt': 'tt-1.0.0', 'weights': {'F': 4, 'B': 3, 'S': 2, 'C': 1},
            'score': {'multiplier': 5, 'offset': 1, 'divisor': 2},
            'primary': {'F': 3, 'score': 50}, 'supporting': {'F': 2, 'score': 40},
            'benefit_max': 2}


def cell(ident='alpha', **kw):
    value = {'id': ident, 'task_type': 'plan', 'scope': ['code'], 'when': {},
             'F': 3, 'B': 2, 'S': 1, 'C': 3, 'raw': 23, 'score': 58,
             'evidence': 'synthetic:1', 'flags': [], 'digest': '0' * 64}
    value.update(kw)
    return value


class TaskDataTests(unittest.TestCase):
    def td(self):
        from skillkit.core import taskdata
        return taskdata

    def test_closed_taxonomy_rejects_unknown_references_and_overlap(self):
        td = self.td()
        td.validate_taxonomy(taxonomy(), cues())
        for mutate in (
            lambda t, c: t['type'].append(copy.deepcopy(t['type'][0])),
            lambda t, c: t['type'][0]['not_this'][0].update(to='missing'),
            lambda t, c: c['steps'].update(missing=['do a thing']),
            lambda t, c: c['conditions'].update(long_running=['*']),
            lambda t, c: c['artifact_order'].remove('code'),
        ):
            t, c = taxonomy(), cues()
            mutate(t, c)
            with self.assertRaises(ValueError):
                td.validate_taxonomy(t, c)
        t, c = taxonomy(), cues()
        t['tie_break'] = []
        c['steps']['debug'] = ['make a plan']
        with self.assertRaisesRegex(ValueError, 'overlap'):
            td.validate_taxonomy(t, c)

    def test_references_in_ties_and_non_mutating_are_closed(self):
        td = self.td()
        t = taxonomy()
        t['tie_break'][0].update(if_true='missing')
        with self.assertRaises(ValueError):
            td.validate_taxonomy(t, cues())
        t = taxonomy()
        t['non_mutating'] = ['missing']
        with self.assertRaises(ValueError):
            td.validate_taxonomy(t, cues())

    def test_precede_rejects_unknown_conditions_results_and_non_tables(self):
        td = self.td()
        for invalid in ({'missing': 'plan'}, {'long_running': 'unclear'}, [], None):
            t = taxonomy()
            t['tie_break'][0]['precede'] = invalid
            with self.subTest(precede=invalid), self.assertRaisesRegex(ValueError, 'precede'):
                td.validate_taxonomy(t, cues())

    def test_pair_resolution_reads_precede_before_condition(self):
        td = self.td()
        t = taxonomy()
        t['conditions'].append('finished_work')
        t['tie_break'] = [{'pair': ['plan', 'debug'],
                          'precede': {'long_running': 'plan'},
                          'condition': 'finished_work', 'if_true': 'debug', 'otherwise': 'plan'}]
        for own, finished, expected in ((True, True, 'plan'), (True, False, 'plan'),
                                        (False, True, 'debug'), (False, False, 'plan')):
            self.assertEqual(td.resolve_tie(['debug', 'plan'],
                {'long_running': own, 'finished_work': finished}, t), expected)
        self.assertIsNone(td.resolve_tie(['plan', 'unclear'], {}, t))
        self.assertEqual(td.resolve_tie(['plan', 'debug'], {}, taxonomy()), 'plan')

    def test_cues_are_normalized_whole_word_and_paths(self):
        td = self.td()
        got = td.match_cues('SKILL.md make_a-plan for a long-running module', taxonomy(), cues())
        self.assertEqual(got, {'artifact': 'agent', 'steps': ['plan'], 'conditions': {'long_running': True}})
        self.assertEqual(td.match_cues('skilled modules in src/foo.py', taxonomy(), cues())['artifact'], 'code')
        self.assertIsNone(td.match_cues('skilled modules', taxonomy(), cues())['artifact'])

    def test_rating_score_and_unknown_not_imputed(self):
        td = self.td()
        td.validate_cell(cell(), taxonomy(), rubric())
        with self.assertRaisesRegex(ValueError, 'score'):
            td.validate_cell(cell(score=57), taxonomy(), rubric())
        with self.assertRaises(ValueError):
            td.validate_cell(cell(when={'missing': True}), taxonomy(), rubric())
        u = cell(F='UNSCORED', B='UNSCORED', S='UNSCORED', C='UNSCORED', raw='UNSCORED', score='UNSCORED')
        td.validate_cell(u, taxonomy(), rubric())
        self.assertIsNone(td.eligibility(u, rubric()))

    def test_low_score_neighbors_still_report_shared_triggers(self):
        td = self.td()
        cells = [cell('alpha', F=2, B=1, S=1, C=1, raw=14, score=35),
                 cell('beta', F=3, B=1, S=1, C=1, raw=18, score=45)]
        caps = {i: {'activation': 'contextual', 'routing': {'phrases': ['shared requirements']}}
                for i in ('alpha', 'beta')}
        found = td.collisions(taxonomy(), rubric(), cells, caps)
        self.assertTrue(any(c['kind'] == 'trigger' for c in found))

    def test_role_cap_limits_eligibility_without_promoting_cells(self):
        td = self.td()
        capped = cell(max_role='supporting')
        td.validate_cell(capped, taxonomy(), rubric())
        self.assertEqual(td.eligibility(capped, rubric()), 'supporting')
        self.assertEqual(td.eligibility(cell(max_role='primary'), rubric()), 'primary')
        self.assertIsNone(td.eligibility(cell(max_role='supporting', F=1, raw=15, score=38), rubric()))
        unknown = cell(max_role='supporting', F='UNSCORED', B='UNSCORED',
                       S='UNSCORED', C='UNSCORED', raw='UNSCORED', score='UNSCORED')
        self.assertIsNone(td.eligibility(unknown, rubric()))
        for invalid in ('reviewer', '', None, 1, []):
            with self.subTest(max_role=invalid), self.assertRaisesRegex(ValueError, 'max_role'):
                td.validate_cell(cell(max_role=invalid), taxonomy(), rubric())

    def test_negation_only_conditions_rejected_but_positive_and_mixed_allowed(self):
        td = self.td()
        with self.assertRaisesRegex(ValueError, 'positive condition'):
            td.validate_cell(cell(when={'long_running': False}), taxonomy(), rubric())
        t = taxonomy()
        t['conditions'].append('semantic_code')
        for when in ({}, {'long_running': True}, {'long_running': False, 'semantic_code': True}):
            td.validate_cell(cell(when=when), t, rubric())

    def test_capped_cells_do_not_create_primary_collisions_or_named_only_rows(self):
        td = self.td()
        cells = [cell(), cell('helper', max_role='supporting')]
        caps = {i: {'activation': 'contextual'} for i in ('alpha', 'helper')}
        rows = td.decision_rows(taxonomy(), rubric(), cells, caps)
        row = next(r for r in rows if r['task_type'] == 'plan' and r['artifact'] == 'code')
        self.assertEqual((row['primary'], row['supporting'], row['status']), ('alpha', ['helper'], 'ok'))
        self.assertEqual(td.collisions(taxonomy(), rubric(), cells, caps), [])
        caps['helper']['activation'] = 'explicit'
        rows = td.decision_rows(taxonomy(), rubric(), cells[1:], caps)
        self.assertTrue(all(r['primary'] is None and r['status'] != 'named-only' for r in rows))

    def test_decisions_preserve_explicit_and_conditional_support(self):
        td = self.td()
        cells = [cell(), cell('named', F=4, raw=27, score=68),
                 cell('helper', F=2, raw=19, score=48, when={'long_running': True})]
        caps = {'alpha': {'activation': 'contextual'}, 'named': {'activation': 'explicit'},
                'helper': {'activation': 'contextual'}}
        rows = td.decision_rows(taxonomy(), rubric(), cells, caps)
        off = next(r for r in rows if r['task_type'] == 'plan' and r['artifact'] == 'code' and not r['when']['long_running'])
        on = next(r for r in rows if r['task_type'] == 'plan' and r['artifact'] == 'code' and r['when']['long_running'])
        self.assertEqual((off['primary'], off['supporting']), ('alpha', []))
        self.assertEqual(on['supporting'], ['helper'])
        rows = td.decision_rows(taxonomy(), rubric(), cells[1:], caps)
        self.assertTrue(all(r['primary'] is None for r in rows))
        self.assertTrue(any(r['status'] == 'named-only' for r in rows))

    def test_collisions_fail_for_multiple_primaries_and_report_triggers(self):
        td = self.td()
        cells = [cell(), cell('beta')]
        caps = {i: {'activation': 'contextual', 'routing': {'phrases': ['make a plan']}} for i in ('alpha', 'beta')}
        found = td.collisions(taxonomy(), rubric(), cells, caps)
        self.assertEqual({x['kind'] for x in found}, {'primary', 'trigger'})
        self.assertTrue(all(set(x) == {'pair', 'cell', 'kind', 'value'} for x in found))
        caps['beta']['activation'] = 'manual'
        self.assertNotIn('primary', {x['kind'] for x in td.collisions(taxonomy(), rubric(), cells, caps)})


class ProvenanceTests(TempCase):
    def gate(self, text, reuse='mechanism', cards=None):
        from skillkit.core import provenance
        (self.tmp / 'source.md').write_text('one two three four five six seven eight nine', encoding='utf-8')
        return provenance.check_texts({'skills/demo/SKILL.md': text}, {},
            [{'path': 'skills/demo/SKILL.md', 'digest': provenance.digest(text),
              'idea_cards': ['demo-01'] if cards is None else cards, 'reuse': reuse}],
            {'demo-01': {'license_verified': False, 'records': ['source.md']}}, self.tmp)

    def test_changed_text_requires_known_cards_and_mechanism_only(self):
        self.assertEqual(self.gate('An independent procedure with its own language. Idea cards: demo-01.'), [])
        self.assertTrue(self.gate('new text'))  # missing in-text card citation
        self.assertTrue(self.gate('new text', cards=[]))
        self.assertTrue(self.gate('new text', cards=['unknown-99']))
        self.assertTrue(self.gate('new text', reuse='phrasing'))

    def test_overlap_is_case_and_punctuation_insensitive(self):
        found = self.gate('ONE, two THREE four five six seven eight!')
        self.assertIn('8gram', {x['kind'] for x in found})
        self.assertEqual(self.gate('one two three four five six seven different eight. Idea cards: demo-01.'), [])

    def test_missing_source_and_stale_attestation_fail_closed(self):
        from skillkit.core import provenance
        found = provenance.check_texts({'x': 'new'}, {},
            [{'path': 'x', 'digest': '0'*64, 'idea_cards': ['a'], 'reuse': 'mechanism'}],
            {'a': {'license_verified': False, 'records': ['absent.md']}}, self.tmp)
        self.assertTrue(found)


class TaskMetricTests(unittest.TestCase):
    def test_precision_uses_expected_type_and_wilson_interval(self):
        from skillkit.core import taskmetrics
        cases = [{'expect': {'task_type': 'plan', 'primary': p, 'steps': ['plan', 'debug'], 'must_not': []}}
                 for p in ['a', 'b', 'a']]
        predictions = [{'primary': 'a', 'task_type': 'plan', 'cue_steps': ['debug']} for _ in cases]
        predictions[-1]['task_type'] = 'unclear'
        report = taskmetrics.summarize(cases, predictions, {'split': 'synthetic'})
        row = report['per_cell'][0]
        self.assertEqual((row['n'], row['correct'], row['precision']), (3, 2, 0.666667))
        self.assertAlmostEqual(row['ci'][0], 0.20766, places=4)
        self.assertAlmostEqual(row['ci'][1], 0.93851, places=4)
        self.assertEqual(report['cue_recall']['value'], 1)
        self.assertFalse(report['unclear_on_clear']['pass'])
        with self.assertRaises(ValueError):
            taskmetrics.summarize(cases, predictions[:1], {})

    def test_missing_prediction_type_cannot_pass_unclear_gate(self):
        from skillkit.core import taskmetrics
        with self.assertRaises(ValueError):
            taskmetrics.summarize([{'expect': {'task_type': 'plan', 'primary': 'a'}}], [{'primary': 'a'}], {})

    def test_empty_denominators_are_unmeasured(self):
        from skillkit.core import taskmetrics
        r = taskmetrics.summarize([], [], {})
        self.assertIsNone(r['cue_recall']['value'])
        self.assertIsNone(r['unclear_on_clear']['value'])
        self.assertIsNone(r['unclear_on_clear']['pass'])


if __name__ == '__main__':
    unittest.main()
