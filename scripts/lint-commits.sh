#!/usr/bin/env bash
# Commit-history neutrality lint. Usage: scripts/lint-commits.sh RANGE
# Feeds commit messages of RANGE plus the branch/tag names that contain the
# range end to `python3 -m skillkit lint commits --stdin` (the core itself
# spawns no process). Exit 0 clean, 1 findings, 2 usage/IO.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ $# -eq 1 ] || { echo "usage: scripts/lint-commits.sh RANGE (e.g. BASE..HEAD)" >&2; exit 2; }
RANGE="$1"
END="${RANGE##*..}"
[ -n "$END" ] || END=HEAD
[ "$END" != "$RANGE" ] || END="$RANGE"
cd "$ROOT"
git rev-parse --verify --quiet "$END^{commit}" >/dev/null || { echo "bad range end: $END" >&2; exit 2; }
US=$(printf '\037'); RS=$(printf '\036')
{
  git log --format='C%x1f%H%x1f%B%x1e' "$RANGE"
  git for-each-ref --contains "$END" --format="R${US}branch${US}%(refname:short)${RS}" refs/heads
  git for-each-ref --contains "$END" --format="R${US}tag${US}%(refname:short)${RS}" refs/tags
} | python3 -m skillkit lint commits --stdin "${@:2}"
