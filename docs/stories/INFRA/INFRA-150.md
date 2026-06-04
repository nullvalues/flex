---
id: INFRA-150
rail: INFRA
title: "`context_budget.py` — block on malformed state.json with operator signal (CER-040)"
status: complete
phase: "59"
story_class: code
primary_files:
  - skills/pairmode/scripts/context_budget.py
  - tests/pairmode/test_context_budget.py
touches: []
---

# INFRA-150 — `context_budget.py`: block on malformed state.json with operator signal (CER-040)

## Context

Phase 58 replaced the broken transcript-parsing approach with a state.json contract: the orchestrator
writes `context_current_tokens` via `flex_build.py set-context-tokens` and the hook reads from there.

The Phase 58 back-check identified a residual silent-fail edge (CER-040): `_read_state()` currently
returns `None` for both "state.json absent" and "state.json exists but malformed". Both paths cause
`decide()` to return `None` (pass-through) with no operator signal.

For non-pairmode projects the first case (no file) is correct behavior — the hook should fail open.
For pairmode projects, the second case (malformed file) is incorrect — it leaves the operator with
a broken gate and no indication that anything is wrong.

The fix is a one-function change to `_read_state()`: distinguish "file absent" (→ `None`, unchanged)
from "file exists but malformed" (→ `{}`, empty dict). When `_read_state` returns `{}`, the existing
`decide()` and `read_context_tokens_from_state({})` path already triggers `_CONTEXT_CHECK_REQUIRED_MSG`
— no changes to those functions are needed.

## Acceptance criteria

### `skills/pairmode/scripts/context_budget.py`

1. **`_read_state(project_dir: Path) -> dict | None`** — update the malformed-file branches:

   - When `state_path.exists()` is `False` → return `None` (unchanged; non-pairmode pass-through).
   - When `state_path.exists()` is `True` but `json.loads()` raises `json.JSONDecodeError` or
     `OSError` → return `{}` (empty dict, not `None`).
   - When `state_path.exists()` is `True` but the parsed value is not a `dict` (e.g. root is `[]`
     or a string) → return `{}` (same treatment as malformed).
   - When `state_path.exists()` is `True` and the file parses to a valid dict → return the dict
     (unchanged).

2. Update the comment inside `decide()` where `state is None` is checked, from:
   ```python
   # No state.json (or malformed) — degrade safely. Without state we have
   # no budget configuration and no current_tokens record; the hook fails
   # open and the orchestrator continues. This matches the pre-INFRA-148
   # behaviour for non-pairmode projects.
   ```
   to:
   ```python
   # No state.json — non-pairmode project, fail-open.
   ```

3. No other changes to `context_budget.py`. `decide()`, `read_context_tokens_from_state()`,
   `should_block()`, `estimate_next_step_tokens()`, and `render_alert_prompt()` are all out of scope.

### Tests — `tests/pairmode/test_context_budget.py`

4. Add three new test cases (may be grouped in a class or added as top-level functions):

   - **`test_decide_no_state_file_passthrough`** — `.companion/` directory exists but
     `state.json` is absent → `decide()` returns `None`.
     *(This may already exist; if so, verify it still passes rather than adding a duplicate.)*

   - **`test_decide_malformed_state_file_context_check_required`** — `.companion/state.json`
     exists and contains invalid JSON (e.g. `"not json{{"`) → `decide()` returns a dict with
     `block=True` and `"CONTEXT CHECK REQUIRED"` in `reason`.

   - **`test_decide_non_dict_state_file_context_check_required`** — `.companion/state.json`
     exists and contains valid JSON but a non-dict root (e.g. `[1, 2, 3]`) → `decide()` returns
     a dict with `block=True` and `"CONTEXT CHECK REQUIRED"` in `reason`.

## Out of scope

- TTL / staleness for `context_current_tokens` (INFRA-151)
- Changes to `flex_build.py`, `story_context.py`, or any hook
- Changes to `hooks/pre_tool_use.py` (no call-site signature change required)
