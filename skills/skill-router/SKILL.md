---
name: skill-router
description: Route non-trivial tasks to the smallest relevant skill, guidance, workflow, or plugin without loading unrelated context.
disable-model-invocation: false
---

# Skill Router

## Quick Index

- **Role:** always on; route, never load the registry wholesale.
- **Path:** type → decision-table row → one skill; `unclear` → ask.

1. **Simple?** If no capability clearly helps, load none.
2. **Named?** Use what the user names; `explicit`/`manual` load only so.
3. **Type.** One of: clarify, design, plan, implement, debug, verify,
   review, deliver, document, research, explore, setup, handoff, answer.
   Ties: own change → verify, else finished work → review; outside facts
   → research, else explore; clarify over design; anything over answer.
   No fit, a missing object ("fix it") or two state-changing types →
   `unclear`: ask one question, load nothing.
4. **Row.** In the registry's `decision-table.json` match type, artifact
   (code, interface, system, agent, docs, none; unstated → the type's
   `artifact_default` in `taxonomy/tt-1.toml`) and any `when` condition. `ok`: its `primary`. `none`: you do
   the step, with at most its first `supporting` entry. `named-only`: you
   do it unless named. `needs_information`: ask.
5. **One skill.** Load only that one; other `supporting` entries wait for
   its handoff. Check `requires` and `conflicts`.
6. **Pointers.** Guidance, workflows, plugins: `capabilities.md`; confirm
   the runtime exists. Install nothing without explicit authorization.
7. **Counts carry.** Routing never resets a correction count
   (`policy/correction-ladder.md` §4).
