---
name: proof-gate
description: Prove your own change meets its criteria with checks run now, one evidence record per criterion; unproven is not done. USE WHEN checking your work before calling it done. NOT FOR review, debug or building.
disable-model-invocation: false
---

# Proof Gate

## Quick Index

- **Gate:** no done claim without evidence observed in this step.
- **Unit:** one record per criterion; its fail condition is written first.
- **Fail-closed:** missing, stale or partial evidence is never a pass.
- **Budget:** one first attempt plus at most three corrections, per the policy.
- **Elsewhere:** finished work or a done claim goes to review, a check
  failing for an unknown cause to debug, an unbuilt change to implement,
  unsettled criteria to clarify.

## Criterion sheet, written before any run

| Field | Fill with |
|---|---|
| Criterion | from the request, a contract, a plan or project rules; none exist: write yours, mark them assumed. Required unless its source marks it optional. One you cannot state or check counts as UNTESTABLE |
| Check | command, test, probe or direct read |
| Expected | the observation that means it holds |
| Fail condition | the observation that means failure; an exit status alone never suffices |

## Evidence sources, strongest first

Executed, deterministic, project-owned checks come first. A system-wide
claim needs an executed check; reading settles only local claims. If
nothing covers a criterion, add a disposable probe in scratch space, built
from a real output's properties.

Run every check now, after the last edit; earlier runs, others' reports
and memory do not count. Keep the command, the observed output or a located
excerpt, and relevant environment facts.

Excuses that do not count: "it passed earlier" (run it now), "the change is
tiny" (the check still runs), "exit code 0" (compare the observation).

## Criterion states

No criterion is left without one: VERIFIED, FALSIFIED, PARTIALLY_VERIFIED,
UNTESTABLE (say why) or NOT_APPLICABLE. NOT_APPLICABLE needs a cited reason
from the criterion's own source or scope that it does not cover this
change; without one, use UNTESTABLE. A check that cannot run is repaired
under the budget below, not counted against the change.

## Gate outcome, first match

| Required criteria | Outcome |
|---|---|
| any FALSIFIED | FAIL |
| any PARTIALLY_VERIFIED or UNTESTABLE once no repair within the remaining budget can supply evidence (policy section 12) | BLOCKED |
| all VERIFIED or NOT_APPLICABLE | PASS_PENDING_REVIEW |

Optional criteria never block; with no match yet, repair first. Never round
up; a later pass does not erase an earlier failure. FAIL with a clear cause
returns to the build work; with an unknown cause it becomes debug work.
State the correction count so far; the receiving work continues it.

## Repair budget for the evidence mechanism

Repairs touch only the evidence mechanism (probe, flag, fixture), never the
change under proof. The first run is attempt zero; each later repair is one
correction, at most three per task including any count inherited from
build or debug work, under the correction ladder
(`policy/correction-ladder.md`):

- the counter never resets, also across handoffs;
- before a repair, inspect the last attempt's side effects (section 10);
  record OBSERVATION, ROOT_CAUSE_HYPOTHESIS, RESEARCH, CHANGE,
  EXPECTED_RESULT, ACTUAL_RESULT and NEXT_DECISION (section 11), with a
  changed method and a bounded test;
- research first when behaviour is uncertain; fresh targeted research before
  correction 2, deep research before correction 3;
- class repairs LOW, MEDIUM or HIGH; MEDIUM fields first, a fresh checkpoint
  before each HIGH.

Never rerun an unchanged check until green; flaky stays flaky.

## Owner halts

Halt and ask the owner when a check needs real credentials or user data,
production, an irreversible action or anything outside the authorized gate;
when a criterion could pass only by weakening it or its check; when a repair
cannot be shown below CRITICAL; or after three failed corrections (write the
policy's reassessment, then read-only work only).

## Evidence record handed on

Per criterion: check, fail condition, evidence, state. Then the outcome, the
correction count, and what stays unverified. PASS_PENDING_REVIEW is not
acceptance; gated independent review still applies.

<!-- provenance: original text (2026-11-08, rev 2026-11-10 H4 restructure).
Mechanisms only, no source wording: superpowers-02, verif-01, verif-02,
verif-04, pstack-05, speckit-01 (mapped to claim states), addy-05; licences
unverified except superpowers. Owner rules: Completion Standard,
Engineering Workflow, owner audit decision (claim states), correction
policy. -->
