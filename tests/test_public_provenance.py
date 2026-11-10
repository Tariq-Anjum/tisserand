"""Public checks remain useful; strict evidence and release binding fail closed."""
import hashlib
import json
import re
import subprocess
from pathlib import Path
from skillkit.core import generate
from tests.helpers import TempCase, run


class PublicProvenanceTests(TempCase):
    def fixture(self, attested=True):
        root = self.copy_fixture('good')
        for p in root.glob('*/*/capability.toml'):
            text = re.sub(r'^(source|ref|derived_from) = .*\n', '', p.read_text(), flags=re.M)
            text = text.replace('origin = "derived"', 'origin = "original"')
            text = text.replace('[provenance]', '[provenance]\ndisposition = "ORIGINAL"')
            p.write_text(text)
        (root / 'sources').mkdir(exist_ok=True)
        self.doc = root / 'skills/alpha-research/SKILL.md'
        text = self.doc.read_text() + '\nfixture-01\n'
        self.doc.write_text(text)
        self.record = self.tmp / 'source.md'; self.record.write_text('Distinct reference concepts without shared phrases.')
        self.evidence = self.tmp / 'map.toml'; self.evidence.write_text('')
        self.baseline = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in root.glob('skills/*/SKILL.md')}
        if attested:
            self.baseline.pop('skills/alpha-research/SKILL.md')
        baseline = 'baseline={' + ','.join(json.dumps(k)+'='+json.dumps(v) for k,v in self.baseline.items()) + '}\n'
        (root / 'sources/idea-cards.toml').write_text(baseline)
        if attested:
            (root / 'sources/idea-cards.toml').write_text(baseline + '[[card]]\nids=["fixture-01"]\nrecords=["source.md"]\n'
                '[[text]]\npath="skills/alpha-research/SKILL.md"\nidea_cards=["fixture-01"]\nreuse="mechanism"\ndigest="' +
                hashlib.sha256(text.encode()).hexdigest() + '"\n')
        code, out, err = run('gen', '--root', str(root), '--sources-root', str(self.tmp))
        self.assertEqual(code, 0, out + err)
        return root

    def check(self, root, *args):
        code, out, err = run('check', '--root', str(root), '--format', 'json', '--no-cache', *args)
        return code, json.loads(out) if out else {}, err

    def test_public_missing_sources_is_incomplete_once_per_text(self):
        root = self.fixture(); code, out, _ = self.check(root)
        self.assertEqual(code, 0, out)
        self.assertEqual(out['provenance']['state'], 'INCOMPLETE')
        self.assertEqual(out['provenance']['unavailable'], 1)
        self.assertIs(out['provenance_complete'], False)
        text = run('check', '--root', str(root))[1]
        self.assertIn('provenance: INCOMPLETE', text)
        self.assertNotIn('OK', next(s for s in text.splitlines() if s.startswith('provenance:')))
        self.assertNotIn('source.md', str(out['findings']))

    def test_digest_and_overlap_errors_are_fatal_without_private_inputs(self):
        root = self.fixture(); self.doc.write_text(self.doc.read_text()+'changed')
        code, out, _ = self.check(root)
        self.assertEqual(code, 1); self.assertEqual(out['provenance']['state'], 'FAILED')
        root = self.fixture(); self.record.write_text(self.doc.read_text())
        code, out, _ = self.check(root, '--sources-root', str(self.tmp))
        self.assertEqual(code, 1); self.assertEqual(out['provenance']['state'], 'FAILED')

    def test_available_sources_complete_missing_record_incomplete(self):
        root = self.fixture(); code, out, _ = self.check(root, '--sources-root', str(self.tmp))
        self.assertEqual(code, 0); self.assertEqual(out['provenance']['state'], 'COMPLETE')
        self.assertIs(out['provenance_complete'], True)
        self.record.unlink(); code, out, _ = self.check(root, '--sources-root', str(self.tmp))
        self.assertEqual(code, 0); self.assertEqual(out['provenance']['unavailable'], 1)

    def test_strict_usage_and_unresolved_evidence(self):
        root = self.fixture()
        self.assertEqual(run('check', '--root', str(root), '--provenance', 'strict')[0], 2)
        self.assertEqual(run('gen', '--root', str(root), '--provenance', 'strict', '--sources-root', str(self.tmp))[0], 2)
        cap = root / 'skills/alpha-research/capability.toml'
        cap.write_text(cap.read_text()+'\nevidence_ref="ev:lic:missing"\n')
        code, out, _ = self.check(root, '--provenance', 'strict', '--sources-root', str(self.tmp), '--evidence-map', str(self.evidence))
        self.assertEqual(code, 1); self.assertEqual(out['provenance']['state'], 'FAILED')

    def test_legacy_gap_differs_by_mode(self):
        root = self.fixture(attested=False)
        cap = root / 'skills/alpha-research/capability.toml'
        cap.write_text(cap.read_text().replace('"ORIGINAL"','"LEGACY-UNATTESTED"'))
        self.assertEqual(run('gen','--root',str(root))[0],0)
        code, out, _ = self.check(root)
        self.assertEqual(code,0); self.assertEqual(out['provenance']['not_cleared'],1)
        code, out, _ = self.check(root,'--provenance=strict','--sources-root',str(self.tmp),'--evidence-map',str(self.evidence))
        self.assertEqual(code,1); self.assertEqual(out['provenance']['state'],'FAILED')

    def test_fast_path_and_invalid_mode(self):
        from skillkit.cli import _fast_check
        self.assertEqual(_fast_check(['check','--provenance','public']).provenance,'public')
        self.assertEqual(_fast_check(['check','--provenance=strict']).provenance,'strict')
        self.assertEqual(run('check','--provenance','loose')[0],2)

    def test_summary_roundtrip_and_tampering(self):
        root = self.fixture(attested=False)
        def git(*args):
            return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
        git('init','-q');git('config','user.name','Fixture');git('config','user.email','fixture@example.org')
        git('add','.');git('commit','-qm','fixture')
        tree=git('rev-parse','HEAD^{tree}');summary=root/'release/provenance-summary.json'
        args=('provenance','summary','--root',str(root),'--sources-root',str(self.tmp),'--evidence-map',str(self.evidence),'--tree',tree,'--out',str(summary))
        self.assertEqual(run(*args)[0],0)
        git('add','.');git('commit','-qm','summary')
        def verify(t=tree):return run('provenance','verify',str(summary),'--root',str(root),'--tree',t)[0]
        self.assertEqual(verify(),0);self.assertEqual(verify('0'*40),1)
        original=summary.read_text();data=json.loads(original);data['date']='/'+'home/private'
        summary.write_text(json.dumps(data));self.assertEqual(verify(),1);summary.write_text(original)
        self.doc.write_text(self.doc.read_text()+'changed');self.assertEqual(verify(),1)
        self.doc.write_text(self.doc.read_text()[:-7]);(root/'extra.txt').write_text('extra');git('add','extra.txt')
        self.assertEqual(verify(),1)

    def test_privacy_no_baseline(self):
        root=self.fixture(attested=False);(root/'private.txt').write_text('/'+'home/private/data')
        (root/'policy/privacy-baseline.json').write_text(json.dumps({'counts':{'private.txt':1},'raises':[]}))
        self.assertEqual(run('lint','privacy','--root',str(root))[0],0)
        self.assertEqual(run('lint','privacy','--root',str(root),'--no-baseline')[0],1)

    def test_duplicate_card_registry_reports_failed_in_every_mode(self):
        root = self.fixture()
        cap = root / 'skills/beta-explicit/capability.toml'
        cap.write_text(cap.read_text().replace('"ORIGINAL"', '"LEGACY-UNATTESTED"'))
        registry = root / 'sources/idea-cards.toml'
        registry.write_text(registry.read_text() + '\n[[card]]\nids=["fixture-01"]\n')
        for mode in ('public', 'strict'):
            with self.subTest(mode=mode):
                args = () if mode == 'public' else (
                    '--sources-root', str(self.tmp), '--evidence-map', str(self.evidence))
                code, out, _ = self.check(root, '--provenance', mode, *args)
                self.assertEqual(code, 1)
                self.assertEqual(out['provenance']['state'], 'FAILED')
                self.assertGreater(out['provenance']['errors'], 0)
                self.assertTrue(any(f['rule'] == 'provenance-registry'
                                    for f in out['findings']))

    def test_schema_provenance_error_reports_failed(self):
        root = self.copy_fixture('bad-derived-no-sha')
        code, out, _ = self.check(root)
        self.assertEqual(code, 1)
        self.assertEqual(out['provenance']['state'], 'FAILED')
        self.assertGreater(out['provenance']['errors'], 0)

    def test_non_object_summary_rejected(self):
        root = self.fixture(attested=False)
        path = root / 'bad-summary.json'
        path.write_text('[]')
        self.assertEqual(run('provenance', 'verify', str(path), '--root', str(root), '--tree', '0'*40)[0], 1)
