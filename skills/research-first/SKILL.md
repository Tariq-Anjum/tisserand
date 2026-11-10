---
name: research-first
description: Research current or uncertain external technical facts before deciding when freshness, versions, evidence, or real-world experience could materially change the answer.
disable-model-invocation: false
---

# Research First

## Quick Index

- **Trigger:** a decision hangs on an outside fact that may be stale,
  version-bound, disputed, thinly documented or known only from use.
- **Process:** name the open question, climb the source ranking, test fit
  to this version and platform, corroborate, then report labelled claims.
- **Verification:** read the source itself, not a search snippet; settle
  conflicts with code, changesets, issues or a runnable check.
- **Halts:** decision saturation, a spent retrieval budget, or unclear
  authority, ownership, compatibility or rollback
  (`policy/correction-ladder.md` §12).
- **Not for:** work the repository alone can settle; having a browser is
  not a reason to search.

## Research loop

1. **Name the question.** State the decision and the one external fact it
   waits on. No specific doubt, no search.
2. **Find, then read.** Search to get candidates, then fetch the actual
   text. Batch fetching only for pages already chosen.
3. **Rank.** Take sources in the order of the table below. Experience
   reports count as testimony, not proof.
4. **Fit check.** Run the applicability sheet before relying on anything.
5. **Break ties in the code.** When sources disagree, go to source code,
   commits, issue threads or a check you can run.
6. **Corroborate what is costly.** Architecture, migrations, purchases,
   security and implementation choices get independent support where it
   can be had. Stop collecting once new sources would not change the
   decision.
7. **Report.** Lead with what the decision needs, then the tradeoffs and
   what is still uncertain. Cite support for every consequential claim. If
   the evidence cannot carry a firm answer, say so.
8. **Keep context lean.** Pull only decision-relevant extracts; leave the
   rest out. Long dependency planning goes to bounded-plan.

## Source ranking

| Rank | Source |
|---|---|
| 1 | official specs and documentation |
| 2 | source code, changelogs, release notes |
| 3 | original technical research and papers |
| 4 | upstream issues, pull requests, maintainer threads |
| 5 | model repositories and model cards, where relevant |
| 6 | specialist project or distribution forums |
| 7 | general community reports (testimony) |

## Applicability sheet

- [ ] Publication date and the versions it covers
- [ ] Operating system, platform and environment assumptions
- [ ] Whether a reported bug is still open
- [ ] Docs match the release actually in use
- [ ] A benchmark's workload matches the claim it is cited for
- [ ] Old evidence is flagged as old, never quietly carried over

## Claim labels (fail-closed)

Tag each claim as one of: established fact, vendor claim, community
report, inference, recommendation, unknown. If the grade is in doubt, use
the weaker one. Many matching anecdotes stay a community report. A
consequential conclusion resting only on snippets is rejected. A question
that retrieval could not settle is reported as unconfirmed.

## Tools

Resolve search and fetch tools through `adapters/web-research/README.md`
and the host's configured bindings; guess no paths. Machine registration
stays out of this text. A missing tool is disclosed, not installed or
repaired here.

## Retrieval retries

- A failed retrieval is ATTEMPT_0 (§2). Each later try is a correction:
  three at most (§3), each with a different query, source or mechanism
  (§8) and a check that could fail (§9). Classify and add MEDIUM/HIGH
  fields as required (§§5–6); look at what the last try left behind (§10).
- Any handoff states the current count and history (§4) and keeps the
  record OBSERVATION to NEXT_DECISION (§11).
- Research done for another campaign spends none of that campaign's
  corrections; it goes into that campaign's RESEARCH field. That campaign
  needs fresh targeted research before its correction 2 and deep research
  before its correction 3 (§7).
- Budget spent: the question stays unconfirmed; stop and report (§12).

## Halts

Stop when further sources cannot change the decision, when the retrieval
budget is spent, or when authority, ownership, compatibility or rollback
is unclear. Halt before any CRITICAL or gated action. Report access you
could not get and conclusions you could not support.

## Neighbours

- **bounded-plan** orders an agreed goal into steps; this skill
  substantiates its external premises. Goals still unsettled are not
  bounded-plan's to plan.
- **final-audit** sends changing external premises here.
- Installing tools or repairing bindings is outside research.
