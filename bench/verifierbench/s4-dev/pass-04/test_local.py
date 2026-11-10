from candidate import *
import json
from pathlib import Path
trace = json.loads(Path("transcript.json").read_text())
assert encode(["elm", "oak"]) == "elm\noak"
assert encode([]) == ""
print("local checks passed")
