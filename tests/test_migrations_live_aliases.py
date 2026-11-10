"""Tests for the migrations live-alias rule and named old-name routing.

Synthetic data only, except the last class, which reads the live registry.
"""
import json
import unittest
from pathlib import Path

from skillkit.core import migrations

ROOT = Path(__file__).resolve().parents[1]


def rec(target):
    return {'target': target, 'reason': 'renamed', 'date': '2026-11-09'}


class LiveAliasRuleTests(unittest.TestCase):
    live = {'new', 'other'}

    def check(self, data, aliases):
        return migrations.validate(dict(schema=1, **data), self.live, aliases)

    def test_alias_owned_by_target_is_accepted(self):
        self.assertEqual(self.check({'aliases': {'old': rec('new')}}, {'old': 'new'}), [])

    def test_alias_owned_by_another_capability_is_rejected(self):
        self.assertTrue(self.check({'aliases': {'old': rec('new')}}, {'old': 'other'}))

    def test_retired_by_key_follows_the_same_rule(self):
        self.assertEqual(self.check({'retired_by': {'old': rec('new')}}, {'old': 'new'}), [])
        self.assertTrue(self.check({'retired_by': {'old': rec('new')}}, {'old': 'other'}))

    def test_owner_must_equal_the_resolved_end_of_a_chain(self):
        data = {'aliases': {'a': rec('b'), 'b': rec('new')}}
        self.assertEqual(self.check(data, {'a': 'new'}), [])
        self.assertTrue(self.check(data, {'a': 'other'}))

    def test_cycle_through_a_live_alias_is_rejected(self):
        self.assertTrue(self.check({'aliases': {'a': rec('b'), 'b': rec('a')}}, {'a': 'new'}))

    def test_key_equal_to_a_live_id_is_rejected(self):
        self.assertTrue(self.check({'aliases': {'new': rec('other')}}, {}))

    def test_plain_alias_set_stays_fail_closed(self):
        self.assertTrue(self.check({'aliases': {'old': rec('new')}}, {'old'}))

    def test_resolution_matches_the_alias_owner(self):
        data = dict(schema=1, aliases={'old': rec('new')})
        self.assertEqual(migrations.resolve('old', data, self.live), 'new')


class NamedOldNameRoutingTests(unittest.TestCase):
    """Requests that name an old id route to its new owner through the
    frozen name detector (capability aliases), not only via host links."""
    cases = (
        ('grill me on the migration plan before we start', 'decision-interview'),
        ('use wayfinder for the data move over multiple milestones', 'bounded-plan'),
        ('apply context-fundamentals to our skill registry loading', 'context-design'),
        ('use serena-code-intelligence to find references to parse_config', 'code-intelligence'),
    )

    def test_old_names_are_detected_as_their_new_owner(self):
        # Production detector inputs: the registry rows the router reads and the
        # committed stopword list (lexical.load_stopwords), as routecli does.
        from skillkit.core import lexical
        from skillkit.core.route.overrides import find_overrides
        catalog = json.loads((ROOT / 'registry/catalog.json').read_text())
        caps = catalog['capabilities'] if isinstance(catalog, dict) else catalog
        entries = [{'id': c['id'], 'name': c.get('name', c['id']), 'aliases': c.get('aliases', []),
                    'activation': c['activation']} for c in caps]
        stop = lexical.load_stopwords(ROOT)
        for text, owner in self.cases:
            with self.subTest(text=text):
                named = [i for i, _ in find_overrides(text, entries, stopwords=stop).named]
                self.assertEqual(named, [owner])


if __name__ == '__main__':
    unittest.main()
