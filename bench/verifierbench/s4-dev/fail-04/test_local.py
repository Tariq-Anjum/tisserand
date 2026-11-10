from candidate import *
import json
from pathlib import Path
trace = json.loads(Path("transcript.json").read_text())
assert expired(5, 5) is True
assert expired(4, 5) is False
print("local checks passed")
