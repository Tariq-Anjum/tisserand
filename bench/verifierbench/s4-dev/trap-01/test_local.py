from candidate import *
import json
from pathlib import Path
trace = json.loads(Path("transcript.json").read_text())
assert isinstance(status(), str)
print("local checks passed")
