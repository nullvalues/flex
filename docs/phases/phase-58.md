---
era: "001"
---

# flex — Phase 58: Context budget gate — state.json contract

← [Phase 57: Global session hook + era-001 documentation close](phase-57.md)

## Goal

The context budget secondary gate (`hooks/pre_tool_use.py` → `context_budget.py`) has been
non-functional since Phase 47. It reads `transcript_path` from the PreToolUse hook payload to
estimate the current token count; that path is unreliable across session boundaries, causing
`compute_context_tokens` to silently return `None` on every production invocation.
Confirmed: `context_budget_acknowledged_at` is absent from every project's `state.json` across
the fleet — the hook has never successfully blocked a Task spawn.

Replace the broken transcript approach with a state.json contract: the orchestrator already calls
`/context` at each story's Context gate; it now also writes the result to `state.json` via a new
`flex_build.py set-context-tokens` command. The hook reads from there. Also update the block
prompt to surface the next-step estimate alongside the current count so the operator can make an
informed proceed-or-clear decision.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-148 | `context_budget.py` — replace transcript parsing with state.json contract | planned |
| INFRA-149 | `CLAUDE.build.md` — record `/context` result to state.json in Context gate | planned |

**Story dependency:** INFRA-149 references the `set-context-tokens` CLI introduced in INFRA-148.
Build INFRA-148 first.

## Schema delivery

No new persistent schema objects.

| Object | Management surface | Exception |
|---|---|---|
| — | — | No new tables |

---

### CP-58 Cold-eyes checklist

— developer fills in after phase completion —
