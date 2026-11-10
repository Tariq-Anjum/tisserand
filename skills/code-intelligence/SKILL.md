---
name: code-intelligence
description: Trace code structure (symbols, references, callers, implementations, diagnostics) through a semantic tool adapter, with text search as a labelled fallback. USE WHEN tracing code structure. NOT FOR exact text, edits or outside facts.
disable-model-invocation: false
---

# Code Intelligence

## Quick Index

- **Use for:** symbols, overviews, references, callers, declarations,
  implementations and diagnostics across files.
- **Not for:** exact text, one known small file, edits, builds, tests, Git.
- **Adapter:** tool steps live in `adapters/<tool>/README.md` in the skills
  source root; this text names no tool.
- **Labels:** SEMANTIC or CANDIDATE findings; CONFIRMED needs every question.
- **Read-only:** output grants no approval, policy or memory authority.

## Boundaries

Not this skill for an exact string or a file you already know (search or
read it directly), outside facts (research), changing code (implement), or
finding a failure's cause (debug, which may call on this for tracing).

## Procedure

1. **Question.** List each structural question asked and the exact
   checkout. If one known small file answers them, read it and stop.
2. **Adapter.** Read the adapter of the semantic tool. Use it only if it
   binds to this exact checkout, never a parent workspace or another
   worktree. A stopped tool is available: the adapter's checkout-scoped
   query may start it and stops a server it started. Unavailable (not
   installed), bound elsewhere, or costlier than the question: step 4.
   Never install or reinstall a tool or language server; that is setup
   work behind the owner's gate.
3. **Query narrowly.** One read-only query per question (overview first if
   it helps). Mark each question ANSWERED (the query ran, an empty result
   included: "none found"), FAILED or SKIPPED. Keep relative paths and line
   ranges as returned; re-read current source where a result looks stale.
   These findings are SEMANTIC.
4. **Fallback.** For questions not ANSWERED: the editor's navigation, else
   text search. These findings are CANDIDATE: possible matches only.
5. **Status,** first match:
   - no question ANSWERED: CANDIDATES;
   - a question FAILED or SKIPPED, or a claim rests on a CANDIDATE: PARTIAL;
   - otherwise (every question ANSWERED): CONFIRMED.

## Corrections

A failed start or query is retried only as a correction under the
correction ladder (`policy/correction-ladder.md`): changed method, at most
three, count
stated in any handoff; never an unchanged repeat. Otherwise fall back.

## Stop

Refuse any edit, refactor, shell, memory or onboarding call a tool offers.
Ask the owner before installing anything or binding a tool to another
checkout.

## Report

Questions with their marks, checkout, adapter used or why not, findings with labels and
path:line, status, and what stays unconfirmed.

<!-- provenance: original text (2026-11-09; replaces our own 2026-10-03
text). Mechanisms only: aspec-02, pstack-03 (licences unverified). Owner
rules: Context Discipline, correction policy. -->
