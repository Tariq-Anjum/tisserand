#!/usr/bin/env bash
# Source before bootstrap/install/git mutations. Hold fd9 through child writers.
# These legacy writers are not release-aware: no flag/environment bypass exists.
activation_lock="${AI_TOOLS_ROOT:?}/.activation.lock"
if [[ ! -d $AI_TOOLS_ROOT || -L $AI_TOOLS_ROOT || -L $activation_lock ]]; then
    echo 'writer: explicit real AI_TOOLS_ROOT directory required' >&2; exit 1
fi
if [[ ! -e /proc/self/fd/9 || ! /proc/self/fd/9 -ef $activation_lock ]]; then
    exec 9> "$activation_lock"
fi
flock -xn 9 || { echo 'writer: activation lock busy' >&2; exit 1; }
if [[ -e $AI_TOOLS_ROOT/skills/current || -L $AI_TOOLS_ROOT/skills/current || -d $AI_TOOLS_ROOT/skills/releases || -d $AI_TOOLS_ROOT/.activation/transaction || -d $AI_TOOLS_ROOT/.activation/preparing ]]; then
    echo 'writer: release layout active; legacy writer prohibited; use the owner-gated release transaction' >&2
    exit 1
fi
if [[ -L $AI_TOOLS_ROOT/skills || -L $AI_TOOLS_ROOT/skills/installed ]]; then
    echo 'writer: indirect skills layout refused' >&2; exit 1
fi
