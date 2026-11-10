import unittest

from skillkit.core import frontmatter as fm, legacy, yamlout

GOOD = "---\nname: a-b\ndescription: Some text, with: colon.\ndisable-model-invocation: false\n---\n\n# T\n"


class FrontmatterTests(unittest.TestCase):
    def test_good(self):
        data, errors, body = fm.parse(GOOD)
        self.assertEqual(errors, [])
        self.assertEqual(data, {"name": "a-b", "description": "Some text, with: colon.",
                                "disable-model-invocation": False})
        self.assertEqual(body, 5)

    def test_quotes_and_bool(self):
        data, errors, _ = fm.parse("---\nname: 'x'\ndescription: \"true\"\ndisable-model-invocation: true\n---\n")
        self.assertEqual(errors, [])
        self.assertEqual(data["name"], "x")
        self.assertEqual(data["description"], "true")
        self.assertIs(data["disable-model-invocation"], True)

    def test_errors(self):
        cases = {
            "no delimiter": "name: x\n",
            "unclosed": "---\nname: x\n",
            "unknown key": "---\nname: x\nid: y\n---\n",
            "duplicate": "---\nname: x\nname: y\n---\n",
            "nested": "---\nname: x\n  sub: y\n---\n",
            "comment": "---\n# c\nname: x\n---\n",
            "no space": "---\nname:x\n---\n",
            "crlf": "---\r\nname: x\r\n---\r\n",
        }
        for label, text in cases.items():
            data, errors, _ = fm.parse(text)
            self.assertIsNone(data, label)
            self.assertTrue(errors, label)


class LegacyTests(unittest.TestCase):
    def test_shape(self):
        text = ("id: x\ncapabilities:\n- a\n- b\nrequires: []\nupstream:\n  repo: https://e.org/x\n"
                "  ref: v1\n  verified_on: 2026-01-02\ninstall:\n  note: one\n    two\n  command: 'it''s'\n"
                "summary: S\n")
        got = legacy.parse(text)
        self.assertEqual(got["capabilities"], ["a", "b"])
        self.assertEqual(got["requires"], [])
        self.assertEqual(got["upstream"]["verified_on"], "2026-01-02")
        self.assertEqual(got["install"], {"note": "one two", "command": "it's"})

    def test_rejects_other_shapes(self):
        bad = ["id: &a x\n", "id: *a\n", "unknown: x\n", "id: x\nid: y\n", "id: [a, b]\n",
               "id: |\n  text\n", "# c\nid: x\n", "upstream:\n  bogus: x\n", "id: x: y\n",
               "id: 'a\n", "capabilities: a\n", "  id: x\n", "id: \"a\\n\"\n"]
        for text in bad:
            with self.assertRaises(legacy.LegacyYamlError, msg=text):
                legacy.parse(text)


class YamlOutTests(unittest.TestCase):
    def test_dump(self):
        obj = {"b": [1, "x y", None, True], "a": {"k": [], "m": {}}, "c": [{"p": 1, "q": [2]}, "s"]}
        self.assertEqual(yamlout.dumps(obj), (
            '"a":\n  "k": []\n  "m": {}\n'
            '"b":\n  - 1\n  - "x y"\n  - null\n  - true\n'
            '"c":\n  - "p": 1\n    "q":\n      - 2\n  - "s"\n'))

    def test_unsupported(self):
        with self.assertRaises(TypeError):
            yamlout.dumps({"a": 1.5})

    def test_unsorted(self):
        self.assertEqual(yamlout.dumps({"z": 1, "a": 2}, sort_keys=False), '"z": 1\n"a": 2\n')


if __name__ == "__main__":
    unittest.main()
