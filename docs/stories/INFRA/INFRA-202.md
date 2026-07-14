---
id: INFRA-202
rail: INFRA
title: Adopt state_utils atomic write in remaining state.json writers (CER-050)
status: planned
phase: "HARNESS015-main"
story_class: code
auth_gated: false
schema_introduces: false
touches:
  - hooks/post_tool_use.py  # protected file — reason: swap the remaining non-atomic state.json write for the shared state_utils atomic writer (CER-050), no other logic change
  - skills/companion/scripts/sidebar.py  # protected file — reason: same swap, three state.json write sites (CER-050)
---

## Requires

- `skills/pairmode/scripts/state_utils.py` `_atomic_write_json(path, data)` (built for CER-050/INFRA-200) already exists and is adopted by `hooks/pre_tool_use.py`, `hooks/session_start.py`, `skills/pairmode/scripts/flex_build.py`, and `skills/pairmode/scripts/pairmode_migrate.py`.
- These `.companion/state.json` writers still use raw `path.write_text(json.dumps(...))` with no temp-file + `os.replace()`:
  - `hooks/post_tool_use.py:63`
  - `skills/pairmode/scripts/story_context.py:50` (`write_state`, used by `set_current_story` / `--clear`)
  - `skills/pairmode/scripts/bootstrap.py:473` (`_record_state`)
  - `skills/companion/scripts/sidebar.py:1692`, `:1839`, `:1856`
- `skills/pairmode/scripts/pairmode_sync.py:577` and `skills/pairmode/scripts/pairmode_register.py:_write_state_atomic` already do their own inline tempfile+`os.replace` — already atomic, out of scope for this story (cosmetic DRY only, not a correctness gap).

## Ensures

- `hooks/post_tool_use.py`'s `state.json` write goes through `state_utils._atomic_write_json` instead of `state_path.write_text(...)`.
- `story_context.py`'s `write_state()` goes through `state_utils._atomic_write_json` instead of `state_path.write_text(...)`.
- `bootstrap.py`'s `_record_state()` (or equivalent state.json write at line 473) goes through `state_utils._atomic_write_json` instead of `state_path.write_text(...)`.
- All three `sidebar.py` state.json write sites (`:1692`, `:1839`, `:1856`) go through `state_utils._atomic_write_json` instead of `write_text(...)`.
- No writer's on-disk JSON output changes shape or key ordering in a way that breaks existing tests — this is a mechanism swap only, not a data-format change.
- `tests/pairmode/test_state_utils.py` or an equivalent per-module test confirms each of the four modules above now round-trips its state.json write via `state_utils._atomic_write_json` (e.g. by monkeypatching/spying on `_atomic_write_json` and asserting it was called, or by verifying no `.tmp` file survives after a write — whichever fits each module's existing test harness).
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

For each of the four writers, replace the direct `path.write_text(json.dumps(data, indent=2))` (or equivalent) call with an import of `state_utils` and a call to `state_utils._atomic_write_json(path, data)`. Match the import pattern already used in `hooks/pre_tool_use.py` / `hooks/session_start.py` (both import `state_utils` via the same `sys.path` injection hooks already use, per `state_utils.py`'s own docstring: "stdlib-only so it can be safely imported by hooks/").

Do not change:
- `pairmode_sync.py` or `pairmode_register.py` (already atomic via their own inline implementations — out of scope).
- The shape of the written JSON, the trailing-newline convention, or key ordering in any of the four files, beyond what naturally follows from routing through the shared helper.

`hooks/post_tool_use.py` and `skills/companion/scripts/sidebar.py` are both on
the reviewer's protected-files list (item 7). The reason for touching them is
declared above in `touches`: this story's entire purpose is closing the last
gap in the CER-050 atomic-write rollout, and these two files are two of the
four remaining non-atomic writers.

## Tests

- Add or extend unit tests for `hooks/post_tool_use.py`, `story_context.py`,
  `bootstrap.py`, and `sidebar.py` confirming their state.json write path now
  delegates to `state_utils._atomic_write_json` (spy/monkeypatch on the
  imported name, or assert the write leaves no orphaned `.tmp` file and the
  target file is replaced via rename rather than truncate-in-place).
- Full suite: `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`.
