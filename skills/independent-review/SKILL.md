---
name: independent-review
description: Judge finished work or a done claim: test each claim against evidence, track coverage, confirm findings before rating, rule-based verdict. USE WHEN asked if work is ready. NOT FOR your own change, debug or fixing.
disable-model-invocation: false
---

# Independent Review

## Quick Index

- **Stance:** the author's summary is a list of claims, not evidence.
- **Hands-off:** change nothing tracked in the work under review; report only.
- **Unit:** every claim gets a state; every finding needs a trace.
- **Verdict:** from claim states and coverage, never from finding counts.
- **Elsewhere:** your own change goes to verify, an unknown-cause failure to
  debug, a build or fix to implement. With final-audit loaded for code, its
  checks run as Phase B passes; the states and ruling here govern.

## Phase A: pin the target

- [ ] Target fixed: the request or criteria it answers, project
  instructions, the diff or files, every claim made (done, safe, ready,
  tests pass). Several fit: say so, review the best-supported one.
- [ ] Claims numbered. Required ones come from the request, its criteria,
  project rules or a done or ready statement; ones you add are optional.
  None stands because a summary, test report, model or earlier review
  asserts it. One resting on external facts needs primary sources.
- [ ] Units listed (files, criteria, interfaces, config) before deep
  reading. A unit a required claim depends on is critical. Coverage is what
  you actually inspected; report the rest.

## Phase B: gather evidence

- [ ] Authorized existing checks run or read before judging by reading.
  They may write only untracked output (caches, builds, reports) in ignored
  paths or scratch space; list it. A check that would change tracked files,
  data or services is skipped and its claim marked UNTESTABLE. An exit
  status is not the outcome. Keep first failures; never rerun until green.
- [ ] A answered: was what was asked actually built?
- [ ] B answered: is it sound (correctness, regressions, failure handling,
  security and authorization, input validation, concurrency, retries,
  resources, architecture fit, missing tests)? Only what the changed
  surface needs.

## Phase C: suspicion to finding

A candidate stays unconfirmed until its path from input to effect is
re-derived; otherwise drop it. Where risk warrants (security, authority,
data, concurrency), add an adversarial pass on the changed surface. No
finding quota; a failed attempt to break a claim is evidence too.

Confirmed means location, preconditions, path, violated rule and observable
impact are stated; only then a severity and a suggested correction. Missing
a field, it is a note. A blocker falsifies a required claim or breaks
security, authorization, data integrity or an accepted rule; others are
major or minor.

## Claim states

Each claim gets one, with its evidence: VERIFIED, FALSIFIED,
PARTIALLY_VERIFIED, UNTESTABLE or NOT_APPLICABLE. NOT_APPLICABLE needs a
cited reason from the claim's source; otherwise UNTESTABLE.

## Ruling, first match wins

| Condition | Ruling |
|---|---|
| a required claim FALSIFIED, or a confirmed blocker | FAIL |
| a required claim PARTIALLY_VERIFIED, UNTESTABLE or stateless, or critical scope uncovered | BLOCKED |
| major or minor findings, other uncovered scope, optional claims not VERIFIED, or named risks remain | PASS WITH WARNINGS |
| required claims VERIFIED or NOT_APPLICABLE, full coverage, nothing open | PASS |
| anything else | BLOCKED |

## Retry accounting

Nothing in the work is corrected here. Carry the author's correction count
into the record; a later fix continues it under the correction ladder
(`policy/correction-ladder.md`), never from a new attempt zero. Repairs to
your own check invocations follow it too: inspect the last attempt's side
effects (section 10), record the section 11 fields (OBSERVATION to
NEXT_DECISION), no counter reset, research first and as staged, MEDIUM
fields, a checkpoint before HIGH.

## Owner halts

Halt and ask the owner when the review would need changes to the work, real
credentials or data, production access or actions outside the authorized
gate, or when ownership of the target is unclear. A ruling is not
acceptance; the owner or the gate decides.

## Hand-off record

Scope, inventory and coverage; claim table; confirmed findings by severity;
dropped candidates; ruling and the row that matched; correction count
carried; what was not verified; residual risk. If nothing material was
found, say so plainly.

<!-- provenance: original text (2026-11-08, rev 2026-11-10 H4 restructure);
extends final-audit. Mechanisms only, no source wording; licences
unverified: tob-01, tob-02, tob-03, mattpocock-03, addy-06, ondrej-02.
Owner rules: Reviews and Audits, Completion Standard, owner audit decision
(claim states, verdict), correction policy. -->
