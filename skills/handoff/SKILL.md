---
name: handoff
description: Write a continuation note so another session or agent resumes in-flight work from checked state, open items, dead ends and pointers. USE WHEN named. NOT FOR durable docs or progress files.
disable-model-invocation: true
---

# Handoff

## Quick Index

- **Start:** only when named; never inferred.
- **Note:** next action first, then item states, dead ends, carry-overs.
- **Point, do not copy:** plans, specs and progress files go by path.
- **Never:** call work done with an item open, or pass on authority.

## Boundaries

Not this skill when nobody named it, when durable records must match
reality (document), when in-flight state must outlive resets
(file-based-planning, whose files the note cites), or when the next move
is ordering the work (plan). It changes no code, plan or record.

## Write

1. **Gather,** read only: the request or contract, plan and progress
   files, working-tree status, checks run and their output.
2. **Next action** first: one concrete step to start.
3. **Items.** Each requested item gets one state:
   - DONE: a check ran and passed; cite it and its result;
   - UNVERIFIED: edited or claimed, not yet checked;
   - OPEN: unstarted or unfinished;
   - BLOCKED: waiting on a named person, input or gate.
   Your own edits stay UNVERIFIED until a check passes.
4. **Dead ends.** Each failed approach with its evidence, so nobody retries
   it unchanged.
5. **Carry-overs.** Each correction campaign under the
   correction ladder (`policy/correction-ladder.md`):
   its accumulated count and
   history, kept when the failure changed form; the receiver continues it,
   never resets it. Approvals with their scope; pending gates; uncommitted
   changes and whose they are.
6. **Pointers.** Decisions, specs and files by path; no copies, no secrets.
7. **Place.** In the reply, unless the user names a file or the receiver
   cannot read the reply; then one file in a safe place (never vendored,
   generated, managed or protected, nor over changes you did not make),
   re-read after writing.

Steps 2-6 are required parts; an empty one says "none".

## Status

First match:
- the note would need a secret or pass on authority the owner did not
  grant, or a required file has no safe place: STOP;
- a required part is missing, an item has no state, a DONE has no check,
  or the file write failed or reads back wrong: INCOMPLETE;
- every required part present and the note delivered: READY;
- otherwise: INCOMPLETE.

READY means the note is complete, not the work: any item OPEN,
UNVERIFIED or BLOCKED leaves the work unfinished.

## Resume

The receiver reads the note, then re-checks each DONE item and the
working tree before acting; a claim that fails becomes OPEN.

<!-- provenance: original text (2026-11-09). Mechanisms only, no source
wording: gstack-04, pwf-01, addy-04 (pwf-01, addy-04 licences unverified).
Owner rules: Agent Behavior, correction policy. -->
