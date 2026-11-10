#!/usr/bin/env python3
import os, sys, yaml, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from skillkit.core import migrations
RUNTIME=Path(os.environ.get("AI_TOOLS_ROOT", str(Path.home() / "AI-tools")))
INST=RUNTIME/"skills/installed"
STATE=RUNTIME/"skills/state/install-manifest.yaml"
cat=yaml.safe_load((ROOT/"catalog.yaml").read_text())["skills"]
ids={e["id"]:e for e in cat}
history=migrations.load(ROOT, set(ids), {a: e["id"] for e in cat for a in e.get("aliases", [])})
def digest(path):
    h=hashlib.sha256()
    for p in sorted(Path(path).rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(path)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()
if not INST.exists():
    print(f"not installed yet: {INST}")
    raise SystemExit(0)
state=(yaml.safe_load(STATE.read_text()) or {}) if STATE.exists() else {"installed":{}}
installed={p.name:p for p in INST.iterdir() if p.is_dir()}
stale=sorted(i for i in installed if migrations.resolve(i, history, set(ids)) is None)
print(f"runtime: {RUNTIME}")
print(f"installed: {len(installed)}")
if stale: print("stale:", ", ".join(stale))
bad=[]
drift=[]
for i,p in installed.items():
    e=ids.get(migrations.resolve(i, history, set(ids)))
    if not e: continue
    source=ROOT/Path(e["path"]).parent
    if not source.exists():
        bad.append(i)
        continue
    if e["type"]=="skill" and not (p/"SKILL.md").exists(): bad.append(i)
    if e["type"] in ("skill", "guidance") and digest(source)!=digest(p): drift.append(i)
if bad: print("missing source or SKILL.md:", ", ".join(bad))
if drift: print("source/runtime drift:", ", ".join(drift))
for target in [Path.home() / ".agents" / "skills",Path.home() / ".pi" / "agent" / "skills",Path.home() / ".codex" / "skills",Path.home() / ".claude" / "skills"]:
    if target.exists():
        count=sum(1 for p in target.iterdir() if p.is_symlink() and p.resolve().parent==INST)
        print(f"linked {count}: {target}")
if stale or bad or drift: raise SystemExit(1)
print("doctor: OK")
