"""SkillBench metrics (manifest spec 6.4) with a seeded percentile bootstrap.

Every ratio metric is a sum of per-case (numerator, denominator) integer pairs,
so a bootstrap resample is just a re-summation. Cases are plain dicts in the
bench-case format; `got` is {"primary", "supporting", "abstain"}.
"""
import math
import random

CI_LEVEL = 0.95
LOW_N = 20
COLLISION_MIN = 3
METRICS = (
    "top1_acc", "top3_acc", "neighbour_confusion", "hard_neg_fp_rate", "hard_neg_nonnull_rate",
    "abstain_precision", "abstain_recall", "composition_f1", "composition_primary_acc",
    "must_not_violation_rate", "route_correct_rate",
)


def violates(case, got):
    """True if the primary or any supporting id is in expect.must_not."""
    banned = set(case["expect"].get("must_not") or [])
    if not banned:
        return False
    return got["primary"] in banned or any(s in banned for s in got["supporting"])


def is_correct(case, got):
    """Primary matches (null matches abstain); composition also needs the
    supporting set to match; a must_not hit is always wrong."""
    exp = case["expect"]
    if got["primary"] != exp.get("primary"):
        return False
    if violates(case, got):
        return False
    if case["kind"] == "composition":
        return set(got["supporting"]) == set(exp.get("supporting") or [])
    return True


def contributions(case, got, top3):
    """{metric: (num, den)} for the metrics that apply to this case."""
    exp = case["expect"]
    kind = case["kind"]
    out = {}
    primary_ok = got["primary"] == exp.get("primary")
    if kind in ("positive", "neighbour"):
        out["top1_acc"] = (int(primary_ok), 1)
        out["top3_acc"] = (int(exp.get("primary") in top3), 1)
    if kind == "neighbour":
        out["neighbour_confusion"] = (int(got["primary"] == case.get("neighbour_of")), 1)
    if kind == "negative":
        wrong = got["primary"] is not None and (
            got["primary"] in (exp.get("must_not") or []) or got["primary"] != exp.get("primary"))
        out["hard_neg_fp_rate"] = (int(wrong), 1)
        out["hard_neg_nonnull_rate"] = (int(got["primary"] is not None), 1)
    pred, want = bool(got["abstain"]), bool(exp.get("abstain"))
    out["abstain_precision"] = (int(pred and want), int(pred))
    out["abstain_recall"] = (int(pred and want), int(want))
    if kind == "composition":
        e, g = set(exp.get("supporting") or []), set(got["supporting"])
        tp = len(e & g)
        den = 2 * tp + len(g - e) + len(e - g)
        out["composition_f1"] = (2 * tp, den)
        out["composition_primary_acc"] = (int(primary_ok), 1)
    if exp.get("must_not"):
        out["must_not_violation_rate"] = (int(violates(case, got)), 1)
    out["route_correct_rate"] = (int(is_correct(case, got)), 1)
    return out


def ratio(pairs):
    """(value or None, n applicable cases) for a list of (num, den) pairs."""
    num = sum(p[0] for p in pairs)
    den = sum(p[1] for p in pairs)
    return (num / den if den else None), sum(1 for p in pairs if p[1])


def point_estimates(contribs):
    """{metric: value or None} over a list of contribution dicts."""
    return {m: ratio([c[m] for c in contribs if m in c])[0] for m in METRICS}


def bootstrap(contribs, seed, resamples):
    """{metric: (lo, hi) or None}: percentile interval over case resamples.

    The generator is seeded once; indices are drawn with `random()` only, so
    the draw is stable across Python versions. A resample in which a metric
    has an empty denominator is skipped for that metric."""
    n = len(contribs)
    if n == 0:
        return {m: None for m in METRICS}
    nums = {m: [c.get(m, (0, 0))[0] for c in contribs] for m in METRICS}
    dens = {m: [c.get(m, (0, 0))[1] for c in contribs] for m in METRICS}
    rng = random.Random(seed)
    draws = {m: [] for m in METRICS}
    rand = rng.random
    for _ in range(resamples):
        idx = [int(rand() * n) for _i in range(n)]
        for m in METRICS:
            nm, dm = nums[m], dens[m]
            d = sum(dm[i] for i in idx)
            if d:
                draws[m].append(sum(nm[i] for i in idx) / d)
    alpha = (1.0 - CI_LEVEL) / 2.0
    out = {}
    for m in METRICS:
        vals = sorted(draws[m])
        k = len(vals)
        if not k:
            out[m] = None
            continue
        lo = vals[min(k - 1, int(math.floor(alpha * k)))]
        hi = vals[min(k - 1, max(0, int(math.ceil((1.0 - alpha) * k)) - 1))]
        out[m] = (lo, hi)
    return out


def _r(x):
    return None if x is None else round(x, 6)


def summarize(cases, gots, tops, seed, resamples):
    """Metric table: {metric: {value, ci, n, low_n}} plus must_not count."""
    contribs = [contributions(c, g, t) for c, g, t in zip(cases, gots, tops)]
    ci = bootstrap(contribs, seed, resamples)
    table = {}
    for m in METRICS:
        value, n = ratio([c[m] for c in contribs if m in c])
        bounds = ci[m]
        table[m] = {"value": _r(value), "n": n, "low_n": n < LOW_N,
                    "ci": None if bounds is None else [_r(bounds[0]), _r(bounds[1])]}
    violations = sorted(c["case_id"] for c, g in zip(cases, gots) if violates(c, g))
    return table, violations


def per_capability(cases, gots, ids):
    """Per-capability counts: expected (positive/neighbour), top-1 hits,
    abstentions on them, routed-to count, false routes, must_not hits."""
    out = {i: {"expected": 0, "correct": 0, "missed_to_abstain": 0, "routed_to": 0,
               "false_routes": 0, "must_not_hits": 0} for i in sorted(ids)}
    for c, g in zip(cases, gots):
        exp = c["expect"].get("primary")
        if c["kind"] in ("positive", "neighbour") and exp in out:
            out[exp]["expected"] += 1
            if g["primary"] == exp:
                out[exp]["correct"] += 1
            elif g["primary"] is None:
                out[exp]["missed_to_abstain"] += 1
        got = g["primary"]
        if got in out:
            out[got]["routed_to"] += 1
            if got != exp:
                out[got]["false_routes"] += 1
            if got in (c["expect"].get("must_not") or []):
                out[got]["must_not_hits"] += 1
    for v in out.values():
        v["top1_acc"] = _r(v["correct"] / v["expected"]) if v["expected"] else None
        v["low_n"] = v["expected"] < LOW_N
    return out


def collisions(cases, gots, minimum=COLLISION_MIN):
    """Capability pairs whose expected positives were routed to each other at
    least `minimum` times in total (both directions)."""
    counts = {}
    for c, g in zip(cases, gots):
        exp, got = c["expect"].get("primary"), g["primary"]
        if c["kind"] in ("positive", "neighbour", "composition") and exp and got and exp != got:
            counts[(exp, got)] = counts.get((exp, got), 0) + 1
    pairs = {}
    for (x, y), n in counts.items():
        a, b = sorted((x, y))
        rec = pairs.setdefault((a, b), {"a": a, "b": b, "a_as_b": 0, "b_as_a": 0})
        rec["a_as_b" if x == a else "b_as_a"] += n
    rows = []
    for rec in pairs.values():
        rec["total"] = rec["a_as_b"] + rec["b_as_a"]
        if rec["total"] >= minimum:
            rows.append(rec)
    rows.sort(key=lambda r: (-r["total"], r["a"], r["b"]))
    return rows


def median(values):
    s = sorted(values)
    n = len(s)
    if not n:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def percentile(values, q):
    s = sorted(values)
    if not s:
        return None
    return s[min(len(s) - 1, int(math.ceil(q * len(s))) - 1)]
