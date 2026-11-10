# Capability registry adapter for `integrating-agent-capabilities`

Where one host keeps the locations the skill names. The skill owns the
lifecycle; this file only says how to find each location. No absolute paths.

| Location | How to resolve it |
|---|---|
| tools root | `$AI_TOOLS_ROOT` (installer default `~/AI-tools`; see `scripts/root.sh`) |
| integration registry and validator | `$AI_TOOLS_ROOT/integrations/` |
| authored skill source | this repository's `skills/` |
| generated runtime | `$AI_TOOLS_ROOT/skills/installed/` (`scripts/install.sh` writes it) |
| canonical shared memory | named by the host's own instructions; never inferred |

If a location cannot be resolved from configuration, stop and ask; do not
create it.
