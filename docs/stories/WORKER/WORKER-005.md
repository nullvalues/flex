---
id: WORKER-005
rail: WORKER
title: Builder leaf worker — thin shell + plugin procedure skill
status: complete
phase: "HARNESS003-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/builder/procedure.md
  - tests/pairmode/test_builder_worker.py
touches:
  - skills/pairmode/scripts/worker_result.py
---

## Context

Converts the builder from a per-project rendered `.claude/agents/builder.md` (derived from
`skills/pairmode/templates/agents/builder.md.j2`) to a thin agent shell + plugin procedure skill
— the same pattern as the gate worker (HARNESS002). The builder procedure is extracted from the
current `CLAUDE.build.md` builder-step prose and the existing `builder.md.j2` template into a
versioned, plugin-owned skill file. The old `.md.j2` template and rendered file remain during the
advisory window (HARNESS006 removes them). Returns `BUILD-RESULT` per the WORKER-004 grammar.

## Requires

- WORKER-004 complete: `worker_result.py` defines `BUILD-RESULT` and `parse_worker_result`.

## Ensures

- `skills/pairmode/skills/builder/procedure.md` — the canonical builder procedure (extracted from
  `CLAUDE.build.md` prose + `builder.md.j2`). The thin agent shell loads this file and follows it
  for the current story. Bounded inputs: the story spec (`docs/stories/<RAIL>/<ID>.md`), the
  phase doc, `CLAUDE.md`, and `CLAUDE.build.md` — no accumulated orchestrator state, no prior
  attempt transcripts beyond what the resolver provides as the `scalar`.
- The thin agent shell (embedded in `procedure.md`'s preamble, or as a companion `shell.md`)
  instructs: "Load `skills/pairmode/skills/builder/procedure.md`. Execute the build procedure for
  story `{scalar}`. Return the result as JSON matching the `BUILD-RESULT` schema."
- **DP1.3 input-bound guard:** the procedure/shell reference only the four declared inputs — no
  phase history, no prior-attempt transcripts, no orchestrator state. Asserted in WORKER-010.
- The `spawn-builder` action already exists in `ACTIONS` and `_SPAWN_ACTIONS` (HARNESS001-main
  RESOLVER-001); no action grammar change in this story.
- **No live API call in tests.** Injected `BUILD-RESULT` objects are fed to the routing assertion.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_builder_worker.py -x -q` passes.
- The existing `builder.md.j2` template and the rendered `.claude/agents/builder.md` are NOT
  removed (advisory window; removed in HARNESS006 HARNESS-002).

## Instructions

- Extract the builder procedure from the current `CLAUDE.build.md` § Build loop prose and the
  `.md.j2` template. Keep the procedure faithful to the current behavior — this is a lift-and-shift,
  not a redesign. Write it to `skills/pairmode/skills/builder/procedure.md`.
- The thin shell is minimal: load the procedure file, run it for the scalar story ID, return
  `BUILD-RESULT` JSON. No business logic in the shell.
- Write `tests/pairmode/test_builder_worker.py` asserting: the procedure file exists; its content
  references only the declared bounded inputs (negative assertion on accumulated-state references);
  an injected `BUILD-RESULT{outcome: "PASS"}` parses correctly via `worker_result.py`; an injected
  `BUILD-RESULT{outcome: "FAIL"}` parses correctly.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_builder_worker.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: procedure file exists with correct bounded inputs; shell is thin; injected results
parse correctly; no live API call; suite green.

### Out of scope

- Routing changes for `BUILD-RESULT` in `resolve_next_action` — the orchestrator handles the
  builder/reviewer micro-sequence within a turn (HARNESS003 agreements DP2); no resolver change.
- Removal of the old `builder.md.j2` and rendered file — HARNESS006 HARNESS-002.
- The reviewer leaf worker — WORKER-006.
