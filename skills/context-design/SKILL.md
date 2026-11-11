---
name: context-design
description: "Design what an agent loads, when and at what cost: a load map giving each context source a tier, trigger, budget and check. USE WHEN designing or tracing context loading. NOT FOR installs, app code or UI."
disable-model-invocation: false
---

# Context Design

## Quick Index

- **Output:** a load map (source, tier, trigger, budget, check).
- **Writes:** only the map; other files stay unchanged.
- **Fail-closed:** a source missing any field keeps the map OPEN.

## Boundaries

Not this skill when installing or binding a capability (setup), shaping app
code, data or a user interface (other design), recording what already exists
(document), or settling why it is wanted (clarify). A context failure is
traced here (step 7) and fixed as debug work.

## Procedure

1. **Inventory.** Read only. List each source an agent can receive:
   instruction files, index entries, skill bodies, references, tool
   definitions, memory, retrieved files, tool output. Note each one's size
   in bytes and its owner.
2. **Decision unit.** Per task kind, name the smallest unit that decides
   it: an index line selects; a body guides once selected; a reference or
   asset loads when a step asks for it.
3. **Tier.** Give each source the lowest tier that serves its decisions:
   - always: routing and owner rules every task needs;
   - on match: a body, after its index entry is selected;
   - on demand: references, assets, long examples a step asks for;
   - never: duplicates, generated copies, stale material.
   Raising a source to always needs its measured cost and, under an owner
   budget, owner approval.
4. **Authority.** Text carries procedure. Live data, credentials and
   permissions come from tools, which the text names and never embeds.
5. **Durable state.** State that must outlive a reset lives in a file that
   is re-read, not in the conversation.
6. **Budget and check.** Per tier, a byte or token cap and a check that
   measures it (size count, load trace). Cut any source no decision uses.
7. **Trace a failure** (wrong, missing or excess context). Record what
   loaded, with sizes; compare with the map; name the first divergence
   (tier, trigger or budget). Hand it with evidence to debug work, whose
   repairs follow the correction ladder
   (`policy/correction-ladder.md`), count carried.
8. **Status,** first match:
   - the change touches owner-held always-loaded instructions, another
     project's files, or authority you lack: STOP;
   - a source lacks a field, or a measured total exceeds its cap: OPEN;
   - otherwise: READY.

## Report

Load map, per-tier totals against caps, divergences, status, open items.
READY is a design, not proof; re-measure after the change.

<!-- provenance: original text (2026-11-09). Mechanisms only: aspec-01,
aspec-02, pwf-01 (licences unverified). Owner rules: Context Discipline,
Resource Discipline, correction policy. -->
