from candidate import *
import json
from pathlib import Path
trace = json.loads(Path("transcript.json").read_text())
assert label("BIRCH") == "birch"
assert label(" ash ") == "ash"
print("local checks passed")
