---
id: INFRA-139
rail: INFRA
title: "`pre_tool_use.py` Edit/Write dispatch + CLAUDE.md carve-out update"
status: planned
phase: "55"
story_class: code
primary_files:
  - hooks/pre_tool_use.py
  - CLAUDE.md
  - skills/pairmode/templates/CLAUDE.md.j2
touches:
  - tests/pairmode/test_pre_tool_use_scope_guard.py
---

# INFRA-139 — `pre_tool_use.py` Edit/Write dispatch + CLAUDE.md carve-out update

## Background

`scope_guard.py` (INFRA-138) provides the enforcement logic; `pre_tool_use.py` must
invoke it. The hook currently has a hard early-exit for any tool that is not `"Task"`.
This story adds an `"Edit"` / `"Write"` branch that delegates to `scope_guard`,
alongside the existing `"Task"` branch that delegates to `context_budget`.

The hook remains a thin dispatcher. All scope logic lives in `scope_guard.py`; the
hook's only new responsibility is: parse `tool_name`, match `"Edit"` or `"Write"`,
extract `file_path` from `tool_input`, call `scope_guard.check_path`, emit a block
response if the call returns `(False, reason)`.

CLAUDE.md's HOOK PERFORMANCE check (#1) documents a carve-out for the existing
`Task → context_budget` delegation. That carve-out must be updated to also document
the new `Edit/Write → scope_guard` delegation, so the reviewer does not flag the
added branch as a CRITICAL violation.

## Ensures

### `pre_tool_use.py` changes

- `hooks/pre_tool_use.py` gains an `elif tool_name in ("Edit", "Write"):` branch
  after the `if tool_name == "Task":` block.
- The new branch:
  1. Extracts `file_path = data.get("tool_input", {}).get("file_path", "")`.
  2. Extracts `cwd = Path(data.get("cwd") or ".")`.
  3. Imports `scope_guard` (same `sys.path` setup already present for `context_budget`).
  4. Calls `scope_guard.check_path(file_path, cwd)` inside a try/except; on any
     exception, falls through to `sys.exit(0)` (fail open — do not block on guard error).
  5. If the result is `(False, reason)`:
     prints `json.dumps({"decision": "block", "reason": reason})` to stdout.
  6. Calls `sys.exit(0)` in all cases (block or allow — the hook always exits 0).
- The existing `"Task"` branch is unchanged.
- The module-level docstring is updated to list both dispatched tool types.

### CLAUDE.md carve-out update

- CLAUDE.md HOOK PERFORMANCE check (#1) currently reads:

  > **Documented thin-delegation exception:** `hooks/pre_tool_use.py`
  > is the canonical thin delegate (CER-027 enforcement). It is
  > allowed: one stdin parse, one `tool_name == "Task"` check, one
  > delegated call into `skills/pairmode/scripts/context_budget.py`,
  > and one stdout emit of the module's return value. All domain
  > logic — transcript read, effort.db query, threshold math, state
  > mutation — lives in the named module, NOT in the hook.
  >
  > Any *additional* logic added inside `pre_tool_use.py` beyond
  > stdin-parse + tool-name-check + delegate + emit remains CRITICAL.

- Replace that block with:

  > **Documented thin-delegation exception:** `hooks/pre_tool_use.py`
  > is a thin dispatcher for two tool types:
  >
  > - `Task` → `skills/pairmode/scripts/context_budget.py`
  >   (CER-027 context-budget enforcement)
  > - `Edit` / `Write` → `skills/pairmode/scripts/scope_guard.py`
  >   (Phase 55 story file-scope enforcement)
  >
  > For each dispatch: one tool-name check, one delegated module call,
  > one stdout emit. All domain logic lives in the named modules, NOT
  > in the hook. The hook owns one state write (acknowledged_at) for
  > the Task branch; the Edit/Write branch is read-only.
  >
  > Any logic added inside `pre_tool_use.py` beyond tool-name dispatch
  > + module delegation + emit remains CRITICAL.
  > Any *other* hook that emits a decision-block response remains CRITICAL.

- `skills/pairmode/templates/CLAUDE.md.j2`: apply the identical replacement
  (same wording, same position in the file).

## Out of scope

- Modifying `scope_guard.py` (INFRA-138).
- Updating `skills/pairmode/templates/CLAUDE.build.md.j2` (BUILD-024).
- Adding scope-guard carve-out to SKILL.md or architecture.md (intent review
  will flag any needed doc updates at checkpoint).

## Instructions

### 1. Edit `hooks/pre_tool_use.py`

Current structure (simplified):
```python
def main():
    ...
    if data.get("tool_name") != "Task":
        sys.exit(0)
    # Task / context_budget logic
    ...
```

Replace with:
```python
def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name")

    if tool_name == "Task":
        try:
            import context_budget
            result = context_budget.decide(
                project_dir=Path(data.get("cwd") or "."),
                transcript_path=data.get("transcript_path") or "",
            )
        except Exception:
            sys.exit(0)
        if result and result.get("block"):
            try:
                state_path = Path(data.get("cwd") or ".") / ".companion" / "state.json"
                if state_path.exists():
                    state = json.loads(state_path.read_text())
                    state["context_budget_acknowledged_at"] = result["acknowledged_at"]
                    state_path.write_text(json.dumps(state, indent=2))
            except Exception:
                pass
            print(json.dumps({"decision": "block", "reason": result["reason"]}))
        sys.exit(0)

    elif tool_name in ("Edit", "Write"):
        try:
            import scope_guard
            file_path = data.get("tool_input", {}).get("file_path", "")
            allowed, reason = scope_guard.check_path(
                file_path=file_path,
                project_dir=Path(data.get("cwd") or "."),
            )
        except Exception:
            sys.exit(0)
        if not allowed:
            print(json.dumps({"decision": "block", "reason": reason}))
        sys.exit(0)

    sys.exit(0)
```

### 2. Update module docstring

Replace the existing docstring to list both dispatch targets:
```
PreToolUse hook — dispatches to context_budget (Task) and scope_guard (Edit/Write).

Thin dispatcher. Domain logic lives in the named modules:
  - Task  → skills/pairmode/scripts/context_budget.py  (CER-027)
  - Edit/Write → skills/pairmode/scripts/scope_guard.py (Phase 55)
No logic beyond tool-name dispatch, module call, and stdout emit.
```

### 3. Edit CLAUDE.md

Find the HOOK PERFORMANCE check #1 carve-out block and replace it as specified
in the Ensures section above. The block begins with
`**Documented thin-delegation exception:**` and ends before
`Any *other* hook that emits`.

### 4. Edit `skills/pairmode/templates/CLAUDE.md.j2`

Apply the identical replacement at the same position in the template file.

## Tests

File: `tests/pairmode/test_pre_tool_use_scope_guard.py`

The test module invokes `pre_tool_use.main()` by patching `sys.stdin` with
crafted JSON payloads and capturing `sys.stdout`. Mock `scope_guard.check_path`
in the `pre_tool_use` module namespace to avoid needing a real project tree.

1. `test_edit_allowed_path_does_not_block`
   — mock `scope_guard.check_path` returning `(True, "allowed")`;
   send `{"tool_name": "Edit", "tool_input": {"file_path": "foo.py"}, "cwd": "/tmp"}`;
   assert no JSON printed to stdout (no block emitted).

2. `test_edit_blocked_path_emits_block`
   — mock `scope_guard.check_path` returning `(False, "not in story scope")`;
   assert stdout contains `{"decision": "block", "reason": "not in story scope"}`.

3. `test_write_blocked_path_emits_block`
   — same as above but `tool_name: "Write"`.

4. `test_scope_guard_exception_fails_open`
   — mock `scope_guard.check_path` raising an exception;
   assert no block emitted and exit 0.

5. `test_task_branch_unaffected`
   — `tool_name: "Task"` with a mock `context_budget.decide` returning a non-block
   result; assert `scope_guard.check_path` not called.

6. `test_unknown_tool_name_exits_cleanly`
   — `tool_name: "Bash"`; assert no block emitted and exit 0.
