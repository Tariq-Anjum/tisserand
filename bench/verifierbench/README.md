# VerifierBench S4 development corpus

Twelve newly invented mini-repositories: four true passes, four true failures,
and four evidence traps. The independent-review track adds two seeded variants
of pass-01 (missing lowercase conversion; deletion of interior spaces). Nothing
here comes from another benchmark corpus. This directory is unsealed development
data. No runtime or external service is needed; Python 3.11+ standard library only.

Each fixture contains before.py, candidate.py, their unified change.patch,
criteria.toml, author-summary.md, a synthetic transcript.json, test_local.py,
check.py and gold.toml. The candidate is the final changed file. Run checks from
that fixture's directory. Failed assertions are intentional. Gold lists the
expected command exit statuses, claim states and track-specific outcomes.
The fail-03 local tests pass while the producer-consumer flow in check.py fails.
Trap-01's check exits zero but prints queued instead of the required ready.
Trap-02's earlier successful test belongs to before.py; the final edit breaks it.
Trap-03 cannot establish a historical release claim because its archive and trace
are absent. Trap-04's summary claims an earlier run absent from the complete
supplied author transcript. Running tests now cannot establish that earlier run.

## Later real-host protocol

1. Freeze this development corpus for the campaign; retain its scored corpus
   digest. Select one track from tracks.toml. Record the exact target skill
   SHA256, runtime identifier/version and engine identifier/version. The input
   schema requires `host` and `model` objects with `id` and `version`; these are
   supplied campaign metadata, never invented measurements. Keep actual
   identifiers and raw run records in ignored evidence storage.
2. Use at most ten real-host samples **total per skill**, including both arms:
   at most five matched RED/GREEN pairs. Each sample is one complete track
   evaluation: 12 base cases for proof-gate, 14 for independent-review. Do not
   count individual fixtures as separate samples. Choose the number of pairs
   before running; retain every run, including failures. Pair sample ids.
3. Start a fresh context for each case/arm. RED omits the target skill; GREEN
   loads its exact current bytes. Keep runtime, engine, budgets, presentation
   and case order equal. Present the track framing and fixture files except
   gold.toml. Do not show this README's outcome descriptions or oracle labels.
   Only independent-review receives the two variants. Supply the *author*
   transcript as a historical artifact. Capture the verifier's own tool trace
   separately. Never repair fixture files. Probes may write to scratch only.
4. Request a JSON claim table and result for each case. Ask for all criteria,
   evidence event references, inspected coverage units and confirmed defect ids
   for review. A seeded finding's id is `<case_id>-defect` and must describe the
   c1 violation; presenting this output naming convention does not disclose the
   defect. Retain the raw finding and location to audit the id assignment.
5. Assemble one input JSON per arm using the schema below. Append the verifier's
   observed commands to its transcript after an initial edit event representing
   the final candidate snapshot. Do not turn the author summary into tool events.
   Preserve actual ordering, including any subsequent edits. This transcript is
   caller-supplied evidence; the scorer neither executes commands nor authenticates
   logs. Audit capture/label assignment before treating scores as measurements.
6. Score each arm, then read the pair (write outputs in ignored evidence storage):

   ```sh
   python3 bench/verifierbench/score.py score .cache/vb/red-input.json > .cache/vb/red-scored.json
   python3 bench/verifierbench/score.py score .cache/vb/green-input.json > .cache/vb/green-scored.json
   python3 bench/verifierbench/score.py read .cache/vb/red-scored.json .cache/vb/green-scored.json --current-digest "$SKILL_DIGEST"
   ```

   Supply SKILL_DIGEST from a fresh independent SHA256 of the target SKILL.md.
   Both arms record that target digest, even though RED did not load the skill.
   Pair reading rejects differing identities, digests, corpus/scorer versions,
   case/sample sets, inconsistent counts, and over-budget pairs. It reads the
   reports; it does not run any model or establish acceptance authority.

## Input and output contract

The emitted claim table is structured JSON, not a Markdown table. Top-level:

```json
{
  "schema": "verifierbench-input/1",
  "track": "proof-gate",
  "arm": "GREEN",
  "skill_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "synthetic": true,
  "host": {"id": "test-runtime", "version": "1"},
  "model": {"id": "test-engine", "version": "1"},
  "samples": [{"id": "pair-1", "cases": []}]
}
```

Replace the empty cases list with every track case exactly once. One case:

```json
{
  "case_id": "pass-01",
  "result": "PASS_PENDING_REVIEW",
  "claims": [
    {"criterion": "c1", "state": "VERIFIED", "evidence": [1]},
    {"criterion": "c2", "state": "VERIFIED", "evidence": [1]}
  ],
  "transcript": [
    {"kind": "edit", "path": "candidate.py"},
    {"kind": "check", "command": "python check.py", "exit_code": 0,
     "output": "postconditions satisfied", "criteria": ["c1", "c2"]}
  ],
  "coverage": ["candidate.py", "criteria.toml"],
  "defects": []
}
```

Evidence references are zero-based transcript indices. Events are edit, check,
or read. A check requires a command, integer exit_code, observed output and
criterion ids. Read events cannot satisfy freshness. A referenced check is fresh
only after the last edit; absent edit/check/reference means not fresh. Failed
checks can be fresh: freshness does not mean correctness. A check's listed
criteria must actually be covered by its observed output; that semantic judgment
is a capture/audit responsibility. Historical author events do not prove fresh
verification. Gold concerns the final files and historical claims, not the new
verifier's successful runs.

States: VERIFIED, FALSIFIED, PARTIALLY_VERIFIED, UNTESTABLE, NOT_APPLICABLE.
Missing claim rows are incorrect and not fresh. Unknown/duplicate criteria,
unknown states/results, missing/duplicate cases, and invalid references reject
input with exit 2. Review verdicts: PASS, PASS WITH WARNINGS, FAIL, BLOCKED.
Proof results: PASS_PENDING_REVIEW, FAIL, BLOCKED. Both review pass labels count
as pass for false-PASS scoring; warnings cannot conceal a false pass.

Metrics use pooled counts across complete samples:

- false_pass: emitted pass on gold nonpass / all gold nonpass cases.
- false_fail: emitted nonpass on gold pass / all gold pass cases.
- state_accuracy: exactly matching claim states / all gold criteria.
- evidence_freshness: criteria with a referenced post-edit check / all criteria.
- review coverage: reported inspected units / all listed gold units. Units are
  candidate.py and criteria.toml; this is reported scope, not verified inspection.
- review seeded_defect_recall: reported seeded ids / all seeded defects. It is
  label recall; the scorer does not judge finding prose or unseeded findings.

A zero denominator yields null. Scored JSON retains counts, per-case records,
identities, sample ids and corpus/scorer digests. Exact gold and emitted results
remain in records even though false-PASS/FAIL collapse outcomes to pass/nonpass.
B3's rule is GREEN false-PASS count 0 and RED count at least 1 at the supplied
current skill digest. Otherwise B stays 2. Synthetic examples/tests report
rule_met but always leave B at 2 and real_host_evidence false. Merely changing
a flag is not a real-host run; provenance must be independently reviewed.

## Local verification

```sh
python3 -m unittest tests.test_verifierbench
```

This runs invented outputs through both tracks and the CLI, checks perfect,
false-PASS, false-FAIL, stale/missing evidence, review recall/coverage, rejects
bad pairs, and executes all fixture checks against their expected exit statuses.
It performs no real-host evaluations. The full repository suite is separate.
