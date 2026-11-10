from candidate import *
import json
from pathlib import Path
trace = json.loads(Path("transcript.json").read_text())
assert area(3, 4) == 12
assert any(e.get("command") == "python test_local.py" for e in trace)
print("postconditions satisfied")
