"""Keep the documented quick start identical to the fresh-clone CI step."""
from pathlib import Path
import re
import unittest

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


ROOT = Path(__file__).resolve().parents[1]


class ReadmeQuickstartTests(unittest.TestCase):
    @unittest.skipIf(yaml is None, "PyYAML unavailable offline; install requirements to compare CI")
    def test_quickstart_matches_fresh_clone_step(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        blocks = re.findall(r"<!-- quickstart -->\n```bash\n(.*?)\n```", readme, re.S)
        self.assertEqual(len(blocks), 1, "expected exactly one marked quick start")
        workflow = yaml.safe_load((ROOT / ".github/workflows/public.yml").read_text())
        steps = [step for step in workflow["jobs"]["fresh-clone"]["steps"]
                 if step.get("name") == "README quick start, verbatim"]
        self.assertEqual(len(steps), 1)
        self.assertEqual(blocks[0] + "\n", steps[0]["run"])


if __name__ == "__main__":
    unittest.main()
