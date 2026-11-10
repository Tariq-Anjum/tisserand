#!/usr/bin/env bash
set -euo pipefail
AI_TOOLS_ROOT="${AI_TOOLS_ROOT:-${AI_TOOLS:-$HOME/AI-tools}}"
export AI_TOOLS_ROOT
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Validate the entire request before removing even its first id.
for id in "$@"; do
  [[ $id =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]] || { echo "uninstall: invalid id: $id" >&2; exit 2; }
done
source "$ROOT/scripts/release_guard.sh"
TARGET="$AI_TOOLS_ROOT/skills/installed"
if [ $# -eq 0 ]; then echo "Usage: ./scripts/uninstall.sh <id>..." >&2; exit 1; fi
for id in "$@"; do
  rm -rf -- "$TARGET/$id"
  for dest in "$HOME/.agents/skills" "$HOME/.pi/agent/skills" "$HOME/.codex/skills" "$HOME/.claude/skills"; do
    if [[ -L $dest/$id && $(readlink -- "$dest/$id") == "$TARGET/$id" ]]; then
      rm -f -- "$dest/$id"
    fi
  done
  echo "removed $id"
done
