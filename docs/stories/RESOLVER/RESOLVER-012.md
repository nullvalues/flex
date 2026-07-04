---
id: RESOLVER-012
rail: RESOLVER
title: "`record-checkpoint-step` CLI + orchestrator wiring"
status: planned
phase: "HARNESS009-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - tests/pairmode/test_record_checkpoint_step.py
---

## Context

`next_action.py:748–758` reads `state.json["checkpoint_step"]` to sequence the four checkpoint
sub-actions (`checkpoint-security`, `checkpoint-intent`, `checkpoint-docs`, `checkpoint-tag`).
No `flex_build.py` CLI currently writes this key — the orchestrator LLM is expected to append
the correct step ID string by prose compliance. There is no validation at write time. If the
orchestrator writes a wrong step ID, the resolver re-emits the same checkpoint action forever
(silent loop). This story closes that gap by adding a CLI command that writes
`state.json["checkpoint_step"]` atomically, with validation and idempotency.

Known step IDs are defined in `_CHECKPOINT_SEQUENCE` at `next_action.py:168–173`:
`checkpoint-security`, `checkpoint-intent`, `checkpoint-docs`, `checkpoint-tag`.

## Ensures

- `flex_build.py record-checkpoint-step <step-id>` command exists.
- It **atomically appends** the step ID to `state.json["checkpoint_step"]` (read → append →
  write in one operation; no partial writes).
- It **validates** the step ID against `_CHECKPOINT_SEQUENCE` before writing. An unknown step
  ID → exits non-zero with a clear error message; state.json is not mutated.
- It is **idempotent**: if the step ID is already in the list, exits 0 with no write.
- It writes only the `checkpoint_step` key; no other keys are touched.
- `CLAUDE.build.md` checkpoint section is updated to include:
  "After each checkpoint leaf worker returns, call `flex_build.py record-checkpoint-step <action>`
  before re-running next-action. checkpoint-tag: `git tag cp-<phase-key> && git push origin harness --tags`."
- `skills/pairmode/templates/CLAUDE.build.md.j2` is updated identically.
- Tests in `tests/pairmode/test_record_checkpoint_step.py` cover:
  - Valid step ID appended to empty list
  - Valid step ID idempotent (already in list → exits 0, no write)
  - Invalid step ID → exits non-zero, state.json unchanged
  - Atomicity: no partial write on concurrent call (sequential test is sufficient)
  - All four known step IDs are accepted
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

1. Add `flex_build.py record-checkpoint-step` as a Click command. It should:
   - Accept `step_id` as a positional argument.
   - Load `_CHECKPOINT_SEQUENCE` from `next_action.py` (import or inline the tuple).
   - Validate `step_id` against `_CHECKPOINT_SEQUENCE`; exit non-zero with message on failure.
   - Read `state.json` from `project_dir` (use `--project-dir` option, same as other commands).
   - If `step_id` already in `state["checkpoint_step"]` list → exit 0, no write.
   - Otherwise append and write atomically (write to temp file, rename).
   - Exit 0 on success.

2. Update `CLAUDE.build.md` `## Checkpoint` section per the Ensures above.

3. Update `skills/pairmode/templates/CLAUDE.build.md.j2` identically.

4. Write `tests/pairmode/test_record_checkpoint_step.py` covering the cases listed in Ensures.
   Use `tmp_path` to create a minimal `state.json` in a temp project dir.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_record_checkpoint_step.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: CLI exists and passes all test cases; CLAUDE.build.md and .j2 template both
updated with `record-checkpoint-step` wiring; full test suite green.
