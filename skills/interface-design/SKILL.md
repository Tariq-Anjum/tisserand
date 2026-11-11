---
name: interface-design
description: "Decide a user interface's shape before building: states, layout, input paths, and a check plan of run and judged items. USE WHEN designing a UI, screen, TUI or theme. NOT FOR building, proving or reviewing it."
disable-model-invocation: false
---

# Interface Design

## Quick Index

- **Output:** a brief (surface, path, layout, states) and a check plan.
- **Split:** each check is RUN (executed or inspected) or JUDGED (criteria, decider).
- **Fail-closed:** an open required check is never ready.
- **Generic:** no platform or app-type depth; project conventions win.

## Boundaries

Not this skill when building it (implement), proving your own built change
(verify), judging finished work (review), shaping code, data or services
without a user surface (other design), settling goal or done (clarify), or
ordering the build (plan). Authorship does not change the type:
redesigning your own or another's surface is design; checking a built one
is verify for your change, else review. The brief's author never reviews
it.

## Procedure

1. **Surface.** Name it (web page, app screen, terminal UI, widget) and its
   inputs (pointer, touch, keyboard, screen reader). If an unknown surface
   or user goal would change the design, halt and ask.
2. **Inventory.** Read only: tokens, components, platform conventions,
   project rules. Reuse first; list reused and new parts.
3. **Brief.** Main task path; layout at small, normal and large sizes;
   element states (default, focus, hover, active, disabled, loading, empty,
   error, success); long text; motion, reduced form; values per theme.
4. **Bar.** The project's named accessibility conformance level; with none,
   propose one and ask: until the owner confirms it, checks it sets stay
   open. Stricter levels and spacing grids only where adopted.
5. **Check plan.** Per requirement: method, pass threshold, failure
   observation; required unless its source says optional. RUN only with a
   named tool, script or inspection step; otherwise JUDGED. Candidates:
   - contrast of text and controls, computed from token values;
   - theme parity: each token has a value per theme, each pair passes;
   - keyboard path: a scripted key walk operates every action, focus order
     follows reading order, focus stays visible;
   - reduced motion: with the setting on, only motion marked essential runs;
   - no clipping or overflow at the named window or terminal sizes;
   - web or app controls expose a name and role; a terminal UI restores
     the terminal on exit.
   JUDGED checks (hierarchy, clarity, convention fit, copy) need written
   criteria and a decider. A check that is neither, or a RUN probe still
   failing to run when the budget ends, is UNTESTABLE.
6. **Baseline,** only if a surface exists: run build-free RUN checks (e.g.
   contrast from a token file) as scratch probes; keep outputs; change
   nothing tracked.
7. **Status,** first match:
   - a requirement conflicts with an owner or project rule, or needs
     authority you lack: STOP;
   - a required check is UNTESTABLE, rests on an unconfirmed bar or
     assumption, lacks an answer, or a baseline failure is left
     unaddressed: OPEN;
   - every required check has method, threshold and failure observation,
     or criteria and decider: READY_FOR_BUILD;
   - otherwise: OPEN.

READY_FOR_BUILD is not proof. The build takes the plan and the probe
correction count (continued in the same task); the result is verified
against the plan, reviewed where gated. Never claim compliance.

## Corrections

Repairs touch only your probes: first run attempt zero, then at most three
corrections per task under the correction ladder
(`policy/correction-ladder.md`): no reset, count
stated in handoffs; side effects inspected (section 10); OBSERVATION to
NEXT_DECISION (section 11), changed method; research when uncertain, fresh
before correction 2, deep before 3; MEDIUM fields first; checkpoint before
HIGH. Never rerun an unchanged probe.

## Stop and escalate

Ask the owner before real user data, credentials, production, a brand or
legal claim, or work outside the gate; when you cannot demonstrate that a
repair is below CRITICAL; after three failed corrections (reassess, read-only).

## Report

Brief; check table (kind, method, threshold, failure sign, state);
baseline; assumptions; status; correction count; open items.

<!-- provenance: original text (2026-11-08, rev 2026-11-09). Mechanisms
only: ifd-01 (no platform packs), ifd-02, ifd-03, ifd-04 (licence
unverified). Owner rules: Engineering Workflow, correction policy. -->
