"""Command line: python -m skillkit {check,gen,lint,bench}.

Exit codes: 0 ok, 1 findings (errors) or generated-file drift, 2 usage / IO.
"""
import os
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


EXIT_OK, EXIT_FINDINGS, EXIT_USAGE = 0, 1, 2


def _default_root():
    env = os.environ.get("SKILLKIT_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1]


def _add_command_parsers(sub, command):
    # Only the selected command needs its implementation imports. Root help
    # still advertises the complete CLI.
    if command in (None, "bench") and importlib.util.find_spec(__package__ + ".benchcli") is not None:
        from . import benchcli
        benchcli.add_parser(sub)
    else:
        sub.add_parser("bench", help="SkillBench corpus tools")
    if command in (None, "route"):
        from . import routecli
        routecli.add_parser(sub)
    else:
        sub.add_parser("route", help="produce a deterministic capability plan")


def _parser(command=None):
    import argparse
    parser = argparse.ArgumentParser(prog="skillkit", description="Capability manifest tooling.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_ in (("check", "validate the repository"),
                        ("gen", "regenerate registry/*.json")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--root", help="repository root (default: $SKILLKIT_ROOT, else the module's repo)")
        p.add_argument("--format", choices=("text", "json"), default="text")
        p.add_argument("--sources-root", help="local root of registered provenance records")
        p.add_argument("--provenance", choices=("public", "strict"), default="public")
        p.add_argument("--evidence-map", help="private evidence identifier map (strict only)")
        if name == "gen":
            p.add_argument("--check", action="store_true", help="write nothing; exit 1 if outputs differ")
        else:
            p.add_argument("--no-lint", action="store_true",
                           help="skip the neutrality/privacy/portability lints (timing budget runs)")
            p.add_argument("--no-cache", action="store_true", help="bypass the lint cache")
    from . import taskcli, provenancecli
    taskcli.add_parser(sub)
    provenancecli.add_parser(sub)
    lint = sub.add_parser("lint", help="run one lint (neutrality, privacy, portability, or commits)")
    lint.add_argument("which", choices=("neutrality", "privacy", "portability", "commits"))
    lint.add_argument("--root", help="repository root (default: $SKILLKIT_ROOT, else the module's repo)")
    lint.add_argument("--format", choices=("text", "json"), default="text")
    lint.add_argument("--no-baseline", action="store_true", help="privacy only: treat baseline as empty")
    lint.add_argument("--no-cache", action="store_true", help="bypass the lint cache")
    lint.add_argument("--update-baseline", action="store_true",
                      help="rewrite policy/<lint>-baseline.json from the current tree (neutrality, privacy)")
    lint.add_argument("--stdin", action="store_true",
                      help="commits only: read the C/R record stream from standard input")
    lint.add_argument("--allow-raise", metavar="REASON",
                      help="with --update-baseline: permit count increases and record this reason (8+ characters)")
    _add_command_parsers(sub, command)
    return parser


def _fast_check(argv):
    """Parse exact common check flags; defer help, errors and abbreviations."""
    if not argv or argv[0] != "check":
        return None
    args = SimpleNamespace(command="check", root=None, format="text", no_lint=False, no_cache=False, sources_root=None, provenance="public", evidence_map=None)
    i = 1
    while i < len(argv):
        token = argv[i]
        if token in ("--no-lint", "--no-cache"):
            setattr(args, token[2:].replace("-", "_"), True)
        else:
            flag, sep, value = token.partition("=")
            if flag not in ("--root", "--format", "--sources-root", "--evidence-map", "--provenance"):
                return None
            if not sep:
                i += 1
                if i >= len(argv) or argv[i].startswith("-"):
                    return None
                value = argv[i]
            if flag == "--format" and value not in ("text", "json"):
                return None
            if flag == "--provenance" and value not in ("public", "strict"):
                return None
            setattr(args, flag[2:].replace("-", "_"), value)
        i += 1
    return args


def _summary(findings):
    counts = {"error": 0, "info": 0, "warn": 0}
    for f in findings:
        counts[f["severity"]] += 1
    return counts


def _emit(findings, fmt, provenance_status=None):
    from .core import jsonout
    if fmt == "json":
        payload = {"findings": findings, "summary": _summary(findings)}
        if provenance_status is not None:
            payload.update(provenance=provenance_status, provenance_complete=provenance_status["state"] == "COMPLETE")
        sys.stdout.write(jsonout.dumps(payload))
        return
    for f in findings:
        who = " %s:" % f["id"] if f["id"] else ""
        sys.stdout.write("%s: %s [%s]%s %s\n" % (f["path"], f["severity"], f["rule"], who, f["msg"]))
    if provenance_status is not None:
        _emit_provenance(provenance_status)
    counts = _summary(findings)
    sys.stdout.write("%d error(s), %d warning(s), %d info\n" % (counts["error"], counts["warn"], counts["info"]))


def _emit_provenance(p):
    if p['state'] == 'FAILED':
        line = 'FAILED (%d error(s))' % p['errors']
    elif p['state'] == 'COMPLETE':
        line = 'COMPLETE'
    else:
        gaps = '%d: source text unavailable' % p['unavailable']
        if p['not_cleared']:
            gaps += '; %d: not cleared' % p['not_cleared']
        line = 'INCOMPLETE (%s)' % gaps
    sys.stdout.write('provenance: ' + line + '\n')


def main(argv=None):
    # Dispatch before constructing the general parser: route must not import
    # bench/lint or load authored capability bodies, including for --help.
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "route":
        import argparse
        from . import routecli
        parser = argparse.ArgumentParser(prog="skillkit")
        sub = parser.add_subparsers(dest="command", required=True)
        routecli.add_parser(sub)
        try:
            args = parser.parse_args(argv)
        except SystemExit as exc:
            return EXIT_USAGE if exc.code else EXIT_OK
        root = Path(args.root) if args.root else _default_root()
        return routecli.run(root, args)
    args = _fast_check(argv)
    if args is None:
        parser = _parser(argv[0] if argv and not argv[0].startswith("-") else None)
        try:
            args = parser.parse_args(argv)
        except SystemExit as exc:
            return EXIT_USAGE if exc.code not in (0, None) else EXIT_OK
    if args.command in ('check', 'gen') and args.provenance == 'strict' and (not args.sources_root or not args.evidence_map):
        sys.stderr.write('skillkit: strict requires --sources-root and --evidence-map\n')
        return EXIT_USAGE
    root = Path(args.root) if args.root else _default_root()
    if not root.is_dir():
        sys.stderr.write("skillkit: root is not a directory: %s\n" % root.name)
        return EXIT_USAGE
    try:
        if args.command == "provenance":
            from . import provenancecli
            return provenancecli.run(root, args)
        if args.command == "task-data":
            from . import taskcli
            return taskcli.run(root, args)
        if args.command == "check":
            return _check(root, args)
        if args.command == "lint":
            return _lint(root, args)
        if args.command == "bench":
            from . import benchcli
            return benchcli.run(root, args)
        return _gen(root, args)
    except OSError as exc:
        sys.stderr.write("skillkit: I/O error: %s\n" % type(exc).__name__)
        return EXIT_USAGE


def _check(root, args):
    from .core import generate
    from .core.model import sort_findings
    result = generate.evaluate(root, with_drift=True, sources_root=args.sources_root, provenance_mode=args.provenance, evidence_map=args.evidence_map)
    seal_findings = []
    if importlib.util.find_spec(__package__ + ".core.bench") is not None:
        from .core import bench
        seal_findings = bench.verify_seal(root)
    findings = sort_findings(result.findings + seal_findings)
    if not args.no_lint:
        found, _stats = _run_lints(root, args)
        findings = sort_findings(findings + found)
    from .core import provenance
    _emit(findings, args.format, provenance.status(findings, args.provenance))
    return EXIT_FINDINGS if any(f["severity"] == "error" for f in findings) else EXIT_OK


def _run_lints(root, args, which=None):
    from .core import lints
    if args.no_cache:
        driver = lints
    else:
        from . import lintcache
        driver = lintcache
    return driver.run(root, lints.LINTS if which is None else which)


def _usage(msg):
    sys.stderr.write("skillkit lint: %s\n" % msg)
    return EXIT_USAGE


def _lint_commits(root, args):
    from .core import jsonout, lint_commits
    from .core.scan import Scan
    if not args.stdin:
        return _usage("commits needs --stdin (use scripts/lint-commits.sh RANGE)")
    if args.update_baseline or args.allow_raise is not None:
        return _usage("commits has no baseline")
    found, stats, ran = lint_commits.run(Scan(root), sys.stdin.read())
    if not ran:
        _emit(found, "text")
        return EXIT_USAGE
    if args.format == "json":
        sys.stdout.write(jsonout.dumps({"findings": found, "stats": stats, "summary": _summary(found)}))
    else:
        _emit(found, "text")
    return EXIT_FINDINGS if found else EXIT_OK


def _lint(root, args):
    from .core import jsonout, lint_neutrality, lints
    from .core.scan import Scan
    name = args.which
    if args.no_baseline and (name != "privacy" or args.update_baseline or args.allow_raise):
        return _usage("--no-baseline is only valid for a privacy check")
    if name == "commits":
        return _lint_commits(root, args)
    if args.allow_raise is not None:
        if not args.update_baseline:
            return _usage("--allow-raise only applies with --update-baseline")
        if len(args.allow_raise.strip()) < 8:
            return _usage("--allow-raise needs a reason of at least 8 characters")
    if args.update_baseline and name not in lints.BASELINED:
        return _usage("%s has no baseline" % name)
    if name == "neutrality" and not lint_neutrality.configured(Scan(root)):
        return _usage("policy/neutrality-terms.toml not found")
    if args.update_baseline:
        return _lint_update(root, args)
    if args.no_baseline:
        from .core import lint_privacy
        found, report, _ = lint_privacy.run(Scan(root), root, no_baseline=True)
        stats = {name: lints._stats(name, report)}
    else:
        found, stats = _run_lints(root, args, (name,))
    if args.format == "json":
        sys.stdout.write(jsonout.dumps({"findings": found, "stats": stats, "summary": _summary(found)}))
    else:
        _emit(found, "text")
    return EXIT_FINDINGS if any(f["severity"] == "error" for f in found) else EXIT_OK


def _lint_update(root, args):
    from .core import jsonout, lints
    reason = args.allow_raise.strip() if args.allow_raise else None
    rises, written, found = lints.update_baseline(root, args.which, reason)
    refused = bool(rises) and written is None
    if args.format == "json":
        sys.stdout.write(jsonout.dumps({
            "findings": found, "refused": refused, "summary": _summary(found),
            "raises": [{"path": p, "from": a, "to": b} for p, a, b in rises], "written": written}))
    else:
        if refused:
            for label, was, now in rises:
                sys.stdout.write("refused: %s would rise from %d to %d\n" % (label, was, now))
            sys.stdout.write("baseline not written; re-run with --allow-raise \"<reason>\" to record a raise\n")
        elif written:
            sys.stdout.write("wrote %s (%d raise(s) recorded)\n" % (written, len(rises)))
        _emit(found, "text")
    return EXIT_FINDINGS if refused or any(f["severity"] == "error" for f in found) else EXIT_OK


def _gen(root, args):
    from .core import generate, jsonout, provenance
    if args.check:
        result = generate.evaluate(root, with_drift=True, sources_root=args.sources_root, provenance_mode=args.provenance, evidence_map=args.evidence_map)
        _emit(result.findings, args.format, provenance.status(result.findings, args.provenance))
        return EXIT_FINDINGS if result.errors else EXIT_OK
    result = generate.evaluate(root, with_drift=False, sources_root=args.sources_root, provenance_mode=args.provenance, evidence_map=args.evidence_map)
    if result.errors:
        _emit(result.findings, args.format, provenance.status(result.findings, args.provenance))
        return EXIT_FINDINGS
    written = generate.write_outputs(root, result.outputs)
    if args.format == "json":
        sys.stdout.write(jsonout.dumps({"written": written, "findings": result.findings,
                                        "summary": _summary(result.findings), "provenance": provenance.status(result.findings, args.provenance),
                                        "provenance_complete": provenance.status(result.findings, args.provenance)["state"] == "COMPLETE"}))
    else:
        for rel in written:
            sys.stdout.write("wrote %s\n" % rel)
        _emit_provenance(provenance.status(result.findings, args.provenance))
        sys.stdout.write("%d file(s) written\n" % len(written))
    return EXIT_OK
