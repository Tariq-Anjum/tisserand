# Agent instructions for tisserand

## Quick Index

- **Scope:** canonical authored skills, registry metadata, and generated runtime installation tooling.
- **Source/runtime:** edit asset files under `skills/` or `guidance/`; `catalog.yaml` is generated and `skills/installed` is output.
- **Routing:** read `INDEX.md`, then only the smallest matching asset set.
- **Preserve:** reconcile drift before generation; do not overwrite unique runtime content or promote external assets blindly.
- **Validation:** run `build_registry.py`, `scripts/validate.sh`, and `scripts/doctor.sh` with a safe test root when possible.
- **Safety:** never put secrets or machine-specific runtime state in this repository; preserve external/vendor ownership.
- **Stop:** obtain clarification when source provenance, ownership, or rollback is unclear.

Before non-trivial work, read `INDEX.md`.

Do not load every skill. Use the registry to identify the smallest relevant set, then read only those skill files.

`explicit` and `manual` skills are user-invoked. Do not infer them.

When changing registry structure or metadata:
1. edit the asset files, not `catalog.yaml`;
2. run `python3 build_registry.py`;
3. run `./scripts/validate.sh`;
4. run `./scripts/doctor.sh` against a test `AI_TOOLS_ROOT` when possible.

Keep external workflows/plugins as pointers unless there is a deliberate decision to curate an independent skill from them.

Never place credentials, API keys, machine-specific state, or runtime caches in this repository.

