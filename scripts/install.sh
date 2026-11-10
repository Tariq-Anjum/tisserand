#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
AI_TOOLS_ROOT="${AI_TOOLS_ROOT:-$("$ROOT/scripts/root.sh")}"; export AI_TOOLS_ROOT
source "$ROOT/scripts/release_guard.sh"
system=false
all=false
ids=()
for arg in "$@"; do
  case "$arg" in
    --system) system=true ;;
    --all) all=true ;;
    --*) echo "unknown option: $arg" >&2; exit 2 ;;
    *) ids+=("$arg") ;;
  esac
done
args=()
$all && args+=(--all)
args+=("${ids[@]}")
"$ROOT/scripts/python.sh" scripts/installer.py "${args[@]}"
if $system; then
  "${ROOT}/scripts/python.sh" scripts/system_link.py
fi
