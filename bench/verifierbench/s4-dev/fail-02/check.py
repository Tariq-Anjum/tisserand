from candidate import *
import json
from pathlib import Path
trace = json.loads(Path("transcript.json").read_text())
assert unique(["b", "a", "b"]) == ["b", "a"]
assert unique(["x", "x"]) == ["x"]
print("postconditions satisfied")
