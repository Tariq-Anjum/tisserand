from candidate import *
import json
from pathlib import Path
trace = json.loads(Path("transcript.json").read_text())
print("observed status:", status())
