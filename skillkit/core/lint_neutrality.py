"""Neutrality lint (spec 5.1, 11.8): product text must not name specific
harnesses, agents or model vendors/models.

Inputs: `policy/neutrality-terms.toml` (the one place such names may appear),
`policy/neutrality-zones.toml`, `policy/neutrality-baseline.json`.

Zones, first matching `[[zone]]` wins; unlisted text files default to
`ratchet` (spec 11.8: unlisted is not exempt):
  hard    any hit is an error; waivers are not honoured.
  ratchet per-file hit count may not exceed the baseline.
  exempt  not checked.
Inside a `capability.toml` the `[provenance]` table is exempt (opaque
upstream data). A hit on a line carrying `neutral-ok: <reason>` (reason of
at least 8 characters) is suppressed in the ratchet zone and counted as a
waiver; the waiver count has its own ratchet.
"""
import re

from . import baseline
from .credits import DATA_PATHS
from .globs import GlobSet
from .model import finding

LINT = "neutrality"
TERMS = "neutrality-terms.toml"
ZONES = "neutrality-zones.toml"
MODES = ("word-ci", "word-cs")
ZONE_NAMES = ("hard", "ratchet", "exempt")
WAIVER = re.compile(r"neutral-ok:[ \t]*(\S.*)?$")
MIN_REASON = 8
_EDGE_L, _EDGE_R = r"(?<![A-Za-z0-9])", r"(?![A-Za-z0-9])"


class Report:
    def __init__(self):
        self.problems = []      # findings about configuration
        self.hard = []          # (path, line, term)
        self.counts = {}        # ratchet zone: path -> hits
        self.waivers = {}       # ratchet zone: path -> waived lines
        self.bad_waivers = []   # (path, line)
        self.zone_hits = {z: 0 for z in ZONE_NAMES}  # all hits seen per zone (before waivers)


class Config:
    def __init__(self, ci, cs, zones):
        self.ci, self.cs, self.zones = ci, cs, zones

    def zone_of(self, rel):
        for name, globs in self.zones:
            if globs.match(rel):
                return name
        return "ratchet"


def configured(scan):
    return scan.has_policy(TERMS)


def _compile(terms):
    parts = {"word-ci": [], "word-cs": []}
    for item in terms:
        parts[item["mode"]].append(re.escape(item["term"]))

    def build(mode, flags):
        if not parts[mode]:
            return None
        return re.compile(_EDGE_L + "(?:" + "|".join(sorted(parts[mode], key=lambda s: (-len(s), s))) + ")" + _EDGE_R, flags)
    return build("word-ci", re.I), build("word-cs", 0)


def load_config(scan, report):
    rel_terms, rel_zones = "policy/" + TERMS, "policy/" + ZONES
    terms = scan.policy(TERMS)
    if terms is None:
        return None
    items = terms.get("terms")
    ok = isinstance(items, list) and bool(items)
    if ok:
        for item in items:
            if not (isinstance(item, dict) and isinstance(item.get("term"), str) and item["term"]
                    and item.get("mode") in MODES):
                ok = False
    if not ok:
        report.problems.append(finding("", "lint-policy", "error", rel_terms,
                                       "'terms' must be a non-empty array of {term, mode} with mode in %s"
                                       % ", ".join(MODES)))
        return None
    zones = []
    zdata = scan.policy(ZONES)
    for entry in (zdata or {}).get("zone", []):
        valid = (isinstance(entry, dict) and entry.get("name") in ZONE_NAMES
                 and isinstance(entry.get("globs"), list) and all(isinstance(g, str) for g in entry["globs"]))
        if not valid:
            report.problems.append(finding("", "lint-policy", "error", rel_zones,
                                           "each [[zone]] needs name in %s and a globs array of strings"
                                           % ", ".join(ZONE_NAMES)))
            return None
        zones.append((entry["name"], GlobSet(entry["globs"])))
    ci, cs = _compile(items)
    return Config(ci, cs, zones)


def _hits(config, line):
    found = []
    for rx in (config.ci, config.cs):
        if rx is not None:
            found.extend(m.group(0) for m in rx.finditer(line))
    return found


def analyse(scan):
    """Scan every text file. Returns (Report, configured_flag)."""
    report = Report()
    config = load_config(scan, report)
    if config is None:
        return report, False
    for f in scan.text_files():
        data = scan.cached(LINT, f, lambda: vars(_file_report(config, f)),
                           policies=(TERMS, ZONES))
        report.hard.extend(data["hard"])
        report.bad_waivers.extend(data["bad_waivers"])
        report.counts.update(data["counts"])
        report.waivers.update(data["waivers"])
        for zone, count in data["zone_hits"].items():
            report.zone_hits[zone] += count
    return report, True


def _file_report(config, f):
    report = Report()
    zone = "exempt" if f.rel in DATA_PATHS else config.zone_of(f.rel)
    if zone == "exempt":
        _tally_exempt(config, f, report)
        return report
    if not _any_hit(config, f.text):
        return report
    in_provenance = False
    is_cap = f.rel.endswith("/capability.toml") or f.rel == "capability.toml"
    for n, line in enumerate(f.text.split("\n"), 1):
        if is_cap:
            stripped = line.strip()
            if stripped.startswith("["):
                header = stripped.split("#", 1)[0].strip().strip("[]")
                in_provenance = header == "provenance" or header.startswith("provenance.")
            if in_provenance:
                continue
        hits = _hits(config, line)
        if not hits:
            continue
        report.zone_hits[zone] += len(hits)
        if zone == "hard":
            for term in hits:
                report.hard.append((f.rel, n, term))
            continue
        m = WAIVER.search(line)
        if m is not None:
            reason = (m.group(1) or "").strip()
            if len(reason) >= MIN_REASON:
                report.waivers[f.rel] = report.waivers.get(f.rel, 0) + 1
                continue
            report.bad_waivers.append((f.rel, n))
        report.counts[f.rel] = report.counts.get(f.rel, 0) + len(hits)
    return report


def _any_hit(config, text):
    return any(rx is not None and rx.search(text) for rx in (config.ci, config.cs))


def _tally_exempt(config, f, report):
    total = sum(len(rx.findall(f.text)) for rx in (config.ci, config.cs) if rx is not None)
    report.zone_hits["exempt"] += total


def findings(report, root):
    out = _non_ratchet(report)
    base, existed, problems = baseline.load(root, LINT, extra_maps=("waivers",))
    for msg in problems:
        out.append(finding("", "lint-baseline", "error", baseline.rel_path(LINT), msg))
    for rel, was, now in baseline.exceeded(report.counts, base["counts"]):
        out.append(finding("", "lint-neutrality-ratchet", "error", rel,
                           "%d named-host hit(s), baseline allows %d; remove them or justify with "
                           "'neutral-ok: <reason>'" % (now, was)))
    for rel, was, now in baseline.exceeded(report.waivers, base["waivers"]):
        out.append(finding("", "lint-neutrality-waiver-ratchet", "error", rel,
                           "%d waiver(s), baseline allows %d" % (now, was)))
    waived = sum(report.waivers.values())
    if waived:
        out.append(finding("", "lint-neutrality-waivers", "info", ".",
                           "%d waived line(s) in %d file(s)" % (waived, len(report.waivers))))
    if base["raises"]:
        out.append(finding("", "lint-neutrality-raises", "info", baseline.rel_path(LINT),
                           "%d recorded baseline raise(s)" % len(base["raises"])))
    return out


def run(scan, root):
    report, ok = analyse(scan)
    if not ok:
        return list(report.problems), report, False
    return findings(report, root), report, True


def update(scan, root, reason):
    """Rewrite the baseline from the current tree. Returns (rises, written_path|None, findings)."""
    report, ok = analyse(scan)
    if not ok:
        return [], None, list(report.problems)
    old, existed, problems = baseline.load(root, LINT, extra_maps=("waivers",))
    if problems:
        return [], None, [finding("", "lint-baseline", "error", baseline.rel_path(LINT), m) for m in problems]
    data, rises = baseline.build_update(old, existed, {"counts": report.counts, "waivers": report.waivers},
                                        reason, extra_maps=("waivers",))
    if rises and not reason:
        return rises, None, []
    return rises, baseline.write(root, LINT, data), _non_ratchet(report)


def _non_ratchet(report):
    out = list(report.problems)
    for rel, n, term in report.hard:
        out.append(finding("", "lint-neutrality-hard", "error", rel,
                           "line %d: names a specific harness/agent/model ('%s') in a hard zone" % (n, term)))
    for rel, n in report.bad_waivers:
        out.append(finding("", "lint-neutrality-waiver", "error", rel,
                           "line %d: neutral-ok needs a reason of at least %d characters" % (n, MIN_REASON)))
    return out
