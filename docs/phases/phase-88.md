---
era: "003"
---

# flex — Phase 88: Scope context-budget gate to pairmode build-cycle agents

← [Phase 87: checklist-item-level override granularity for sync/audit](phase-87.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Scope the context_budget PreToolUse gate so it fires only for pairmode build-cycle agent spawns, never for general-purpose ones. Today hooks/pre_tool_use.py's Task/Agent branch calls context_budget.decide() for every spawn with no subagent-type discrimination, so a general-purpose Plan/general-purpose/Explore spawn gets repeatedly blocked once context_current_tokens has accumulated past threshold — and because the gate's turn-tracking acknowledgment (INFRA-192/193) only clears on a genuine new UserPromptSubmit, a same-turn retry can never satisfy it. The fix keys the gate on the spawn payload's tool_input.subagent_type field (confirmed via docs/architecture.md:530 — distinct from the top-level agent_type field the Read-branch cold_read_guard uses to identify the acting subagent), gating only when subagent_type is one of the five build-cycle agents (builder, reviewer, loop-breaker, security-auditor, intent-reviewer). Everything else passes through untouched. context_budget.py's internal logic and turn-tracking are unchanged — only the hook's dispatch condition narrows.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-199 | Scope context-budget PreToolUse gate to pairmode build-cycle agent spawns via tool_input.subagent_type allowlist | planned |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-88 Cold-eyes checklist

— developer fills in after phase completion —
