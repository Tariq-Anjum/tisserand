"""Ordered hard eligibility filters."""
from collections import namedtuple

Ctx = namedtuple("Ctx", "platforms artifacts", defaults=(frozenset(), frozenset()))
Eligibility = namedtuple("Eligibility", "ids excluded")


def filter_eligible(entries, ov, ctx):
    named = {i for i, _ in ov.named}
    ids, excluded = [], {}
    for e in sorted(entries, key=lambda e: e["id"]):
        ident = e["id"]
        code = None
        if e.get("activation") == "always":
            code = "router_self"
        elif not e.get("routable", True) or e.get("activation") in ("manual", "dependency"):
            code = "unroutable"
        elif ident in ov.negated:
            code = "named_negative:" + ident
        elif e.get("activation") == "explicit" and ident not in named:
            code = "explicit_unnamed"
        else:
            for field in ("platforms", "artifacts"):
                allowed, supplied = e.get(field) or (), getattr(ctx, field)
                if allowed and supplied and set(allowed).isdisjoint(supplied):
                    code = field[:-1] + "_mismatch"
                    break
        if code:
            excluded[ident] = code
        else:
            ids.append(ident)
    return Eligibility(tuple(ids), excluded)
