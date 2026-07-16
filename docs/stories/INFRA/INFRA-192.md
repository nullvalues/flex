---
id: INFRA-192
rail: INFRA
title: "UserPromptSubmit hook — user-turn sequence counter"
status: complete
phase: "85"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - hooks/user_prompt_submit.py
  - hooks/hooks.json
touches:
  - CLAUDE.md
  - tests/pairmode/test_hooks.py
---

## Requires

- `hooks/session_start.py` and `hooks/pre_tool_use.py` establish the existing
  thin-dispatcher pattern this story must follow: read stdin JSON, do at most
  one delegated read/write of `.companion/state.json`, never raise.
- `hooks/hooks.json` registers hook events as a JSON object keyed by event name,
  each holding a list of `{matcher, hooks: [{type, command, timeout}]}` entries
  (`UserPromptSubmit` has no `matcher` field — it is not tool-scoped, matching
  the existing `Stop` and `SessionEnd` entries in the file).

## Ensures

- `hooks/user_prompt_submit.py` exists, is executable Python, and on stdin
  containing `{}` (no `cwd`, no `.companion/state.json` present) exits 0 with
  empty stdout and does not raise.
- Given a project dir with `.companion/state.json` containing no
  `context_budget_user_turn_seq` key, invoking the hook with
  `{"cwd": "<project_dir>"}` on stdin causes state.json to contain
  `context_budget_user_turn_seq: 1` afterward.
- Invoking the hook a second time against the same state.json increments the
  value to `2` (monotonic, not reset).
- The hook never prints a `{"decision": ...}` block/reason payload — it is
  write-only, matching the documented `post_tool_use.py` Task/Agent branch
  contract in `CLAUDE.md`.
- If `.companion/state.json` is absent, the hook exits 0 and creates no files
  (fail-open — matches `context_budget._read_state()`'s non-pairmode-project
  contract).
- If `.companion/state.json` contains malformed JSON, the hook exits 0 and
  leaves the file untouched (no crash, no corruption).
- `hooks/hooks.json` contains a `UserPromptSubmit` entry invoking
  `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/user_prompt_submit.py` with a `timeout`
  of `5`.
- `CLAUDE.md`'s hook documentation (Review checklist item 1) is updated to
  list `hooks/user_prompt_submit.py` as a third documented thin-delegation
  exception, describing its one state write.
- `grep -n "user_prompt_submit" CLAUDE.md` returns at least one match.

## Instructions

**1. Create `hooks/user_prompt_submit.py`.**

Follow the exact structural pattern of `hooks/session_start.py`: read stdin
JSON defensively, resolve `project_dir` from `data.get("cwd") or "."`, do one
read-modify-write of `.companion/state.json`, wrapped so any exception exits 0
silently.

```python
#!/usr/bin/env python3
"""UserPromptSubmit hook — records a monotonic user-turn sequence counter.

Thin-delegation exception: fires on every user prompt submission. Increments
``context_budget_user_turn_seq`` in state.json by 1 (starting from 0 when
absent). This is the sole signal that a genuine human turn has occurred,
consumed by ``context_budget.should_block()`` (INFRA-193) to distinguish
"the block fired" from "the user actually replied" when deciding whether to
suppress a repeat context-budget prompt.

Never emits a decision. Never blocks. Write-only, one state.json read-modify-
write, matching the ``post_tool_use.py`` Task/Agent branch contract.
"""
import json
import sys
from pathlib import Path


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    project_dir = Path(data.get("cwd") or ".")
    state_path = project_dir / ".companion" / "state.json"

    try:
        if not state_path.exists():
            sys.exit(0)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            sys.exit(0)
        current = state.get("context_budget_user_turn_seq", 0)
        try:
            current = int(current)
        except (TypeError, ValueError):
            current = 0
        state["context_budget_user_turn_seq"] = current + 1
        state_path.write_text(json.dumps(state, indent=2))
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
```

**2. Register the hook in `hooks/hooks.json`.**

Add a top-level `"UserPromptSubmit"` key (no `matcher` field, following the
`Stop`/`SessionEnd` pattern already in the file) alongside the existing
`PreToolUse`/`PostToolUse` entries:

```json
"UserPromptSubmit": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/user_prompt_submit.py",
        "timeout": 5
      }
    ]
  }
]
```

**3. Update `CLAUDE.md`'s Review checklist item 1 (HOOK PERFORMANCE).**

After the existing `hooks/session_start.py` thin-delegation paragraph, add a
new paragraph documenting `hooks/user_prompt_submit.py`:

```markdown
   `hooks/user_prompt_submit.py` (INFRA-192) is a thin dispatcher for the
   `UserPromptSubmit` event:

   - Every event → one state.json read-modify-write incrementing
     `context_budget_user_turn_seq`. No decision logic, no block/reason
     emission. This is the sole source of the human-turn signal consumed by
     `context_budget.should_block()` (INFRA-193).
```

Also add `hooks/user_prompt_submit.py` to the "Any logic added inside..."
closing sentence of item 1 so it is covered by the same CRITICAL-if-violated
rule as the other three dispatchers.

## Tests

Add to `tests/pairmode/test_hooks.py` (or a new
`tests/pairmode/test_user_prompt_submit_hook.py` if `test_hooks.py` is
organized per-hook — check the file before choosing):

- `test_user_prompt_submit_no_state_file_exits_cleanly(tmp_path)` — no
  `.companion/state.json`; hook exits 0, no file created.
- `test_user_prompt_submit_increments_from_absent_key(tmp_path)` — seed
  state.json with no `context_budget_user_turn_seq` key; after one hook
  invocation, key is `1`.
- `test_user_prompt_submit_increments_monotonically(tmp_path)` — seed
  state.json with `context_budget_user_turn_seq: 5`; after one invocation,
  key is `6`.
- `test_user_prompt_submit_malformed_json_does_not_crash(tmp_path)` — seed
  state.json with invalid JSON content; hook exits 0, file left unmodified.
- `test_user_prompt_submit_never_emits_decision(tmp_path)` — seed a valid
  state.json; assert hook stdout is empty (no `{"decision": ...}` payload
  under any input).

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q -k "user_prompt_submit"
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```
