# Capability Pointers

This file is intentionally compact.
Use it to identify external guidance, workflows, and plugins.
Do not recursively search the repository for capability discovery.

| ID | Type | Capability | Runtime location |
|---|---|---|---|
| `bmad` | `workflow` | agile-development, multi-perspective-planning, requirements, architecture | `$AI_TOOLS_ROOT/workflows/bmad/` |
| `caveman` | `workflow` | token-efficiency, concise-output, agent-installation | `$AI_TOOLS_ROOT/workflows/caveman/` |
| `openspec` | `workflow` | spec-driven-development, planning, change-management | `$AI_TOOLS_ROOT/workflows/openspec/` |
| `understand-anything` | `plugin` | code-understanding, architecture-exploration, dependency-analysis, impact-analysis | `$AI_TOOLS_ROOT/plugins/understand-anything/` |

## Runtime rules

- `skill`: loaded by the Agent Skills mechanism.
- `guidance`: task-selected reference material; load only when relevant.
- `workflow`: external development system; inspect its manifest and runtime command.
- `plugin`: external integration; inspect its manifest and runtime installation.
- Never confuse registration with installation.
