---
era: "002"
---

# flex — Phase 69: PreToolUse matcher dead under Agent tool rename (CER-049)

← [Phase 68: SessionStart context-counter reset](phase-68.md)

**Parent phase:** Phase 68 — cp-68 tagging is paused on this fix (CER-049) and
on CER-046 (Phase 66). Spec'd immediately after the Phase 68 build observed the
context-budget hook never firing; build deferred past a `/clear` to avoid
compaction mid-checkpoint.

## Goal

Verify and fix CER-049. During the Phase 68 build, four subagent spawns
proceeded with `context_current_tokens` between 151k and 694k — far past the
132k block ceiling — and `hooks/pre_tool_use.py` never blocked and never wrote
`context_budget_acknowledged_at`. Hypothesis: `hooks/hooks.json` registers the
PreToolUse matcher `"Task"`, but current Claude Code harnesses name the
agent-spawn tool `Agent`, so the matcher never matches and the mechanical
context gate (CER-027 → CER-039 → CER-045 lineage) is silently disabled
fleet-wide. Verify the actual `tool_name` first, then widen the matcher and the
dispatcher's tool-name check to accept both names.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-176 | Verify spawn-tool name and widen PreToolUse matcher/dispatch to Task+Agent | complete |
| INFRA-177 | Remove completed one-time lessons bypass rule from pairmode_migrate.py (cp-69 security audit) | complete |
| INFRA-178 | Single-source PAIRMODE_VERSION into _version.py (CER-046) | complete |

## Schema delivery

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-69 Cold-eyes checklist

— developer fills in after phase completion —
