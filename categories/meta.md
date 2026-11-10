# Meta

| Asset | Type | Activation | Capabilities | Description |
|---|---|---|---|---|
| [context-design](../skills/context-design/SKILL.md) | skill | contextual | load-map, context-tiers, context-budget, load-trace | Design what an agent loads, when and at what cost: a load map giving each context source a tier, trigger, budget and check. USE WHEN designing or tracing context loading. NOT FOR installs, app code or UI. |
| [session-reconcile](../skills/session-reconcile/SKILL.md) | skill | contextual | drift-ledger, documentation-hygiene, memory-hygiene | Check what a session changed against docs, agent instructions and memory; list each mismatch, fix only approved ones. USE WHEN records may lag reality. NOT FOR handoff notes or progress files. |
| [skill-router](../skills/skill-router/SKILL.md) | skill | always | capability-routing, context-management, progressive-disclosure | Route non-trivial tasks to the smallest relevant skill, guidance, workflow, or plugin without loading unrelated context. |
