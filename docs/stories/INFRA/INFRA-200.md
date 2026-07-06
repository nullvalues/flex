---
id: INFRA-200
rail: INFRA
title: state.json atomic writes
status: draft
phase: "HARNESS011-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - hooks/session_start.py
  - hooks/pre_tool_use.py
  - skills/pairmode/scripts/flex_build.py
touches: []
---

## Acceptance criterion

- **CER-050** — All three `state.json` writers use atomic write (temp file + `os.replace()`):
  - `hooks/session_start.py` (INFRA-175 reset write)
  - `hooks/pre_tool_use.py` (`acknowledged_at` write)
  - `flex_build.py` CLI paths that write `state.json`
- A shared helper `_atomic_write_json(path: Path, data: dict) -> None` is added. It:
  1. Writes `json.dumps(data, indent=2)` to a `.tmp` sibling of `path` (same directory).
  2. Calls `os.replace(tmp_path, path)` (atomic on POSIX).
  3. On any exception: deletes the `.tmp` file if it exists, then re-raises.
- All existing `write_text()` / direct `open(..., "w")` state.json write calls are
  replaced with the helper.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

Add `_atomic_write_json` to a shared location. Options in priority order:
1. Add to `skills/pairmode/scripts/flex_build.py` (already imports across hooks via
   PYTHONPATH) and import from there in the hooks.
2. Or add to a new `skills/pairmode/scripts/state_utils.py` module.

Update each writer to use the helper. Verify the `.tmp` cleanup behavior on exception
with a test that patches `os.replace` to raise.

## Tests

Add to `tests/pairmode/test_flex_build.py` (or a new `test_state_utils.py`):
- `_atomic_write_json` writes the expected content.
- `_atomic_write_json` cleans up the `.tmp` file on exception.
