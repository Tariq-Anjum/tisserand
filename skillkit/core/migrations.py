"""Permanent capability history, independent of the bounded routing index.

Format: schema = 1; [aliases.<old>] and [retired_by.<old>] each hold target,
reason and a quoted YYYY-MM-DD date. No expiry field is accepted. Chains must
terminate at a live id. Missing files mean no migrations for older repositories.
A historical key may also be a live capability alias only when `live_aliases`
is a mapping {alias: owner id} and the owner equals the key's resolved target;
a plain set or list of aliases keeps every coexistence an error (fail closed).
"""
import re
from pathlib import Path

from . import schemacheck, tomlio

PATH = 'registry/migrations.toml'
_ID = re.compile(r'^[a-z0-9-]{1,64}$')


def validate(data, live_ids, live_aliases=()):
    errors = []
    if not isinstance(data, dict) or type(data.get('schema')) is not int or data.get('schema') != 1:
        return ['migrations require schema = 1']
    if set(data) - {'schema', 'aliases', 'retired_by'}:
        errors.append('unknown migrations field')
    records = {}
    owners = dict(live_aliases) if isinstance(live_aliases, dict) else dict.fromkeys(live_aliases)
    for group in ('aliases', 'retired_by'):
        table = data.get(group, {})
        if not isinstance(table, dict):
            errors.append('%s must be a map' % group)
            continue
        for old, record in sorted(table.items()):
            if not isinstance(old, str) or not _ID.fullmatch(old):
                errors.append('invalid historical id')
            if old in live_ids or old in records:
                errors.append('historical id collides: %s' % old)
            if not isinstance(record, dict) or set(record) != {'target', 'reason', 'date'}:
                errors.append('%s needs target, reason and date only' % old)
                continue
            if not isinstance(record['target'], str) or not _ID.fullmatch(record['target']):
                errors.append('%s has invalid target' % old)
                continue
            if not isinstance(record['reason'], str) or not record['reason'].strip():
                errors.append('%s needs a reason' % old)
            if schemacheck.validate(record['date'], {'type': 'string', 'x-format': 'date'}):
                errors.append('%s needs a quoted YYYY-MM-DD date' % old)
            records[old] = record
    for old in sorted(records):
        seen, target = set(), old
        while target in records and target not in seen:
            seen.add(target)
            target = records[target]['target']
        if target in seen:
            errors.append('%s has a migration cycle' % old)
        elif target not in live_ids:
            errors.append('%s has no live target' % old)
        elif old in owners and owners[old] != target:
            errors.append('historical id collides: %s (live alias of %s, resolves to %s)'
                          % (old, owners[old], target))
    return sorted(set(errors))


def load(root, live_ids, live_aliases=()):
    path = Path(root) / PATH
    data = tomlio.loads(path.read_text(encoding='utf-8')) if path.exists() else {'schema': 1}
    errors = validate(data, live_ids, live_aliases)
    if errors:
        raise ValueError('; '.join(errors))
    return data


def resolve(ident, data, live_ids):
    """Resolve a validated permanent map, with no date-based expiry."""
    records = dict(data.get('aliases', {}), **data.get('retired_by', {}))
    seen = set()
    while ident in records and ident not in seen:
        seen.add(ident)
        ident = records[ident]['target']
    return ident if ident in live_ids else None
