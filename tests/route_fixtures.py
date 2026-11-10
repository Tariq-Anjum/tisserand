"""Router inputs constructed entirely in memory; no repository policy reads."""
import json

from skillkit.core.route import overrides


def parameters():
    return {"schema": 1, "identity": {"name": "router-v2", "version": "1"},
            "tokens": {"stem": True}, "bm25": {"k1": 1.2, "b": 0.75},
            "weights": dict(intent=3.0, phrase=4.0, provides=1.0, bm25=2.0, excl=2.0, named=1000.0),
            "decision": dict(tau=1.0, delta=0.05, tau_s=1.0),
            "compose": dict(max_supporting=2, max_depth=3),
            "overrides": overrides.default_params(), "bootstrap": dict(seed=42, resamples=12)}


def params_text(params):
    lines = ["schema = 1"]
    for section, table in params.items():
        if section == "schema":
            continue
        lines.append("[" + section + "]")
        for key, value in table.items():
            lines.append(key + " = " + json.dumps(value))
    return "\n".join(lines) + "\n"
