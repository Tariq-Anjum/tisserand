"""Router I/O boundary; only index, parameters and stopwords are read."""
import sys
import hashlib
import os
from pathlib import Path

from .core import lexical, tomlio
from .core.route import plan
from .core.route.params import PARAMS_PATH, ParamsError, validate_params

TASK_LIMIT = 8000


def add_parser(sub):
    p = sub.add_parser("route", help="produce a deterministic capability plan")
    p.add_argument("--root")
    p.add_argument("--trace", action="store_true")
    p.add_argument("--format", choices=("json", "text"), default="json")
    p.add_argument("--cache-dir", metavar="D", help="optional decision cache directory")
    p.add_argument("--params", default=PARAMS_PATH)
    p.add_argument("--rung", metavar="PROFILE", help="optional external embedding profile")
    p.add_argument("--rerank", metavar="PROFILE", help="optional external rerank profile (M-all)")
    p.add_argument("--rerank-params", metavar="PATH", help="optional rerank parameters; defaults are untuned")
    p.add_argument("--platform", action="append", default=[])
    p.add_argument("--artifact", action="append", default=[])
    p.add_argument("task", metavar="TASK|-", help="task text, or - for UTF-8 stdin")


def load_params(root, rel=PARAMS_PATH):
    try:
        text = (Path(root) / rel).read_bytes().decode("utf-8")
        return validate_params(tomlio.loads(text))
    except (OSError, UnicodeError, tomlio.TomlError, ParamsError) as exc:
        raise ParamsError("%s: %s" % (rel, exc)) from None


def _task(arg):
    if arg != "-":
        data = arg.encode("utf-8")
    elif hasattr(sys.stdin, "buffer"):
        data = sys.stdin.buffer.read(TASK_LIMIT + 1)
    else:
        data = sys.stdin.read(TASK_LIMIT + 1).encode("utf-8")
    if len(data) > TASK_LIMIT:
        raise ValueError("task exceeds 8000 UTF-8 bytes")
    return data.decode("utf-8")


def run(root, args):
    try:
        task = _task(args.task)
        params = load_params(root, args.params)
        entries, _ = lexical.load_index(root)
        stopwords = lexical.load_stopwords(root)
        index = plan.build_index(entries, stopwords, params)
        ctx = plan.Ctx(frozenset(args.platform), frozenset(args.artifact))
        from . import routecache
        cache_dir = routecache.directory(root, args.cache_dir)
        profile = args.rung if args.rung is not None else os.environ.get('SKILLKIT_RUNG_PROFILE')
        rerank_profile = args.rerank if args.rerank is not None else os.environ.get('SKILLKIT_RERANK_PROFILE')
        digest = None
        out = None
        if rerank_profile:
            from .rerankroute import Session, unavailable
            try:
                rerank_params = (Path(root) / args.rerank_params) if args.rerank_params else None
                session = Session(root, rerank_profile, params, params=rerank_params)
                out = session.make_plan(task, ctx, index, params, args.trace)
            except (OSError, ValueError, KeyError, TypeError):
                out = unavailable(plan.make_plan(task, ctx, index, params, args.trace), args.trace)
        elif profile:
            from .semroute import Session, unavailable
            try:
                session = Session(root, profile, params)
                hashes = None
                if cache_dir is not None and not args.trace:
                    hashes = (hashlib.sha256((Path(root) / 'registry/manifest.lock.json').read_bytes()).hexdigest(),
                              hashlib.sha256((Path(root) / 'policy/stopwords.txt').read_bytes()).hexdigest())
                out = session.make_plan(task, ctx, index, params, args.trace, cache_dir, hashes)
            except (OSError, ValueError, KeyError, TypeError):
                out = unavailable(plan.make_plan(task, ctx, index, params, args.trace), args.trace)
        elif cache_dir is not None and not args.trace:
            registry_hash = hashlib.sha256((Path(root) / "registry/manifest.lock.json").read_bytes()).hexdigest()
            stop_hash = hashlib.sha256((Path(root) / "policy/stopwords.txt").read_bytes()).hexdigest()
            digest = routecache.key(task, ctx, index, params, registry_hash, stop_hash)
            out = routecache.get(cache_dir, digest)
        if out is None:
            out = plan.make_plan(task, ctx, index, params, trace=args.trace)
            if digest is not None:
                routecache.put(cache_dir, digest, out)
        data = plan.encode(out)
        if not args.trace and len(data) > 1024:
            raise ValueError("task_plan exceeds 1024 bytes")
        if args.format == "json":
            if hasattr(sys.stdout, "buffer"):
                sys.stdout.buffer.write(data)
            else:
                sys.stdout.write(data.decode("utf-8"))
        else:
            sys.stdout.write("primary: %s\nsupporting: %s\nreference: %s\nmode: %s\nreasons: %s\n" % (
                out["primary"] or "abstain", ", ".join(out["supporting"]) or "-",
                ", ".join(out["reference"]) or "-", out["mode"] or "-", ", ".join(out["reasons"]) or "-"))
        return 0
    except (ParamsError, lexical.ParamsError, OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        sys.stderr.write("skillkit route: %s\n" % exc)
        return 2
