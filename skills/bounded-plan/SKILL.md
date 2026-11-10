---
name: bounded-plan
description: Order an agreed goal into a sized plan of checked steps, or a typed ticket map when multi-session work has an unclear route. USE WHEN the goal is settled. NOT FOR unclear goals, architecture or building.
disable-model-invocation: false
---

# Bounded Plan

## Quick Index

- **Input:** an agreed objective; none, halt and ask (step 1).
- **Output:** checked steps, or tickets when sessions span an unclear route.
- **No build:** writes only its plan file or tickets.

## Boundaries

Not this skill when the goal or definition of done is unsettled (clarify),
the open question is the solution's shape (design), or a plan exists and the
next move is building it (implement). Long-running progress files belong to
file-based-planning.

## Procedure

1. **Check input.** Find the objective and done-criteria in the request, a
   contract or a cited file. Objective missing, or two readings would change
   different things: halt with that question; never invent a goal. For a
   clear goal, draft missing criteria as assumptions.
2. **Mode.** Tickets only if both hold: the work spans several sessions,
   and which stages come in what order is not yet known. Either false or
   unknown: steps. A call by the old name takes this test.
3. **Size and ground.** One unit of change is one step and its check. Read
   the affected code, config or docs without changing them.
4. **Write steps.** Each: outcome, files or areas, what it waits on, its
   check (command, test or observable result), criterion.
5. **Trace.** Every criterion has a step; drop or justify a step serving none.
6. **Order.** Dependencies first, then the earliest checkable result; risky
   or irreversible steps get a checkpoint and an owner gate.
7. **Bound.** A failed check goes to correction under the owner's
   correction ladder (`policy/correction-ladder.md`), count stated in any
   handoff.
   Revise a wrong plan with a dated reason.
8. **Hand off.** Used by a later stage or session: one file, path cited;
   else keep it in the reply.

## Ticket mode

Steps 4-6 yield tickets: outcome, done-check, criterion, blocking tickets,
and one task-type label (design, research, implement...), never a skill
name; the router picks each ticket's capability. No cycles; mark what can
start now; detail ready tickets, refine the rest when reached. Write them
into the project's existing tracker when you have access and posting is
authorised; else put the map in the plan file and name what is missing.
Never work a ticket: each is its own routed task, research ones isolated.

## Report

Plan or map location, criterion-to-step table, ready tickets, assumptions,
risks, open questions. A step is done only when its check passes.

<!-- provenance: original text (2026-11-07, rev 2026-11-09). Mechanisms
only: gstack-04, bmad-02, pwf-01, kiro-01, ondrej-01 (three licences
unverified). Owner rules: Engineering Workflow, correction policy,
D5 composition. -->
