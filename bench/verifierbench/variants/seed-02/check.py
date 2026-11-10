from candidate import *
import json
from pathlib import Path
trace = json.loads(Path("transcript.json").read_text())
assert label("red oak") == "red oak"
assert label(" ash ") == "ash"
print("postconditions satisfied")
