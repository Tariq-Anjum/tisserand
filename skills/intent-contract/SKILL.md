---
name: intent-contract
description: Turn an unsettled request into a written contract with checkable done-criteria, then proceed or ask. USE WHEN goal, scope or done is unclear, or a plan needs critique. NOT FOR design, plans, known small edits, named interviews.
disable-model-invocation: false
---

# Intent Contract

## Quick Index

- **Output:** objective, limits, done-criteria, assumptions, gate.
- **Gate:** `go`, `ask` or `stop`; later steps start only on `go`.
- **Rule:** inspect before asking; assume when reversible; ask only what blocks.

## Boundaries

Not this skill when the open question is shape or structure (design), an
agreed goal needs ordering (plan), the change is known and small (implement),
or the user names an interview skill.

## Procedure

1. **Read.** Restate the request in a sentence. Inspect the workspace
   read-only; never ask what a file or command answers. If the user offers a
   plan or decision for critique, it is the draft: each weak or open branch
   becomes an unknown with your best guess.
2. **Draft.**
   - objective: the outcome, as the user would check it;
   - limits: in and out of scope, plus owner or project constraints;
   - done-criteria: each checkable by a command, an observable result or a
     named check; drop or rewrite any nobody could check;
   - repeated or automated work also gets a cap on rounds, a time or spend
     limit, and a stop and escalation rule.
3. **Sort unknowns.** Each open item is either
   - *assume*: a safe, reversible, cheap default exists; this wins, so list
     it as an assumption; or
   - *ask*: no such default, and the answer changes the deliverable, is
     costly or irreversible to get wrong, touches security, credentials, real
     data or authority, or two readings would change different things.
4. **Gate.**
   - `go`: no *ask* items; proceed with the assumptions listed.
   - `ask`: the fewest questions that unblock, at most three per round, each
     with a recommended answer; after two rounds, `go` on stated
     assumptions or `stop`.
   - `stop`: it conflicts with an owner rule, needs authority you lack, or
     cannot be met; say why and escalate.
5. **Record.** Keep the contract in the reply; write a file only when a later
   stage or session reads it, or on request; cite its path.

Asking while nothing blocks is a failure; so is guessing past a blocking item.
A new answer or a broken assumption reopens the contract: edit, then re-gate.

## Report

Contract, gate value, assumptions to confirm, file path if written. A contract
is an agreement, not evidence; verification proves its criteria later.

<!-- provenance: original text (2026-11-07, rev 2026-11-08). Mechanisms
only, no source wording; licences unverified: mattpocock-01, kiro-01,
ondrej-01, speckit-01. Owner rules applied: global Agent Behavior and
Engineering Workflow. -->
