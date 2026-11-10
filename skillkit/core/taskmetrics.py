"""Metrics over caller-supplied cases/predictions; never loads a corpus."""
import math


def ratio(correct, n):
    if not n:
        return {'correct': correct, 'n': n, 'value': None, 'ci': None}
    p, z = correct / n, 1.959963984540054
    scale = 1 + z * z / n
    center = (p + z * z / (2 * n)) / scale
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / scale
    return {'correct': correct, 'n': n, 'value': round(p, 6),
            'ci': [round(max(0, center - half), 6), round(min(1, center + half), 6)]}


def summarize(cases, predictions, identity):
    if not isinstance(cases, list) or not isinstance(predictions, list) or not isinstance(identity, dict):
        raise ValueError('cases/predictions must be lists and identity must be an object')
    if len(cases) != len(predictions):
        raise ValueError('one prediction required for every case')
    cells, recall = {}, {}
    clear = abstained = 0
    for case, got in zip(cases, predictions):
        exp = case['expect']
        task_type = exp.get('task_type')
        if task_type is None:
            continue
        if not isinstance(task_type, str) or not task_type or not isinstance(got.get('task_type'), str) or not got['task_type']:
            raise ValueError('labelled cases require expected and predicted task_type')
        if 'primary' not in got or got['primary'] is not None and not isinstance(got['primary'], str):
            raise ValueError('labelled predictions require primary (id or null)')
        if not isinstance(got.get('cue_steps', []), list):
            raise ValueError('cue_steps must be a list')
        primary = got.get('primary')
        if primary is not None:
            key = (primary, task_type)
            counts = cells.setdefault(key, [0, 0, 0])
            counts[0] += primary == exp.get('primary')
            counts[1] += 1
            counts[2] += primary in exp.get('must_not', [])
        if task_type != 'unclear':
            clear += 1
            abstained += got.get('task_type') == 'unclear'
        for step in set(exp.get('steps', [])) - {task_type, 'unclear'}:
            counts = recall.setdefault(step, [0, 0])
            counts[0] += step in got.get('cue_steps', [])
            counts[1] += 1
    per_cell = []
    for (ident, task_type), (correct, n, banned) in sorted(cells.items()):
        r = ratio(correct, n)
        r['precision'] = r.pop('value')
        per_cell.append(dict(r, id=ident, task_type=task_type, must_not=banned, low_n=n < 10))
    unclear = ratio(abstained, clear)
    unclear['pass'] = abstained / clear <= .10 if clear else None
    recall_rows = {k: ratio(*counts) for k, counts in sorted(recall.items())}
    return {'identity': identity, 'per_cell': per_cell, 'cue_recall':
            dict(ratio(sum(c[0] for c in recall.values()), sum(c[1] for c in recall.values())), by_step=recall_rows),
            'unclear_on_clear': unclear}
