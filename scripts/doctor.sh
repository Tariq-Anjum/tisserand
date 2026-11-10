#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
AI_TOOLS_ROOT="${AI_TOOLS_ROOT:-$("$ROOT/scripts/root.sh")}"; export AI_TOOLS_ROOT
source "$ROOT/scripts/release_guard.sh"
"$ROOT/scripts/python.sh" build_registry.py >/dev/null
"$ROOT/scripts/validate.sh"
"$ROOT/scripts/python.sh" scripts/doctor.py
