---
era: "002"
---

# flex — Phase 72: Restore JSONL-based context gate

← [Phase 71: Propagate BUILD-029 Context gate fix into CLAUDE.build.md.j2 template](phase-71.md)

## Goal

Restore the JSONL transcript–based token count source in the `pre_tool_use.py` hook
gate, removing the dependency on LLM cooperation that has made the gate unreliable
since INFRA-148.

**Background:** The original Phase 47 / INFRA-128 hook read the session JSONL
transcript to get the live context token count. INFRA-148 replaced that with a
state.json contract requiring the orchestrator to call `/context` and run
`set-context-tokens`. That contract is broken by design: `/context` is a user-facing
slash command the orchestrator LLM cannot invoke, so the gate has silently operated on
a stale 25,000-token SessionStart baseline for every session since.

**Root cause (confirmed):** The original code derived the transcript path from
`data.get("transcript_path")`, which is absent or incorrect in PreToolUse hook events.
The JSONL format itself is fine — tail-parsing the last 100 lines finds the last
`type: "assistant"` entry and its `usage` block correctly. The fix is to construct the
path ourselves from `cwd` (available in the event) and `session_id` (also available):

```
~/.claude/projects/{cwd.replace("/", "-")}/{session_id}.jsonl
```

**Design after this phase:**
- `context_budget.py` derives the transcript path and reads the live count from JSONL.
  Falls back to `context_current_tokens` in state.json if JSONL parsing fails.
- `pre_tool_use.py` passes `session_id` to the module, and writes the JSONL-derived
  count back to state.json so the CLAUDE.build.md Context gate can display it.
- `CLAUDE.build.md` Context gate becomes a display-only step (reads state.json; no
  `/context` call; no `set-context-tokens`). The hook is the sole enforcer.
- `set-context-tokens` is retained as a manual override for debugging.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-179 | Restore JSONL transcript parsing in context_budget.py; make hook the sole enforcer | complete |

## Schema delivery

| Object | Management surface | Exception |
|---|---|---|
| — | — | — |

---

### CP-72 Cold-eyes checklist

— developer fills in after phase completion —
