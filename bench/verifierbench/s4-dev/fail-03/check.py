from candidate import *
import json
from pathlib import Path
trace = json.loads(Path("transcript.json").read_text())
assert consume(pack(3)) == 3
assert pack(0) == "0"
print("postconditions satisfied")
