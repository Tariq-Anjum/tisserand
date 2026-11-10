---
name: fault-loop
description: Diagnose and repair an observed failure (error, crash, wrong output, failing test or check) by proving the cause before changing anything. USE WHEN something already fails and the cause is unknown. NOT FOR new work with nothing failing, a tool or skill the agent cannot see, checking your own finished change, or judging someone else's finished work.
disable-model-invocation: false
---

# Fault Loop

## Quick Index

- **Gate:** no edit until the failure is observed and a cause is named.
- **Loop:** observe, collect, suspect, make a single edit, observe again, widen.
- **Budget:** one first attempt plus at most three corrections, per the owner policy.
- **Stop:** anything the policy calls CRITICAL, or a fourth correction.

## Boundaries

Not this skill when:

- nothing is failing and the task is a planned change (implement);
- a tool, MCP server or skill is missing or invisible (setup);
- the job is proving your own change meets its criteria (verify);
- someone asks whether finished work is ready (review).

## Procedure

Never guess forward past a step. If a step hits a recoverable obstacle (a
broken probe, a wrong suspicion, a flaky tool), treat it as a failed attempt
and go to Corrections. Halt only on the conditions under Stop and escalate.

1. **Observe.** Trigger the symptom yourself with the smallest command or
   input that shows it. Record that command and its exact output. If it will
   not appear, report what you tried; do not patch an unseen fault.
2. **Collect.** Read logs, versions, recent diffs, config and the code on the
   failing path. Write down facts, separate from guesses.
3. **Suspect.** Name one cause that explains every recorded fact, plus what
   result would prove it wrong. Run that test before editing. External or
   version-dependent behaviour needs primary-source research first.
4. **Change.** Make the smallest edit that removes the cause, not the symptom.
   Before a risky edit, take a checkpoint and confirm it restores.
5. **Re-observe.** Repeat the step-1 command unchanged. The symptom must be gone
   for the stated reason; a green exit code alone is not proof.
6. **Widen.** Run the nearest existing tests or checks around the touched code
   and report any new failure.
7. **Settle.** If the same class of fault has recurred, propose moving the
   guard into code, a type, lint or a test rather than a note.

## Corrections

Your first pass through steps 3 to 6 is attempt zero and uses no budget,
unless the work arrives with a count from build or verify work; then it is
the next correction. Each later pass, started because a step failed, is one
correction, at most three per task in total. Obey the correction ladder
(`policy/correction-ladder.md`):

- the counter never resets, even if the error looks new;
- each cycle carries fresh evidence, a new suspected cause and a changed method;
- new research before correction 2, deeper research before correction 3;
- MEDIUM and HIGH cycles record the fields that policy demands.

Repeating an unchanged action after a failure is forbidden.

## Stop and escalate

Halt and ask the owner when a fix would touch security, authority, accepted
architecture, credentials, real data or anything irreversible; when three
corrections have failed (write the policy's reassessment, then read-only work
only); or when the fault cannot be observed and no safe probe remains.

## Report

Give the reproducer, the cause with its evidence, the change, before and after
output, checks run, the correction count, and what stays unverified. A fix is
not acceptance; independent review still applies where a gate demands it.

<!-- provenance: original text (2026-11-07, rev 2026-11-08). Mechanisms only, no
source wording: superpowers-03 (observe before fixing), superpowers-01/testmu-01
merge (pass condition fixed in advance), suite32-05 (recovery checkpoint that is
tested; licence unverified, mechanism only), pstack-01 (recurring fault moves
into structure; licence unverified, mechanism only). Owner rules applied:
global Debugging Workflow and the correction policy above. -->
