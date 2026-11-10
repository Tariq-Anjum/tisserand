"""Private strict summaries and public verification; no Git subprocess or network."""
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import struct
import sys

from .core import generate, provenance


def add_parser(sub):
    p = sub.add_parser('provenance', help='produce or verify a sanitized strict evidence summary')
    actions = p.add_subparsers(dest='action', required=True)
    for name in ('summary', 'verify'):
        a = actions.add_parser(name)
        a.add_argument('--root')
        a.add_argument('--tree', required=True)
        if name == 'summary':
            a.add_argument('--sources-root', required=True)
            a.add_argument('--evidence-map', required=True)
            a.add_argument('--out', required=True)
        else:
            a.add_argument('file')


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _safe_path(rel):
    if (not isinstance(rel, str) or not rel or '\\' in rel or '\x00' in rel
            or PurePosixPath(rel).is_absolute() or any(p in ('', '.', '..', '.git') for p in rel.split('/'))):
        raise ValueError('invalid repository-relative path')
    return rel


def _tracked(root):
    """Read the native index directly, preserving linked-worktree ownership.

    v2/v3 indexes are supported; unknown versions, required extensions, merge
    stages, submodules and sparse-directory entries fail closed.
    """
    gitdir = root / '.git'
    if gitdir.is_file():
        marker = gitdir.read_text().strip()
        if not marker.startswith('gitdir: '):
            raise ValueError('invalid Git directory marker')
        gitdir = (root / marker[8:]).resolve()
    raw = (gitdir / 'index').read_bytes()
    if len(raw) < 32 or raw[:4] != b'DIRC' or hashlib.sha1(raw[:-20]).digest() != raw[-20:]:
        raise ValueError('invalid Git index')
    version, count = struct.unpack('!II', raw[4:12])
    if version not in (2, 3):
        raise ValueError('summary requires a v2 or v3 Git index')
    pos, out = 12, {}
    for _ in range(count):
        start = pos
        if pos + 62 >= len(raw) - 20:
            raise ValueError('truncated Git index entry')
        mode = struct.unpack('!I', raw[pos+24:pos+28])[0]
        flags = struct.unpack('!H', raw[pos+60:pos+62])[0]
        if flags & 0x3000 or mode not in (0o100644, 0o100755, 0o120000):
            raise ValueError('unsupported or unmerged Git index entry')
        pos += 62
        if flags & 0x4000:
            if version < 3:
                raise ValueError('invalid extended index entry')
            pos += 2
        end = raw.index(b'\0', pos, len(raw)-20)
        name = _safe_path(raw[pos:end].decode('utf-8'))
        if name in out:
            raise ValueError('duplicate Git index entry')
        out[name] = mode
        pos = start + ((end + 1 - start + 7) // 8) * 8
    while pos < len(raw)-20:
        signature = raw[pos:pos+4]
        if len(signature) != 4 or not 65 <= signature[0] <= 90:
            raise ValueError('unsupported required Git index extension')
        size = struct.unpack('!I', raw[pos+4:pos+8])[0]
        pos += 8 + size
    if pos != len(raw)-20:
        raise ValueError('invalid Git index extension')
    return out


def _bytes(root, rel, mode):
    path = root / _safe_path(rel)
    # Reject symlinked parent directories; never follow a tracked link target.
    for parent in path.relative_to(root).parents:
        if parent != Path('.') and (root / parent).is_symlink():
            raise ValueError('tracked path has a symlinked parent')
    if mode == 0o120000:
        if not path.is_symlink():
            raise ValueError('tracked symlink changed type')
        return os.fsencode(os.readlink(path))
    if path.is_symlink() or not path.is_file():
        raise ValueError('tracked file missing or changed type')
    return path.read_bytes()


def _tree(root, tracked):
    """Compute the source tree identity from working bytes and index modes."""
    tree = {}
    hashes = {}
    for rel, mode in sorted(tracked.items()):
        raw = _bytes(root, rel, mode)
        hashes[rel] = _hash(raw)
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).digest()
        parts = rel.split('/')
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = (mode, blob)
    def encode(node):
        raw = b''
        for name, value in sorted(node.items(), key=lambda item: os.fsencode(item[0]) + (b'/' if isinstance(item[1], dict) else b'')):
            mode, obj = (0o40000, encode(value)) if isinstance(value, dict) else value
            raw += ('%o' % mode).encode() + b' ' + os.fsencode(name) + b'\0' + obj
        return hashlib.sha1(b'tree ' + str(len(raw)).encode() + b'\0' + raw).digest()
    return encode(tree).hex(), hashes


def _sanitize(value):
    if isinstance(value, str):
        # Assemble reserved private markers so the checker does not leak them.
        if any(x in value for x in ('/'+'mnt/', '/'+'home/', 'G'+'2/', chr(64))):
            raise ValueError('summary contains private markers')
    elif isinstance(value, dict):
        for k, v in value.items():
            _sanitize(k)
            _sanitize(v)
    elif isinstance(value, list):
        for v in value:
            _sanitize(v)


def summary(root, args):
    result = generate.evaluate(root, with_drift=True, sources_root=args.sources_root,
                               provenance_mode='strict', evidence_map=args.evidence_map)
    state = provenance.status(result.findings, 'strict')
    if result.errors or state['state'] != 'COMPLETE':
        raise ValueError('strict repository checks are not complete')
    tracked = _tracked(root)
    out = Path(args.out).resolve()
    if root not in out.parents or out.relative_to(root).as_posix() in tracked:
        raise ValueError('summary output must be a new repository-relative file')
    tree, files = _tree(root, tracked)
    if tree != args.tree:
        raise ValueError('source tree does not match working files')
    from .core import tomlio
    registry = tomlio.loads(result.repo.files.get('sources/idea-cards.toml', b'').decode())
    cards = {i:c for c in registry.get('card', []) for i in c['ids']}
    att = {r['path']: r for r in registry.get('text', [])}
    caps = []
    for cap in sorted(result.repo.caps, key=lambda c: c.id):
        ids = att.get(cap.doc_path, {}).get('idea_cards', [])
        refs = {r for i in ids for r in cards.get(i, {}).get('records', [])}
        caps.append(dict(id=cap.id, path=cap.doc_path, sha256=cap.sha_doc,
            disposition=cap.raw['provenance'].get('disposition', 'UNKNOWN'), idea_cards=ids,
            sources_compared=len(refs), overlap_8gram=0))
    data = dict(schema=1, mode='strict', state='COMPLETE', tree=tree, date=datetime.date.today().isoformat(),
        tool=dict(skillkit_schema=2, python=platform.python_version()), files=files, capabilities=caps,
        evidence=provenance.evidence_hashes(result.repo, args.sources_root, args.evidence_map))
    _sanitize(data)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, sort_keys=True, indent=2)+'\n')


def verify(root, args):
    path = Path(args.file).resolve()
    if root not in path.parents:
        raise ValueError('summary must be inside repository')
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError('summary must be an object')
    _sanitize(data)
    if data.get('schema') != 1 or data.get('state') != 'COMPLETE' or data.get('mode') != 'strict' or data.get('tree') != args.tree:
        raise ValueError('summary state or tree mismatch')
    tracked = _tracked(root)
    tracked.pop(path.relative_to(root).as_posix(), None)
    tree, files = _tree(root, tracked)
    if files != data.get('files') or tree != args.tree:
        raise ValueError('tracked files or source tree mismatch')
    result = generate.evaluate(root, with_drift=True)
    if result.errors:
        raise ValueError('public repository checks failed')
    caps = {c.id: c for c in result.repo.caps}
    records = data.get('capabilities')
    if not isinstance(records, list) or len(records) != len(caps) or {r['id'] for r in records} != set(caps):
        raise ValueError('capability inventory mismatch')
    for record in records:
        cap = caps[record['id']]
        if (record.get('path') != cap.doc_path or record.get('sha256') != cap.sha_doc
                or record.get('disposition') != cap.raw['provenance'].get('disposition', 'UNKNOWN')
                or record.get('disposition') in provenance.NOT_CLEARED or record.get('overlap_8gram') != 0):
            raise ValueError('capability summary mismatch')
    evidence = data.get('evidence')
    if not isinstance(evidence, list) or len({e['id'] for e in evidence}) != len(evidence):
        raise ValueError('invalid evidence inventory')
    if {e['id'] for e in evidence} != provenance.evidence_ids(result.repo):
        raise ValueError('evidence inventory mismatch')
    for item in evidence:
        if not provenance.EVIDENCE_ID.fullmatch(item['id']) or not re.fullmatch(r'[a-f0-9]{64}', item['sha256']):
            raise ValueError('invalid evidence identity')


def run(root, args):
    if not re.fullmatch('[a-f0-9]{40}', args.tree):
        sys.stderr.write('skillkit provenance: invalid source tree identity\n')
        return 2
    try:
        (summary if args.action == 'summary' else verify)(Path(root).resolve(), args)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, struct.error):
        sys.stderr.write('skillkit provenance: evidence or tree verification failed\n')
        return 1
    sys.stdout.write('provenance: COMPLETE\n')
    return 0
