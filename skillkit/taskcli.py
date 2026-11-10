"""Offline inspection of task data, provenance and caller-supplied metrics."""
import json
import sys
from pathlib import Path

from .core import jsonout, model, rules, taskbuild, taskdata, taskmetrics


def add_parser(sub):
    p = sub.add_parser('task-data', help='validate and inspect offline task-type data')
    p.add_argument('action', choices=('validate', 'collisions', 'provenance', 'metrics'))
    p.add_argument('--root')
    p.add_argument('--sources-root', help='local root of registered provenance records; no network')
    p.add_argument('--input', help='JSON object with synthetic cases, predictions and identity')


def run(root, args):
    repo = model.load(root)
    data, findings, _ = taskbuild.load(repo, args.sources_root)
    findings = repo.findings + rules.run(repo) + findings
    if args.action == 'metrics':
        if any(f['severity'] == 'error' for f in findings):
            sys.stdout.write(jsonout.dumps({'findings': findings}))
            return 1
        if data is None or not args.input:
            sys.stderr.write('task-data metrics needs valid data and --input\n')
            return 2
        try:
            path = Path(args.input).resolve()
            for banned in ('bench/skillbench', 'evals/adjudication'):
                base = (Path(root) / banned).resolve()
                taskdata.require(base != path and base not in path.parents, 'protected input path')
            payload = json.loads(path.read_text(encoding='utf-8'))
            cases, predictions = payload['cases'], payload['predictions']
            ids = {t['id'] for t in data['tt']['type']}
            for c, got in zip(cases, predictions):
                taskdata.require(c['expect'].get('task_type') in ids and got.get('task_type') in ids,
                                 'unknown/missing expected or predicted task_type')
                taskdata.require(set(c['expect'].get('steps', [])) <= ids, 'unknown expected step')
                if 'cue_steps' not in got:
                    got['cue_steps'] = taskdata.match_cues(c.get('task', ''), data['tt'], data['cues'])['steps']
            report = taskmetrics.summarize(cases, predictions, payload.get('identity', {}))
            for k, v in (('tt', data['tt']['version']), ('rb', data['rb']['version'])):
                taskdata.require(report['identity'].get(k, v) == v, 'mixed metric versions')
                report['identity'][k] = v
            for key in ('split', 'seal', 'router'):
                report['identity'].setdefault(key, None)
            report['identity']['capabilities'] = {c.id: {'version': c.raw.get('version'), 'digest': c.sha_doc}
                                                 for c in repo.caps if c.ok}
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            sys.stderr.write('task-data metrics: %s\n' % exc)
            return 2
        sys.stdout.write(jsonout.dumps(report))
        return 1 if report['unclear_on_clear']['pass'] is False else 0
    report = {'findings': findings}
    if args.action == 'collisions':
        report['collisions'] = data['collisions'] if data else []
    sys.stdout.write(jsonout.dumps(report))
    return int(any(f['severity'] == 'error' for f in findings))
