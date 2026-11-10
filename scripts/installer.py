#!/usr/bin/env python3
import sys, os, shutil, hashlib
from pathlib import Path
from release_guard import guard
guard(os.environ.get("AI_TOOLS_ROOT", str(Path.home() / "AI-tools")))
from _bootstrap import ensure_yaml
ensure_yaml()
import yaml
ROOT=Path(__file__).resolve().parents[1]
CAT=ROOT/"catalog.yaml"
RUNTIME=Path(os.environ.get("AI_TOOLS_ROOT", str(Path.home() / "AI-tools")))
TARGET=RUNTIME/"skills/installed"
STATE=RUNTIME/"skills/state/install-manifest.yaml"

def catalog():
    return yaml.safe_load(CAT.read_text(encoding="utf-8")).get("skills",[])

def find(entries,i):
    return next((e for e in entries if e["id"]==i),None)

def deps(entries,i,seen=None):
    seen=seen or []
    if i in seen: return seen
    e=find(entries,i)
    if not e: raise SystemExit(f"unknown dependency: {i}")
    for d in e.get("requires",[]) or []: deps(entries,d,seen)
    if i not in seen: seen.append(i)
    return seen

def digest(path):
    h=hashlib.sha256()
    for p in sorted(Path(path).rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(path)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()

def install_skill(e):
    src=ROOT/Path(e["path"]).parent
    dst=TARGET/e["id"]
    TARGET.mkdir(parents=True,exist_ok=True)
    if dst.exists() or dst.is_symlink(): shutil.rmtree(dst) if dst.is_dir() and not dst.is_symlink() else dst.unlink()
    shutil.copytree(src,dst)
    return digest(dst)

def main():
    entries=catalog()
    raw=sys.argv[1:]
    want=[e["id"] for e in entries] if not raw or raw==["--all"] else [x for x in raw if x!="--all"]
    selected=[]
    for i in want:
        for r in deps(entries,i):
            if r not in selected: selected.append(r)
    state={"schema_version":1,"root":str(RUNTIME),"installed":{}}
    if STATE.exists():
        state=yaml.safe_load(STATE.read_text()) or state
    for i in selected:
        e=find(entries,i)
        if e["type"] not in ("skill","guidance"):
            print(f"skip {i}: {e['type']} is a pointer; see {e['path']}")
            continue
        d=install_skill(e)
        state["installed"][i]={"type":e["type"],"source":e["path"],"sha256":d}
        print(f"installed {i} -> {TARGET/i}")
    STATE.parent.mkdir(parents=True,exist_ok=True)
    STATE.write_text(yaml.safe_dump(state,sort_keys=False),encoding="utf-8")
if __name__=="__main__": main()
