"""Pure router facade and compact task_plan encoding."""
import copy
import json
from collections import namedtuple

from . import compose, eligible, normalize, overrides, score
from .params import ROUTER_NAME, ROUTER_VERSION, params_sha256, validate_params

Index = namedtuple("Index", "entries by_id stopwords model params_sha256")
Prepared = namedtuple("Prepared", "query overrides eligibility features")
Ctx = eligible.Ctx


def build_index(entries, stopwords, params):
    params = validate_params(params)
    entries = tuple(sorted(copy.deepcopy(entries), key=lambda e: e["id"]))
    by_id = {e["id"]: e for e in entries}
    if len(by_id) != len(entries):
        raise ValueError("duplicate registry ids")
    stop = frozenset(stopwords)
    return Index(entries, by_id, stop, score.build_model(entries, stop, params), params_sha256(params))


def prepare(task, ctx, index, params):
    """Compute invariant features once; tuning changes only weights/decisions."""
    if params_sha256(params) != index.params_sha256:
        raise ValueError("index was built with different parameters")
    q = normalize.normalize(task, index.stopwords, params["tokens"]["stem"])
    ov = overrides.find_overrides(q, index.entries, params["overrides"], index.stopwords)
    elig = eligible.filter_eligible(index.entries, ov, ctx)
    return Prepared(q, ov, elig, score.feature_rows(q, index.model, index.by_id, elig, ov))


def make_plan(task, ctx, index, params, trace=False):
    prepared = prepare(task, ctx, index, params)
    return decide(prepared, score.combine(prepared.features, params), index.by_id, params, trace)


def decide(prepared, scored, entries_by_id, params, trace=False):
    """Shared production/tuning decision and composition, with precomputed ranking."""
    q, ov, elig = prepared.query, prepared.overrides, prepared.eligibility
    s1 = scored[0].total if scored else 0.0
    s2 = scored[1].total if len(scored) > 1 else 0.0
    margin = (s1 - s2) / s1 if s1 else 0.0
    named = [i for i, _ in ov.named if i in elig.ids]
    reasons = {"named_negative:" + i for i in ov.negated}
    reasons.update("named_unroutable:" + i for i in ov.unroutable_named)
    error = None
    draft = None
    if not q.words:
        error = "empty_task"
    elif not scored:
        error = "no_candidate"
    elif not named and s1 < params["decision"]["tau"]:
        error = "below_tau"
    elif not named and margin < params["decision"]["delta"]:
        error = "low_margin"
    else:
        draft = compose.compose(scored, ov, entries_by_id, q, params)
        reasons.update(draft.reasons)
        if draft.invalid:
            error = "plan_invalid:" + draft.invalid
    if error:
        reasons.add(error)
    # Preserve the decision reason when diagnostic reasons exceed the cap.
    essential = {error} if error else ({"named_primary:" + draft.primary} if named else set())
    output_reasons = sorted(essential | set(sorted(reasons - essential)[:12 - len(essential)]))
    confidence = 0.0 if error else 1.0 if named else round(
        min(1, s1 / (2 * max(params["decision"]["tau"], 0.25))) * (0.5 + 0.5 * margin), 3)
    out = {"abstain": bool(error), "confidence": confidence,
           "mode": None if error else draft.mode, "primary": None if error else draft.primary,
           "reasons": output_reasons, "reference": [] if error else list(draft.reference),
           "router": ROUTER_NAME + "/" + ROUTER_VERSION, "schema": 1,
           "supporting": [] if error else list(draft.supporting)}
    if trace:
        excluded = dict(elig.excluded)
        trace_reasons = ["exclusion_hit:" + s.id for s in scored if s.features["excl"]]
        if ov.named and not named:
            trace_reasons.append("named_ineligible")
        out["trace"] = {"query_terms": list(q.terms), "named": [i for i, _ in ov.named],
                        "excluded": excluded, "candidates": [s._asdict() for s in scored[:5]],
                        "params_sha256": params_sha256(params),
                        "decision": {"s1": s1, "s2": s2, "margin": round(margin, 6)}}
        if trace_reasons:
            out["trace"]["reasons"] = sorted(set(trace_reasons))
    return out


def encode(plan):
    return (json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")
