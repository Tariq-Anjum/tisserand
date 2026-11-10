from candidate import *
import json
from pathlib import Path
trace = json.loads(Path("transcript.json").read_text())
assert tag() == "stable"
print("archive unavailable; criterion c2 cannot be checked")
