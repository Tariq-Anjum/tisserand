#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AI_TOOLS_ROOT="${AI_TOOLS_ROOT:-$("$ROOT/scripts/root.sh")}"; export AI_TOOLS_ROOT
source "$ROOT/scripts/release_guard.sh"
VENV="$ROOT/.venv"
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi
if ! "$VENV/bin/python" -c 'import yaml' >/dev/null 2>&1; then
  echo "tisserand: installing Python dependency PyYAML into $VENV" >&2
  "$VENV/bin/python" -m pip install --disable-pip-version-check -r "$ROOT/requirements.txt"
fi
exec "$VENV/bin/python" "$@"
