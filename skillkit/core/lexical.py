"""Rung-0 lexical scorer (G1/S5a): a deterministic diagnostic baseline.

Reads only the generated router surface (`registry/index.json`: id, activation,
routable, provides, intents, description and, once present, phrases) and the
committed stopword list. It never reads SKILL.md bodies or case expectations.

Pipeline (the deterministic cascade, rung 0):
  1. override   - a task that names a routable capability by id is routed to it;
  2. eligibility - routable=false entries are skipped; `explicit` entries are
                  eligible only when the task names them;
  3. scoring    - BM25F over the fields name (the id words), provides,
                  description, intents and phrases, with per-field weights;
  4. decision   - primary iff top score >= tau and the relative margin to the
                  runner-up >= delta, else abstain; supporting entries are
                  those scoring >= tau_s (at most max_supporting).

Scores are summed over query terms in sorted order so results are bit-for-bit
reproducible. Parameters live in `policy/lexical-params.toml`.
"""
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

from . import tomlio

SCORER_NAME = "lexical-bm25f"
SCORER_VERSION = "1"
PARAMS_PATH = "policy/lexical-params.toml"
INDEX_PATH = "registry/index.json"
FIELDS = ("name", "provides", "description", "intents", "phrases")
NORMS = ("none", "query")

_WORD = re.compile(r"[a-z0-9]+")


class ParamsError(Exception):
    """The parameter file or the index is unusable."""


def words(text):
    return _WORD.findall(text.lower())


def stem(word):
    """Crude, deterministic suffix stripper (applied to documents and queries alike)."""
    n = len(word)
    if n > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if n > 5 and word.endswith("sses"):
        return word[:-2]
    if n > 5 and word.endswith("ing"):
        return word[:-3]
    if n > 4 and word.endswith("ed"):
        return word[:-2]
    if n > 4 and word.endswith("es") and word[-3] in "sxz":
        return word[:-2]
    if n > 3 and word.endswith("s") and word[-2] not in "sui":
        return word[:-1]
    return word


# ---------------------------------------------------------------------- params
_SECTIONS = {
    "scoring": ("k1", "b", "stem", "norm"),
    "weights": FIELDS,
    "decision": ("tau", "delta", "tau_s", "max_supporting"),
    "bootstrap": ("seed", "resamples"),
}


def default_params():
    return {
        "scoring": {"k1": 1.2, "b": 0.75, "stem": False, "norm": "none"},
        "weights": {"name": 1.0, "provides": 1.0, "description": 1.0, "intents": 2.0, "phrases": 3.0},
        "decision": {"tau": 1.0, "delta": 0.1, "tau_s": 2.0, "max_supporting": 2},
        "bootstrap": {"seed": 20261105, "resamples": 1000},
    }


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_params(doc):
    """Normalised copy of a parameter document; raises ParamsError."""
    if not isinstance(doc, dict):
        raise ParamsError("parameters must be a table")
    out = {}
    for section, keys in _SECTIONS.items():
        table = doc.get(section)
        if not isinstance(table, dict):
            raise ParamsError("[%s] is missing" % section)
        extra = sorted(set(table) - set(keys))
        missing = sorted(set(keys) - set(table))
        if extra or missing:
            raise ParamsError("[%s]: unexpected %s, missing %s" % (section, extra, missing))
        out[section] = dict(table)
    s, w, d, bs = out["scoring"], out["weights"], out["decision"], out["bootstrap"]
    if not (_num(s["k1"]) and s["k1"] >= 0):
        raise ParamsError("scoring.k1 must be a number >= 0")
    if not (_num(s["b"]) and 0 <= s["b"] <= 1):
        raise ParamsError("scoring.b must be within [0, 1]")
    if not isinstance(s["stem"], bool):
        raise ParamsError("scoring.stem must be a boolean")
    if s["norm"] not in NORMS:
        raise ParamsError("scoring.norm must be one of %s" % ", ".join(NORMS))
    for f in FIELDS:
        if not (_num(w[f]) and w[f] >= 0):
            raise ParamsError("weights.%s must be a number >= 0" % f)
    if not (_num(d["tau"]) and d["tau"] >= 0):
        raise ParamsError("decision.tau must be a number >= 0")
    if not (_num(d["delta"]) and 0 <= d["delta"] <= 1):
        raise ParamsError("decision.delta must be within [0, 1]")
    if not (_num(d["tau_s"]) and d["tau_s"] >= 0):
        raise ParamsError("decision.tau_s must be a number >= 0")
    ms = d["max_supporting"]
    if isinstance(ms, bool) or not isinstance(ms, int) or not 0 <= ms <= 5:
        raise ParamsError("decision.max_supporting must be an integer in 0..5")
    for key, lo, hi in (("seed", 0, 2 ** 63), ("resamples", 1, 100000)):
        v = bs[key]
        if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
            raise ParamsError("bootstrap.%s must be an integer in %d..%d" % (key, lo, hi))
    return out


def load_params(root, rel=PARAMS_PATH):
    path = Path(root) / rel
    try:
        text = path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        raise ParamsError("%s not found" % rel) from None
    except (OSError, UnicodeDecodeError) as exc:
        raise ParamsError("%s: cannot read (%s)" % (rel, type(exc).__name__)) from None
    try:
        return validate_params(tomlio.loads(text))
    except tomlio.TomlError as exc:
        raise ParamsError("%s: %s" % (rel, exc)) from None
    except ParamsError as exc:
        raise ParamsError("%s: %s" % (rel, exc)) from None


def params_sha256(params):
    blob = json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return json.dumps(v)
    return repr(v)


def render_params(params, header_lines=()):
    """Deterministic TOML text for a parameter document with a comment header."""
    out = ["# " + line if line else "#" for line in header_lines]
    if out:
        out.append("")
    out.append("schema = 1")
    for section, keys in _SECTIONS.items():
        out.append("")
        out.append("[%s]" % section)
        for key in keys:
            out.append("%s = %s" % (key, _toml_value(params[section][key])))
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------- index
def load_index(root, rel=INDEX_PATH):
    """(entries, byte size) of the router surface. Raises ParamsError."""
    path = Path(root) / rel
    try:
        data = path.read_bytes()
        doc = json.loads(data.decode("utf-8"))
        entries = doc["capabilities"]
        if not isinstance(entries, list) or any(not isinstance(e, dict) or "id" not in e for e in entries):
            raise ValueError("bad entries")
    except FileNotFoundError:
        raise ParamsError("%s not found" % rel) from None
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ParamsError("%s: unusable (%s)" % (rel, type(exc).__name__)) from None
    return entries, len(data)


def load_stopwords(root, rel="policy/stopwords.txt"):
    try:
        text = (Path(root) / rel).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ParamsError("%s: cannot read (%s)" % (rel, type(exc).__name__)) from None
    return frozenset(w for w in text.split("\n") if w)


# ----------------------------------------------------------------------- model
class _Doc:
    __slots__ = ("id", "routable", "activation", "phrase", "tf", "length")


class Model:
    """BM25F statistics over the index entries (the document set is fixed)."""

    def __init__(self, entries, stopwords, scoring, weights):
        self.stop = frozenset(stopwords)
        self.use_stem = bool(scoring["stem"])
        self.k1 = float(scoring["k1"])
        self.b = float(scoring["b"])
        self.norm = scoring["norm"]
        self.w = {f: float(weights[f]) for f in FIELDS}
        self.docs = []
        for e in sorted(entries, key=lambda x: x["id"]):
            d = _Doc()
            d.id = e["id"]
            d.routable = bool(e.get("routable", True))
            d.activation = e.get("activation", "contextual")
            d.phrase = tuple(d.id.split("-"))
            texts = {
                "name": d.id.replace("-", " "),
                "provides": " ".join(e.get("provides") or []),
                "description": e.get("description") or "",
                "intents": " ".join(e.get("intents") or []),
                "phrases": " ".join(e.get("phrases") or []),
            }
            d.tf = {f: Counter(self._terms(texts[f])) for f in FIELDS}
            d.length = {f: sum(d.tf[f].values()) for f in FIELDS}
            self.docs.append(d)
        n = len(self.docs)
        self.avg = {f: (sum(d.length[f] for d in self.docs) / n if n else 0.0) for f in FIELDS}
        df = Counter()
        for d in self.docs:
            seen = set()
            for f in FIELDS:
                seen.update(d.tf[f])
            df.update(seen)
        self.idf = {t: math.log(1.0 + (n - c + 0.5) / (c + 0.5)) for t, c in sorted(df.items())}

    def _terms(self, text):
        if self.use_stem:
            return [stem(w) for w in words(text) if w not in self.stop]
        return [w for w in words(text) if w not in self.stop]

    def named(self, ws):
        """Routable ids whose id words occur contiguously in the task words,
        longest name first, then id."""
        hits = []
        for d in self.docs:
            if not d.routable:
                continue
            k = len(d.phrase)
            for i in range(len(ws) - k + 1):
                if tuple(ws[i:i + k]) == d.phrase:
                    hits.append((-k, d.id))
                    break
        return [i for _k, i in sorted(hits)]

    def rank(self, task):
        """(ranked [(id, score)] best first with score > 0, named ids)."""
        ws = words(task)
        named = self.named(ws)
        named_set = set(named)
        q = sorted({stem(w) if self.use_stem else w for w in ws if w not in self.stop})
        qv = [t for t in q if t in self.idf]
        denom = (self.k1 + 1.0) * sum(self.idf[t] for t in qv)
        ranked = []
        for d in self.docs:
            if not d.routable or (d.activation == "explicit" and d.id not in named_set):
                continue
            score = 0.0
            for t in qv:
                pseudo = 0.0
                for f in FIELDS:
                    tf = d.tf[f].get(t, 0)
                    wf = self.w[f]
                    if not tf or not wf:
                        continue
                    avg = self.avg[f]
                    lnorm = 1.0 - self.b + self.b * (d.length[f] / avg) if avg else 1.0
                    pseudo += wf * tf / lnorm
                if pseudo:
                    score += self.idf[t] * pseudo * (self.k1 + 1.0) / (pseudo + self.k1)
            if self.norm == "query":
                score = score / denom if denom else 0.0
            if score > 0.0:
                ranked.append((d.id, score))
        ranked.sort(key=lambda r: (-r[1], r[0]))
        return ranked, named


def decide(ranked, named, decision):
    """{"primary", "supporting", "abstain"} from a ranking (see module docstring)."""
    tau, delta = decision["tau"], decision["delta"]
    tau_s, max_sup = decision["tau_s"], decision["max_supporting"]
    primary = None
    if named:
        primary = named[0]
    elif ranked:
        s1 = ranked[0][1]
        s2 = ranked[1][1] if len(ranked) > 1 else 0.0
        if s1 >= tau and (s1 - s2) / s1 >= delta:
            primary = ranked[0][0]
    if primary is None:
        return {"primary": None, "supporting": [], "abstain": True}
    supporting = [i for i, s in ranked if i != primary and s >= tau_s][:max_sup]
    return {"primary": primary, "supporting": supporting, "abstain": False}


def top_ids(ranked, named, k=3):
    out = list(named[:1])
    for i, _s in ranked:
        if i not in out:
            out.append(i)
    return out[:k]
