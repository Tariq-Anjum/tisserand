"""Closed router parameter schema; file loading is delegated to the CLI boundary."""
import math

from ..lexical import params_sha256
from . import overrides

ROUTER_NAME = "router-v2"
ROUTER_VERSION = "1"
PARAMS_PATH = "policy/router-params.toml"
SECTIONS = {
    "identity": ("name", "version"), "tokens": ("stem",),
    "bm25": ("k1", "b"),
    "weights": ("intent", "phrase", "provides", "bm25", "excl", "named"),
    "decision": ("tau", "delta", "tau_s"),
    "compose": ("max_supporting", "max_depth"),
    "overrides": ("negation_cues", "bridge", "invoke_before", "invoke_after"),
    "bootstrap": ("seed", "resamples"),
}


class ParamsError(ValueError):
    """Invalid router parameters."""


def validate_params(doc):
    if not isinstance(doc, dict) or set(doc) != {"schema", *SECTIONS}:
        raise ParamsError("unexpected or missing top-level parameter keys")
    if type(doc["schema"]) is not int or doc["schema"] != 1:
        raise ParamsError("schema must be 1")
    out = {"schema": 1}
    for section, keys in SECTIONS.items():
        table = doc[section]
        if not isinstance(table, dict) or set(table) != set(keys):
            raise ParamsError("[%s]: unexpected or missing keys" % section)
        out[section] = dict(table)
    if out["identity"] != {"name": ROUTER_NAME, "version": ROUTER_VERSION}:
        raise ParamsError("identity must be router-v2/1")
    if type(out["tokens"]["stem"]) is not bool:
        raise ParamsError("tokens.stem must be boolean")
    for section in ("bm25", "weights", "decision"):
        for key, value in out[section].items():
            if (type(value) not in (int, float) or not math.isfinite(value) or value < 0
                    or (key in ("b", "delta") and value > 1)):
                raise ParamsError("%s.%s is out of range" % (section, key))
            out[section][key] = float(value)
    if out["weights"]["named"] != 1000.0:
        raise ParamsError("weights.named is fixed at 1000.0")
    for section, key, lo, hi in (("compose", "max_supporting", 0, 4),
                                 ("compose", "max_depth", 0, None),
                                 ("bootstrap", "seed", 0, 2 ** 63),
                                 ("bootstrap", "resamples", 1, 100000)):
        value = out[section][key]
        if type(value) is not int or value < lo or (hi is not None and value > hi):
            raise ParamsError("%s.%s is out of range" % (section, key))
    try:
        overrides.validate_params(out["overrides"])
    except overrides.OverrideParamsError as exc:
        raise ParamsError(str(exc)) from None
    out["overrides"] = {k: list(v) for k, v in out["overrides"].items()}
    return out


def load_params(root, rel=PARAMS_PATH):
    """Explicit I/O adapter, outside the pure planning/scoring call graph."""
    from ...routecli import load_params as load
    return load(root, rel)
