from candidate import *
import json
from pathlib import Path
trace = json.loads(Path("transcript.json").read_text())
assert total([2, None, 4]) == 6
assert total([]) == 0
print("local checks passed")
