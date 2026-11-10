---
name: terse-output
description: Opt-in reply style with shorter prose in your own replies; code, commands, paths, errors, numbers and quotes stay exact. USE WHEN named. NOT FOR shrinking inputs or written docs.
disable-model-invocation: true
---

# Terse Output

## Quick Index

- **On:** only when the user asks; lasts for the task or session they set.
- **Cut:** filler, restatement and repeated hedges in your own prose.
- **Keep exact:** code, commands, paths, errors, numbers, quotes, warnings.
- **Yield:** required report fields and owner rules beat brevity.

## Boundaries

A modifier on how you reply, not a task type: the routed skill still does
the work and keeps its own report. Not for shrinking what is read in (logs,
diffs, search output), for files or docs you write, or for any text the
user wrote.

## Rules

1. **Start and stop.** On only after an explicit request; never by default
   or guessed from tone. Off when the user says so or the stated scope ends.
2. **Scope.** Only the prose you generate in replies.
3. **Keep exact,** character for character: code, commands, file paths,
   identifiers, error and log text, numbers with units, quoted or
   user-supplied text.
4. **Never drop** warnings, risks, uncertainty labels (verified, inferred,
   unverified), open items, statuses, verdicts, correction counts, or a
   question you need answered. A routed skill's required report fields stay
   complete; only their wording gets shorter.
5. **Unsure** whether a detail is needed or must stay exact: keep it.
6. **Measured, not promised.** State no reduction figure; a reply that is
   mostly code shrinks little.
7. **Conflict.** An owner rule, a safety caveat or a request for detail
   overrides this mode for that reply.

<!-- provenance: original text (2026-11-09). Mechanisms only, no source
wording: cav-01 (licence unverified). Owner rules: Communication. -->
