from candidate import *
import json
from pathlib import Path
trace = json.loads(Path("transcript.json").read_text())
assert preview([1, 2, 3], 2) == [1, 2]
assert (lambda xs: (preview(xs, 1), xs)[1])([1, 2]) == [1, 2]
print("local checks passed")
