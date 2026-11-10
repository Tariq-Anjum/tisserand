---
name: thin-slice
description: Build a known change in thin end-to-end slices, each checked before the next. USE WHEN implementing and nothing fails. NOT FOR debug, clarify, plan, setup, verify or review.
disable-model-invocation: false
---

# Thin Slice

## Quick Index

- **First slice:** the narrowest path through every layer the change touches.
- **Gate:** name each slice's check before coding; never stack unchecked slices.
- **Scope:** unrelated problems are noted, not fixed.
- **Budget:** one first attempt plus at most three corrections, per the policy.

## Boundaries

Not this skill when:

- something already fails and the cause is unknown (debug);
- what to build, or what counts as done, is unsettled (clarify);
- a large effort needs ordering into steps before building (plan);
- a tool, package or binding must be installed or repaired (setup);
- the job is proving the finished change (verify) or judging finished work
  (review).

## Procedure

1. **Done-check.** Take the criteria from the request, a contract or a plan.
   If there are none, write down the check you will accept (command, test or
   observable result) before editing. If the target is ambiguous in a way that
   changes what gets edited, halt and ask.
2. **Cut.** Pick the first slice: one small behaviour that runs end to end
   through every layer involved (for example input, logic, storage, output),
   however narrow. Do not finish one layer before the others exist. A change
   that is one unit is its own single slice. If no part can be checked alone,
   say so and treat the whole change as one slice.
3. **Name the check** for that slice. Where possible run it first and see it
   fail or show the old behaviour.
4. **Build** only that slice, reusing project abstractions; add none it does
   not need. Take a checkpoint before any risky or hard-to-undo edit.
5. **Check.** Run the slice check and keep its output. Pass: go on. Fail: go to
   Corrections. A failure whose cause is unclear becomes a debug task that
   inherits the correction count used so far.
6. **Widen.** Add the next slice the same way, and rerun the earlier slice
   checks so a later slice cannot quietly break an earlier one.
7. **Close.** Run the nearest existing tests and linters around the touched
   code. List the problems you noted but left alone.

## Corrections

Building a slice the first time is attempt zero; its failure uses no budget.
Each repair after a failed check is one correction, at most three per task,
under the correction ladder
(`policy/correction-ladder.md`):

- the count never resets, also across a handoff to debug work: state the
  count in the handoff, and the debug work continues it, not a new attempt zero;
- each repair carries the preserved failure evidence, a named cause, a changed
  method and a bounded test;
- research first when the behaviour is external or uncertain; fresh targeted
  research before correction 2, deep research before correction 3;
- class each repair LOW, MEDIUM or HIGH as the policy defines them; write the
  policy's MEDIUM fields before a MEDIUM repair, and take a fresh checkpoint
  before each HIGH one.

Repeating an unchanged edit is forbidden.

## Stop and escalate

Halt and ask the owner when a slice or repair would touch security, authority
or authorization, credentials, real data, accepted architecture or identities,
activation, anything irreversible, or anything outside the authorized gate;
when you cannot show a repair is below CRITICAL; or when three corrections
have failed (write the policy's reassessment, then read-only work only).

## Report

Each slice with its check and output, the correction count, tests run, noted
problems, and what stays unverified. Slice checks are not acceptance: proving
the whole change and independent review remain separate where a gate needs
them.

<!-- provenance: original text (2026-11-07, rev 2026-11-09). Mechanisms
only, no source wording; licences unverified: mattpocock-02, pstack-06, kg-01.
Owner rules applied: global Engineering Workflow, Debugging Workflow and the
correction policy above. -->
