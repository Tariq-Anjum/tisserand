"""Synthetic provenance, history, and attribution contract tests."""
import copy
import json
from pathlib import Path

from skillkit.core import generate, model, provenance, schemacheck
from tests.helpers import TempCase, run

ROOT = Path(__file__).resolve().parents[1]


class ProvenanceSchemaTests(TempCase):
    def setUp(self):
        super().setUp()
        self.root = self.copy_fixture('good')
        self.rel = 'skills/alpha-research/capability.toml'
        self.schema = json.loads((ROOT / 'schema/capability.schema.json').read_text())
        self.raw = model.load(self.root).caps[0].raw
        self.p = self.raw['provenance']

    def validate(self, **values):
        raw = copy.deepcopy(self.raw)
        raw['provenance'].update(values)
        return schemacheck.validate(raw, self.schema)

    def test_legacy_and_complete_inspiration(self):
        self.assertFalse(self.validate(derived_from='old source'))
        self.assertFalse(self.validate(inspired_by=[dict(name='Example', url='https://example.org/repo',
            sha='a' * 40, licence='MIT', date='2026-11-09')], disposition='UNKNOWN'))

    def test_inspiration_shapes(self):
        good = dict(name='Example', url='https://example.org/repo', sha='a' * 40,
                    licence='MIT', date='2026-11-09')
        for key in good:
            bad = dict(good)
            del bad[key]
            self.assertTrue(self.validate(inspired_by=[bad], disposition='UNKNOWN'), key)
        for key, value in [('url', '/local'), ('sha', 'HEAD'), ('date', '2026-02-30'), ('name', '')]:
            self.assertTrue(self.validate(inspired_by=[dict(good, **{key: value})], disposition='UNKNOWN'))
        self.assertTrue(self.validate(inspired_by=[]))
        self.assertTrue(self.validate(disposition='CLEARED'))

    def test_relative_evidence_only(self):
        self.assertFalse(self.validate(evidence_ref='ev:lic:example'))
        legacy = 'G' + '2/' + 'licence' + '-evidence/'
        for value in ['/tmp/evidence', '../evidence', legacy + '../bad',
                      legacy, 'ev:lic:', 'ev:lic:Bad_Case', legacy + 'old', 'C:\\evidence', 'https://example.org/evidence']:
            self.assertTrue(self.validate(evidence_ref=value), value)

    def findings(self, extra):
        with (self.root / self.rel).open('a') as f:
            f.write('\n' + extra + '\n')
        return generate.evaluate(self.root, with_drift=False).errors

    def test_copied_requires_evidence(self):
        for disposition in ('COPIED-PERMISSIVE', 'COPIED-UNCLEARED'):
            root = self.copy_fixture('good')
            path = root / self.rel
            path.write_text(path.read_text() + '\ndisposition = "' + disposition + '"\n')
            self.assertIn('provenance-evidence', {f['rule'] for f in generate.evaluate(root, False).errors})

    def test_independent_rejects_derivation_text(self):
        self.assertIn('provenance-independent', {f['rule'] for f in self.findings(
            'disposition = "INDEPENDENT"\nderived_from = "old source"')})

    def test_mit_clearance_and_current_rewrite_attestation(self):
        p = self.root / self.rel
        p.write_text(p.read_text() + '\nderived_from = "legacy source"\n')
        self.assertIn('provenance-clearance', {f['rule'] for f in generate.evaluate(self.root, False).errors})
        source = self.root / 'sources'
        source.mkdir()
        text = (self.root / 'skills/alpha-research/SKILL.md').read_text() + '\nexample-01\n'
        (self.root / 'skills/alpha-research/SKILL.md').write_text(text)
        (self.tmp / 'original.md').write_text('Unrelated upstream words with no shared eight word sequence.')
        att = ('schema = 1\n[[card]]\nids = ["example-01"]\nrecords = ["original.md"]\n'
               '[[text]]\npath = "skills/alpha-research/SKILL.md"\nidea_cards = ["example-01"]\n'
               'reuse = "mechanism"\ndigest = "' + provenance.digest(text) + '"\n')
        (source / 'idea-cards.toml').write_text(att)
        self.assertNotIn('provenance-clearance', {f['rule'] for f in
            generate.evaluate(self.root, False, sources_root=self.tmp).errors})
        (source / 'idea-cards.toml').write_text(att.replace(provenance.digest(text), '0' * 64))
        self.assertIn('provenance-clearance', {f['rule'] for f in
            generate.evaluate(self.root, False, sources_root=self.tmp).errors})


class MigrationTests(TempCase):
    def module(self):
        from skillkit.core import migrations
        return migrations

    def test_resolution_is_permanent_and_transitive(self):
        m = self.module()
        data = {'schema': 1, 'aliases': {'old': dict(target='middle', reason='rename', date='2000-01-01')},
                'retired_by': {'middle': dict(target='live', reason='merge', date='2000-01-02')}}
        self.assertEqual(m.validate(data, {'live'}), [])
        self.assertEqual(m.resolve('old', data, {'live'}), 'live')
        self.assertEqual(m.resolve('middle', data, {'live'}), 'live')
        self.assertIsNone(m.resolve('missing', data, {'live'}))

    def test_invalid_maps(self):
        m = self.module()
        rec = dict(target='live', reason='rename', date='2026-11-09')
        for data in [dict(schema=1, aliases={'live': rec}),
                     dict(schema=1, aliases={'old': rec}, retired_by={'old': rec}),
                     dict(schema=1, aliases={'old': dict(rec, target='missing')}),
                     dict(schema=1, aliases={'old': dict(rec, target='old')}),
                     dict(schema=1, aliases={'old': dict(rec, date='2026-02-30')}),
                     dict(schema=1, aliases={'old': dict(rec, reason='')}),
                     dict(schema=1, aliases={'old': dict(rec, expires='2027-01-01')}),
                     dict(schema=2), dict(schema=1, aliases=[]),
                     dict(schema=1, aliases={'Bad ID': rec})]:
            self.assertTrue(m.validate(data, {'live'}), data)
        self.assertTrue(m.validate(dict(schema=1, aliases={'old': rec}), {'live'}, {'old'}))

    def test_loader_check_and_lock(self):
        m = self.module()
        root = self.copy_fixture('good')
        p = root / m.PATH
        p.write_text('schema = 1\n[aliases.old]\ntarget = "alpha-research"\nreason = "rename"\ndate = "2000-01-01"\n')
        self.assertEqual(m.load(root, {'alpha-research'})['aliases']['old']['target'], 'alpha-research')
        self.assertEqual(run('gen', '--root', str(root))[0], 0)
        lock = json.loads((root / 'registry/manifest.lock.json').read_text())
        self.assertIn(m.PATH, lock['inputs'])
        p.write_text(p.read_text().replace('alpha-research', 'absent'))
        self.assertIn('migrations', {f['rule'] for f in generate.evaluate(root, False).errors})


class AttributionTests(TempCase):
    def test_generates_unknown_without_clearance_claim(self):
        root = self.copy_fixture('good')
        self.assertEqual(run('gen', '--root', str(root))[0], 0)
        credits = (root / 'CREDITS.md').read_text()
        self.assertIn('UNKNOWN', credits)
        self.assertNotIn('no text copied', credits)
        self.assertEqual(run('gen', '--check', '--root', str(root))[0], 0)
        (root / 'CREDITS.md').write_text('stale')
        self.assertNotEqual(run('gen', '--check', '--root', str(root))[0], 0)

    def test_copied_notice_and_independent_credit(self):
        from skillkit.core import credits
        entries = [dict(id='example', routing={'provides': ['planning']}, provenance=dict(
            disposition='COPIED-PERMISSIVE', evidence_ref='ev:lic:example',
            inspired_by=[dict(name='Example', url='https://example.org/repo', sha='a' * 40,
                             licence='MIT', date='2026-11-09')]))]
        sources = {'sources/notices.toml': b'[[notice]]\nevidence_ref="ev:lic:example"\ntext="Copyright Example; exact required upstream notice."\n'}
        outputs = credits.build(entries, sources)
        notice = outputs['THIRD_PARTY_NOTICES'].decode()
        for item in ('Example', 'https://example.org/repo', 'a' * 40, 'MIT', '2026-11-09',
                     'example', 'ev:lic:example'):
            self.assertIn(item, notice)
        self.assertIn('required', notice.lower())
        entries[0]['provenance']['disposition'] = 'INDEPENDENT'
        outputs = credits.build(entries, {})
        self.assertIn('no text copied', outputs['CREDITS.md'].decode())
        self.assertNotIn('Capability: example', outputs['THIRD_PARTY_NOTICES'].decode())
        retained = credits.build(entries, sources)['THIRD_PARTY_NOTICES'].decode()
        self.assertIn('Copyright Example; exact required upstream notice.', retained)

    def test_sources_and_mechanism_citations_are_retained(self):
        from skillkit.core import credits
        sources = {'sources/example.md': b'# Example\n\nRepo: https://example.org/repo\nLicense: verify at source\n',
                   'sources/idea-cards.toml': b'[[card]]\nids=["example-01"]\nrecord="ev:card:example"\n[[text]]\npath="skills/example/SKILL.md"\nidea_cards=["example-01"]\nreuse="mechanism"\n'}
        entries = [dict(id='example', path='skills/example/SKILL.md', routing={'provides': ['planning']}, provenance={})]
        text = credits.build(entries, sources)['CREDITS.md'].decode()
        for value in ('https://example.org/repo', 'example-01', 'planning', 'skills/example/SKILL.md'):
            self.assertIn(value, text)


class AttributionBoundaryTests(TempCase):
    def test_only_generated_provenance_paths_are_lint_exempt(self):
        from skillkit.core import lint_neutrality, lint_privacy
        from skillkit.core.scan import ScannedFile, Scan
        config = lint_neutrality.Config(__import__('re').compile('Example'), None, [])
        for rel in ('CREDITS.md', 'THIRD_PARTY_NOTICES', 'ordinary.md'):
            f = ScannedFile(rel, b'Example', 'Example')
            report = lint_neutrality._file_report(config, f)
            self.assertEqual(bool(report.counts), rel == 'ordinary.md')
        root = self.tmp / 'repo'
        root.mkdir()
        for rel in ('CREDITS.md', 'THIRD_PARTY_NOTICES', 'ordinary.md'):
            (root / rel).write_text('person' + '@' + 'private.invalid')
        report = lint_privacy.analyse(Scan(root))
        self.assertEqual(set(report.counts), {'ordinary.md'})

    def test_nested_inspirations_are_provenance_data(self):
        import re
        from skillkit.core import lint_neutrality
        from skillkit.core.scan import ScannedFile
        config = lint_neutrality.Config(re.compile('Example'), None, [])
        text = '[[provenance.inspired_by]]\nname="Example"\n[routing]\nname="Example"\n'
        report = lint_neutrality._file_report(config, ScannedFile('skills/example/capability.toml', text.encode(), text))
        self.assertEqual(report.counts, {'skills/example/capability.toml': 1})

    def test_missing_exact_notice_fails_closed(self):
        from skillkit.core import credits
        entry = dict(id='example', provenance=dict(disposition='COPIED-UNCLEARED',
                     evidence_ref='ev:lic:example'))
        with self.assertRaisesRegex(ValueError, 'required upstream notice missing'):
            credits.build([entry], {})

    def test_independent_mit_and_copied_with_evidence(self):
        root = self.copy_fixture('good')
        rel = 'skills/alpha-research/capability.toml'
        p = root / rel
        p.write_text(p.read_text() + '\ndisposition="INDEPENDENT"\ninspired_by=[]\n')
        result = generate.evaluate(root, False)
        self.assertFalse(result.errors, result.errors)
        p.write_text(p.read_text().replace('license = "MIT"', 'license = "Apache-2.0"')
                     .replace('"INDEPENDENT"', '"COPIED-UNCLEARED"') +
                     '\nevidence_ref="ev:lic:example"\n')
        (root / 'sources').mkdir()
        (root / 'sources/notices.toml').write_text('[[notice]]\nevidence_ref="ev:lic:example"\ntext="Required upstream notice."\n')
        result = generate.evaluate(root, False)
        self.assertFalse(result.errors, result.errors)
        self.assertIn(b'COPIED-UNCLEARED', result.outputs['THIRD_PARTY_NOTICES'])

    def test_history_cycles_and_bad_toml_are_findings(self):
        from skillkit.core import migrations
        rec = lambda target: dict(target=target, reason='merge', date='2000-01-01')
        data = dict(schema=1, aliases={'old': rec('middle')}, retired_by={'middle': rec('old')})
        self.assertTrue(migrations.validate(data, {'live'}))
        root = self.copy_fixture('good')
        (root / migrations.PATH).write_text('schema = [')
        self.assertIn('migrations', {f['rule'] for f in generate.evaluate(root, False).errors})

    def test_task_data_provenance_uses_disposition_rules(self):
        root = self.copy_fixture('good')
        p = root / 'skills/alpha-research/capability.toml'
        p.write_text(p.read_text() + '\ndisposition="COPIED-PERMISSIVE"\n')
        code, output, _ = run('task-data', 'provenance', '--root', str(root))
        self.assertEqual(code, 1)
        self.assertIn('provenance-evidence', output)
