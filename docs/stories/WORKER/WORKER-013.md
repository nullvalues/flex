---
id: WORKER-013
rail: WORKER
title: Spec-writer leaf worker — thin shell + plugin procedure skill
status: complete
phase: "HARNESS005-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/spec-writer/procedure.md
  - tests/pairmode/test_spec_writer_worker.py
touches:
  - skills/pairmode/scripts/worker_result.py
---

## Context

The WORKER half of HARNESS005 (agreements DP2): the spec-writer leaf worker. Replaces the inline
Plan-subagent spawn in `CLAUDE.build.md` spec mode with a thin agent shell + plugin procedure skill.
The worker receives a stub story ID as its scalar, reads the bounded inputs, expands the story
spec in place, and returns `SPEC-RESULT`. Advisory-only — not wired into the live `CLAUDE.build.md`
until HARNESS006.

## Requires

- RESOLVER-009 complete: `spawn-spec-writer` in `ACTIONS`; `needs_spec` Position flag.

## Ensures

- `skills/pairmode/skills/spec-writer/procedure.md` — spec-writer procedure. Bounded inputs:
  (1) the stub story file (`docs/stories/<RAIL>/<ID>.md`), (2) the phase doc
  (`docs/phases/phase-<key>.md`), (3) the active era doc (`docs/eras/*.md` where `status: active`),
  (4) one recent complete story as format exemplar. No accumulated orchestrator state.
- The procedure: read the four bounded inputs → draft the Ensures/Instructions/Tests/Out-of-scope
  sections → write them to the story file in place (expanding the stub) → return `SPEC-RESULT`.
- Returns `SPEC-RESULT{type: "SPEC-RESULT", story_id: str, status: "done"|"revised"}`.
  Returns `"revised"` if the procedure identifies that human review is needed before building.
- The thin shell: "Load `skills/pairmode/skills/spec-writer/procedure.md`. Run the spec-writing
  procedure for story `{scalar}`. Return the result as JSON matching the `SPEC-RESULT` schema."
- **DP1.3 input-bound guard:** procedure references only the four declared bounded inputs.
  Asserted in WORKER-014.
- **Single write target:** the procedure writes ONLY to the story file identified by `scalar`.
  No other files are touched. A `grep` in the test asserts the procedure contains no paths
  outside `docs/stories/`.
- `spawn-spec-writer` in `ACTIONS` + `_SPAWN_ACTIONS` (RESOLVER-009). `SCHEMA_VERSION == 4`.
- Tests assert: procedure file exists; bounded inputs (negative assertion); single write target
  (no out-of-scope paths in procedure); injected `SPEC-RESULT{status: "done"}` parses;
  injected `SPEC-RESULT{status: "revised"}` parses. No live API call.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Adapt the current `CLAUDE.build.md` § Spec workflow steps 3–5 into the procedure. The procedure
  runs the Plan-role logic within the spec-writer's disposable context (not a recursive spawn).
- The format exemplar input is bounded: the procedure reads one file from `docs/stories/` (the
  most recently modified complete story in the same rail, or any rail if none). No directory scan.
- Write the procedure so a fresh-context agent running it produces a complete story spec body
  (Context + Requires + Ensures + Instructions + Tests + Out of scope) in the story file.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_spec_writer_worker.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: procedure file exists; bounded inputs; single write target; injected results parse;
no live API call; suite green.

### Out of scope

- HARNESS005 isolation suite (WORKER-014).
- Phase scaffolding (`phase_new.py` / `story_new.py`) — operator action, unchanged.
- Multi-story spec generation (the worker operates on one story at a time).
- Wiring into live `CLAUDE.build.md` (HARNESS006).
