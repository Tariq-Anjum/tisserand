---
name: session-reconcile
description: Check what a session changed against docs, agent instructions and memory; list each mismatch, fix only approved ones. USE WHEN records may lag reality. NOT FOR handoff notes or progress files.
disable-model-invocation: false
---

# Session Reconcile

## Quick Index

- **Start:** a session changed code, config, conventions or decisions, or
  a record looks out of date.
- **Ledger:** each touched record claim is MATCH, DRIFT, MISSING or
  UNCHECKED.
- **Edit:** approved or project-authorised fixes only; never on inference.
- **Status:** RECONCILED only when nothing is left open.

## Boundaries

Not this skill for a note that moves work to the next session or agent
(handoff), for in-flight progress state (file-based-planning), for
recording interview decisions (decision-interview), or for new docs no
change calls for. It does not judge the work itself.

## Procedure

1. **Changes.** List what really changed: working-tree diff, commits,
   commands with effects, decisions taken. Mark which changes are yours;
   never edit or take credit for others' uncommitted work.
2. **Records.** Find what could describe those changes: project docs, the
   repository's agent instruction files, and the memory store named by the
   owner's memory policy. Read the relevant parts.
3. **Ledger.** Per record claim a change touches:
   - MATCH: the record agrees with the evidence;
   - DRIFT: the record says one thing, the evidence another (cite both);
   - MISSING: a durable fact (convention, constraint, decision) has no
     record;
   - UNCHECKED: the record could not be read or verified.
4. **Propose** the smallest edit per DRIFT or MISSING. A durable fact
   carries its source and last-checked date; an old entry you cannot
   re-check is flagged stale, not trusted. For a rule corrected by hand
   again and again, propose a check or lint before more prose.
5. **Apply** only what the owner approved or the project's rules already
   allow. Never in vendored, generated or managed files, nor over changes
   you did not make; memory only through its configured interface and on
   material change, never per prompt. Re-read each edit. A failed write
   follows the correction ladder (`policy/correction-ladder.md`): first
   attempt, at most three
   corrections, count stated in any handoff.
6. **Status,** first match:
   - a fix conflicts with an owner rule or needs authority you lack: STOP;
   - a DRIFT or MISSING is neither fixed nor declined by the owner, or a
     record is UNCHECKED: OPEN;
   - every touched claim is MATCH, fixed and re-read, or declined:
     RECONCILED;
   - otherwise: OPEN.

## Report

Ledger, edits made (paths), proposals awaiting approval, declined items,
status.

<!-- provenance: original text (2026-11-09). Mechanisms only, no source
wording: gstack-03, pstack-01 (pstack-01 licence unverified). Owner rules:
shared memory governance, correction policy. -->
