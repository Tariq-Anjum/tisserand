# tisserand registry index

Read this compact routing index before non-trivial work.
Do not load every asset.

## Rules

1. Match the task to a category first.
2. Load only the smallest relevant skill set.
3. `explicit` / `manual` skills are never inferred unless requested.
4. `contextual` capabilities may be selected when the task clearly matches.
5. `skill-router` is the only always-on routing skill.
6. Guidance, workflows, and plugins are capability pointers, not skill prompts.
7. Use `capabilities.md` for non-skill capability lookup.
8. Never recursively search the repository for routine capability discovery.

## Categories

- **Engineering** → `categories/engineering.md`
- **Meta** → `categories/meta.md`
- **Planning** → `categories/planning.md`
- **Productivity** → `categories/productivity.md`
- **Research** → `categories/research.md`

## Capability layer

Use `capabilities.md` for guidance, workflow, and plugin routing.
Use `$AI_TOOLS_ROOT/guidance/INDEX.md` for coding/task guidance.

## Canonical curation and exposure

Authored curated source: `$AI_TOOLS_ROOT/tisserand/repo/skills/`.
Generated shared runtime: `$AI_TOOLS_ROOT/skills/installed/`; do not hand-edit it.
Harness skill roots are thin links to that runtime where supported.
Externally derived copies in user-level skill roots are separate; do not auto-promote, overwrite, or remove them.
Skills use standard `SKILL.md` metadata and are installed into Agent Skills-compatible global locations.

## Runtime

`$AI_TOOLS_ROOT` is the durable local AI-tools root.
Skills: `$AI_TOOLS_ROOT/skills/installed/`
Guidance: `$AI_TOOLS_ROOT/guidance/`
Workflows: `$AI_TOOLS_ROOT/workflows/`
Plugins: `$AI_TOOLS_ROOT/plugins/`

[Ratings](ratings/INDEX.md)
