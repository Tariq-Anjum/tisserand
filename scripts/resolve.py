#!/usr/bin/env python3
import sys, os, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import ensure_yaml

ensure_yaml()

import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from skillkit.core import migrations
CAT=ROOT/"catalog.yaml"

def load():
    return yaml.safe_load(CAT.read_text(encoding="utf-8")).get("skills", [])

def score(e, text):
    q=text.lower()
    s=0
    terms=set(re.findall(r"[a-z0-9_-]+", q))
    caps=set(e.get("capabilities",[]))
    for c in caps:
        if c.lower() in q: s+=4
    desc=(e.get("description") or e.get("summary") or "").lower()
    for t in terms:
        if len(t)>3 and t in desc: s+=1
    if e.get("priority")=="foundational": s+=1
    if e.get("activation") in ("always","contextual"): s+=1
    if e.get("activation") in ("explicit","manual"): s-=1
    if e.get("risk")=="high": s-=1
    return s

def main():
    entries=load()
    if len(sys.argv)<2:
        print("usage: ai-skills <list|resolve|info> ...")
        return 2
    cmd=sys.argv[1]
    if cmd=="list":
        for e in entries:
            print(f"{e['id']}\t{e['type']}\t{e.get('activation','')}\t{e.get('description') or e.get('summary','')}")
        return 0
    if cmd=="info" and len(sys.argv)>=3:
        eid=sys.argv[2]
        live = {x["id"] for x in entries}
        history = migrations.load(ROOT, live, {a: x["id"] for x in entries for a in x.get("aliases", [])})
        eid = migrations.resolve(eid, history, live) or eid
        e=next((x for x in entries if x["id"]==eid or eid in x.get("aliases", [])),None)
        if not e: print(f"unknown skill: {eid}", file=sys.stderr); return 1
        print(yaml.safe_dump(e, sort_keys=False))
        return 0
    if cmd=="resolve" and len(sys.argv)>=3:
        q=" ".join(sys.argv[2:])
        live = {x["id"] for x in entries}
        history = migrations.load(ROOT, live, {a: x["id"] for x in entries for a in x.get("aliases", [])})
        target = migrations.resolve(q, history, live)
        if target:
            q = target
        ranked=sorted(((100 if e["id"] == target else score(e,q),e) for e in entries), key=lambda x:(x[0],x[1]["id"]), reverse=True)
        shown=0
        for s,e in ranked:
            if s<=0: continue
            if shown>=6: break
            req=", ".join(e.get("requires",[])) or "none"
            print(f"{e['id']}\t{e['type']}\t{e.get('activation','')}\tscore={s}\trequires={req}\n  {e.get('description') or e.get('summary','')}")
            shown+=1
        if shown==0: print("No strong catalog match. Do not load a skill by default.")
        return 0
    print("usage: ai-skills list | resolve <task> | info <id>")
    return 2

if __name__=="__main__": raise SystemExit(main())
