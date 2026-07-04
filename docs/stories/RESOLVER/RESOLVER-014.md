---
id: RESOLVER-014
rail: RESOLVER
title: Fix active-phase selection — first non-inactive wins
status: complete
phase: "HARNESS009-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
  - tests/pairmode/test_active_phase_selection.py
touches: []
---

## Context

`_resolve_active_phase` in `next_action.py` walks the phase index and keeps the **last**
non-inactive row (`active_phase_ref = phase_ref  # last non-inactive row wins`). This is
wrong for sequential phases: when two phases are both `planned`, it picks the later one
instead of the earlier one, making it impossible to build them in order.

The bug surfaced at HARNESS009-main start-up: both HARNESS009-main and HARNESS010-main
are `planned` in the index; the resolver picked HARNESS010-main (alphabetically later) and
tried to build HARNESS-004 instead of RESOLVER-012. The "last non-inactive wins" comment
was written during CER-056 as a contrast to the prior `deferred`/`backlog` skip logic, but
the semantics are wrong for a sequential build queue.

The fix is one character: `break` after the first non-inactive hit, making it **first
non-inactive wins**. This preserves the CER-056 fix (inactive statuses are still skipped)
while correctly sequencing multiple planned phases.

## Ensures

- `_resolve_active_phase` returns the **first** phase file whose status is not inactive
  (not `complete`, `deferred`, or `backlog`), walking the index in document order.
- The comment on the assignment is updated to `# first non-inactive row wins`.
- Given a phase index with phases A=`complete`, B=`planned`, C=`planned`, the function
  returns B (not C).
- Given a phase index with A=`complete`, B=`deferred`, C=`planned`, the function returns C.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

1. In `skills/pairmode/scripts/next_action.py`, in `_resolve_active_phase`, change the
   loop body from:
   ```python
   for phase_ref, status in phase_rows:
       if not _is_phase_inactive(status):
           active_phase_ref = phase_ref  # last non-inactive row wins
   ```
   to:
   ```python
   for phase_ref, status in phase_rows:
       if not _is_phase_inactive(status):
           active_phase_ref = phase_ref  # first non-inactive row wins
           break
   ```

2. Write `tests/pairmode/test_active_phase_selection.py` with parametrized tests covering:
   - A=complete, B=planned, C=planned → returns B
   - A=complete, B=deferred, C=planned → returns C
   - A=complete, B=backlog, C=planned → returns C
   - All complete → returns None
   - Single planned → returns it

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_active_phase_selection.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```
