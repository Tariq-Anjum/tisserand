"""Offline task-type data tooling. Nothing in the router imports this module."""
import itertools
import re
from pathlib import Path

from . import tomlio


class DataError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise DataError(message)


def read_toml(root, rel):
    path = Path(root) / rel
    require(not Path(rel).is_absolute() and Path(root).resolve() in path.resolve().parents,
            'data path escapes root')
    try:
        return tomlio.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, tomlio.TomlError) as exc:
        raise DataError('%s: %s' % (rel, exc)) from None


def normalize(text):
    return ' '.join(text.lower().replace('-', ' ').replace('_', ' ').split())


def matches(cue, text):
    # Filename patterns are finite extensions, never arbitrary regex/globs.
    if cue.startswith('*.'):
        return bool(re.search(r'(?<![\w.])[^\s/]+\.' + re.escape(cue[2:].lower()) + r'(?!\w)', text.lower()))
    return bool(re.search(r'(?<!\w)' + re.escape(normalize(cue)) + r'(?!\w)', normalize(text)))


def _strings(items):
    return isinstance(items, list) and all(isinstance(x, str) and x.strip() for x in items) and len(items) == len(set(items))


def validate_taxonomy(tt, cues):
    require(re.fullmatch(r'tt-\d+\.\d+\.\d+', tt.get('version', '')), 'invalid taxonomy version')
    types = tt.get('type', [])
    require(isinstance(types, list) and 1 <= len(types) <= 15, 'taxonomy must contain <=15 types including unclear')
    ids = [t.get('id') for t in types]
    require(all(isinstance(x, str) and re.fullmatch('[a-z]+', x) for x in ids)
            and len(set(ids)) == len(ids) and 'unclear' in ids, 'type ids must be unique and include unclear')
    for key in ('artifacts', 'conditions', 'stage_order'):
        require(_strings(tt.get(key)), '%s must be a finite unique vocabulary' % key)
    require('none' in tt['artifacts'] and 'any' in tt['stage_order'], 'missing none/any defaults')
    orders = []
    for t in types:
        orders.append(t.get('order'))
        require(type(t.get('order')) is int, 'type order must be integer')
        require(t.get('stage') in tt['stage_order'] and t.get('artifact_default') in tt['artifacts'], 'unknown stage/artifact')
        require(isinstance(t.get('definition'), str) and t['definition'], 'missing definition')
        require(isinstance(t.get('not_this'), list), 'missing NOT-this pairs')
        for pair in t['not_this']:
            require(pair.get('to') in ids and isinstance(pair.get('when'), str) and pair['when'], 'unknown NOT-this reference')
    require(len(set(orders)) == len(orders), 'duplicate type order')
    require(set(tt.get('unclear', {})) == {'U1', 'U2', 'U3'}, 'unclear rules must be U1-U3')
    require(set(tt.get('non_mutating', [])) <= set(ids), 'unknown non-mutating type')
    ties = set()
    for tie in tt.get('tie_break', []):
        pair = tie.get('pair', [])
        require(len(pair) == 2 and pair[0] != pair[1]
                and all(x in ids or x == '*' for x in pair), 'unknown tie-break reference')
        if 'choose' in tie:
            require(tie['choose'] in pair, 'unknown tie-break choice')
        for key in ('if_true', 'otherwise'):
            if key in tie:
                require(tie[key] in pair, 'unknown tie-break result')
        if 'condition' in tie:
            require(tie['condition'] in tt['conditions'], 'unknown tie-break condition')
        if 'precede' in tie:
            require(isinstance(tie['precede'], dict)
                    and set(tie['precede']) <= set(tt['conditions'])
                    and all(v in pair for v in tie['precede'].values()),
                    'unknown tie-break precede condition/result')
        if 'artifact' in tie:
            require(tie['artifact'] in tt['artifacts'], 'unknown tie-break artifact')
        ties.add(frozenset(pair))
    require(cues.get('tt') == tt['version'], 'mixed cue/taxonomy versions')
    groups = (('artifact', tt['artifacts']), ('steps', ids), ('conditions', tt['conditions']))
    artifact_keys = set(cues.get('artifact', {}))
    order = cues.get('artifact_order', [])
    require(_strings(order) and set(order) == artifact_keys, 'artifact precedence is not total')
    require(set(cues.get('conditions', {})) == set(tt['conditions']), 'condition cues are not total')
    for group, vocab in groups:
        table = cues.get(group, {})
        require(isinstance(table, dict) and set(table) <= set(vocab), 'unknown %s cue target' % group)
        flattened = []
        for target, phrases in table.items():
            require(_strings(phrases) and 0 < len(phrases) <= 128, 'cue table must be finite')
            for phrase in phrases:
                require(len(phrase) <= 160 and ('*' not in phrase or re.fullmatch(r'\*\.[a-z]+', phrase)), 'non-finite cue')
                require(group == 'artifact' or len(normalize(phrase).split()) >= 2, 'step/condition cues need multiple words')
                flattened.append((target, phrase))
        for (a, x), (b, y) in itertools.combinations(flattened, 2):
            if a == b or group == 'artifact':  # the complete A1 precedence resolves these
                continue
            if matches(x, y) or matches(y, x):
                declared = frozenset((a, b)) in ties or any(frozenset((k, '*')) in ties for k in (a, b))
                require(declared, 'overlapping %s cues without tie-break: %s/%s' % (group, a, b))
    return tt


def resolve_tie(pair, conditions, tt):
    """Resolve an explicitly supplied pair offline; this is not a type chooser."""
    require(len(pair) == 2 and len(set(pair)) == 2
            and set(pair) <= {t['id'] for t in tt['type']}, 'unknown resolution pair')
    for tie in tt.get('tie_break', []):
        declared = set(tie['pair'])
        if declared != set(pair) and not ('*' in declared and declared - {'*'} <= set(pair)):
            continue
        for condition, result in tie.get('precede', {}).items():
            if conditions.get(condition, False):
                return result
        if 'condition' in tie:
            return tie['if_true'] if conditions.get(tie['condition'], False) else tie['otherwise']
        if 'choose' in tie:
            return next(t for t in pair if t not in declared) if tie['choose'] == '*' else tie['choose']
    return None


def match_cues(text, tt, cues):
    artifact = next((a for a in cues['artifact_order'] if any(matches(c, text) for c in cues['artifact'][a])), None)
    steps = {s for s, words in cues['steps'].items() if any(matches(c, text) for c in words)}
    order = {t['id']: (tt['stage_order'].index(t['stage']), t['order']) for t in tt['type']}
    return {'artifact': artifact, 'steps': sorted(steps, key=order.get),
            'conditions': {k: any(matches(c, text) for c in cues['conditions'][k]) for k in tt['conditions']}}


def validate_rubric(rb, tt):
    require(rb.get('tt') == tt['version'], 'mixed rubric/taxonomy versions')
    require(re.fullmatch(r'rb-\d+\.\d+\.\d+', rb.get('version', '')), 'invalid rubric version')
    require(set(rb.get('weights', {})) == set('FBSC'), 'missing dimension weights')
    require(all(type(v) is int and v >= 0 for v in rb['weights'].values()), 'invalid weights')
    formula = rb.get('score', {})
    require(all(type(formula.get(k)) is int for k in ('multiplier', 'offset', 'divisor'))
            and formula['divisor'] > 0, 'invalid score formula')
    for key in ('primary', 'supporting'):
        require(type(rb.get(key, {}).get('F')) is int and 0 <= rb[key]['F'] <= 4
                and type(rb[key].get('score')) is int and 0 <= rb[key]['score'] <= 100, 'invalid eligibility')
    require(type(rb.get('benefit_max')) is int and 0 <= rb['benefit_max'] <= 4, 'invalid benefit maximum')


def validate_cell(c, tt, rb):
    validate_rubric(rb, tt)
    require(c.get('task_type') in {t['id'] for t in tt['type']}, 'unknown cell type')
    require(_strings(c.get('scope')) and set(c['scope']) <= set(tt['artifacts']), 'unknown cell scope')
    require(isinstance(c.get('when'), dict) and set(c['when']) <= set(tt['conditions'])
            and all(type(v) is bool for v in c['when'].values()), 'unknown cell condition')
    require(not c['when'] or any(c['when'].values()), 'when needs at least one positive condition')
    require(c.get('max_role', 'primary') in ('primary', 'supporting'), 'invalid max_role')
    require(isinstance(c.get('evidence'), str) and c['evidence'] and _strings(c.get('flags')), 'missing evidence/flags')
    require(re.fullmatch('[a-f0-9]{64}', c.get('digest', '')), 'invalid text digest')
    known = [c.get(k) for k in 'FBSC']
    require(all(v == 'UNSCORED' or type(v) is int and 0 <= v <= 4 for v in known), 'invalid dimension')
    if 'UNSCORED' in known:
        require(c.get('raw') == c.get('score') == 'UNSCORED', 'unknown dimension cannot have a score')
    else:
        require(c['B'] <= rb['benefit_max'], 'benefit exceeds evidence ceiling')
        raw = sum(rb['weights'][k] * c[k] for k in 'FBSC')
        f = rb['score']
        score = (f['multiplier'] * raw + f['offset']) // f['divisor']
        require(type(c.get('raw')) is int and c['raw'] == raw and type(c.get('score')) is int and c['score'] == score,
                'printed raw/score disagrees with dimensions')


def eligibility(c, rb):
    if any(c[k] == 'UNSCORED' for k in 'FBSC'):
        return None
    for key in ('primary', 'supporting'):
        if key == 'primary' and c.get('max_role') == 'supporting':
            continue
        if c['F'] >= rb[key]['F'] and c['score'] >= rb[key]['score']:
            return key
    return None


def rank(c):
    return (-c['raw'], c['id'].encode('utf-8'))


def _applies(c, artifact, conditions):
    return (not c['scope'] or artifact in c['scope']) and all(conditions[k] == v for k, v in c['when'].items())


def decision_rows(tt, rb, cells, caps):
    rows = []
    for t in sorted(tt['type'], key=lambda t: t['order']):
        pool = [c for c in cells if c['task_type'] == t['id'] and eligibility(c, rb)]
        keys = sorted({k for c in pool for k in c['when']})
        for artifact, bits in itertools.product(tt['artifacts'], itertools.product((False, True), repeat=len(keys))):
            when = dict(zip(keys, bits))
            applicable = sorted((c for c in pool if _applies(c, artifact, when)), key=rank)
            inferred = [c for c in applicable if caps[c['id']]['activation'] == 'contextual']
            primaries = [c for c in inferred if eligibility(c, rb) == 'primary']
            primary = primaries[0]['id'] if len(primaries) == 1 else None
            named = any(eligibility(c, rb) == 'primary' and caps[c['id']]['activation'] in ('explicit', 'manual') for c in applicable)
            status = ('collision' if len(primaries) > 1 else 'ok' if primary else 'named-only' if named else 'none')
            if t['id'] == 'unclear':
                primary, inferred, status = None, [], 'needs_information'
            rows.append({'task_type': t['id'], 'artifact': artifact, 'when': when, 'primary': primary,
                         'supporting': [c['id'] for c in inferred if c['id'] != primary], 'status': status})
    return rows


def collisions(tt, rb, cells, caps):
    out = []
    for row in decision_rows(tt, rb, cells, caps):
        if row['status'] == 'collision':
            candidates = sorted(c['id'] for c in cells if c['task_type'] == row['task_type']
                and _applies(c, row['artifact'], row['when']) and eligibility(c, rb) == 'primary'
                and caps[c['id']]['activation'] == 'contextual')
            for pair in itertools.combinations(candidates, 2):
                out.append({'pair': list(pair), 'cell': {k: row[k] for k in ('task_type', 'artifact', 'when')},
                            'kind': 'primary', 'value': len(candidates)})
    for a, b in itertools.combinations(cells, 2):
        if a['id'] == b['id'] or a['task_type'] != b['task_type'] or any(c['raw'] == 'UNSCORED' or c['F'] < 2 for c in (a, b)):
            continue
        if a['scope'] and b['scope'] and not set(a['scope']) & set(b['scope']):
            continue
        if any(k in b['when'] and b['when'][k] != v for k, v in a['when'].items()):
            continue
        def terms(c):
            r = caps[c['id']].get('routing', {})
            return {normalize(v) for k in ('phrases', 'intents', 'provides') for v in r.get(k, [])}
        for term in sorted(terms(a) & terms(b)):
            out.append({'pair': sorted((a['id'], b['id'])), 'cell': {'task_type': a['task_type']},
                        'kind': 'trigger' if len(term.split()) > 1 else 'provides', 'value': term})
    return sorted(out, key=lambda x: (x['pair'], str(x['cell']), x['kind'], str(x['value'])))
