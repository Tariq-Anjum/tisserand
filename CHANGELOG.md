# Changelog

## Unreleased

### Removed
- **grill-with-docs** old-name alias retired. Name decision-interview and ask for record mode instead.

## Unreleased: typed routing and skill rewrite (G1 + G2)

Experimental; not activated. Behavioural benefit unmeasured.

### Added
- **Capability manifests:** every skill now has a `capability.toml` (type, activation, risk, access, provenance) validated against JSON schemas.
- **`skillkit`:** a standard-library toolkit with these commands:
  - `check`, `gen` and `gen --check`, which generate a deterministic registry, CREDITS and notices;
  - `lint` (neutrality, privacy, portability, commits);
  - `task-data`;
  - `bench`;
  - an experimental lexical `route`.
- **Typed task taxonomy** `tt-1.1.0`: 14 types plus `unclear`, artifacts, conditions and tie-break rules.
- **Rating rubric** `rb-1.1.0`, with per-skill ratings and a generated `decision-table.json` (126 rows, at most one PRIMARY per row, collision-checked).
- **Skills, rewritten or new in our own words:** fault-loop, intent-contract, bounded-plan, thin-slice, proof-gate, independent-review, interface-design, decision-interview, context-design, code-intelligence, file-based-planning, handoff (named-only), session-reconcile, terse-output.
- **Public correction ladder** `policy/correction-ladder.md`, cited by every skill that retries.
- **Adapters** for the web-research and capability-registry bindings; machine-specific bindings stay outside the repository.
- **VerifierBench:** invented mini-repo fixtures with known outcomes, plus an offline scorer. Real-host runs not yet done.
- **Provenance:**
  - idea-card attestations;
  - an 8-gram overlap gate against the recorded sources;
  - dispositions INDEPENDENT, ORIGINAL, LEGACY-UNATTESTED and UNKNOWN (the last two block a release; none remain);
  - neutral evidence ids.
- **Provenance modes:** `--provenance public` reports `INCOMPLETE` without the private records and never shows OK; `--provenance strict` is required for a release.
- **CI:** `public.yml` (Python 3.11 and latest, plus a fresh-clone job) and `release.yml` (verifies the strict summary). Actions are pinned by commit SHA.
- **Migrations map** for renamed, merged and retired capabilities.

### Changed
- **skill-router** is now typed: pick a type, look up the decision-table row, load one skill.
- **wayfinder** is merged into bounded-plan (ticket mode).
- **grill-me and grill-with-docs** are merged into decision-interview.
- **context-fundamentals** is now context-design.
- **serena-code-intelligence** is now code-intelligence.
- **BMAD-METHOD, OpenSpec, Understand-Anything and caveman** are explicit pointers only.
- **CREDITS.md** is one generated table with notes below it.

### Removed
- karpathy-guidelines (one mechanism survives in thin-slice) and skill-memory (retired).
- Machine paths and private record references in shipped files.

### Known limits
- The lexical router is below target: in the recorded development baseline of 2026-11-05 it picked the expected primary skill (top-1) for 0.316 of reachable positive and neighbour tasks (n=231) and 0.233 of all development positive and neighbour tasks (n=313), against a target of 0.85. Development set only; see "Status and limits" in `README.md` for what "reachable" excludes.
- 55 of 126 table rows have no skill.
- No automatic type chooser ships.

## 2026-09-15 — registry hardening
- Fixed executable permissions on all shell/Python tooling.
- Added the missing `build_registry.py` generator.
- Removed the stale documentation dependency on a non-existent registry table.
- Added Agent Skills-standard `description` metadata to curated skills.
- Added `disable-model-invocation` for explicit skills.
- Added `skill-router` as the single foundational always-on routing skill.
- Added a durable system runtime installer for `~/AI-tools`.
- Added shared Agent Skills links for the shared user skills folder plus detected harness skill folders.
- Added deterministic `ai-skills resolve`, `list`, and `info` commands.
- Added runtime checksums/state and safer doctor/sync flows.
- Updated external workflow/plugin pointers against current upstream installation guidance.
- Added Caveman as an upstream pointer without absorbing its proxy/runtime tooling.

## Initial
- Initial curated registry and source provenance structure.
