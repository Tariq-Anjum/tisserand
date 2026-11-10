#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -n "${AI_TOOLS_ROOT:-}" ]; then
  printf '%s\n' "$AI_TOOLS_ROOT"
elif [ -n "${AI_TOOLS:-}" ]; then
  printf '%s\n' "$AI_TOOLS"
elif [ "$(basename "$(dirname "$ROOT")")" = "AI-tools" ]; then
  printf '%s\n' "$(dirname "$ROOT")"
else
  printf '%s\n' "$HOME/AI-tools"
fi
