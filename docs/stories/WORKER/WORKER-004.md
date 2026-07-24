---
id: WORKER-004
rail: WORKER
title: Generalized worker return contract (`worker_result.py` + grammar fixture)
status: complete
phase: "HARNESS003-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/worker_result.py
  - tests/pairmode/fixtures/worker_result_grammar.json
  - tests/pairmode/test_worker_result.py
touches:
  - skills/pairmode/scripts/next_action.py
---

## Context

HARNESS002 established the gate-verdict grammar (`clean|block:<reason>|flag:<reason>`) as a
per-gate map returned by the gate worker. HARNESS003 generalizes this to a typed return contract
covering all five remaining workers. This story defines the shared `worker_result.py` module and
pins the grammar with a fixture and round-trip test — the foundation that all subsequent worker
conversion stories (WORKER-005 through WORKER-009) depend on.

The new resolver actions (`spawn-reviewer`, `spawn-security-auditor`, `spawn-intent-reviewer`)
are also registered here (touching `next_action.py`) so the action vocabulary is complete before
individual worker stories add their procedure skills.

## Requires

- WORKER-003 complete (HARNESS002 done): the gate-verdict grammar and its isolation suite exist.

## Ensures

- `skills/pairmode/scripts/worker_result.py` — a new module defining:
  - Four named result type strings: `BUILD_RESULT = "BUILD-RESULT"`, `REVIEW_RESULT = "REVIEW-RESULT"`,
    `ADVICE = "ADVICE"`, `SPEC_RESULT = "SPEC-RESULT"`.
  - JSON schemas for each type:
    - `BUILD-RESULT`: `{type, outcome: "PASS"|"FAIL", story_id: str, reason: str}`
    - `REVIEW-RESULT`: `{type, verdict: "PASS"|"FAIL", findings: [str], reason: str}`
    - `ADVICE`: `{type, approach: str, rationale: str}`
    - `SPEC-RESULT`: `{type, story_id: str, status: "done"|"revised"}`
  - `parse_worker_result(text: str) -> dict` — parses JSON text and validates against the
    declared type schema; raises `ValueError` on type mismatch or missing required fields.
  - `validate_worker_result(obj: object) -> list[str]` — returns a list of violation strings
    (empty = valid).
- `tests/pairmode/fixtures/worker_result_grammar.json` — fixture with at least two valid and
  two invalid examples for each result type. Parallel to `gate_verdict_grammar.json`.
- `tests/pairmode/test_worker_result.py` — round-trip test: valid examples parse → serialize →
  re-parse with no change; invalid examples produce non-empty violation lists.
- **New ACTIONS entries** in `next_action.py`:
  - `SPAWN_REVIEWER = "spawn-reviewer"` added to `ACTIONS` and `_SPAWN_ACTIONS`.
  - `SPAWN_SECURITY_AUDITOR = "spawn-security-auditor"` added to `ACTIONS` and `_SPAWN_ACTIONS`.
  - `SPAWN_INTENT_REVIEWER = "spawn-intent-reviewer"` added to `ACTIONS` and `_SPAWN_ACTIONS`.
  - `SCHEMA_VERSION` bumped from 1 to 2.
- `test_cli_surface_freeze.py` stays green (additions allowed).
- No change to `resolve_next_action` routing logic — only the action vocabulary is extended.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Model `worker_result.py` on `gate_verdict.py` — parallel structure, separate module (the gate
  verdict is structurally different and already has its own tests; do not merge them).
- Keep the type schemas minimal but complete: every field the routing logic needs must be present;
  freeform text fields (`reason`, `approach`, `rationale`) carry no structured sub-schema.
- The `ACTIONS`/`_SPAWN_ACTIONS` additions in `next_action.py` are additive. Do not change any
  routing row in `resolve_next_action`. Only the vocabulary and `SCHEMA_VERSION` change.
- The `SPEC_RESULT` type is defined here for completeness (RESOLVER-009 / HARNESS005 uses it)
  but no routing for it is added in this story.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_worker_result.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_cli_surface_freeze.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: all four result types parse/validate; grammar fixture round-trips; new ACTIONS entries
present; `SCHEMA_VERSION == 2`; freeze green; suite green.

### Out of scope

- The individual worker procedure skills and thin shells — WORKER-005 through WORKER-009.
- The gate-verdict grammar (`gate_verdict.py`) — unchanged.
- Routing changes in `resolve_next_action` — none in this story.
- `spawn-spec-writer` action — RESOLVER-009 (HARNESS005).
