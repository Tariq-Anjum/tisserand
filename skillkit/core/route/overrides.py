"""Named-capability detector (router design spec, section 4). Pure, stdlib only.

Finds capabilities that a task names (id, display name or alias, matched
contiguously on word boundaries) and capabilities it explicitly rules out
("without X", "do not use X"). Deterministic: no clock, randomness,
environment or I/O; the result depends only on its arguments.

Rules, in order:
1. Name phrases per entry: words(id), words(name), words(alias) for every
   alias. Phrases that are empty, made only of stopwords, or a single token
   of at most 2 characters are dropped.
2. A phrase matches where it occurs contiguously in the task words.
3. A match lying strictly inside a longer match of another entry is dropped.
4. A match is negated when a negation cue ends immediately before it, or
   ends before it with exactly one bridge token in between. Any negated
   match of an id puts that id in `negated`, and a negated id is never named.
5. A single-token match for an entry whose activation is "explicit" counts
   only with an invocation cue: an `invoke_before` token within the 2 tokens
   before it, or an `invoke_after` token immediately after it. Multi-token
   matches and non-explicit entries need no cue.
6. Entries with `routable` false are reported in `unroutable_named`, never
   in `named`. `named` is ordered by (earliest position, longer phrase, id).
"""
from collections import namedtuple

from .. import lexical

DETECTOR_VERSION = "1"
MIN_SINGLE_TOKEN = 3  # single-token phrases shorter than this are dropped

Overrides = namedtuple("Overrides", ("named", "negated", "unroutable_named"))

_DEFAULTS = {
    "negation_cues": ("without", "no", "dont use", "don t use", "do not use", "never use", "stop using", "skip"),
    "bridge": ("the", "a", "any", "using", "use"),
    "invoke_before": ("use", "run", "invoke", "apply", "activate", "enable", "with", "using", "load"),
    "invoke_after": ("skill", "mode", "command"),
}
_KEYS = tuple(sorted(_DEFAULTS))


class OverrideParamsError(ValueError):
    """The override parameters are malformed."""


def default_params():
    """A fresh copy of the committed default cue lists (lists of strings)."""
    return {key: list(value) for key, value in _DEFAULTS.items()}


def validate_params(doc):
    """Return `doc` unchanged when it holds exactly the four cue lists, each a
    list of non-empty strings; raise OverrideParamsError otherwise."""
    if not isinstance(doc, dict) or sorted(doc) != list(_KEYS):
        raise OverrideParamsError("override params must have exactly the keys: " + ", ".join(_KEYS))
    for key in _KEYS:
        value = doc[key]
        if not isinstance(value, (list, tuple)) or not value:
            raise OverrideParamsError("%s must be a non-empty list" % key)
        for item in value:
            if not isinstance(item, str) or not lexical.words(item):
                raise OverrideParamsError("%s holds an empty or non-string entry" % key)
    return doc


def _cue_tuples(items):
    return tuple(sorted({tuple(lexical.words(item)) for item in items}, key=lambda t: (-len(t), t)))


def _name_phrases(entry, stopwords):
    texts = [entry.get("id", ""), entry.get("name") or ""]
    texts += [a for a in (entry.get("aliases") or ()) if isinstance(a, str)]
    out = []
    for text in texts:
        toks = tuple(lexical.words(text))
        if not toks or all(t in stopwords for t in toks):
            continue
        if len(toks) == 1 and len(toks[0]) < MIN_SINGLE_TOKEN:
            continue
        if toks not in out:
            out.append(toks)
    return out


def _query_words(q):
    if isinstance(q, str):
        return tuple(lexical.words(q))
    return tuple(getattr(q, "words", q))


def _negated(words, start, cues, bridge):
    for cue in cues:
        n = len(cue)
        if start >= n and tuple(words[start - n:start]) == cue:
            return True
        if start >= n + 1 and words[start - 1] in bridge and tuple(words[start - 1 - n:start - 1]) == cue:
            return True
    return False


def _has_invoke_cue(words, start, end, before, after):
    if any(w in before for w in words[max(0, start - 2):start]):
        return True
    return end < len(words) and words[end] in after


def find_overrides(q, entries, params=None, stopwords=frozenset()):
    """Detect named and negated capabilities in a task.

    q         task text, a sequence of normalised words, or an object with a
              `.words` sequence (words as produced by `lexical.words`).
    entries   iterable of dicts with `id` and optionally `name`, `aliases`,
              `activation` and `routable` (default True).
    params    the four cue lists (see `default_params`); defaults when None.
    stopwords words that never form a name on their own.

    Returns Overrides(named=((id, position), ...), negated=frozenset(ids),
    unroutable_named=(id, ...)).
    """
    p = validate_params(default_params() if params is None else params)
    words = _query_words(q)
    cues = _cue_tuples(p["negation_cues"])
    bridge = frozenset(w for item in p["bridge"] for w in lexical.words(item))
    before = frozenset(w for item in p["invoke_before"] for w in lexical.words(item))
    after = frozenset(w for item in p["invoke_after"] for w in lexical.words(item))
    stop = frozenset(stopwords)
    matches = []  # (start, end, id)
    info = {}
    for entry in entries:
        ident = entry["id"]
        info[ident] = entry
        for phrase in _name_phrases(entry, stop):
            n = len(phrase)
            for i in range(len(words) - n + 1):
                if tuple(words[i:i + n]) == phrase and (i, i + n, ident) not in matches:
                    matches.append((i, i + n, ident))
    kept = []
    for start, end, ident in matches:
        inside = any(o_id != ident and o_start <= start and end <= o_end and (o_end - o_start) > (end - start)
                     for o_start, o_end, o_id in matches)
        if not inside:
            kept.append((start, end, ident))
    negated, positive = set(), {}
    for start, end, ident in kept:
        if _negated(words, start, cues, bridge):
            negated.add(ident)
            continue
        entry = info[ident]
        if (end - start) == 1 and entry.get("activation") == "explicit" and not _has_invoke_cue(words, start, end, before, after):
            continue
        key = (start, -(end - start), ident)
        if ident not in positive or key < positive[ident]:
            positive[ident] = key
    named, unroutable = [], []
    for ident in sorted(positive, key=lambda i: positive[i]):
        if ident in negated:
            continue
        if info[ident].get("routable", True) is False:
            unroutable.append(ident)
        else:
            named.append((ident, positive[ident][0]))
    return Overrides(tuple(named), frozenset(negated), tuple(unroutable))
