---
era: "003"
---

# flex — Phase 85: Context budget acknowledgment integrity fix

← [Phase 84: Spec preflight verification](phase-84.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->

## Goal

Close a CRITICAL self-clearing bug in the context-budget gate (CER-027/CER-049/INFRA-182)
found via an external report from another pairmode-run project: `context_budget.decide()`
returns `acknowledged_at = current_tokens` (the token count at the moment of the block,
not a distinct "a human saw this" marker), and `pre_tool_use.py` writes it to state.json
unconditionally, before any human has replied. Because a blocked Task/Agent call never
completes, `context_current_tokens` does not advance on the very next attempt — so the
reprompt-suppression check (`current_tokens < acknowledged_at + reprompt_margin`) is
trivially satisfied by `current_tokens == acknowledged_at`, and the gate silently stands
down on a bare identical retry with zero human involvement. This is not adversarial to
trigger — ordinary agent retry-on-error behavior clears it.

Root cause: the gate conflates "the block fired" with "the user acknowledged it." The fix
introduces a genuine human-turn signal (a `UserPromptSubmit` hook incrementing a
monotonic sequence counter in state.json) and requires that a new user turn has occurred
since the block before a retry may pass silently — token-count progress alone is no
longer sufficient.

Two deliverables: `hooks/user_prompt_submit.py`, a new thin `UserPromptSubmit` hook
recording a user-turn sequence counter, and an update to `context_budget.py` /
`hooks/pre_tool_use.py` making the reprompt-suppression check require both token
progress AND a new user turn since the block.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-192 | UserPromptSubmit hook — user-turn sequence counter | complete |
| INFRA-193 | context_budget acknowledgment gate — require genuine user turn since block | planned |

## Schema delivery

No new persistent schema objects introduced in this phase. `state.json` gains two
scalar keys (`context_budget_user_turn_seq`, `context_budget_acknowledged_user_turn_seq`)
— not a schema object, covered under the existing state.json contract (Phase 58).
