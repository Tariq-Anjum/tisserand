# Correction ladder

The rule every skill in this repository follows when a step fails and the
agent wants to try again. It is self-contained: nothing here depends on a
private file. Skills cite it as `policy/correction-ladder.md` and its
sections by number.

## 1. Why

Agents repeat failing actions with small variations until something turns
green. That hides the cause, piles up side effects and spends budget. The
ladder makes every retry a deliberate, recorded, bounded correction.

## 2. Terms

- **Attempt zero (ATTEMPT_0):** the first try at a step. Its failure costs
  no correction; it is evidence.
- **Correction:** any later change made because an earlier try failed:
  a code edit, a config change, a different command, a re-run with new
  arguments. A re-run with nothing changed is not a correction; it is not
  allowed (§8).
- **Campaign:** all tries aimed at the same goal in the same task, however
  the failure changes form.

## 3. Budget

At most **three** corrections per campaign, after attempt zero. Corrections
1, 2 and 3 may each be LOW, MEDIUM or HIGH (§5). A CRITICAL change is never
an autonomous correction.

## 4. The counter

- It never resets: not when the error message changes, not when a new
  hypothesis appears, not on a new day.
- It is carried across handoffs. Whoever passes the work on states the
  count and the correction history; whoever receives it continues from that
  count. Build, debug and verify work share one counter for one goal.
- Only the owner can grant budget beyond three (§12).

## 5. Levels

Classify each correction before making it, by the worst plausible effect:

| Level | Typical scope |
|---|---|
| LOW | local and trivially reversible: the task's own files, a test command, a typo |
| MEDIUM | behaviour across several files or config inside the task's scope; reversible with known steps |
| HIGH | shared state, public interfaces, data, dependencies, persistent services, or hard to reverse |
| CRITICAL | destructive or irreversible, credentials, security or authority boundaries, owner-held instructions, other projects |

When in doubt, take the higher level.

## 6. Records required per level

| Level | Before the change | After the change |
|---|---|---|
| LOW | the §11 record | verification result |
| MEDIUM | §11 record **plus** BOUNDARY (what may change, what must not) and ROLLBACK (exact undo steps) | verification, and confirmation nothing outside BOUNDARY changed |
| HIGH | everything MEDIUM needs **plus** a CHECKPOINT (a restorable snapshot or commit, named) | verification, then restore-test the checkpoint when practical |
| CRITICAL | stop; describe the change, its risk and rollback; wait for owner input | none: no autonomous action |

## 7. Research before corrections

- Any correction that depends on uncertain external or runtime behaviour
  (a library, a tool, a platform) needs research from current primary
  sources first.
- Before correction 2: fresh, targeted research on the specific failure.
- Before correction 3: deep research: several independent primary sources,
  version-checked, and a written comparison of the remaining hypotheses.

## 8. Changed method

Each correction states a root-cause hypothesis backed by evidence from the
last try and changes the method, not just the inputs. Repeating the same
action and hoping is forbidden.

## 9. Verification

Each correction ends with a bounded check that would fail if the hypothesis
were wrong. A correction is not done until that check has actually run;
an unrun check is reported as not run.

## 10. Side effects

Before any correction, inspect what the previous try left behind: files
written, processes started, state changed, partial migrations. Undo or
account for them first; never stack a new try on unknown residue.

## 11. Correction record

One record per correction, headed `COUNT n of 3, LEVEL <level>`, with
these fields in order (skills cite them as "OBSERVATION to NEXT_DECISION"):

1. OBSERVATION: what failed, with the evidence quoted exactly.
2. ROOT_CAUSE_HYPOTHESIS: the suspected cause and the evidence for it.
3. RESEARCH: the sources consulted, or "not needed" and why (§7).
4. CHANGE: what will be done and how its method differs from the last
   try (§8).
5. EXPECTED_RESULT: what the §9 check should show if the hypothesis holds.
6. ACTUAL_RESULT: what the check showed, or "not run".
7. NEXT_DECISION: stop, continue (the next correction), or escalate (§12).

MEDIUM and HIGH records add the §6 fields before CHANGE.

Keep the record with the work: in the reply, the handoff, or the task's
progress file. Failed records are never rewritten or deleted.

## 12. Stop and reassess

Stop autonomous correction and report to the owner when any of these holds:

- three corrections have failed: reassess the goal, the evidence and the
  hypotheses before anything else; a fourth corrective change needs
  explicit owner authorization;
- the next change is CRITICAL;
- ownership, authority, compatibility or rollback is unclear;
- a stricter project rule, accepted gate or independent review applies.

Read-only investigation may continue while stopped. Correcting,
verifying, accepting, publishing and activating are separate steps. Passing
one does not grant the next.
