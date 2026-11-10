# JuliusBrussee/caveman

Repo: https://github.com/JuliusBrussee/caveman
License: Apache-2.0 at pinned revision 3dc497a7 (repository root; a root
NOTICE file exists, not fetched). BSL-1.1 applied only to pre-3.0.0 runtime components.
What we took: the idea lives in `skills/terse-output/SKILL.md`, rewritten
clean-room on 2026-11-09 (INDEPENDENT).
What we did NOT take: the read-side compression proxy (a local process that
shrinks logs/diffs/JSON before they reach the model). That's real
infrastructure with its own benchmarks and licensing split — if you want it,
install it directly from upstream rather than treating it as part of this
registry:
  npm install -g @caveman-ai/cli && caveman setup --install
Status: INDEPENDENT rewrite (skill idea) + not absorbed (proxy).
