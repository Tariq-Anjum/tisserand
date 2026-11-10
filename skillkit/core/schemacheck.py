"""In-repo JSON Schema subset checker (spec 4.1, 11.9). Fail closed.

Supported keywords: type, enum, const, pattern, minLength, maxLength,
minItems, maxItems, uniqueItems, items, properties, required,
additionalProperties (boolean only), $ref (local `#/$defs/...` only), $defs,
oneOf, if/then/else, and `x-format: "date"`. The annotations $schema, $id,
title and description are ignored. Any other keyword in a schema is reported
by `check_schema` as unsupported.
"""
import datetime
import json
import re

SUPPORTED = frozenset((
    "type", "enum", "const", "pattern", "minLength", "maxLength", "minItems",
    "maxItems", "uniqueItems", "items", "properties", "required",
    "additionalProperties", "$ref", "$defs", "oneOf", "if", "then", "else",
    "x-format",
))
ANNOTATIONS = frozenset(("$schema", "$id", "title", "description"))
TYPES = frozenset(("string", "integer", "boolean", "array", "object", "null"))
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MAX_DEPTH = 64


class SchemaError(Exception):
    pass


def _type_name(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _resolve(ref, root):
    if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
        return None
    name = ref[len("#/$defs/"):]
    defs = root.get("$defs")
    if isinstance(defs, dict) and isinstance(defs.get(name), dict):
        return defs[name]
    return None


# ---------------------------------------------------------------- schema check
def check_schema(schema):
    """Return a sorted list of (pointer, message) problems with the schema."""
    errs = []
    _walk(schema, "", schema, errs, 0)
    return sorted(set(errs))


def _walk(node, ptr, root, errs, depth):
    where = ptr or "/"
    if depth > _MAX_DEPTH:
        errs.append((where, "schema nesting too deep"))
        return
    if not isinstance(node, dict):
        errs.append((where, "schema must be an object"))
        return
    for key in sorted(node):
        val = node[key]
        here = ptr + "/" + key
        if key in ANNOTATIONS:
            continue
        if key not in SUPPORTED:
            errs.append((here, "unsupported keyword '%s'" % key))
            continue
        if key == "type":
            names = val if isinstance(val, list) else [val]
            if not names or any(not isinstance(n, str) or n not in TYPES for n in names):
                errs.append((here, "invalid type"))
        elif key == "enum":
            if not isinstance(val, list) or not val:
                errs.append((here, "enum must be a non-empty array"))
        elif key == "pattern":
            try:
                re.compile(val)
            except (re.error, TypeError):
                errs.append((here, "invalid pattern"))
        elif key in ("minLength", "maxLength", "minItems", "maxItems"):
            if not isinstance(val, int) or isinstance(val, bool) or val < 0:
                errs.append((here, "must be a non-negative integer"))
        elif key == "uniqueItems":
            if not isinstance(val, bool):
                errs.append((here, "must be a boolean"))
        elif key == "required":
            if not isinstance(val, list) or any(not isinstance(v, str) for v in val):
                errs.append((here, "required must be an array of strings"))
        elif key == "additionalProperties":
            if not isinstance(val, bool):
                errs.append((here, "additionalProperties must be a boolean"))
        elif key == "x-format":
            if val != "date":
                errs.append((here, "unsupported x-format"))
        elif key == "$ref":
            if _resolve(val, root) is None:
                errs.append((here, "unresolvable $ref (only local #/$defs/<name>)"))
        elif key in ("properties", "$defs"):
            if not isinstance(val, dict):
                errs.append((here, "must be an object of schemas"))
            else:
                for name in sorted(val):
                    _walk(val[name], here + "/" + name, root, errs, depth + 1)
        elif key == "oneOf":
            if not isinstance(val, list) or not val:
                errs.append((here, "oneOf must be a non-empty array"))
            else:
                for i, sub in enumerate(val):
                    _walk(sub, "%s/%d" % (here, i), root, errs, depth + 1)
        elif key in ("items", "if", "then", "else"):
            _walk(val, here, root, errs, depth + 1)
        # "const" accepts any JSON value.


# -------------------------------------------------------------------- validate
def validate(instance, schema):
    """Validate; return a sorted list of (pointer, message). Assumes the
    schema already passed `check_schema`."""
    errs = []
    _v(instance, schema, "", schema, errs, 0)
    return sorted(set(errs))


def _v(inst, node, ptr, root, errs, depth):
    if depth > _MAX_DEPTH:
        raise SchemaError("schema recursion too deep")
    where = ptr or "/"
    if "$ref" in node:
        target = _resolve(node["$ref"], root)
        if target is None:
            raise SchemaError("unresolvable $ref %r" % (node["$ref"],))
        _v(inst, target, ptr, root, errs, depth + 1)
    if "type" in node:
        names = node["type"] if isinstance(node["type"], list) else [node["type"]]
        actual = _type_name(inst)
        if actual not in names:
            errs.append((where, "expected %s, got %s" % ("|".join(names), actual)))
            return
    if "const" in node and not _equal(inst, node["const"]):
        errs.append((where, "must equal %s" % json.dumps(node["const"])))
    if "enum" in node and not any(_equal(inst, e) for e in node["enum"]):
        errs.append((where, "must be one of %s" % json.dumps(node["enum"])))
    if isinstance(inst, str):
        if "minLength" in node and len(inst) < node["minLength"]:
            errs.append((where, "shorter than %d characters" % node["minLength"]))
        if "maxLength" in node and len(inst) > node["maxLength"]:
            errs.append((where, "longer than %d characters" % node["maxLength"]))
        if "pattern" in node and not re.search(node["pattern"], inst):
            errs.append((where, "does not match pattern %s" % node["pattern"]))
        if node.get("x-format") == "date" and not _is_date(inst):
            errs.append((where, "not a valid YYYY-MM-DD date"))
    if isinstance(inst, list):
        if "minItems" in node and len(inst) < node["minItems"]:
            errs.append((where, "fewer than %d items" % node["minItems"]))
        if "maxItems" in node and len(inst) > node["maxItems"]:
            errs.append((where, "more than %d items" % node["maxItems"]))
        if node.get("uniqueItems"):
            seen = set()
            for item in inst:
                key = json.dumps(item, sort_keys=True, default=str)
                if key in seen:
                    errs.append((where, "items must be unique"))
                    break
                seen.add(key)
        if "items" in node:
            for i, item in enumerate(inst):
                _v(item, node["items"], "%s/%d" % (ptr, i), root, errs, depth + 1)
    if isinstance(inst, dict):
        for name in node.get("required", ()):
            if name not in inst:
                errs.append((where, "missing required property '%s'" % name))
        props = node.get("properties", {})
        for name in sorted(inst):
            if name in props:
                _v(inst[name], props[name], ptr + "/" + name, root, errs, depth + 1)
            elif node.get("additionalProperties") is False:
                errs.append((ptr + "/" + name, "unknown property '%s'" % name))
    if "oneOf" in node:
        hits = 0
        for sub in node["oneOf"]:
            trial = []
            _v(inst, sub, ptr, root, trial, depth + 1)
            if not trial:
                hits += 1
        if hits != 1:
            errs.append((where, "must match exactly one alternative (matched %d)" % hits))
    if "if" in node:
        trial = []
        _v(inst, node["if"], ptr, root, trial, depth + 1)
        branch = node.get("then") if not trial else node.get("else")
        if branch is not None:
            _v(inst, branch, ptr, root, errs, depth + 1)


def _equal(a, b):
    return _type_name(a) == _type_name(b) and a == b


def _is_date(text):
    if not _DATE.match(text):
        return False
    try:
        datetime.date(int(text[:4]), int(text[5:7]), int(text[8:10]))
    except ValueError:
        return False
    return True
