"""Label-derived reporting views, shared by router reporting and dev tuning."""


def reachable(case, by_id):
    primary = case["expect"].get("primary")
    return (not primary or by_id.get(primary, {}).get("activation") != "explicit"
            or "explicit-named" in case.get("tags", ()))


def explicit_violation(case, got, by_id):
    allowed = {case["expect"].get("primary")} if "explicit-named" in case.get("tags", ()) else set()
    return any(by_id.get(ident, {}).get("activation") == "explicit" and ident not in allowed
               for ident in (got["primary"], *got["supporting"]) if ident)
