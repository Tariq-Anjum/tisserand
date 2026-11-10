import unittest

from skillkit.core import schemacheck as sc


def ok(instance, schema):
    return sc.validate(instance, schema) == []


class CheckSchemaTests(unittest.TestCase):
    def test_supported_keywords_pass(self):
        schema = {
            "$schema": "x", "$id": "y", "title": "t", "description": "d",
            "type": "object", "required": ["a"], "additionalProperties": False,
            "properties": {"a": {"$ref": "#/$defs/s"}},
            "$defs": {"s": {"type": "string", "minLength": 1, "maxLength": 3, "pattern": "^a",
                            "enum": ["ab"], "x-format": "date"}},
            "oneOf": [{"type": "object"}], "if": {"type": "object"}, "then": {}, "else": {},
        }
        self.assertEqual(sc.check_schema(schema), [])

    def test_unsupported_keywords_fail_closed(self):
        for kw in ("minimum", "allOf", "patternProperties", "format", "default", "anyOf",
                   "not", "dependentRequired", "$comment", "x-other", "propertyNames"):
            problems = sc.check_schema({"type": "object", "properties": {"a": {kw: 1}}})
            self.assertEqual(len(problems), 1, kw)
            self.assertIn("unsupported keyword '%s'" % kw, problems[0][1])
            self.assertEqual(problems[0][0], "/properties/a/%s" % kw)

    def test_unsupported_keyword_nested_everywhere(self):
        schema = {"items": {"oneOf": [{"if": {"bad": 1}}]}, "$defs": {"d": {"nope": 1}}}
        pointers = [p for p, _ in sc.check_schema(schema)]
        self.assertEqual(pointers, ["/$defs/d/nope", "/items/oneOf/0/if/bad"])

    def test_structural_errors(self):
        self.assertTrue(sc.check_schema({"additionalProperties": {"type": "string"}}))
        self.assertTrue(sc.check_schema({"type": "number"}))
        self.assertTrue(sc.check_schema({"$ref": "http://example.org/x"}))
        self.assertTrue(sc.check_schema({"$ref": "#/$defs/missing"}))
        self.assertTrue(sc.check_schema({"pattern": "("}))
        self.assertTrue(sc.check_schema({"minLength": -1}))
        self.assertTrue(sc.check_schema({"properties": {"a": True}}))
        self.assertTrue(sc.check_schema({"x-format": "email"}))
        self.assertTrue(sc.check_schema([]))


class ValidateTests(unittest.TestCase):
    def test_type(self):
        self.assertTrue(ok("a", {"type": "string"}))
        self.assertFalse(ok(1, {"type": "string"}))
        self.assertTrue(ok(1, {"type": "integer"}))
        self.assertFalse(ok(True, {"type": "integer"}))
        self.assertTrue(ok(True, {"type": "boolean"}))
        self.assertTrue(ok(None, {"type": "null"}))
        self.assertTrue(ok([], {"type": "array"}))
        self.assertTrue(ok({}, {"type": "object"}))
        self.assertTrue(ok(1, {"type": ["string", "integer"]}))
        self.assertFalse(ok(1.5, {"type": "integer"}))

    def test_enum_const(self):
        self.assertTrue(ok("a", {"enum": ["a", "b"]}))
        self.assertFalse(ok("c", {"enum": ["a", "b"]}))
        self.assertFalse(ok(True, {"enum": [1]}))
        self.assertTrue(ok(1, {"const": 1}))
        self.assertFalse(ok(2, {"const": 1}))

    def test_string_keywords(self):
        self.assertFalse(ok("", {"minLength": 1}))
        self.assertFalse(ok("abcd", {"maxLength": 3}))
        self.assertTrue(ok("abc", {"maxLength": 3, "minLength": 3}))
        self.assertTrue(ok("xxabc", {"pattern": "abc"}))
        self.assertFalse(ok("xyz", {"pattern": "^abc"}))

    def test_date_format(self):
        schema = {"type": "string", "x-format": "date"}
        self.assertTrue(ok("2026-11-05", schema))
        self.assertFalse(ok("2026-13-05", schema))
        self.assertFalse(ok("2026-1-5", schema))
        self.assertFalse(ok("20261105", schema))

    def test_array_keywords(self):
        self.assertFalse(ok([], {"minItems": 1}))
        self.assertFalse(ok([1, 2], {"maxItems": 1}))
        self.assertFalse(ok([1, 1], {"uniqueItems": True}))
        self.assertTrue(ok([1, 2], {"uniqueItems": True}))
        errs = sc.validate([1, "a"], {"items": {"type": "integer"}})
        self.assertEqual(errs, [("/1", "expected integer, got string")])

    def test_object_keywords(self):
        schema = {"required": ["a"], "properties": {"a": {"type": "integer"}}, "additionalProperties": False}
        self.assertTrue(ok({"a": 1}, schema))
        errs = sc.validate({"b": 1}, schema)
        self.assertEqual([m for _, m in errs], ["missing required property 'a'", "unknown property 'b'"])
        self.assertTrue(ok({"a": 1, "b": 2}, {"properties": {"a": {}}}))

    def test_ref(self):
        schema = {"properties": {"a": {"$ref": "#/$defs/n"}}, "$defs": {"n": {"type": "integer"}}}
        self.assertTrue(ok({"a": 1}, schema))
        self.assertEqual(sc.validate({"a": "x"}, schema), [("/a", "expected integer, got string")])

    def test_one_of(self):
        schema = {"oneOf": [{"type": "string"}, {"type": "integer"}]}
        self.assertTrue(ok("a", schema))
        self.assertTrue(ok(1, schema))
        self.assertFalse(ok(None, schema))
        self.assertFalse(ok(1, {"oneOf": [{"type": "integer"}, {"type": "integer"}]}))

    def test_if_then_else(self):
        schema = {"if": {"properties": {"k": {"const": "x"}}, "required": ["k"]},
                  "then": {"required": ["a"]}, "else": {"required": ["b"]}}
        self.assertTrue(ok({"k": "x", "a": 1}, schema))
        self.assertFalse(ok({"k": "x"}, schema))
        self.assertTrue(ok({"k": "y", "b": 1}, schema))
        self.assertFalse(ok({"k": "y", "a": 1}, schema))

    def test_errors_sorted_and_deterministic(self):
        schema = {"properties": {"b": {"type": "string"}, "a": {"type": "string"}}}
        errs = sc.validate({"b": 1, "a": 2}, schema)
        self.assertEqual([p for p, _ in errs], ["/a", "/b"])


if __name__ == "__main__":
    unittest.main()
