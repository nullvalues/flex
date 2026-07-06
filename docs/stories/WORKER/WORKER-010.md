---
id: WORKER-010
rail: WORKER
title: HARNESS003 isolation suite
status: complete
phase: "HARNESS003-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - tests/pairmode/test_harness003_isolation.py
touches:
  - tests/pairmode/test_worker_result.py
  - tests/pairmode/resolver_fixtures.py
---

## Context

The acceptance backbone of HARNESS003 (agreements DP6): the five worker conversions (builder,
reviewer, loop-breaker, security-auditor, intent-reviewer) involve LLM judgment, so the suite
tests the **deterministic scaffold**, not judgment quality. No live API call anywhere. This
story consolidates the per-worker isolation tests into a single comprehensive matrix, parallel
to WORKER-003 for the gate worker. The LLM-judgment gap is documented explicitly (deliberate,
not silent).

## Requires

- WORKER-004 through WORKER-009 all complete: the grammar, all five procedure skills and thin
  shells, and the per-worker focused test files exist. This suite exercises all of them in
  isolation.

## Ensures

The suite covers the full HARNESS003 isolation matrix, deterministically and hermetically (no
network, no live model call):

- **Return contract round-trip** — the `worker_result_grammar.json` fixture: every valid example
  for all four result types round-trips through `parse_worker_result → serialize → parse` unchanged
  and validates; every invalid example yields a non-empty violation list.
- **Shell input-bound guard** — for each of the five procedure skills (builder, reviewer,
  loop-breaker, security-auditor, intent-reviewer), assert the procedure/shell text references
  only the declared bounded inputs (the four items per WORKER-005 context, or the equivalent per
  worker) and does NOT reference accumulated loop state, prior-attempt transcripts, or
  orchestrator-held phase history. Mirror the WORKER-003 DP1.3 test (assert on source text).
- **Injected-result routing** — for `BUILD-RESULT{outcome: "PASS"}`, `BUILD-RESULT{outcome: "FAIL"}`,
  `REVIEW-RESULT{verdict: "PASS"}`, `REVIEW-RESULT{verdict: "FAIL"}`, `ADVICE{approach: "..."}`:
  assert `parse_worker_result` returns the correct typed dict and `validate_worker_result` returns
  no violations.
- **`SCHEMA_VERSION == 2`** — assert `next_action.SCHEMA_VERSION == 2` (WORKER-004 bump).
- **New ACTIONS present** — assert `spawn-reviewer`, `spawn-security-auditor`,
  `spawn-intent-reviewer` all in `next_action.ACTIONS` and `next_action._SPAWN_ACTIONS`.
- A short module docstring states the **LLM-judgment gap explicitly**: judgment quality is out of
  scope for unit assertion; validated by procedure content + manual review.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Reuse `tests/pairmode/resolver_fixtures.py` where synthetic project trees are needed.
- Use `pytest.mark.parametrize` for the per-worker input-bound guard so the matrix reads as one
  artifact (one parameterized test over five (worker_name, procedure_path) pairs).
- For the input-bound guard, `grep` / `open().read()` the procedure file and assert absence of
  accumulated-state keywords (`state.json`, `effort.db`, `attempt_count` beyond what the scalar
  conveys, `phase_history`, prior transcript references). Customize per worker as needed.
- Any per-worker test from WORKER-005 through WORKER-009 that is not already consolidated here
  may be left in its own file; `test_harness003_isolation.py` covers the cross-cutting concerns.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_harness003_isolation.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: grammar round-trip for all four types; input-bound guard for all five workers;
injected-result parsing; `SCHEMA_VERSION == 2`; new ACTIONS present; LLM-judgment gap documented;
full suite green.

### Out of scope

- Asserting LLM judgment quality (deliberate gap).
- States belonging to checkpoint decomposition (HARNESS004), spec-writer (HARNESS005), or the flip.
- Live API calls.
