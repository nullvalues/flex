---
era: "002"
---

# flex — Phase 70: Restore per-story `/context` call in Context gate

← [Phase 69: PreToolUse matcher dead under Agent tool rename (CER-049)](phase-69.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

The build loop conflates two distinct token-tracking processes. record_attempt.py feeds effort.db for cost estimation (correct, untouched). bump-context-tokens was intended to track orchestrator context growth between stories but uses subagent total_tokens as its cost input — which is the subagent's own internal context, not the orchestrator's context growth (subagents start fresh with only the story ID). This produces wildly inflated context_current_tokens values and causes false context budget blocks. Phase 70 removes the two bump-context-tokens calls from the build loop. The authoritative context_current_tokens path is the SessionStart hook reset (on clear/startup) plus user-driven set-context-tokens after running /context. The hook already enforces CONTEXT CHECK REQUIRED when the value is absent or stale — that is the right mechanism.

## Stories

| ID | Title | Status |
|----|-------|--------|
| BUILD-029 | Restore per-story `/context` call in Context gate; remove `bump-context-tokens` | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-70 Cold-eyes checklist

— developer fills in after phase completion —
