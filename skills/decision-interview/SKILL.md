---
name: decision-interview
description: Settle each open branch of a plan or decision, one question per turn with a recommended answer; record mode keeps only pinned terms and qualifying decisions. USE WHEN named. NOT FOR unnamed clarifying, design, plans or building.
disable-model-invocation: true
---

# Decision Interview

## Quick Index

- **Start:** only when named; never inferred.
- **Turn:** one question, with a recommended answer and reason.
- **Close:** first-match status; an unengaged branch stays OPEN.
- **Writes:** nothing, except record mode with a safe target.

## Boundaries

Not this skill when nobody named it (unnamed clarify work), the open
question is a shape (design), an agreed goal needs ordering (plan), or the
work is building. It never edits code, plans or specs.

Old names, kept for one release: `grill-me` opens interview mode;
`grill-with-docs` opens record mode.

## Interview

1. **Branches.** Read the plan or decision; inspect the workspace read-only.
   List its open branches: choices, unstated assumptions, risks, ordering.
   Settle by reading what a file or command answers; ask only where the
   answer changes the plan.
2. **Ask.** One branch per turn, most consequential first, with your
   recommended answer and why; the user confirms or corrects it.
3. **Weigh.** A bare assent on a contested branch gets one sharper follow-up.
   Still unengaged: the branch stays OPEN, your recommendation noted.
4. **Track.** Each branch is RESOLVED (the user decided), ASSUMED (the user
   accepted a stated default) or OPEN. New branches join the list.
5. **Status,** first match:
   - a branch conflicts with an owner rule or needs authority you lack: STOP;
   - any branch OPEN: OPEN (the user may stop; list open ones);
   - otherwise: SETTLED.

## Record mode

Only when the user asks to record terms or decisions, or opens it by the
record name above, and only with a safe target: a writable place in the
project's own repository that already holds its decisions or glossary, or
one the user names; never a vendored, generated, managed or protected path,
nor a file with changes you did not make. No safe target: write nothing,
put records in the reply, say why.

- **Terms:** only those whose meaning the user pinned this session.
- **Decisions:** only those meeting all three bars: real alternatives were
  argued; undoing it is costly; without a record someone would have
  to rebuild the reasoning.
- Nothing pinned: nothing written. Append; never rewrite earlier records.
- A failed write follows the correction ladder
  (`policy/correction-ladder.md`): first attempt, at
  most three corrections, count stated in any handoff.

## Report

Branches (state, answer or default), status, record paths or "none".

<!-- provenance: original text (2026-11-09). Mechanisms only, no source
wording: mattpocock-01, gstack-04, pwf-01 (licences unverified). Owner
rules: Agent Behavior, correction policy. -->
