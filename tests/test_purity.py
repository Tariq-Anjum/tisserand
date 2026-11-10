"""The core must stay stdlib-only, portable and free of machine-specific text."""
import ast
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "skillkit"
FORBIDDEN_CORE_CALLS = {("os", "system"), ("shutil", "which"), ("os", "popen"),
                        ("os", "fork"), ("os", "posix_spawn"), ("os", "posix_spawnp")}
FORBIDDEN_CORE_IMPORTS = {"subprocess", "socket", "urllib", "http"}


def sources():
    return sorted(PKG.rglob("*.py"))


class PurityTests(unittest.TestCase):
    def test_only_stdlib_or_relative_imports(self):
        stdlib = sys.stdlib_module_names
        for path in sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [] if node.level else [node.module.split(".")[0]]
                else:
                    continue
                for mod in mods:
                    self.assertIn(mod, stdlib, "%s imports non-stdlib %s" % (path.name, mod))

    def test_core_has_no_process_spawning(self):
        for path in sorted((PKG / "core").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse(FORBIDDEN_CORE_IMPORTS & {a.name.split(".")[0] for a in node.names}, path.name)
                if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in FORBIDDEN_CORE_IMPORTS:
                    self.fail("%s imports %s" % (path.name, node.module))
                if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                        and (node.value.id, node.attr) in FORBIDDEN_CORE_CALLS):
                    self.fail("%s uses %s.%s" % (path.name, node.value.id, node.attr))
                if isinstance(node, ast.ImportFrom) and node.module == 'os':
                    self.assertFalse({a.name for a in node.names} &
                                     {'system', 'popen', 'fork', 'posix_spawn', 'posix_spawnp'}, path.name)

    def test_route_cascade_has_no_io_clock_or_environment(self):
        # params.load_params is the spec's explicit loading adapter; its I/O
        # implementation lives in routecli and is never used by the cascade.
        forbidden = {"os", "pathlib", "time", "datetime", "random", "subprocess", "socket", "urllib", "http"}
        for path in sorted((PKG / "core" / "route").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse(forbidden & {a.name.split(".")[0] for a in node.names}, path.name)
                if isinstance(node, ast.ImportFrom) and not node.level:
                    self.assertNotIn((node.module or "").split(".")[0], forbidden, path.name)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"open", "hash", "eval", "exec", "__import__"}, path.name)

    def test_no_machine_specific_paths(self):
        needles = ["/" + "home" + "/", "/" + "mnt" + "/", "/" + "Users" + "/", "~" + "/."]
        files = sources() + sorted((REPO / "schema").glob("*.schema.json")) + sorted((REPO / "tests").rglob("*.py"))
        for path in files:
            text = path.read_text(encoding="utf-8")
            for needle in needles:
                self.assertNotIn(needle, text, "%s contains %s" % (path.name, needle))

    def test_no_third_party_package_or_venv_reference(self):
        for path in sources():
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"^\s*(import|from)\s+yaml\b", text, re.M), path.name)
            self.assertNotIn(".venv", text)


if __name__ == "__main__":
    unittest.main()
