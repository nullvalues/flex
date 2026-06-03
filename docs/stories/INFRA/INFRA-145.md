---
id: INFRA-145
rail: INFRA
title: "CER-038: `phase_new.py` phase-id/suffix path validation"
status: complete
phase: "56"
primary_files:
  - skills/pairmode/scripts/phase_new.py
touches:
  - tests/pairmode/test_phase_new.py
---

# INFRA-145 — CER-038: `phase_new.py` phase-id/suffix path validation

## Context

Phase 56 security audit found that `--phase-id` and `--suffix` CLI arguments in
`phase_new.py` are accepted as free-form strings and embedded directly into
filesystem paths without sanitization. A crafted argument like
`--suffix "../../../../../../etc/attack"` can write outside the project directory.
The `relative_to()` calls in the code are display-only; they do not protect the write.
Secondary finding: no traversal test cases in the new test classes.

## Acceptance criteria

1. At the start of the `phase_new` Click command (before any filesystem access), validate
   both `phase_id` and `suffix` (when non-None) against:
   ```python
   re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value)
   ```
   On failure: `click.echo(f"Error: --phase-id / --suffix must match [A-Za-z0-9][A-Za-z0-9_-]*", err=True)` and `raise SystemExit(1)`.

2. An empty string for `phase_id` is rejected by the same check (the pattern requires at
   least one character, and the first character must be alphanumeric).

3. Tests in `test_phase_new.py` cover:
   - `--phase-id "../../../attack"` → exits with code 1, no file written
   - `--phase-id "56" --suffix "../../escape"` → exits with code 1, no file written
   - `--phase-id "56" --suffix "/abs/path"` → exits with code 1, no file written
   - `--phase-id "PM025" --suffix "main"` → still works (valid characters)
   - `--phase-id "56"` (no suffix) → still works

4. All 1951 existing tests continue to pass.

## Implementation notes

- Add validation immediately after the `project_path` and `phases_dir` setup, before the
  idempotency check and any other logic.
- The pattern `[A-Za-z0-9][A-Za-z0-9_-]*` allows: `56`, `PM025`, `main`, `post1`,
  `ante1`, `sec`, `PM025-main` (though dashes within the id are also allowed as it's
  one token). It rejects: `..`, `/`, `../../etc`, empty string.
- Only validate `suffix` when it is not None (it's an optional parameter).
