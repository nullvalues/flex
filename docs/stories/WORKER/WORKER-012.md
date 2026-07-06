---
id: WORKER-012
rail: WORKER
title: HARNESS004 isolation suite
status: complete
phase: "HARNESS004-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - tests/pairmode/test_harness004_isolation.py
touches:
  - tests/pairmode/resolver_fixtures.py
  - tests/pairmode/test_checkpoint_routing.py
---

## Context

The acceptance backbone of HARNESS004 (agreements DP6): pins the entire checkpoint action
sequence deterministically. No live API call, no real git operations, no real pytest invocations.
The LLM-judgment gap (the actual security/intent/docs review quality) is documented explicitly.

## Requires

- RESOLVER-007, WORKER-011, RESOLVER-008 all complete.

## Ensures

The suite covers the full HARNESS004 isolation matrix:

- **Pre-checkpoint guard failures** — one fixture per guard class:
  - Incomplete phase (at least one story `planned`/`in-progress`) → `await-user:checkpoint-guard-failed:phase-incomplete`.
  - CER Do Now not clear → `await-user:checkpoint-guard-failed:cer-do-now`.
  - Build gate fails (injected; no real pytest run) → `await-user:checkpoint-guard-failed:build-gate`.
- **Checkpoint step sequencing** — the ordered 5-state matrix (no step → security; security done →
  intent; security+intent done → docs; security+intent+docs done → tag; all done → done/next-phase).
  All states asserted with synthetic `position["checkpoint_step"]` values.
- **`checkpoint-tag` action shape** — `model=None`; `scalar=phase_key`; NOT in `_SPAWN_ACTIONS`.
- **Docs-review worker input-bound guard** — procedure at
  `skills/pairmode/skills/checkpoint-docs/procedure.md` references only its declared bounded inputs
  (the five docs listed in WORKER-011 Ensures); no accumulated orchestrator state references.
- **`SCHEMA_VERSION == 3`** — assert it.
- **All checkpoint actions in `ACTIONS`**; `"checkpoint"` NOT in `ACTIONS`.
- LLM-judgment gap documented: the security/intent/docs review verdicts are injected; actual
  judgment quality is out of scope for this suite.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Use `resolver_fixtures.py` for synthetic durable-state trees with controlled `checkpoint_step`
  values in `state.json`.
- Inject the build gate function via dependency injection (pass a `gate_fn=lambda: True` to the
  pre-checkpoint guard helper) to avoid real pytest invocations.
- Table-driven `pytest.mark.parametrize` for the step-sequence matrix.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_harness004_isolation.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: all three guard failures; all five step-sequence states; `checkpoint-tag` shape;
docs-review input-bound guard; `SCHEMA_VERSION == 3`; LLM-judgment gap documented; suite green.

### Out of scope

- Asserting review judgment quality.
- Live git operations (tag/push).
- Spec-writer (HARNESS005).
