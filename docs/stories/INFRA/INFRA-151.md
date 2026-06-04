---
id: INFRA-151
rail: INFRA
title: "`context_budget.py` — timestamp `context_current_tokens` and treat stale values as absent (CER-041)"
status: complete
phase: "59"
story_class: code
primary_files:
  - skills/pairmode/scripts/context_budget.py
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/scripts/story_context.py
  - tests/pairmode/test_context_budget.py
  - tests/pairmode/test_story_context.py
touches: []
---

# INFRA-151 — `context_budget.py`: timestamp `context_current_tokens` and treat stale values as absent (CER-041)

## Context

The Phase 58 back-check identified a second residual silent-fail edge (CER-041): after `/clear`,
`context_current_tokens` in state.json retains the previous session's value indefinitely. If the
operator spawns a Task before reaching the next Context gate (where the orchestrator calls
`flex_build.py set-context-tokens`), the hook reads a token count that could be hours old. The
CONTEXT CHECK REQUIRED block that should fire on a fresh session never fires.

The fix has three parts:
1. `set-context-tokens` writes a `context_current_tokens_recorded_at` UTC timestamp alongside
   `context_current_tokens`.
2. `read_context_tokens_from_state` treats a value older than the TTL as absent (returns `None`),
   which causes `decide()` to fire CONTEXT CHECK REQUIRED.
3. `story_context.py --clear` removes both keys from state, so a cleared session presents as
   unrecorded rather than stale — belt-and-suspenders alongside the TTL.

## Acceptance criteria

### `skills/pairmode/scripts/flex_build.py`

1. **`cmd_set_context_tokens`** — after writing `state["context_current_tokens"] = tokens`, also
   write:
   ```python
   state["context_current_tokens_recorded_at"] = datetime.now(timezone.utc).isoformat()
   ```
   Add `from datetime import datetime, timezone` at the top of the file if not already present.
   No other changes to `set-context-tokens`.

### `skills/pairmode/scripts/story_context.py`

2. **`clear_current_story(companion_dir: Path) -> dict`** — after removing `current_story`, also
   remove the two token-tracking keys:
   ```python
   state.pop("context_current_tokens", None)
   state.pop("context_current_tokens_recorded_at", None)
   ```
   No other changes to `story_context.py`.

### `skills/pairmode/scripts/context_budget.py`

3. Add `from datetime import datetime, timezone` at the top of the file.

4. **`read_context_tokens_from_state(state: dict, _now: datetime | None = None) -> int | None`** —
   add a `_now` parameter (private, for test injection; not part of the public contract) and add a
   staleness check after the existing positive-integer validation:

   ```
   After returning a valid positive int from `context_current_tokens`:
   
   a. Read recorded_at = state.get("context_current_tokens_recorded_at").
      If None or empty: skip the staleness check, return the value as-is.
   
   b. Parse recorded_at with datetime.fromisoformat(recorded_at).
      If parsing raises ValueError: skip the staleness check, return the value as-is.
   
   c. Compute now = _now if _now is not None else datetime.now(timezone.utc).
      Ensure now is UTC-aware (it always will be when using datetime.now(timezone.utc)
      or when tests pass a tzinfo=timezone.utc datetime).
   
   d. Read ttl_minutes = int(state.get("context_current_tokens_ttl_minutes", 60) or 60).
   
   e. Compute age_minutes = (now - recorded_at_dt).total_seconds() / 60.
      If age_minutes > ttl_minutes: return None (stale, treat as absent).
   
   f. Otherwise: return the validated int as before.
   ```

   Signature becomes:
   ```python
   def read_context_tokens_from_state(
       state: dict,
       _now: datetime | None = None,
   ) -> int | None:
   ```

   No other changes to `context_budget.py`. `decide()`, `_read_state()`, `should_block()`,
   `estimate_next_step_tokens()`, and `render_alert_prompt()` are all out of scope.

   **Note:** `decide()` calls `read_context_tokens_from_state(state)` without passing `_now`.
   This is correct — `decide()` should always use the real wall clock. Only tests use `_now`.

### Tests — `tests/pairmode/test_context_budget.py`

5. Add staleness tests for `read_context_tokens_from_state`:

   - **`test_read_context_tokens_fresh`** — state has `context_current_tokens=50000` and
     `context_current_tokens_recorded_at` set 10 minutes ago (use `_now` override with default
     TTL=60) → returns `50000`.

   - **`test_read_context_tokens_stale`** — state has `context_current_tokens=50000` and
     `context_current_tokens_recorded_at` set 90 minutes ago (use `_now` override, default
     TTL=60) → returns `None`.

   - **`test_read_context_tokens_no_recorded_at`** — state has `context_current_tokens=50000`
     but no `context_current_tokens_recorded_at` key → returns `50000` (no TTL enforced).

   - **`test_read_context_tokens_unparseable_recorded_at`** — state has
     `context_current_tokens=50000` and `context_current_tokens_recorded_at="not-a-date"` →
     returns `50000` (parse failure skips staleness check).

   - **`test_read_context_tokens_custom_ttl`** — state has `context_current_tokens=50000`,
     `context_current_tokens_recorded_at` set 30 minutes ago, and
     `context_current_tokens_ttl_minutes=20` → returns `None` (stale under custom TTL).

6. Add a test for the `set-context-tokens` CLI timestamp write:

   - **`test_set_context_tokens_writes_recorded_at`** — call `set-context-tokens --tokens 42000`
     on a temp project dir; read back `state.json`; assert `context_current_tokens_recorded_at`
     is present and can be parsed by `datetime.fromisoformat()`.

### Tests — `tests/pairmode/test_story_context.py`

7. Add a test for the `--clear` token wipe:

   - **`test_clear_removes_context_tokens`** — seed `state.json` with `current_story`,
     `context_current_tokens=50000`, and `context_current_tokens_recorded_at="2026-01-01T00:00:00+00:00"`;
     call `story_context --clear`; assert neither `context_current_tokens` nor
     `context_current_tokens_recorded_at` appears in the resulting `state.json`.

## Out of scope

- Changes to `_read_state()` (INFRA-150)
- Changes to `hooks/pre_tool_use.py`
- Surfacing recorded_at or TTL in the CONTEXT BUDGET alert prompt
- Syncing the `--clear` behavior change to downstream projects via `pairmode_sync.py`
  (the set-context-tokens step is part of the build loop, not the sync template)
