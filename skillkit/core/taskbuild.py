"""Task data -> offline generated table, ratings index and validation findings."""
from . import jsonout, provenance, taskdata
from .model import finding

TAXONOMY = 'taxonomy/tt-1.toml'
RUBRIC = 'ratings/rb-1/rubric.toml'
PROVENANCE = 'sources/idea-cards.toml'
ROUTER_DIR = 'skills/skill-router/'
RATING_LINK = '\n[Ratings](ratings/INDEX.md)\n'


def load(repo, sources_root=None, provenance_mode='public', evidence_map=None):
    """Optional for old/synthetic repositories. Refuse partial/stale data."""
    root = repo.root
    findings, inputs = [], {}
    data = None

    def read(rel):
        result = taskdata.read_toml(root, rel)
        inputs[rel] = (root / rel).read_bytes()
        return result

    try:
        if (root / TAXONOMY).exists():
            tt = read(TAXONOMY)
            cues = read('taxonomy/' + tt['cue_file'])
            taskdata.validate_taxonomy(tt, cues)
            rb = read(RUBRIC)
            taskdata.validate_rubric(rb, tt)
            caps = {c.id: c for c in repo.caps if c.ok}
            entries = {i: dict(c.raw, routing=c.raw.get('routing', {})) for i, c in caps.items()}
            cells = []
            for path in sorted((root / 'ratings/rb-1').glob('*.toml')):
                if path.name == 'rubric.toml':
                    continue
                doc = read(path.relative_to(root).as_posix())
                ident = doc.get('id')
                taskdata.require(ident in caps and path.stem == ident, 'unknown rating capability')
                cap = caps[ident]
                taskdata.require(doc.get('tt') == tt['version'] and doc.get('rb') == rb['version'], 'mixed rating versions')
                taskdata.require(doc.get('version') == cap.raw.get('version'), 'stale capability version')
                seen = set()
                for record in doc.get('cell', []):
                    c = dict(record, id=ident)
                    taskdata.validate_cell(c, tt, rb)
                    key = (c['task_type'], tuple(c['scope']), tuple(sorted(c['when'].items())))
                    taskdata.require(key not in seen, 'duplicate rating cell')
                    seen.add(key)
                    taskdata.require(c['digest'] == cap.sha_doc, '%s: stale text digest' % ident)
                    if 'metadata_digest' in doc:
                        taskdata.require(doc['metadata_digest'] == cap.sha_toml, '%s: stale metadata digest' % ident)
                    if 'task_types' in cap.raw:
                        taskdata.require(c['task_type'] in cap.raw['task_types'], 'rating not in capability task_types')
                    cells.append(c)
                if 'task_types' in cap.raw:
                    taskdata.require(set(cap.raw['task_types']) == {c['task_type'] for c in cells if c['id'] == ident},
                                     'task_types not total over ratings')
            for c in caps.values():
                if 'task_types' in c.raw:
                    taskdata.require(set(c.raw['task_types']) <= {t['id'] for t in tt['type']}, 'unknown capability task type')
                    taskdata.require(set(c.raw['task_types']) == {x['task_type'] for x in cells if x['id'] == c.id},
                                     'missing ratings for capability task_types')
            collisions = taskdata.collisions(tt, rb, cells, entries)
            for c in collisions:
                if c['kind'] == 'primary':
                    findings.append(finding('', 'task-primary-collision', 'error', 'decision-table.json', str(c)))
            data = {'tt_bytes': inputs[TAXONOMY], 'tt': tt, 'cues': cues, 'rb': rb, 'cells': cells, 'caps': entries, 'collisions': collisions}
        elif (root / 'ratings/rb-1').exists():
            raise taskdata.DataError('ratings require a taxonomy')
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        findings.append(finding('', 'task-data', 'error', TAXONOMY, str(exc)))
    try:
        if data is not None:
            taskdata.require((root / PROVENANCE).is_file(), 'task data requires provenance registry')
        if (root / PROVENANCE).exists():
            p = read(PROVENANCE)
            cards = {}
            for c in p.get('card', []):
                for ident in c['ids']:
                    taskdata.require(ident not in cards, 'duplicate idea card')
                    cards[ident] = c
            texts = {c.doc_path: repo.files[c.doc_path].decode('utf-8') for c in repo.caps if c.ok and c.type == 'skill'}
            checks = provenance.check_texts(texts, p.get('baseline', {}), p.get('text', []), cards, sources_root)
            unavailable = set()
            for c in checks:
                if c['kind'] == 'source-text-unavailable':
                    if c['path'] not in unavailable:
                        findings.append(finding('', 'provenance-incomplete',
                            'error' if provenance_mode == 'strict' else 'info', c['path'], 'source text unavailable'))
                        unavailable.add(c['path'])
                else:
                    findings.append(finding('', 'provenance', 'error', c['path'], c['kind']))
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        findings.append(finding('', 'provenance-registry', 'error', PROVENANCE, str(exc)))
    repo.files.update(inputs)
    try:
        findings += provenance.capability_checks(repo, sources_root, provenance_mode)
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        findings.append(finding('', 'provenance', 'error', PROVENANCE, str(exc)))
    findings += provenance.mode_checks(repo, provenance_mode, sources_root, evidence_map)
    return data, findings, inputs


def outputs(data):
    if data is None:
        return {}
    tt, rb, cells = data['tt'], data['rb'], data['cells']
    rows = taskdata.decision_rows(tt, rb, cells, data['caps'])
    table = {'tt': tt['version'], 'revision': tt['revision'], 'rb': rb['version'], 'rows': rows}
    lines = ['<!-- Generated by skillkit gen; do not edit. -->', '',
             '# Capability ratings', '', '%s rev %s · %s' % (tt['version'], tt['revision'], rb['version']), '',
             '| Capability | Task type | Scope | When | F | B | S | C | Raw | Score | Precision | Flags |',
             '|---|---|---|---|---|---|---|---|---|---|---|---|']
    for c in sorted(cells, key=lambda c: (c['id'], c['task_type'])):
        when = ', '.join(('' if v else '¬') + k for k, v in sorted(c['when'].items())) or '—'
        vals = [c['id'], c['task_type'], ', '.join(c['scope']) or 'all', when]
        vals += [str(c[k]) for k in ('F', 'B', 'S', 'C', 'raw', 'score')]
        vals += ['P —', ', '.join(c['flags']) or '—']
        lines.append('| ' + ' | '.join(vals) + ' |')
    encoded = jsonout.encode(table)
    # The router reads these at step 4; ship copies inside its own skill folder so the
    # installed runtime (skills/installed/skill-router/) carries them without the source tree.
    return {'decision-table.json': encoded,
            ROUTER_DIR + 'decision-table.json': encoded,
            ROUTER_DIR + TAXONOMY: data['tt_bytes'],
            'ratings/INDEX.md': ('\n'.join(lines) + '\n').encode('utf-8')}
