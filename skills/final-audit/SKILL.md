---
name: final-audit
description: Independently audit completed implementation work before acceptance when another agent, developer, or prior pass claims the task is finished, production-ready, safe, or ready to merge.
disable-model-invocation: false
---

# Final Audit

## Quick Index

- **Trigger:** someone else's work is called done, safe, ready to merge or
  production-ready, and needs a check before acceptance.
- **Process:** fix scope, read the real artifacts, sweep the four lenses,
  prove what matters, write findings, close with residual risk.
- **Verification:** a pass counts only when you watched it run; everything
  else is reported as unconfirmed.
- **Halts:** unclear ownership, authority, compatibility or rollback; any
  CRITICAL change; a stricter gate (`policy/correction-ladder.md` §12).
- **Not for:** ordinary implementation with no acceptance review in view;
  proving your own change (proof-gate).

## Audit passes

1. **Scope.** Collect what was asked, the instructions and design limits
   that govern it, the files that changed, and every check the author says
   passed. Find the target from the request and the workspace. If more than
   one target fits, say which ones and audit the one the evidence supports.
   Keep other repositories out; do not propose unrelated restructuring.
2. **Primary material.** Open the diff and the code around it, plus config,
   schemas, interfaces, tests and the docs that apply. An author summary, a
   reported green run or an earlier approval is a claim to test, never a
   substitute for reading. Plausible is not proven.
3. **Lens sweep.** Work through the table below, only as far as the changed
   surface reaches.
4. **Proof.** For each claim that would change acceptance, run the
   smallest relevant check you are permitted to run. Facts outside the
   workspace that may have changed (versions, APIs, platform behaviour) go
   to research-first; its tool bindings live in
   `adapters/web-research/README.md`. For symbol and caller tracing,
   code-intelligence can assist.
5. **Findings.** Use the sheet below. Invent nothing to look thorough.
6. **Close.** If nothing consequential turned up, say so in plain words.
   List what you read, what you ran and what stayed unconfirmed, then the
   remaining exposure. Stop once more digging could not move the
   acceptance decision.

## Lens table

| Lens | Probe for |
|---|---|
| Behaviour | wrong output, missing requirements, regressions, hidden assumptions, edge and bad inputs, failure paths, stored state left inconsistent |
| Operations | authorization, input validation, secrets, outbound calls, privilege split, concurrency, cancellation, retries and idempotent replay, cleanup, durable writes |
| Structure | broken component or policy boundaries, needless dependencies, duplicated mechanisms, vendor lock-in, idle resource cost, brittle path or shell assumptions |
| Claims | each asserted check: observed by you, or only reported |

## Evidence rules (fail-closed)

- No observed run, no pass: a check you did not see execute stays
  unconfirmed in the report.
- A check you could not run is named as not run, with the reason.
- A target you could not pin narrows the audit; it never widens it.
- This skill has no verdict words of its own. Findings inform acceptance;
  they do not grant it.

## Finding sheet

Each finding carries: severity, location, evidence, impact and a suggested
remedy. Sort them into three tiers: blocking, significant but advisory,
and optional.

## Retry accounting

- You report; others repair. When their check failed, record the author's
  correction count next to it; a later fix continues that count, never a
  fresh start (§§3–4).
- When one of your own check invocations fails, that failure is ATTEMPT_0
  of a reviewer-tool campaign (§2), with at most three corrections (§3).
  Classify each and add the MEDIUM/HIGH fields (§§5–6). Research as staged
  before corrections 2 and 3 (§7). Change the method and end with a check
  that could fail (§§8–9). Inspect what the last try left behind first
  (§10). Keep the record OBSERVATION to NEXT_DECISION (§11).
- A spent budget leaves the claim unconfirmed; stop and report (§12).

## Halts

Stop and ask the owner when ownership, authority, compatibility or rollback
is unclear, or before any CRITICAL change. Respect stricter gates and any
required independent judgment. Correcting, verifying and accepting stay
separate steps (§12).

## Neighbours

- **independent-review** governs the judgment when both are loaded; these
  code checks run under its claim states and ruling.
- **proof-gate** owns proof of your own change; it in turn leaves judging
  finished work here.
- **research-first** settles external premises.
- This skill supports review; it claims no exclusive right to code review.
