# Contributing

Thank you for helping. This project values checkable claims over volume, so the rules below are strict.

## Before you start

- Open an issue first for a new skill. Name the task type and the decision-table cells it would fill (`decision-table.json`), and describe the real failures you saw without it. Skills are added for observed gaps, not for completeness.
- Small fixes (typos, broken links, test gaps) can go straight to a pull request.

## Write in your own words

1. Never paste text from another skill collection, prompt library or article. You may build on an *idea*; credit it as "inspired by (mechanism only)" in `capability.toml`.
2. Copied text is allowed only under a compatible licence, with a notice in `THIRD_PARTY_NOTICES` and a `COPIED-PERMISSIVE` disposition.
3. If you are unsure where a sentence came from, say so in the pull request. An honest "unknown" is fine; a guessed "original" is not.

## A new skill needs

- `skills/<id>/SKILL.md` with `name`, `description`, `disable-model-invocation`, a `## Quick Index`, numbered steps, closed status words and named stop conditions. Cite `policy/correction-ladder.md` for retries.
- `skills/<id>/capability.toml`: type, activation, risk, access, provenance.
- A rating in `ratings/rb-1/<id>.toml` and typed cases.
- Ids are permanent. A rename is an alias in `registry/migrations.toml`, never a silent move.

## Checks (all must pass)

```bash
python -m skillkit gen
python -m skillkit check
python -m skillkit gen --check
python -m unittest discover -s tests -t .
```

In a fresh clone a few tests skip because they need the private provenance reference tree; report the skip count in your pull request rather than treating it as a pass.

Never edit generated files (`registry/`, `decision-table.json`, `CREDITS.md`) by hand. Commit messages are short and neutral, with no tool or product names.

## Claims

Make no claim that a skill improves results, speed or reliability unless the pull request links published, reproducible evidence (inputs, commands, unedited outputs, failures included). Design differences are fine to describe; quality comparisons are not.

## Conduct and security

See [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Report vulnerabilities privately as described in [`SECURITY.md`](SECURITY.md), not in a public issue.

By contributing you agree that your contribution is licensed under the MIT licence of this repository.
