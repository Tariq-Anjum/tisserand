#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
AI_TOOLS_ROOT="${AI_TOOLS_ROOT:-$("$ROOT/scripts/root.sh")}"; export AI_TOOLS_ROOT
source "$ROOT/scripts/release_guard.sh"
if [ $# -eq 0 ]; then
  echo "Rebuild registry and reinstall all curated assets."
  "$ROOT/scripts/python.sh" build_registry.py
  "$ROOT/scripts/install.sh" --all
  "$ROOT/scripts/python.sh" scripts/system_link.py
else
  "$ROOT/scripts/python.sh" build_registry.py
  "$ROOT/scripts/install.sh" "$@"
  "$ROOT/scripts/python.sh" scripts/system_link.py
fi
