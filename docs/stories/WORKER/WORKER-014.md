---
id: WORKER-014
rail: WORKER
title: HARNESS005 isolation suite
status: complete
phase: "HARNESS005-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - tests/pairmode/test_harness005_isolation.py
touches:
  - tests/pairmode/resolver_fixtures.py
  - tests/pairmode/test_needs_spec.py
---

## Context

The acceptance backbone of HARNESS005 (agreements DP4): pins the spec-writer's deterministic
scaffold — `needs_spec` detection, `spawn-spec-writer` routing, `SPEC-RESULT` routing — with no
live API calls. The LLM-generated spec quality is documented as a deliberate out-of-scope gap.

## Requires

- RESOLVER-009 and WORKER-013 both complete.

## Ensures

The suite covers the full HARNESS005 isolation matrix:

- **`needs_spec` detection** (synthetic story file fixtures):
  - Story with no `## Ensures` section → `needs_spec: True` → resolver emits `spawn-spec-writer`.
  - Story with stub `## Ensures` (< 5 non-blank lines) → `needs_spec: True`.
  - Story with complete `## Ensures` (≥ 5 non-blank lines) → `needs_spec: False` → resolver
    proceeds to `spawn-gate-worker` (or `spawn-builder` if gates clean).
- **`SPEC-RESULT` routing** (injected verdicts):
  - `SPEC-RESULT{status: "done"}` injected → harness re-reads `next-action` on the now-expanded
    story → `needs_spec` is False → resolver emits the normal next action (assert `spawn-gate-worker`
    or `spawn-builder`, not `spawn-spec-writer`). Simulate by providing the "done" result and an
    expanded-story fixture.
  - `SPEC-RESULT{status: "revised"}` injected → the harness emits `await-user` with
    `reason="spec-revised-awaiting-review"`. Assert this routing.
- **`SPEC-RESULT` grammar round-trip** — via `worker_result.py`: both `"done"` and `"revised"`
  parse and validate; invalid (missing `story_id`) fails validation.
- **Spec-writer shell input-bound guard** — procedure at `skills/pairmode/skills/spec-writer/
  procedure.md` references only the four declared bounded inputs (stub story, phase doc, era doc,
  format exemplar); no accumulated orchestrator state; no paths outside `docs/stories/` in write
  targets.
- **`SCHEMA_VERSION == 4`** — assert it; `"spawn-spec-writer"` in `ACTIONS` and `_SPAWN_ACTIONS`.
- LLM-judgment gap documented: spec text quality is out of scope for unit assertion.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Use `resolver_fixtures.py` for synthetic story files (write a minimal stub story to a temp dir,
  run `infer_position`, assert `needs_spec`).
- For the `SPEC-RESULT{status: "done"}` routing test: patch `infer_position` to return a
  `needs_spec: False` Position after the "done" result (simulating the story file having been
  expanded by the worker), then assert the resolver emits `spawn-gate-worker`.
- Table-driven parametrize for the `needs_spec` detection fixtures (no `## Ensures` / stub /
  complete).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_harness005_isolation.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: all `needs_spec` detection states; `SPEC-RESULT` routing (done / revised);
grammar round-trip; input-bound guard; `SCHEMA_VERSION == 4`; LLM gap documented; suite green.

### Out of scope

- Asserting LLM spec quality.
- Phase scaffolding CLIs.
- Wiring into live `CLAUDE.build.md` (HARNESS006).
