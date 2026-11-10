"""Shared helpers for scripts/*.sh. Not meant to be run directly."""
import os, sys
from pathlib import Path
from _bootstrap import ensure_yaml
ensure_yaml()
import yaml

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load_catalog():
    with open(os.path.join(REPO_ROOT, "catalog.yaml")) as f:
        data = yaml.safe_load(f)
    return data.get("skills", [])


def find(entries, entry_id):
    for e in entries:
        if e["id"] == entry_id:
            return e
    return None


def resolve_deps(entries, entry_id, seen=None):
    """Returns [entry_id, ...requires... , entry_id] in load order."""
    seen = seen or []
    if entry_id in seen:
        return seen
    e = find(entries, entry_id)
    if e is None:
        print(f"warning: unknown id '{entry_id}' in requires/conflicts", file=sys.stderr)
        return seen
    for dep in e.get("requires", []):
        resolve_deps(entries, dep, seen)
    if entry_id not in seen:
        seen.append(entry_id)
    return seen


def target_dir():
    """Where installed assets get copied to.

    AI_SKILLS_TARGET wins; otherwise use AI_TOOLS_ROOT, matching all other
    registry/runtime tooling.
    """
    root = os.environ.get("AI_TOOLS_ROOT", str(Path.home() / "AI-tools"))
    return os.environ.get("AI_SKILLS_TARGET", os.path.join(root, "skills", "installed"))
