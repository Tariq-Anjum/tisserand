# Capability Pointers

This file is intentionally compact.
Use it to identify external guidance, workflows, and plugins.
Do not recursively search the repository for capability discovery.

| ID | Type | Capability | Runtime location |
|---|---|---|---|
| `eta-guidance` | `guidance` | fixture-guidance | `$AI_TOOLS_ROOT/guidance/eta-guidance/` |
| `iota-plugin` | `plugin` | fixture-plugin | `$AI_TOOLS_ROOT/plugins/iota-plugin/` |
| `theta-flow` | `workflow` | fixture-workflow | `$AI_TOOLS_ROOT/workflows/theta-flow/` |

## Runtime rules

- `skill`: loaded by the Agent Skills mechanism.
- `guidance`: task-selected reference material; load only when relevant.
- `workflow`: external development system; inspect its manifest and runtime command.
- `plugin`: external integration; inspect its manifest and runtime installation.
- Never confuse registration with installation.
