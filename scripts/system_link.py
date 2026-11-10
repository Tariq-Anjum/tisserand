#!/usr/bin/env python3

import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNTIME = Path(
    os.environ.get(
        "AI_TOOLS_ROOT",
        REPO.parent,
    )
)

from release_guard import guard
guard(RUNTIME)

INSTALLED = RUNTIME / "skills" / "installed"
SELECTED_SKILLS = set(sys.argv[1:])


def safe_link(target: Path, source: Path):
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.is_symlink():
        target.unlink()
    elif target.exists():
        print(f"skip {target}: real path exists")
        return

    target.symlink_to(source, target_is_directory=source.is_dir())
    print(f"linked {source} -> {target}")


def link_tree_entries(source_root: Path, runtime_root: Path):
    runtime_root.mkdir(parents=True, exist_ok=True)

    if not source_root.exists():
        return

    for entry in sorted(source_root.iterdir()):
        if entry.name.startswith("."):
            continue

        target = runtime_root / entry.name
        safe_link(target, entry)


# ------------------------------------------------------------------
# Agent Skills
# ------------------------------------------------------------------

agent_skill_roots = [
    Path.home() / ".agents" / "skills",
]

for binary, path in [
    ("pi", Path.home() / ".pi" / "agent" / "skills"),
    ("codex", Path.home() / ".codex" / "skills"),
    ("claude", Path.home() / ".claude" / "skills"),
]:
    if shutil.which(binary) or path.exists():
        agent_skill_roots.append(path)

if SELECTED_SKILLS:
    available = {
        p.name for p in INSTALLED.iterdir()
        if p.is_dir() and (p / "SKILL.md").exists()
    } if INSTALLED.exists() else set()
    unknown = SELECTED_SKILLS - available
    if unknown:
        raise SystemExit(f"unknown installed skill id(s): {', '.join(sorted(unknown))}")

for root in agent_skill_roots:
    root.mkdir(parents=True, exist_ok=True)

    if INSTALLED.exists():
        for skilldir in sorted(INSTALLED.iterdir()):
            if SELECTED_SKILLS and skilldir.name not in SELECTED_SKILLS:
                continue
            if not skilldir.is_dir():
                continue
            if not (skilldir / "SKILL.md").exists():
                continue

            safe_link(
                root / skilldir.name,
                skilldir,
            )

# ------------------------------------------------------------------
# Runtime registry
# ------------------------------------------------------------------

runtime_skills = RUNTIME / "skills"
runtime_skills.mkdir(parents=True, exist_ok=True)

for name in [
    "INDEX.md",
    "catalog.yaml",
    "capabilities.md",
]:
    safe_link(
        runtime_skills / name,
        REPO / name,
    )

safe_link(
    runtime_skills / "categories",
    REPO / "categories",
)

# ------------------------------------------------------------------
# Runtime capability areas
# ------------------------------------------------------------------

link_tree_entries(
    REPO / "guidance",
    RUNTIME / "guidance",
)

link_tree_entries(
    REPO / "workflows",
    RUNTIME / "workflows",
)

link_tree_entries(
    REPO / "plugins",
    RUNTIME / "plugins",
)

print(f"AI_TOOLS_ROOT={RUNTIME}")
print(f"skills={runtime_skills}")
print(f"guidance={RUNTIME / 'guidance'}")
print(f"workflows={RUNTIME / 'workflows'}")
print(f"plugins={RUNTIME / 'plugins'}")
