---
name: file-based-planning
description: Keep a long task's progress, findings and dead ends in files so a reset or crash resumes from disk. USE WHEN work is long-running. NOT FOR ordering steps, handoff notes or doc drift.
disable-model-invocation: false
---

# File-Based Planning

## Quick Index

- **Start:** long-running work that a reset or crash would cost.
- **Keep:** goal pointer, phases, findings, dead ends, next action.
- **Resume:** read the files, then check them against the workspace.
- **Status:** CURRENT only with every phase stated and a next action.

## Boundaries

Not this skill for work that fits in one exchange, for ordering an agreed
goal into steps (plan; cite it), for a note that moves work to another
session or agent (handoff, named only), or for drift in docs, agent
instructions or memory (document). A written check is not proof: proving
your own change is verify.

## Procedure

1. **Place.** The project's working-notes location, or one the user
   names. Never a vendored, generated, managed or protected path, nor
   a file holding changes you did not make. No safe place: keep the state
   in the reply and say why. Never store secrets.
2. **Seed.** Goal and done-criteria by path to the contract or plan; each
   phase in one state (TODO, ACTIVE, DONE, BLOCKED); the next action.
3. **Write on events,** never on a timer: a phase changes state; a fact is
   learned (with its source); an approach fails (what, evidence; never
   retried unchanged); a choice is made (option, reason). Append; fix
   entries by dated correction, never by deletion.
4. **Re-read** the goal and next action before each phase, before any
   major action (irreversible, shared or costly) and after any reset.
5. **DONE needs a check.** Cite the check and result; otherwise the phase
   stays ACTIVE.
6. **Failures.** A failed check or write follows the
   correction ladder (`policy/correction-ladder.md`):
   first attempt, at most three
   corrections per campaign. Record its count and history; they carry
   across changed symptoms and sessions, never reset.
7. **Resume.** Read the files first; check each DONE entry and the next
   action against the workspace, as files go stale. Restart
   an ACTIVE phase at its last step; check a step's effect before
   repeating it unless repeating is harmless.
8. **Status,** first match:
   - the place is unsafe, the content needs a secret, or a step needs
     authority you lack: STOP;
   - an entry contradicts the workspace or cannot be checked, or the last
     write failed: STALE (list them; repair first);
   - each phase has a state and the next action is written: CURRENT;
   - otherwise: STALE.

## Report

Paths, phase states, next action, open campaigns and counts, status.

<!-- provenance: original text (2026-11-09). Mechanisms only, no source
wording: pwf-01, suite32-03, addy-04 (licences unverified). Owner rules:
Engineering Workflow, correction policy. -->
