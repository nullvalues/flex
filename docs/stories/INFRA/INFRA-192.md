---
id: INFRA-192
rail: INFRA
title: Context gate edge cases and session_id safety
status: draft
phase: "HARNESS011-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/context_budget.py
  - skills/pairmode/scripts/flex_build.py
touches:
  - tests/pairmode/test_context_budget.py
---

## Acceptance criterion

- **CER-040** — `context_budget.decide()` no longer fails open silently when `state.json`
  is absent or contains malformed JSON. When `_read_state()` returns `None`:
  - If the current project directory has a `.companion/` directory (i.e. is a pairmode
    project), `decide()` returns `_CONTEXT_CHECK_REQUIRED_MSG` (same message as a missing
    key), not `None`.
  - If no `.companion/` directory exists (non-pairmode project), `decide()` returns `None`
    (preserves existing pass-through for non-pairmode use).
  - Rationale: a pairmode project with a corrupted/missing state.json should surface the
    gate as needing attention, not silently pass.
- **CER-041** — `set-context-tokens` CLI writes `context_current_tokens_recorded_at` (ISO
  8601 UTC timestamp) alongside `context_current_tokens` in `state.json`.
  `read_context_tokens_from_state()` treats a value whose `recorded_at` is older than 60
  minutes as absent (returns `None`). The TTL is a named constant
  `_CONTEXT_TOKEN_STALE_MINUTES = 60`.
- **CER-051** — `_derive_transcript_path()` in `context_budget.py` validates `session_id`
  before constructing the path: rejects any value containing `/` or `..`. On rejection,
  returns `None` (safe fail-open, same as other error paths in the function).
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_context_budget.py -x -q`
  passes.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

### CER-040 — decide() pairmode-aware fail-closed

In `context_budget.py`, modify `decide()`:
- After `_read_state()` returns `None`, check for the presence of `.companion/` in the
  project directory (`Path(project_dir) / ".companion"`).
- If present: return `_CONTEXT_CHECK_REQUIRED_MSG`.
- If absent: return `None` (non-pairmode pass-through unchanged).

### CER-041 — recorded_at timestamp

In `flex_build.py`, `cmd_set_context_tokens()`:
- Write `context_current_tokens_recorded_at` as `datetime.utcnow().isoformat() + "Z"`
  alongside `context_current_tokens`.

In `context_budget.py`, `read_context_tokens_from_state()`:
- After reading `context_current_tokens`, also read `context_current_tokens_recorded_at`.
- If `recorded_at` is present and older than `_CONTEXT_TOKEN_STALE_MINUTES`, return
  `None` (treat as absent).
- If `recorded_at` is absent, the value is used as-is (backward-compatible with existing
  state.json files that lack the field).

### CER-051 — session_id traversal guard

In `context_budget.py`, `_derive_transcript_path()`:
- At function entry, after receiving `session_id`, check: `if "/" in session_id or ".." in session_id: return None`.
- No other change to the function.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_context_budget.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

New test cases to add in `test_context_budget.py`:
- `decide()` returns check-required message when `.companion/` exists but `state.json` is
  absent.
- `decide()` returns `None` when `.companion/` is absent (non-pairmode path).
- `read_context_tokens_from_state()` returns `None` when `recorded_at` is older than 60
  min.
- `read_context_tokens_from_state()` returns value when `recorded_at` is absent
  (backward-compat).
- `_derive_transcript_path()` returns `None` for `session_id` containing `/`.
- `_derive_transcript_path()` returns `None` for `session_id` containing `..`.
