from candidate import *
import json
from pathlib import Path
trace = json.loads(Path("transcript.json").read_text())
assert pack(0) == "0"
print("local checks passed")
