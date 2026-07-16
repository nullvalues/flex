---
id: RESOLVER-015
rail: RESOLVER
title: "`flex_build.py` hygiene — depth guard, single-source `_CHECKPOINT_SEQUENCE`, `_story_path` containment"
status: complete
phase: "HARNESS009-post1"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
touches:
  - tests/pairmode/test_record_checkpoint_step.py
---

## Context

Three small hygiene issues in `flex_build.py` surfaced during HARNESS009-main's checkpoint
reviews. All three are in the same file; this story batches them.

**CER-061** — `cmd_record_checkpoint_step` (added in RESOLVER-012) does not call
`_depth_guard(project_dir)` before writing `state.json`, unlike every other write-capable
command that takes `--project-dir`. The write destination is always the fixed relative path
`.companion/state.json` and `step_id` is whitelist-validated, so there is no traversal risk
— but the missing guard is an inconsistency with the project convention.

**CER-068** — `_CHECKPOINT_SEQUENCE` is inlined as literal strings in `flex_build.py`'s
`record-checkpoint-step` helper instead of imported from `next_action.py` where the tuple
is the authoritative definition. A future change to `next_action.py`'s `_CHECKPOINT_SEQUENCE`
must also be applied manually to `flex_build.py`; there is no mechanical enforcement.

**CER-034** — `_story_path()` in `flex_build.py` constructs `docs/stories/<rail>/<story_id>.md`
from the `--story-id` CLI argument with no `Path.resolve().relative_to(stories_root)`
containment check. A crafted story ID with `..` segments could escape `docs/stories/`. Blast
radius is low (read-only, orchestrator-supplied input), but inconsistent with the containment
discipline applied elsewhere.

## Ensures

- **CER-061:** `cmd_record_checkpoint_step` calls `_depth_guard(project_dir)` before any I/O.
  The call is placed at the entry of the command function, consistent with all other write
  commands (`cmd_write_attempt_count`, `cmd_clear_attempt_count`, etc.).

- **CER-068:** `_CHECKPOINT_SEQUENCE` is imported from `next_action` in `flex_build.py`
  (e.g. `from next_action import _CHECKPOINT_SEQUENCE`). The inlined tuple in the
  `_record_checkpoint_step` helper is removed. The same four values are now in exactly one
  place. If circular import is a concern, extract to a thin `checkpoint_constants.py` module
  imported by both (but try the direct import first — `flex_build.py` already imports from
  `next_action`).

- **CER-034:** `_story_path()` adds a `Path.resolve().relative_to(stories_root)` containment
  check after constructing the candidate path. On containment failure, the function raises
  `ValueError` (which callers already handle as a path-not-found condition) or exits non-zero
  with a clear error message. `stories_root` is `project_dir / "docs" / "stories"`.

- Existing tests in `tests/pairmode/test_record_checkpoint_step.py` still pass (the depth
  guard call is transparent for valid `project_dir` values used in tests).
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

1. **CER-068 first (import before use):** In `flex_build.py`, add
   `from next_action import _CHECKPOINT_SEQUENCE` to the imports section (near the top, with
   other `next_action` imports if any exist, otherwise with the pairmode-scripts imports).
   Remove the inlined tuple from `_record_checkpoint_step`.

2. **CER-061:** In `cmd_record_checkpoint_step`, add `_depth_guard(project_dir)` immediately
   after `project_dir = Path(project_dir).resolve()`. Follow the pattern of any adjacent
   write command (`cmd_write_attempt_count` is a close reference).

3. **CER-034:** In `_story_path()`, after resolving the candidate path, add:
   ```python
   stories_root = (project_dir / "docs" / "stories").resolve()
   try:
       resolved.relative_to(stories_root)
   except ValueError:
       raise ValueError(f"story ID escapes stories root: {story_id}")
   ```
   Adjust the exact error surface (ValueError vs. sys.exit) to match how callers currently
   handle a missing story file — look at how `cmd_check_stub` and `cmd_next_action` call
   `_story_path` and respond to errors.

4. Run tests:
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
   ```

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_record_checkpoint_step.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: depth guard present in `cmd_record_checkpoint_step`; `_CHECKPOINT_SEQUENCE`
imported from `next_action` (no inline tuple in `flex_build.py`); `_story_path()` rejects
`..` traversal; full suite green.
