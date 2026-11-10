#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export AI_TOOLS_ROOT="${AI_TOOLS_ROOT:-$("$ROOT/scripts/root.sh")}"
source "$ROOT/scripts/release_guard.sh"

if [ -d .git ]; then
    git pull --ff-only
fi


"$ROOT/scripts/python.sh" build_registry.py
"$ROOT/scripts/validate.sh"
"$ROOT/scripts/install.sh" --all
"$ROOT/scripts/system_link.py"
"$ROOT/scripts/doctor.sh"
