"""Disposition shapes and attribution rendering stay separate from clearance."""
import hashlib
import re
import tomllib
from pathlib import Path
from skillkit.core import credits, model, provenance
from tests.helpers import TempCase

ROOT = Path(__file__).resolve().parents[1]


class DispositionTests(TempCase):
    def fixture(self, disposition, extra='', baseline=False):
        root = self.copy_fixture('good')
        cap = root / 'skills/alpha-research/capability.toml'
        own = re.sub(r'^(source|ref|adaptation) = .*\n', '', cap.read_text(), flags=re.M).replace('origin = "derived"', 'origin = "original"')
        cap.write_text(own + '\ndisposition = "' + disposition + '"\n' + extra)
        if baseline:
            (root / 'sources').mkdir(exist_ok=True)
            text = (root / 'skills/alpha-research/SKILL.md').read_bytes()
            (root / 'sources/idea-cards.toml').write_text(
                'baseline = {"skills/alpha-research/SKILL.md" = "' + hashlib.sha256(text).hexdigest() + '"}\n')
        repo = model.load(root)
        if (root / 'sources/idea-cards.toml').exists():
            repo.files['sources/idea-cards.toml'] = (root / 'sources/idea-cards.toml').read_bytes()
        return repo

    def test_original_without_upstream_passes(self):
        self.assertFalse(provenance.capability_checks(self.fixture('ORIGINAL')))

    def test_original_with_upstream_fails(self):
        repo = self.fixture('ORIGINAL')
        repo.caps[0].raw['provenance']['inspired_by'] = []
        self.assertIn('provenance-original', {f['rule'] for f in provenance.capability_checks(repo)})

    def test_legacy_requires_baseline(self):
        self.assertFalse(provenance.capability_checks(self.fixture('LEGACY-UNATTESTED', baseline=True)))
        self.assertIn('provenance-legacy', {f['rule'] for f in provenance.capability_checks(self.fixture('LEGACY-UNATTESTED'))})

    def test_unknown_disposition_fails_closed(self):
        repo = self.fixture('UNKNOWN')
        repo.caps[0].raw['provenance']['disposition'] = 'UNRECOGNIZED'
        self.assertIn('provenance-disposition', {f['rule'] for f in provenance.capability_checks(repo)})

    def test_original_attestation_requires_mechanism(self):
        repo = self.fixture('ORIGINAL')
        repo.files['sources/idea-cards.toml'] = b'[[text]]\npath="skills/alpha-research/SKILL.md"\nreuse="phrasing"\n'
        self.assertIn('provenance-original', {f['rule'] for f in provenance.capability_checks(repo)})

    def test_missing_disposition_on_attested_text_fails(self):
        repo = self.fixture('UNKNOWN'); del repo.caps[0].raw['provenance']['disposition']
        repo.files['sources/idea-cards.toml'] = b'[[text]]\npath="skills/alpha-research/SKILL.md"\nreuse="mechanism"\n'
        self.assertIn('provenance-disposition', {f['rule'] for f in provenance.capability_checks(repo)})


class CreditRenderingTests(TempCase):
    def test_own_text_rows_have_applicable_values_and_contiguous_table(self):
        entries = [dict(id='example', provenance=dict(origin='original', license='MIT', disposition='ORIGINAL')),
                   dict(id='legacy', provenance=dict(origin='original', license='MIT', disposition='LEGACY-UNATTESTED'))]
        text = credits.build(entries, {})['CREDITS.md'].decode()
        rows = [s for s in text.splitlines() if s.startswith('| ')]
        self.assertIn('| example | own text | n/a | n/a | MIT | UNKNOWN | ORIGINAL | n/a |', rows)
        self.assertNotIn('Mechanisms |', text)
        self.assertIn('legacy: earlier registry text; origin not attested; no upstream compare run; not cleared.', text)
        self.assertNotIn('no text copied', text)
        self.assertLess(text.index('| legacy |'), text.index('## Notes'))

    def test_every_shipped_card_has_an_existing_source_record(self):
        registry = tomllib.loads((ROOT / 'sources/idea-cards.toml').read_text())
        cards = {i:c for c in registry['card'] for i in c['ids']}
        for att in registry['text']:
            for ident in att['idea_cards']:
                path = cards[ident].get('source_record')
                self.assertIsNotNone(path, ident)
                self.assertTrue((ROOT / path).is_file(), ident)
