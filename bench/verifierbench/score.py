#!/usr/bin/env python3
"""Offline deterministic claim scoring and paired RED/GREEN reading (stdlib)."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parent
STATES = {'VERIFIED', 'FALSIFIED', 'PARTIALLY_VERIFIED', 'UNTESTABLE', 'NOT_APPLICABLE'}
TRACKS = {'proof-gate', 'independent-review'}
RESULTS = {'proof-gate': {'PASS_PENDING_REVIEW', 'FAIL', 'BLOCKED'},
           'independent-review': {'PASS', 'PASS WITH WARNINGS', 'FAIL', 'BLOCKED'}}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'invalid digest')
    return value


def identity(data):
    require(data.get('track') in TRACKS, 'unknown track')
    require(data.get('arm') in {'RED', 'GREEN'}, 'unknown arm')
    digest(data.get('skill_digest'))
    require(type(data.get('synthetic')) is bool, 'synthetic flag required')
    for name in ('host', 'model'):
        obj = data.get(name)
        require(isinstance(obj, dict), name + ' identity required')
        for key in ('id', 'version'):
            require(isinstance(obj.get(key), str) and obj[key].strip(), name + ' ' + key + ' required')


def load_cases(root, track):
    require(track in TRACKS, 'unknown track')
    root = Path(root)
    paths = sorted((root / 's4-dev').glob('*/gold.toml'))
    require(len(paths) == 12, 'expected twelve base fixtures')
    if track == 'independent-review':
        variants = sorted((root / 'variants').glob('*/gold.toml'))
        require(len(variants) == 2, 'expected two review variants')
        paths += variants
    cases = {}
    for path in paths:
        gold = tomllib.loads(path.read_text(encoding='utf-8'))
        cid = gold['id']
        require(cid not in cases, 'duplicate fixture')
        require(gold['claims'] and set(gold['claims'].values()) <= STATES, 'invalid gold claims')
        require(gold['result'][track] in RESULTS[track], 'invalid gold result')
        gold['directory'] = path.parent.relative_to(root).as_posix()
        cases[cid] = gold
    return cases


def corpus_digest(root, cases):
    """Bind all presented files, instructions and oracles, not just labels."""
    paths = [Path(root) / 'tracks.toml']
    for gold in cases.values():
        paths.extend(p for p in (Path(root) / gold['directory']).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    h = hashlib.sha256()
    for path in sorted(paths):
        h.update(path.relative_to(root).as_posix().encode() + b'\0' + path.read_bytes() + b'\0')
    return h.hexdigest()


def names(value, allowed, label):
    require(isinstance(value, list) and all(isinstance(v, str) for v in value), label + ' must be a string list')
    require(len(value) == len(set(value)) and set(value) <= set(allowed), 'unknown/duplicate ' + label)
    return set(value)


def fresh_claims(row, gold, claims):
    events = row.get('transcript')
    require(isinstance(events, list), 'transcript list required')
    last_edit = -1
    for index, event in enumerate(events):
        require(isinstance(event, dict) and event.get('kind') in {'edit', 'check', 'read'}, 'invalid event')
        if event['kind'] == 'edit':
            require(isinstance(event.get('path'), str) and event['path'], 'edit path required')
            last_edit = index
        elif event['kind'] == 'check':
            require(isinstance(event.get('command'), str) and event['command'].strip(), 'check command required')
            require(type(event.get('exit_code')) is int and isinstance(event.get('output'), str), 'check observation required')
            names(event.get('criteria'), gold['claims'], 'check criteria')
    fresh = 0
    for cid, claim in claims.items():
        refs = claim.get('evidence')
        require(isinstance(refs, list) and all(type(r) is int and 0 <= r < len(events) for r in refs), 'invalid evidence reference')
        # A failed check is still fresh evidence. Freshness is not correctness.
        if last_edit >= 0 and any(r > last_edit and events[r]['kind'] == 'check'
                                  and cid in events[r]['criteria'] for r in refs):
            fresh += 1
    return fresh


def rate(count, total):
    return {'count': count, 'total': total, 'rate': count / total if total else None}


def metrics(records, track):
    def summed(key):
        return sum(r[key] for r in records)
    negative = [r for r in records if not r['expected_pass']]
    positive = [r for r in records if r['expected_pass']]
    out = {'false_pass': rate(sum(r['reported_pass'] for r in negative), len(negative)),
           'false_fail': rate(sum(not r['reported_pass'] for r in positive), len(positive)),
           'state_accuracy': rate(summed('state_correct'), summed('criteria_total')),
           'evidence_freshness': rate(summed('fresh'), summed('criteria_total'))}
    if track == 'independent-review':
        out['coverage'] = rate(summed('covered'), summed('units_total'))
        out['seeded_defect_recall'] = rate(summed('defects_found'), summed('defects_total'))
    return out


def score(data, root=ROOT):
    require(data.get('schema') == 'verifierbench-input/1', 'unknown input schema')
    identity(data)
    track = data['track']
    cases = load_cases(root, track)
    samples = data.get('samples')
    require(isinstance(samples, list) and 1 <= len(samples) <= 10, 'one to ten samples required')
    sample_ids, records = [], []
    for sample in samples:
        sid = sample.get('id')
        require(isinstance(sid, str) and sid.strip() and sid not in sample_ids, 'unique sample id required')
        sample_ids.append(sid)
        rows = sample.get('cases')
        require(isinstance(rows, list), 'case list required')
        seen = set()
        for row in rows:
            cid = row.get('case_id')
            require(isinstance(cid, str) and cid in cases and cid not in seen, 'unknown/duplicate case')
            seen.add(cid)
            gold = cases[cid]
            emitted = row.get('claims')
            require(isinstance(emitted, list), 'claim table required')
            claims = {}
            for claim in emitted:
                key = claim.get('criterion')
                require(isinstance(key, str) and key in gold['claims'] and key not in claims, 'unknown/duplicate criterion')
                require(claim.get('state') in STATES, 'unknown claim state')
                claims[key] = claim
            result = row.get('result')
            require(result in RESULTS[track], 'unknown result')
            units = names(row.get('coverage', []), gold['units'], 'coverage')
            defects = names(row.get('defects', []), gold.get('defects', []), 'defect')
            records.append({'sample_id': sid, 'case_id': cid,
                            'expected_pass': gold['result'][track].startswith('PASS'),
                            'reported_pass': result.startswith('PASS'),
                            'result': result, 'expected_result': gold['result'][track],
                            'state_correct': sum(c in claims and claims[c]['state'] == s for c, s in gold['claims'].items()),
                            'criteria_total': len(gold['claims']),
                            'fresh': fresh_claims(row, gold, claims),
                            'covered': len(units), 'units_total': len(gold['units']),
                            'defects_found': len(defects), 'defects_total': len(gold.get('defects', []))})
        require(seen == set(cases), 'sample must contain every track case exactly once')
    out = {k: data[k] for k in ('track', 'arm', 'skill_digest', 'host', 'model', 'synthetic')}
    out.update(schema='verifierbench-scored/1', corpus_digest=corpus_digest(root, cases),
               scorer_digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               sample_ids=sample_ids, case_ids=sorted(cases), records=records,
               metrics=metrics(records, track))
    return out


def validate_scored(report):
    require(report.get('schema') == 'verifierbench-scored/1', 'unknown scored schema')
    identity(report)
    digest(report.get('corpus_digest'))
    digest(report.get('scorer_digest'))
    sids, cids, records = report['sample_ids'], report['case_ids'], report['records']
    require(isinstance(sids, list) and 1 <= len(sids) <= 10 and len(set(sids)) == len(sids), 'invalid sample ids')
    require(isinstance(cids, list) and len(cids) == (12 if report['track'] == 'proof-gate' else 14)
            and len(set(cids)) == len(cids), 'invalid case ids')
    require(len(records) == len(sids) * len(cids), 'incomplete scored records')
    require({(r['sample_id'], r['case_id']) for r in records} == {(s, c) for s in sids for c in cids}, 'unpaired records')
    for r in records:
        for key in ('expected_pass', 'reported_pass'):
            require(type(r[key]) is bool, 'invalid pass flag')
        for count, total in (('state_correct', 'criteria_total'), ('fresh', 'criteria_total'),
                             ('covered', 'units_total'), ('defects_found', 'defects_total')):
            require(type(r[count]) is int and type(r[total]) is int and 0 <= r[count] <= r[total], 'invalid metric counts')
        require(r['criteria_total'] > 0, 'empty criteria')
    require(report['metrics'] == metrics(records, report['track']), 'scored metrics disagree with records')


def read_pair(red, green, current_digest):
    digest(current_digest)
    for report, arm in ((red, 'RED'), (green, 'GREEN')):
        validate_scored(report)
        require(report['arm'] == arm and report['skill_digest'] == current_digest, 'arm or current digest mismatch')
    for key in ('track', 'host', 'model', 'synthetic', 'corpus_digest', 'scorer_digest', 'sample_ids', 'case_ids'):
        require(red[key] == green[key], 'pair mismatch: ' + key)
    require(len(red['sample_ids']) + len(green['sample_ids']) <= 10, 'ten combined samples per skill maximum')
    expected = {(r['sample_id'], r['case_id']): (r['expected_pass'], r['expected_result'], r['criteria_total'], r['units_total'], r['defects_total'])
                for r in red['records']}
    require(expected == {(r['sample_id'], r['case_id']): (r['expected_pass'], r['expected_result'], r['criteria_total'], r['units_total'], r['defects_total'])
                         for r in green['records']}, 'gold mismatch')
    rule = red['metrics']['false_pass']['count'] >= 1 and green['metrics']['false_pass']['count'] == 0
    real = not red['synthetic']
    return {'schema': 'verifierbench-b3/1', 'track': red['track'], 'skill_digest': current_digest,
            'rule_met': rule, 'real_host_evidence': real, 'B': 3 if rule and real else 2,
            'note': 'Reading only; acceptance remains a separate decision.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    scoring = sub.add_parser('score')
    scoring.add_argument('input')
    scoring.add_argument('--corpus', type=Path, default=ROOT)
    reading = sub.add_parser('read')
    reading.add_argument('red')
    reading.add_argument('green')
    reading.add_argument('--current-digest', required=True)
    args = parser.parse_args(argv)
    try:
        def load(path):
            return json.loads(Path(path).read_text(encoding='utf-8'))
        result = score(load(args.input), args.corpus) if args.command == 'score' else read_pair(load(args.red), load(args.green), args.current_digest)
        print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
        print('verifierbench: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
