---
name: integrating-agent-capabilities
description: Safely integrate shared agent capabilities by discovering providers, classifying ownership, reusing installations, adding thin harness bindings, validating, and registering verified state.
disable-model-invocation: false
---

# Capability Wiring

## Quick Index

- **Trigger:** a tool, MCP server, skill, plugin or harness binding shared
  across agents must be added, updated, removed or fixed.
- **Process:** seven phases below, cheapest reuse first.
- **Verification:** only what the real harness was seen to discover and
  run counts as available.
- **Halts:** owner approval before any gated action; on failure, scoped
  rollback and BLOCKED (`policy/correction-ladder.md` §12).
- **Not for:** spec or change plan; application code. openspec (loads
  only when named) owns plans and leaves installs and bindings here.
  Application code is implementation. External premises get researched
  without new routes.

## Phases

1. **L, locate.** Find where the registry, validator, authored source,
   runtime and canonical memory live, using the host configuration and
   `adapters/capability-registry/README.md`. A mirror is never promoted to
   canonical. Edit sources, never generated runtime output. Nothing
   configured? Ask, do not create.
2. **I, inventory.** Pair each wanted feature with its existing
   provider. Keep packages, processes, bindings, skills and mirrors
   apart, each tagged with its owner and a word from the vocabulary.
   Install, config, trust and discovery are separate checks; something
   present but unseen gets its visibility fixed, not a second install.
3. **V, vet.** Clear every row of the risk sheet.
4. **B, baseline.** Capture repo status, dirty-file digests, config
   identity, links and installed versions; unrelated work stays as found.
   Plan: files, outcome, checks, resource cost, undo. Favour scoped
   backups and reversible edits; no new repos or commits without
   authorization.
5. **R, reuse.** Take the first option that works: fix settings or
   permissions; extend the present provider; add thin glue for one
   harness; install a new provider only once its need is shown. One
   logical provider per harness, declared once; one shared install where
   feasible, with any checkout or lifecycle reason for a copy written down.
6. **T, test.** Prove, in order: the config parses and fits its schema;
   it connects, and one functional call works with least privilege; the
   harness itself discovers it; no duplicate ids, aliases, shadowing or
   leftovers remain; startup cost, memory, workers and shutdown are clean;
   rollback works, where feasible; the phase L registry validator passes.
7. **W, write.** Register as available only what phase T saw, then rerun
   that validator; a skipped or failed run fails closed.

## Risk sheet

| Area | Check |
|---|---|
| Versions | consequential ones confirmed from official sources |
| Launch | transport, command, argument handling |
| Environment | variable names inspected; values never shown |
| Reach | file access, network, listening ports |
| Persistence | long-lived workers, write privileges |
| Data | flows and credentials; no secret in any artifact |
| Fit | licence; overlap with present capabilities |
| Authority | mirrors and dev tools keep their narrow limits |

## Vocabulary (closed)

| Word | Meaning |
|---|---|
| canonical-shared | centrally owned provider, capability or skill |
| harness-adapter | thin connection layer for one harness |
| vendor-managed | owned externally, and stays so |
| system-package | controlled by the OS or toolchain |
| project-local | confined to one checkout |
| planned / gated / blocked | install or verification not finished |
| BLOCKED | the task failed and scoped rollback was reported |

Lowercase blocked is not BLOCKED. Fail closed: an unknown owner pauses
the task; declared but unobserved stays planned, gated or blocked. No other
spellings.

## Approvals and failure

Gated, so the owner decides first, shown the command, its origin, version,
effects and undo: network-backed provider fetch or install; toolchain
changes; privileged runs; persistent services; destructive
migrations; swaps where ownership is in doubt; pushing aside a native
harness feature that works. Doubt about ownership, compatibility,
licence, permissions or rollback also pauses. Product and vendor edits
need separate authorization.

On failure: halt writes, reverse only what this task changed, and diff
hashes and status against the baseline with unrelated work intact. Report
BLOCKED with evidence, affected paths, the missing permission and a safe
next step. Rollback never licenses a gated retry. Any retry obeys the
ladder: count and budget carried (§§2–4), level records, CRITICAL never
autonomous (§§5–6), research first (§7), new method, real check (§§8–9),
residue checked, record OBSERVATION to NEXT_DECISION (§§10–11), owner
halts, lifecycle steps kept apart (§12).
