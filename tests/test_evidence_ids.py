"""Neutral evidence identifiers in authored metadata are public-safe."""
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID = re.compile(r'ev:(lic|card|note|rate|design|report):[a-z0-9][a-z0-9.-]{0,62}')


class EvidenceIdsTests(unittest.TestCase):
    def test_authored_metadata_identifiers(self):
        paths = [*ROOT.glob('skills/*/capability.toml'),
                 *ROOT.glob('workflows/*/capability.toml'),
                 *ROOT.glob('plugins/*/capability.toml'),
                 *ROOT.glob('ratings/rb-1/*.toml'),
                 ROOT / 'sources/idea-cards.toml', ROOT / 'taxonomy/tt-1.toml']
        def walk(value):
            if isinstance(value, dict):
                for item in value.values():
                    yield from walk(item)
            elif isinstance(value, list):
                for item in value:
                    yield from walk(item)
            elif isinstance(value, str) and value.startswith('ev:'):
                yield value
        for path in paths:
            for value in walk(tomllib.loads(path.read_text())):
                self.assertRegex(value, '^' + ID.pattern + '$', str(path.relative_to(ROOT)))
