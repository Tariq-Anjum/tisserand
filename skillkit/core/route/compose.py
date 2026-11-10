"""Deterministic dependency expansion, marginal composition and conflicts."""
from collections import namedtuple

from .. import lexical

Draft = namedtuple("Draft", "primary supporting reference mode reasons invalid")


def compose(scored, ov, entries_by_id, q, params):
    ranked = {s.id: s for s in scored}
    named = [i for i, _ in ov.named if i in ranked]
    if not scored:
        return Draft(None, (), (), None, (), None)
    primary = named[0] if named else scored[0].id
    selected, required, reasons = {primary}, set(), set()
    roots = {primary, *named}
    if named:
        reasons.add("named_primary:" + primary)
        if len(named) > 1:
            reasons.add("named_multi")

    def invalid(code):
        return Draft(primary, (), (), None, tuple(sorted(reasons)), code)

    def expand(ident, depth, stack):
        if ident not in entries_by_id:
            return "unknown_id"
        if ident in stack:
            return "cycle"
        if depth > params["compose"]["max_depth"]:
            return "requires_depth"
        for dep in sorted(entries_by_id[ident].get("requires", ())):
            if dep in ov.negated:
                # A hard named-negative exclusion cannot be silently overridden
                # by dependency expansion. Reuse the closed invalid-plan code
                # for a primary/requirement conflict.
                return "conflict_requires"
            error = expand(dep, depth + 1, stack | {ident})
            if error:
                return error
            selected.add(dep)
            required.add(dep)
            reasons.add("requires_added:" + dep)
        return None

    error = expand(primary, 0, set())
    if error:
        return invalid(error)

    query = frozenset(q.terms)
    def matched(ident):
        e = entries_by_id[ident]
        words = (w for field in ("intents", "phrases", "provides")
                 for text in e.get(field, ()) for w in lexical.words(text))
        return query & {lexical.stem(w) if params["tokens"]["stem"] else w for w in words}

    p = entries_by_id[primary]
    linked = set(p.get("composes_with", ()))
    linked.update(i for i in sorted(entries_by_id)
                  if primary in entries_by_id[i].get("composes_with", ()))
    candidates = (linked | set(named)) & set(ranked) - selected
    additions = 0
    for ident in sorted(candidates, key=lambda i: (-ranked[i].total, i)):
        if ident in selected:
            continue
        guidance = entries_by_id[ident].get("type") == "guidance"
        if not guidance and additions >= params["compose"]["max_supporting"]:
            continue
        covered = set().union(*(matched(i) for i in sorted(selected)))
        if ident not in named and (ranked[ident].total < params["decision"]["tau_s"]
                                   or not (matched(ident) - covered)):
            continue
        selected.add(ident)
        roots.add(ident)
        reasons.add("compose_added:" + ident)
        if not guidance:
            additions += 1
        error = expand(ident, 0, set())
        if error:
            return invalid(error)

    def priority(ident):
        s = ranked.get(ident)
        return (-(ident in named), -(s.total if s and ident not in required else 0.0), ident)

    # Resolve conflicts between roots before considering their dependencies.
    # A removed root cannot make its otherwise orphaned requirements mandatory.
    surviving_roots = []
    for ident in [primary] + sorted((roots & selected) - {primary}, key=priority):
        clashes = [other for other in surviving_roots
                   if other in entries_by_id[ident].get("conflicts_with", ())
                   or ident in entries_by_id[other].get("conflicts_with", ())]
        if clashes:
            reasons.add("conflict_dropped:" + ident)
        else:
            surviving_roots.append(ident)
    roots = set(surviving_roots)
    retained = set()
    def retain_root_dependencies(ident):
        if ident in retained:
            return
        retained.add(ident)
        for dep in entries_by_id[ident].get("requires", ()):
            retain_root_dependencies(dep)
    for ident in sorted(roots):
        retain_root_dependencies(ident)
    selected &= retained
    reasons.difference_update("conflict_dropped:" + i for i in retained)
    required = {dep for i in sorted(retained) for dep in entries_by_id[i].get("requires", ())}

    # Resolve strongest entries first, so an entry later dropped cannot itself
    # eliminate another survivor. The primary has absolute precedence.
    survivors = []
    for ident in [primary] + sorted(selected - {primary}, key=priority):
        clashes = [other for other in survivors
                   if other in entries_by_id[ident].get("conflicts_with", ())
                   or ident in entries_by_id[other].get("conflicts_with", ())]
        if clashes:
            if ident in required or any(other in required for other in clashes):
                return invalid("conflict_requires")
            reasons.add("conflict_dropped:" + ident)
        else:
            survivors.append(ident)
    selected = set(survivors)

    # A dependency remains only while a surviving root needs it. In
    # particular, dropping a conflicting composed entry must not leave its
    # otherwise-unused dependencies in the final plan.
    retained = set()
    def retain_dependencies(ident):
        if ident in retained:
            return
        retained.add(ident)
        for dep in sorted(entries_by_id[ident].get("requires", ())):
            if dep in selected:
                retain_dependencies(dep)
    for ident in sorted(roots & selected):
        retain_dependencies(ident)
    selected = retained
    reasons = {reason for reason in reasons
               if not reason.startswith("requires_added:") or reason.split(":", 1)[1] in selected}

    # Kahn ordering across the whole set; remove primary only after ordering so
    # its dependencies retain precedence over independent additions.
    ordered, pending = [], set(selected)
    while pending:
        ready = [i for i in sorted(pending) if not (set(entries_by_id[i].get("requires", ())) & pending)]
        if not ready:
            return invalid("cycle")
        ident = min(ready, key=priority)
        ordered.append(ident)
        pending.remove(ident)
    reference = tuple(i for i in ordered if i != primary and entries_by_id[i].get("type") == "guidance")
    supporting = tuple(i for i in ordered if i != primary and i not in reference)
    members = {primary, *supporting}
    staged = any(set(entries_by_id[i].get("requires", ())) & members for i in sorted(members))
    mode = "staged" if staged else "parallel" if len(members) >= 2 else None
    if mode:
        reasons.add("mode_" + mode)
    return Draft(primary, supporting, reference, mode, tuple(sorted(reasons)), None)
