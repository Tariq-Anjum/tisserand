# Serena adapter for `code-intelligence`

Tool-specific steps for the neutral `code-intelligence` skill. The skill
owns the procedure, labels, status and stop rules; this file only says how
to drive one tool. `adapters/**` is exempt from the neutrality lint because
an adapter binds to a specific tool by design. No absolute paths: the
launcher is found on `PATH`.

Provider: Serena (LSP-backed semantic code server), read-only mode, run
through the shared launcher `serena-shared`. The launcher is owned by the
shared integrations tooling; this adapter never installs, reinstalls or
reconfigures it, and never installs language servers (owner gate).

## Availability check

Three states; only the last forces the skill's fallback (its step 4):

- **Running for this checkout:** `serena-shared status` names this project;
  query it.
- **Stopped (available):** the launcher is on `PATH` and `status` reports
  stopped. Use the on-request query below: it starts a server for this
  checkout and stops the server it started. Do not fall back just because
  nothing is running.
- **Unavailable or bound elsewhere:** the launcher is not on `PATH`, `status`
  errors, or a server runs for a different project (see below).
- `serena-shared doctor` diagnoses the launcher; run it only when the owner
  asks for launcher repair, which is setup work, not this skill.

## Bind to the exact checkout

- Identify the exact project checkout under discussion (the Git checkout
  root, not a parent workspace and not another worktree).
- If `status` shows a server for a different project, do not switch it:
  another session may own it. Fall back, or ask the owner.
- The launcher resolves Git targets to their checkout root and refuses a
  non-Git directory unless `--allow-non-git` is passed; pass that flag only
  for an intentional, owner-named project.

## On-request query (default)

`serena-shared query <exact-project-path> [tool] --arguments '<json object>'`

- Starts the server only if needed, checks identity and readiness, runs one
  tool call, and stops a server it started (this is the default path for a
  stopped tool; it never touches a server another session started).
- Omit `[tool]` to list the read-only tool schemas the server exposes.
- `--arguments` must be one JSON object; an invalid object is an error, not
  a fallback.

## Warm session (several queries in a row)

`serena-shared start <exact-project-path>`, then queries, then
`serena-shared stop`. Stop only a server this session started.

## Allowed tools (read-only)

| Question | Tool |
|---|---|
| module or file overview | `get_symbols_overview` |
| locate a symbol | `find_symbol` |
| references and callers | `find_referencing_symbols` |
| declaration | `find_declaration` |
| implementations | `find_implementations` |
| diagnostics for a file | `get_diagnostics_for_file` |

Never call editing, refactoring, shell-execution, memory, onboarding or
project-management tools, even when a configuration exposes them. Results
from the calls above are SEMANTIC findings in the skill's terms; report the
relative paths and line ranges exactly as returned. A call that returns an
empty list marks its question ANSWERED ("none found"); a call that errors,
times out or is refused marks it FAILED.

## Failure handling

- Start or query fails: record the error. A retry with a changed method is a
  correction under the skill's Corrections rule (at most three per task,
  count carried); an unchanged repeat is never allowed; otherwise fall back.
- "busy" from the launcher: another query holds the lock; wait or fall back,
  never kill it.
- Server reports a different project after start: stop only if this session
  started it, then fall back.

## Native bindings

A direct tool binding inside a host is off by default. Turning one on is an
owner decision and applies only after `start` on the exact checkout.
