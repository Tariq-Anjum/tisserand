"""Privacy lint (spec 5.2, 11.8): committed text must not carry machine paths,
personal addresses, non-loopback IP literals or likely secrets.

Existing hits are held by a per-file ratchet (`policy/privacy-baseline.json`)
so G1 does not rewrite skills; a file without a baseline entry must be clean.
`policy/privacy-allow.toml` lists exempt file globs and allowlisted e-mail
patterns. An optional local denylist (a file named by the environment
variable SKILLKIT_PRIVACY_DENYLIST, one literal per line) is applied when
set; its hits are always errors, never baselined, and never echo the literal.
Messages never contain the matched text, only the kind and line number.
"""
import fnmatch
import os
import re
from pathlib import Path

from . import baseline
from .credits import DATA_PATHS
from .globs import GlobSet
from .model import finding

LINT = "privacy"
ALLOW = "privacy-allow.toml"
DENYLIST_ENV = "SKILLKIT_PRIVACY_DENYLIST"

# Patterns are assembled from fragments so this file does not itself contain
# the literal strings it looks for.
_SEP = "/"
_LEAD = r"(?<![\w.-])"  # an absolute path starts a token
# (kind, regex, cheap substring gate: the regex only runs if the gate is in the text)
_PATHS = [
    ("home-path", re.compile(_LEAD + _SEP + "ho" + "me" + _SEP + r"[A-Za-z0-9._-]+"), _SEP + "ho" + "me" + _SEP),
    ("users-path", re.compile(_LEAD + _SEP + "Us" + "ers" + _SEP + r"[^\s/]+"), _SEP + "Us" + "ers" + _SEP),
    ("windows-profile", re.compile(r"[A-Za-z]:\\+Us" + r"ers\\"), "Us" + "ers\\"),
    ("mnt-path", re.compile(_LEAD + _SEP + "m" + "nt" + _SEP), _SEP + "m" + "nt" + _SEP),
    ("tilde-dotpath", re.compile("~" + _SEP + r"\."), "~" + _SEP),
]
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}")
_IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d]|\.\d)")
_KW_ASSIGN = re.compile(r"(?i)(?:api[_-]?key|token|secret)[ \t]*[:=][ \t]*([^\s$<{%]\S{11,})")
_SECRET_PREFIXES = [
    ("secret-prefix", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), "sk-"),
    ("secret-prefix", re.compile(r"\bghp_[A-Za-z0-9]{20,}"), "ghp_"),
    ("secret-prefix", re.compile(r"\bgho_[A-Za-z0-9]{20,}"), "gho_"),
    ("secret-prefix", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "github_pat_"),
    ("secret-prefix", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AKIA"),
    ("secret-prefix", re.compile(r"\bxox[bap]-[A-Za-z0-9-]{10,}"), "xox"),
    ("private-key", re.compile("-----BEGIN [A-Z ]*PRIVATE" + " KEY-----"), "-----BEGIN"),
]
_KW_GATES = ("api_key", "api-key", "apikey", "token", "secret")
_DOC_NETS = ((192, 0, 2), (198, 51, 100), (203, 0, 113))


class Allow:
    def __init__(self, file_globs, emails):
        self.files = GlobSet(file_globs)
        self.emails = tuple(e.lower() for e in emails)

    def email_ok(self, addr):
        low = addr.lower()
        return any(fnmatch.fnmatchcase(low, pat) for pat in self.emails)


def _ip_flagged(text):
    parts = [int(x) for x in text.split(".")]
    if any(p > 255 for p in parts):
        return False
    if parts[0] == 127 or parts == [0, 0, 0, 0]:
        return False
    return tuple(parts[:3]) not in _DOC_NETS


def _text_hits(text, allow):
    """[(line_number, kind)] for the whole file; one regex pass per pattern
    (line numbers are only computed for actual hits)."""
    found = []

    def at(m, kind):
        found.append((text.count("\n", 0, m.start()) + 1, kind))

    for kind, rx, gate in _PATHS:
        if gate in text:
            for m in rx.finditer(text):
                at(m, kind)
    if "@" in text:
        for m in _EMAIL.finditer(text):
            if not allow.email_ok(m.group(0)):
                at(m, "email")
    for m in _IPV4.finditer(text):
        if _ip_flagged(m.group(0)):
            at(m, "ipv4")
    lower = text.lower()
    if any(g in lower for g in _KW_GATES):
        for m in _KW_ASSIGN.finditer(text):
            at(m, "secret-assignment")
    for kind, rx, gate in _SECRET_PREFIXES:
        if gate in text:
            for m in rx.finditer(text):
                at(m, kind)
    found.sort()
    return found


class Report:
    def __init__(self):
        self.problems = []
        self.counts = {}      # path -> hits (patterns)
        self.detail = {}      # path -> [(line, kind)]
        self.denylist = []    # (path, line, entry number)
        self.by_kind = {}


def load_allow(scan, report):
    data = scan.policy(ALLOW)
    if data is None:
        return Allow([], [])
    files = data.get("files", {}).get("allow", [])
    emails = data.get("email", {}).get("allow", [])
    if not (isinstance(files, list) and isinstance(emails, list)
            and all(isinstance(x, str) for x in files + emails)):
        report.problems.append(finding("", "lint-policy", "error", "policy/" + ALLOW,
                                       "[files].allow and [email].allow must be arrays of strings"))
        return Allow([], [])
    return Allow(files, emails)


def load_denylist(report):
    """Literals from the file named by the environment, or [] when unset."""
    name = os.environ.get(DENYLIST_ENV)
    if not name:
        return []
    try:
        lines = Path(name).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        report.problems.append(finding("", "lint-privacy-denylist", "warn", ".",
                                       "cannot read the file named by %s: %s" % (DENYLIST_ENV, type(exc).__name__)))
        return []
    return [x.strip() for x in lines if x.strip() and not x.lstrip().startswith("#")]


def analyse(scan):
    report = Report()
    allow = load_allow(scan, report)
    deny = load_denylist(report)
    for f in scan.text_files():
        if f.rel in DATA_PATHS or allow.files.match(f.rel):
            continue
        hits, matches = scan.cached(LINT, f,
                                   lambda: (_text_hits(f.text, allow), _deny_hits(f.text, deny)),
                                   policies=(ALLOW,), extra=repr(deny))
        for n, kind in hits:
            report.counts[f.rel] = report.counts.get(f.rel, 0) + 1
            report.detail.setdefault(f.rel, []).append((n, kind))
            report.by_kind[kind] = report.by_kind.get(kind, 0) + 1
        report.denylist.extend((f.rel, n, i) for n, i in matches)
    return report


def _deny_hits(text, deny):
    return [(n, i) for i, literal in enumerate(deny, 1) if literal in text
            for n, line in enumerate(text.split("\n"), 1) if literal in line]


def findings(report, root, no_baseline=False):
    out = list(report.problems)
    for rel, n, i in report.denylist:
        out.append(finding("", "lint-privacy-denylist", "error", rel,
                           "line %d: matches local denylist entry #%d" % (n, i)))
    base, _existed, problems = (baseline.empty(), False, []) if no_baseline else baseline.load(root, LINT)
    for msg in problems:
        out.append(finding("", "lint-baseline", "error", baseline.rel_path(LINT), msg))
    for rel, was, now in baseline.exceeded(report.counts, base["counts"]):
        detail = report.detail[rel]
        sample = ", ".join("%d:%s" % (n, k) for n, k in detail[:5])
        more = "" if len(detail) <= 5 else ", ..."
        out.append(finding("", "lint-privacy-ratchet", "error", rel,
                           "%d privacy hit(s), baseline allows %d (line:kind %s%s)" % (now, was, sample, more)))
    if base["raises"]:
        out.append(finding("", "lint-privacy-raises", "info", baseline.rel_path(LINT),
                           "%d recorded baseline raise(s)" % len(base["raises"])))
    return out


def run(scan, root, no_baseline=False):
    report = analyse(scan)
    return findings(report, root, no_baseline), report, True


def update(scan, root, reason):
    """Rewrite the baseline. Returns (rises, written_path|None, findings)."""
    report = analyse(scan)
    old, existed, problems = baseline.load(root, LINT)
    if problems:
        return [], None, [finding("", "lint-baseline", "error", baseline.rel_path(LINT), m) for m in problems]
    data, rises = baseline.build_update(old, existed, {"counts": report.counts}, reason)
    rest = list(report.problems) + [
        finding("", "lint-privacy-denylist", "error", rel, "line %d: matches local denylist entry #%d" % (n, i))
        for rel, n, i in report.denylist]
    if rises and not reason:
        return rises, None, rest
    return rises, baseline.write(root, LINT, data), rest
