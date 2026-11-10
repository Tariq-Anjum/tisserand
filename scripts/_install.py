#!/usr/bin/env python3
"""Copies skill/guidance assets into the local install target and records
provenance. Workflow/plugin entries are never auto-installed — they print
their manifest's install command instead, since those need a shell outside
this repo, an agent chat, or infra (Docker, API keys) you must approve.
"""
import os
from pathlib import Path
from release_guard import guard
guard(os.environ.get("AI_TOOLS_ROOT", str(Path.home() / "AI-tools")))
import sys, shutil, yaml, datetime
from _lib import load_catalog, find, resolve_deps, target_dir, REPO_ROOT

def install_one(entries, entry_id):
    e = find(entries, entry_id)
    if e is None:
        print(f"Unknown id: {entry_id} (see catalog.yaml)", file=sys.stderr)
        return False

    if e["type"] in ("workflow", "plugin"):
        manifest_path = os.path.join(REPO_ROOT, e["path"])
        with open(manifest_path) as f:
            m = yaml.safe_load(f)
        print(f"== {entry_id} ({e['type']}, not auto-installed) ==")
        print(f"upstream: {m['upstream']['repo']}")
        print(f"install ({m['install']['kind']}):")
        print(f"  {m['install']['command']}")
        if m["install"].get("note"):
            print(f"  # {m['install']['note']}")
        print()
        return True

    # skill / guidance: load deps first, then copy this entry's own dir
    for dep_id in resolve_deps(entries, entry_id):
        dep = find(entries, dep_id)
        src = os.path.join(REPO_ROOT, os.path.dirname(dep["path"]))
        dst = os.path.join(target_dir(), dep_id)
        os.makedirs(target_dir(), exist_ok=True)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print(f"installed {dep_id} -> {dst}")
    return True


def main():
    entries = load_catalog()
    args = sys.argv[1:]
    if not args or args == ["--all"]:
        ids = [e["id"] for e in entries]
    else:
        ids = args
    ok = True
    for i in ids:
        ok = install_one(entries, i) and ok
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
