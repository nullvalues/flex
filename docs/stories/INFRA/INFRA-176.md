---
id: INFRA-176
rail: INFRA
title: "Verify spawn-tool name and widen PreToolUse matcher/dispatch to `Task|Agent`"
status: planned
phase: "69"
story_class: code
primary_files:
  - hooks/hooks.json
  - hooks/pre_tool_use.py
touches:
  - tests/pairmode/test_pre_tool_use_hook.py
  - docs/architecture.md
---

# INFRA-176 — Verify spawn-tool name and widen PreToolUse matcher/dispatch to `Task|Agent`

**Phase:** 69
**Rail:** INFRA
**Status:** planned

## Problem (CER-049)

`hooks/hooks.json:26-37` registers the PreToolUse hook with matcher `"Task"`,
and `hooks/pre_tool_use.py:25` dispatches on `tool_name == "Task"`. Current
Claude Code harnesses name the agent-spawn tool `Agent`. Observed Phase 68
build (2026-06-12): four subagent spawns at 151k–694k accumulated tokens (block
ceiling 132k) produced no block and no `context_budget_acknowledged_at` write —
consistent with the matcher never firing. If confirmed, the mechanical
context-budget gate has been dead since the harness rename.

## Fix

1. **Verify first.** Determine the actual `tool_name` delivered to PreToolUse
   on an agent spawn in the current harness (e.g., temporarily log
   `data.get("tool_name")` from a catch-all matcher in a scratch hooks config,
   or consult harness release notes). Record the finding in this story file
   under a `## Verification result` heading.
2. `hooks/hooks.json`: change the PreToolUse matcher `"Task"` → `"Task|Agent"`.
3. `hooks/pre_tool_use.py`: change `if tool_name == "Task":` →
   `if tool_name in ("Task", "Agent"):`. No other logic changes — the thin
   dispatcher contract (CLAUDE.md item 1) is unchanged.
4. `docs/architecture.md`: update matcher references (search `matcher "Task"` /
   `matcher \`Task\``) to name both tool names and cite CER-049.

## Acceptance criteria

1. `hooks/hooks.json` PreToolUse matcher is `"Task|Agent"`.
2. `pre_tool_use.py` dispatches the context-budget branch for `tool_name`
   values `"Task"` and `"Agent"`; all other tool names fall through unchanged
   (`Edit`/`Write` branch unaffected).
3. `tests/pairmode/test_pre_tool_use_hook.py` gains a parametrized case
   invoking the hook with `tool_name: "Agent"` and asserting identical
   block/pass behavior to `"Task"`.
4. `## Verification result` section records the observed harness tool name.
5. `docs/architecture.md` matcher references updated.
6. Full suite passes: `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`.

## Primary files

- `hooks/hooks.json` — protected file; modification reason: CER-049 fix is the
  matcher string itself.
- `hooks/pre_tool_use.py` — protected file; modification reason: dispatch
  tool-name check must accept the renamed tool.

## Touches

- `tests/pairmode/test_pre_tool_use_hook.py`
- `docs/architecture.md`
