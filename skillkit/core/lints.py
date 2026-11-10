"""Lint driver: runs the neutrality, privacy and portability lints over one
shared tree scan and returns findings in the standard shape."""
from . import lint_neutrality, lint_portability, lint_privacy
from .model import sort_findings
from .scan import Scan

LINTS = ("neutrality", "privacy", "portability")
MODULES = {
    "neutrality": lint_neutrality,
    "privacy": lint_privacy,
    "portability": lint_portability,
}
BASELINED = ("neutrality", "privacy")


def _dedupe(items):
    seen, out = set(), []
    for f in items:
        key = (f["path"], f["rule"], f["id"], f["msg"], f["severity"])
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def run(root, which=LINTS, scan=None):
    """Return (findings, {lint: stats}). Unconfigured neutrality is skipped."""
    scan = scan or Scan(root)
    out, stats = [], {}
    for name in which:
        found, report, ran = MODULES[name].run(scan, root)
        out += found
        if ran:
            stats[name] = _stats(name, report)
    out += scan.findings
    return sort_findings(_dedupe(out)), stats


def _stats(name, report):
    if name == "neutrality":
        return {"hard_hits": len(report.hard),
                "ratchet_hits": sum(report.counts.values()),
                "ratchet_files": len(report.counts),
                "waivers": sum(report.waivers.values()),
                "hits_by_zone": dict(sorted(report.zone_hits.items()))}
    if name == "privacy":
        return {"hits": sum(report.counts.values()), "files": len(report.counts),
                "hits_by_kind": dict(sorted(report.by_kind.items()))}
    return {}


def update_baseline(root, name, reason):
    """Returns (rises, written_path|None, findings)."""
    scan = Scan(root)
    rises, written, found = MODULES[name].update(scan, root, reason)
    return rises, written, sort_findings(_dedupe(found + scan.findings))
