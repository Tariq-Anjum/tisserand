"""Weight-independent features and fixed-order weighted scoring."""
from collections import namedtuple

from .. import lexical
from .normalize import terms

Model = namedtuple("Model", "bm25 stopwords stem coverage phrases exclusions")
Scored = namedtuple("Scored", "id total features named")


def build_model(entries, stopwords, params):
    stop, use_stem = frozenset(stopwords), params["tokens"]["stem"]
    coverage, phrases, exclusions, descriptions = {}, {}, {}, []
    for e in sorted(entries, key=lambda e: e["id"]):
        ident = e["id"]
        coverage[ident] = {field: tuple(terms(t, stop, use_stem) for t in e.get(field, ()))
                           for field in ("intents", "provides", "phrases")}
        phrases[ident] = tuple(tuple(lexical.words(t)) for t in e.get("phrases", ()))
        exclusions[ident] = tuple(terms(t, stop, use_stem) for t in e.get("exclusions", ()))
        if (e.get("routable", True) and e.get("activation") not in ("always", "manual", "dependency")):
            descriptions.append({"id": ident, "description": e.get("description", ""),
                                 "activation": "contextual"})
    bm = lexical.Model(descriptions, stop, dict(params["bm25"], stem=use_stem, norm="query"),
                       {f: float(f == "description") for f in lexical.FIELDS})
    # lexical.Model derives name terms from id even at zero weight. Blank them
    # and rebuild IDF so only descriptions contribute to document frequency.
    from collections import Counter
    import math
    df = Counter()
    for d in bm.docs:
        for field in lexical.FIELDS:
            if field != "description":
                d.tf[field].clear()
                d.length[field] = 0
        df.update(d.tf["description"].keys())
    n = len(bm.docs)
    bm.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in sorted(df.items())}
    return Model(bm, stop, use_stem, coverage, phrases, exclusions)


def _features(q, model, entry, bm25):
    ident, query = entry["id"], frozenset(q.terms)
    cov = model.coverage[ident]
    def maximum(field):
        return max((len(ts & query) / len(ts) if ts else 0.0 for ts in cov[field]), default=0.0)
    phrase = any(p and any(q.words[i:i + len(p)] == p for i in range(len(q.words) - len(p) + 1))
                 for p in model.phrases[ident])
    excl = min(2, sum(bool(ts) and ts <= query for ts in model.exclusions[ident]))
    return {"intent": round(maximum("intents"), 6), "phrase": float(phrase),
            "provides": round(maximum("provides"), 6), "bm25": round(bm25, 6), "excl": float(excl)}


def features(q, model, entry):
    ranked, _ = model.bm25.rank(q.key)
    return _features(q, model, entry, dict(ranked).get(entry["id"], 0.0))


def matched_terms(q, model, ident):
    return frozenset(q.terms) & frozenset(t for groups in model.coverage[ident].values()
                                        for group in groups for t in group)


def feature_rows(q, model, entries_by_id, elig, ov):
    """Weight-independent rows, including candidates currently scoring <= 0."""
    bm25 = dict(model.bm25.rank(q.key)[0])
    named = {i for i, _ in ov.named}
    return tuple((ident, _features(q, model, entries_by_id[ident], bm25.get(ident, 0.0)), ident in named)
                 for ident in elig.ids)


def combine(rows, params):
    """Recombine cached features with exactly the production scoring order."""
    w, out = params["weights"], []
    for ident, f, is_named in rows:
        total = round(w["intent"] * f["intent"] + w["phrase"] * f["phrase"]
                      + w["provides"] * f["provides"] + w["bm25"] * f["bm25"]
                      + w["named"] * is_named - w["excl"] * f["excl"], 6)
        if total > 0 or is_named:
            out.append(Scored(ident, total, f, is_named))
    return tuple(sorted(out, key=lambda s: (-s.total, s.id)))


def score_all(q, model, entries_by_id, elig, ov, params):
    return combine(feature_rows(q, model, entries_by_id, elig, ov), params)
