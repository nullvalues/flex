---
id: RESOLVER-016
rail: RESOLVER
title: Remove `parse_worker_verdict_text` + test cleanup
status: complete
phase: "HARNESS009-post1"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
  - tests/pairmode/test_next_action.py
touches:
  - tests/pairmode/test_parse_worker_verdict_json.py
---

## Context

RESOLVER-013 replaced `parse_worker_verdict_text` with `parse_worker_verdict_json` (fail-closed
JSON parser) but retained the old function as dead code with a deprecation note rather than
removing it, because the story spec said "removing is preferred" but the builder chose the
conservative path. The function has no live call sites in production code. Tests in
`test_next_action.py` still exercise it directly (the `TestParseWorkerVerdictText` class,
~10 tests, around line 1213).

This story completes the RESOLVER-013 spec intent: remove the deprecated function and replace
its tests with equivalent coverage of `parse_worker_verdict_json`.

**CER-063.**

## Ensures

- `parse_worker_verdict_text` is removed from `next_action.py`. No stub, no deprecation
  comment — the function is gone.
- `tests/pairmode/test_next_action.py` no longer imports `parse_worker_verdict_text`. The
  `TestParseWorkerVerdictText` class is removed.
- If `TestParseWorkerVerdictText` covered any edge cases not already covered by
  `tests/pairmode/test_parse_worker_verdict_json.py` (written in RESOLVER-013), those cases
  are ported as new tests in `test_parse_worker_verdict_json.py` before removing the old class.
  If all cases are already covered, the class is simply deleted.
- `route_gate_verdict`'s docstring reference to `parse_worker_verdict_text` (the `:func:`
  cross-reference in its parameters section) is updated to reference `parse_worker_verdict_json`.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

1. In `next_action.py`, find and delete `parse_worker_verdict_text` (the function definition
   starting around line 1077, ending before `route_gate_verdict`).

2. In `route_gate_verdict`'s docstring, find the `:func:\`parse_worker_verdict_text\`` cross-
   reference in the Parameters section and update it to `:func:\`parse_worker_verdict_json\``.

3. In `tests/pairmode/test_next_action.py`, find `TestParseWorkerVerdictText`. Before deleting
   it, review each test case and check whether an equivalent case exists in
   `tests/pairmode/test_parse_worker_verdict_json.py`. Port any uncovered cases. Then delete
   the class and its import of `parse_worker_verdict_text`.

4. Run tests:
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
   ```

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_parse_worker_verdict_json.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: `parse_worker_verdict_text` removed from production code and tests; no import of
the old name anywhere; `test_parse_worker_verdict_json.py` covers all previously-tested cases;
full suite green.
