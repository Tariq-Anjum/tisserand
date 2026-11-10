from candidate import *
import json
from pathlib import Path
trace = json.loads(Path("transcript.json").read_text())
assert area(3, 4) == 12
print("local checks passed")
