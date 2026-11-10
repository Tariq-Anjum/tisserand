"""Synthetic verifier output contracts; no external runs or protected corpus reads."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from bench.verifierbench import score as vb

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'bench/verifierbench'


def payload(track='proof-gate', arm='GREEN'):
    """Invented outputs; fixture gold supplies labels, not measured results."""
    cases = vb.load_cases(CORPUS, track)
    rows = []
    for cid, gold in cases.items():
        rows.append({'case_id': cid, 'result': gold['result'][track],
                     'claims': [{'criterion': k, 'state': v, 'evidence': [1]}
                                for k, v in gold['claims'].items()],
                     'transcript': [{'kind': 'edit', 'path': 'candidate.py'},
                                    {'kind': 'check', 'command': 'python check.py',
                                     'exit_code': 0, 'output': 'synthetic observation',
                                     'criteria': list(gold['claims'])}],
                     'coverage': gold['units'], 'defects': gold.get('defects', [])})
    return {'schema': 'verifierbench-input/1', 'track': track, 'arm': arm,
            'skill_digest': 'a' * 64, 'synthetic': True,
            'host': {'id': 'test-runtime', 'version': '1'},
            'model': {'id': 'test-engine', 'version': '1'},
            'samples': [{'id': 'pair-1', 'cases': rows}]}


class ScorerTests(unittest.TestCase):
    def test_perfect_claims_and_outcomes(self):
        report = vb.score(payload(), CORPUS)
        self.assertEqual(report['metrics']['false_pass'], {'count': 0, 'total': 8, 'rate': 0.0})
        self.assertEqual(report['metrics']['false_fail'], {'count': 0, 'total': 4, 'rate': 0.0})
        self.assertEqual(report['metrics']['state_accuracy']['rate'], 1.0)
        self.assertEqual(report['metrics']['evidence_freshness']['rate'], 1.0)

    def test_false_pass_false_fail_and_missing_state(self):
        data = payload()
        rows = data['samples'][0]['cases']
        by_id = {r['case_id']: r for r in rows}
        by_id['pass-01']['result'] = 'FAIL'
        by_id['fail-01']['result'] = 'PASS_PENDING_REVIEW'
        by_id['pass-01']['claims'].pop()
        m = vb.score(data, CORPUS)['metrics']
        self.assertEqual(m['false_pass']['rate'], 0.125)
        self.assertEqual(m['false_fail']['rate'], 0.25)
        self.assertEqual(m['state_accuracy']['count'], 23)
        self.assertEqual(m['state_accuracy']['total'], 24)

    def test_stale_unreferenced_and_missing_checks_do_not_count(self):
        for mode in ('stale', 'unreferenced', 'missing', 'read'):
            data = payload()
            row = data['samples'][0]['cases'][0]
            if mode == 'stale':
                row['transcript'].append({'kind': 'edit', 'path': 'candidate.py'})
            elif mode == 'unreferenced':
                for claim in row['claims']:
                    claim['evidence'] = []
            elif mode == 'missing':
                row['transcript'] = []
                for claim in row['claims']:
                    claim['evidence'] = []
            else:
                row['transcript'][1] = {'kind': 'read', 'path': 'candidate.py'}
            self.assertEqual(vb.score(data, CORPUS)['metrics']['evidence_freshness']['count'], 22, mode)

    def test_review_coverage_and_seeded_defect_recall(self):
        data = payload('independent-review')
        rows = data['samples'][0]['cases']
        rows[-1]['defects'] = []
        rows[-1]['coverage'] = []
        m = vb.score(data, CORPUS)['metrics']
        self.assertEqual(m['seeded_defect_recall'], {'count': 1, 'total': 2, 'rate': 0.5})
        self.assertEqual(m['coverage']['count'], 26)
        self.assertEqual(m['coverage']['total'], 28)

    def test_bad_records_rejected(self):
        for mode in ('duplicate', 'unknown', 'state', 'identity', 'missing-case', 'evidence', 'empty'):
            data = payload()
            row = data['samples'][0]['cases'][0]
            if mode == 'duplicate':
                row['claims'].append(copy.deepcopy(row['claims'][0]))
            elif mode == 'unknown':
                row['claims'][0]['criterion'] = 'unknown'
            elif mode == 'state':
                row['claims'][0]['state'] = 'probably'
            elif mode == 'identity':
                data['model']['version'] = ''
            elif mode == 'missing-case':
                data['samples'][0]['cases'].pop()
            elif mode == 'evidence':
                row['claims'][0]['evidence'] = [99]
            else:
                data['samples'] = []
            with self.assertRaises(ValueError, msg=mode):
                vb.score(data, CORPUS)

    def test_cli_scores_json_and_rejects_invalid_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'input.json'
            source.write_text(json.dumps(payload()))
            cmd = [sys.executable, str(CORPUS / 'score.py'), 'score', str(source)]
            run = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)['metrics']['false_pass']['count'], 0)
            source.write_text('{}')
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 2)


class ReaderTests(unittest.TestCase):
    def pair(self):
        red, green = payload(arm='RED'), payload()
        next(r for r in red['samples'][0]['cases'] if r['case_id'] == 'fail-01')['result'] = 'PASS_PENDING_REVIEW'
        # These are still invented records. The reader must label them synthetic.
        return vb.score(red, CORPUS), vb.score(green, CORPUS)

    def test_red_green_rule_and_synthetic_boundary(self):
        red, green = self.pair()
        got = vb.read_pair(red, green, 'a' * 64)
        self.assertTrue(got['rule_met'])
        self.assertEqual(got['B'], 2)
        self.assertFalse(got['real_host_evidence'])
        red['synthetic'] = green['synthetic'] = False
        self.assertEqual(vb.read_pair(red, green, 'a' * 64)['B'], 3)

    def test_no_red_failure_or_green_failure_keeps_b_two(self):
        green = vb.score(payload(), CORPUS)
        red = copy.deepcopy(green)
        red['arm'] = 'RED'
        self.assertFalse(vb.read_pair(red, green, 'a' * 64)['rule_met'])
        red, green = self.pair()
        green = copy.deepcopy(red)
        green['arm'] = 'GREEN'
        self.assertFalse(vb.read_pair(red, green, 'a' * 64)['rule_met'])

    def test_unpaired_or_stale_or_tampered_reports_rejected(self):
        for mode in ('digest', 'host', 'model', 'corpus', 'track', 'samples', 'count', 'aggregate'):
            red, green = self.pair()
            if mode == 'digest':
                green['skill_digest'] = 'b' * 64
            elif mode in ('host', 'model'):
                green[mode]['version'] = '2'
            elif mode == 'corpus':
                green['corpus_digest'] = 'b' * 64
            elif mode == 'track':
                green['track'] = 'independent-review'
            elif mode == 'samples':
                green['sample_ids'] = ['other']
            elif mode == 'count':
                red['sample_ids'] = green['sample_ids'] = [str(i) for i in range(6)]
            else:
                green['metrics']['false_pass']['count'] = 9
            with self.assertRaises(ValueError, msg=mode):
                vb.read_pair(red, green, 'a' * 64)



if __name__ == '__main__':
    unittest.main()
