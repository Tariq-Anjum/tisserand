"""Fail-closed idea-card provenance and zero-overlap 8-gram gate; no network."""
import hashlib
import re
from pathlib import Path


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def ngrams(text):
    words = re.findall(r'\w+', text.casefold())
    return {tuple(words[i:i + 8]) for i in range(max(0, len(words) - 7))}


def check_texts(texts, baseline, attestations, cards, sources_root=None):
    out = []
    by_path = {}
    for record in attestations:
        path = record.get('path')
        if path in by_path:
            out.append({'path': path, 'kind': 'duplicate-attestation'})
        by_path[path] = record
    for path, text in sorted(texts.items()):
        if baseline.get(path) == digest(text):
            continue
        record = by_path.get(path, {})
        ids = record.get('idea_cards', [])
        if record.get('digest') != digest(text) or not ids or not isinstance(ids, list):
            out.append({'path': path, 'kind': 'missing-or-stale-provenance'})
            continue
        if record.get('reuse') not in ('mechanism', 'phrasing'):
            out.append({'path': path, 'kind': 'invalid-reuse-mode'})
        refs = set()
        for ident in ids:
            if not isinstance(ident, str) or not re.search(r'(?<![\w-])' + re.escape(ident) + r'(?![\w-])', text):
                out.append({'path': path, 'kind': 'missing-card-citation', 'card': ident})
            card = cards.get(ident)
            if not card or card.get('dropped'):
                out.append({'path': path, 'kind': 'unknown-or-dropped-card', 'card': ident})
                continue
            if not card.get('license_verified', False) and record.get('reuse') != 'mechanism':
                out.append({'path': path, 'kind': 'mechanism-only', 'card': ident})
            refs.update(card.get('records', []))
        if not refs or sources_root is None:
            out.append({'path': path, 'kind': 'source-text-unavailable'})
            continue
        for rel in sorted(refs):
            source = Path(sources_root) / rel
            try:
                if Path(rel).is_absolute() or Path(sources_root).resolve() not in source.resolve().parents:
                    raise ValueError('source path escapes root')
                original = source.read_text(encoding='utf-8')
            except (OSError, UnicodeError, ValueError):
                out.append({'path': path, 'kind': 'source-text-unavailable', 'source': rel})
                continue
            overlap = len(ngrams(text) & ngrams(original))
            if overlap:
                out.append({'path': path, 'kind': '8gram', 'source': rel, 'overlap': overlap})
    return out


def capability_checks(repo, sources_root=None, mode='public'):
    """Disposition/clearance rules; legacy provenance remains readable.

    The original MIT declarations are unchanged. Entries with recorded upstream
    derivation can clear to MIT only by independent disposition or a current,
    mechanism-only rewrite attestation through the existing source overlap gate.
    """
    from . import tomlio
    from .model import finding
    out = []
    registry = {}
    if 'sources/idea-cards.toml' in repo.files:
        try:
            registry = tomlio.loads(repo.files['sources/idea-cards.toml'].decode('utf-8'))
        except tomlio.TomlError:
            return [finding('', 'provenance', 'error', 'sources/idea-cards.toml', 'invalid attestation registry')]
    cards = {ident: card for card in registry.get('card', []) for ident in card['ids']}
    attestations = registry.get('text', [])
    for cap in repo.caps:
        if not cap.ok:
            continue
        p = cap.raw['provenance']
        disposition = p.get('disposition', 'UNKNOWN')
        def add(rule, msg):
            out.append(finding(cap.id, rule, 'error', cap.toml_path, msg))
        records = [r for r in attestations if r.get('path') == cap.doc_path]
        allowed = {'INDEPENDENT', 'COPIED-PERMISSIVE', 'COPIED-UNCLEARED',
                   'ORIGINAL', 'LEGACY-UNATTESTED', 'UNKNOWN'}
        if disposition not in allowed or (records and 'disposition' not in p):
            add('provenance-disposition', 'explicit recognized disposition required for attested text')
        if disposition == 'ORIGINAL':
            if (p.get('origin') != 'original' or any(k in p for k in ('inspired_by', 'source', 'ref', 'derived_from'))
                    or any(r.get('reuse') != 'mechanism' for r in records)):
                add('provenance-original', 'ORIGINAL requires own mechanism-only text without upstream derivation')
            continue
        if disposition == 'LEGACY-UNATTESTED':
            if (p.get('origin') != 'original' or 'inspired_by' in p
                    or cap.doc_path not in registry.get('baseline', {}) or records):
                add('provenance-legacy', 'LEGACY-UNATTESTED requires baseline own text without an attestation')
            continue
        if disposition.startswith('COPIED-') and not p.get('evidence_ref'):
            add('provenance-evidence', 'copied dispositions require evidence_ref')
        legacy = bool(p.get('derived_from', '').strip()) or bool(re.search(
            r'^\s*#\s*derived_from\b', cap.toml_text, re.M))
        if disposition == 'INDEPENDENT' and legacy:
            add('provenance-independent', 'INDEPENDENT forbids derived_from text')
        upstream = legacy or 'inspired_by' in p or 'disposition' in p
        if p['license'] == 'MIT' and upstream and disposition != 'INDEPENDENT':
            records = [r for r in attestations if r.get('path') == cap.doc_path]
            valid = (len(records) == 1 and records[0].get('reuse') == 'mechanism'
                     and not [c for c in check_texts({cap.doc_path: repo.files[cap.doc_path].decode('utf-8')},
                                         {}, records, cards, sources_root)
                              if mode == 'strict' or c['kind'] != 'source-text-unavailable'])
            if not valid:
                add('provenance-clearance', 'MIT clearance requires INDEPENDENT or a current rewrite attestation')
    return out


EVIDENCE_ID = re.compile(r'ev:(lic|card|note|rate|design|report):[a-z0-9][a-z0-9.-]{0,62}')
NOT_CLEARED = frozenset(('UNKNOWN', 'LEGACY-UNATTESTED', 'COPIED-UNCLEARED'))


def evidence_ids(repo):
    """Collect identifiers from authored metadata, without reading their targets."""
    from . import tomlio
    def walk(obj):
        if isinstance(obj, dict):
            for value in obj.values():
                yield from walk(value)
        elif isinstance(obj, list):
            for value in obj:
                yield from walk(value)
        elif isinstance(obj, str) and obj.startswith('ev:'):
            yield obj
    out = set()
    for cap in repo.caps:
        if cap.ok:
            out.update(walk(cap.raw))
    for rel, raw in repo.files.items():
        if rel.endswith('.toml') and rel.startswith(('sources/', 'ratings/', 'taxonomy/')):
            out.update(walk(tomlio.loads(raw.decode('utf-8'))))
    return out


def evidence_hashes(repo, sources_root, evidence_map):
    """Resolve a private map without exposing its paths or source text."""
    from . import tomlio
    mapping = tomlio.loads(Path(evidence_map).read_text(encoding='utf-8'))
    root = Path(sources_root).resolve()
    out = []
    for ident in sorted(evidence_ids(repo)):
        if not EVIDENCE_ID.fullmatch(ident):
            raise ValueError('malformed evidence identifier')
        rel = mapping.get(ident)
        if not isinstance(rel, str) or Path(rel).is_absolute():
            raise ValueError('unresolvable evidence identifier')
        path = (root / rel).resolve()
        if root not in path.parents or not path.is_file():
            raise ValueError('unresolvable evidence identifier')
        out.append({'id': ident, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return out


def mode_checks(repo, mode='public', sources_root=None, evidence_map=None):
    from .model import finding
    out = []
    for cap in repo.caps:
        if cap.ok and cap.raw['provenance'].get('disposition', 'UNKNOWN') in NOT_CLEARED:
            out.append(finding(cap.id, 'provenance-not-cleared', 'error' if mode == 'strict' else 'info',
                               cap.toml_path, 'disposition not cleared'))
    try:
        ids = evidence_ids(repo)
        if any(not EVIDENCE_ID.fullmatch(i) for i in ids):
            raise ValueError('malformed evidence identifier')
        if mode == 'strict':
            evidence_hashes(repo, sources_root, evidence_map)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        out.append(finding('', 'provenance-evidence-map', 'error', 'sources/idea-cards.toml',
                           'evidence identifiers or private resolution invalid'))
    return out


def status(findings, mode='public'):
    unavailable = {f['path'] for f in findings if f['rule'] == 'provenance-incomplete'}
    not_cleared = {f['path'] for f in findings if f['rule'] == 'provenance-not-cleared'}
    errors = sum(f['severity'] == 'error' and (f['rule'].startswith('provenance')
                 or (f['rule'] == 'schema.capability' and f['msg'].startswith('/provenance')))
                 for f in findings)
    return {'mode': mode, 'state': 'FAILED' if errors else 'INCOMPLETE' if unavailable or not_cleared else 'COMPLETE',
            'unavailable': len(unavailable), 'not_cleared': len(not_cleared), 'errors': errors}
