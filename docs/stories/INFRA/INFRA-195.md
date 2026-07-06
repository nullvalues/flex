---
id: INFRA-195
rail: INFRA
title: PIPE_PATH redirectable via crafted state.json
status: draft
phase: "HARNESS011-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - hooks/post_tool_use.py
touches: []
---

## Acceptance criterion

- **CER-009** — `hooks/post_tool_use.py` no longer reads `pipe_path` from `state.json`
  to override `PIPE_PATH`. The pipe path is fixed to the default
  `os.path.join(tempfile.gettempdir(), "companion.pipe")` for portability. The `state.json`
  read for `pipe_path` is removed from `post_tool_use.py`.
- Existing FIFO-write behavior is unchanged: if the FIFO does not exist or the write
  fails, the failure is silently swallowed (no change to error handling).
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

In `hooks/post_tool_use.py`:
1. Remove the block that reads `.companion/state.json` for `pipe_path`.
2. Change `PIPE_PATH` to `os.path.join(tempfile.gettempdir(), "companion.pipe")` (matching
   the pattern `exit_plan_mode.py` already uses).
3. Add `import tempfile` if not already present.

Do not modify `hooks/stop.py` or `hooks/session_end.py` — those are on `main` only and
out of scope for the harness branch.

## Tests

No new tests required for this story. The pipe-write path is exercised by existing hook
tests; the change is a removal of the state.json read, not a behavior change.
