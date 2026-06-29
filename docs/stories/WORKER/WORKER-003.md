---
id: WORKER-003
rail: WORKER
title: Isolation test suite (DP8)
status: planned
phase: "HARNESS002-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - tests/pairmode/test_gate_worker_isolation.py
  - tests/pairmode/fixtures/gate_signals.json
touches:
  - tests/pairmode/resolver_fixtures.py
---

## Context

The acceptance backbone of HARNESS002 (agreements `HARNESS002-main.md` DP8): the
worker's verdict is LLM judgment, so the suite tests the **deterministic
scaffold**, not the LLM's judgment quality. **No live API call** anywhere in the
suite. This story is the exhaustive deterministic matrix that pins the whole
phase's contract at once and backs review-checklist items 6 (test coverage) and
10 (build gate). It consolidates regressions that earlier stories carry focused
cases for.

The LLM-judgment gap is **deliberate and stated explicitly**: judgment quality is
validated by the worker's prompt + manual review, not unit tests (DP8.2). The
suite may **optionally** seed non-gating golden eval fixtures (story + signals →
expected verdict) for manual validation; these do **not** gate the build.

## Requires

- WORKER-001, RESOLVER-005, WORKER-002, RESOLVER-006 all complete: the grammar,
  the `spawn-gate-worker` action + verdict routing/aggregation, the gate-worker
  scaffold, and the CF-1 fix. This suite exercises all of them in isolation.

## Ensures

The suite covers the full DP8.1 matrix, deterministically and hermetically (no
network, no live model call, no dependence on the real project's phase docs or
git history):

- **Signal collection** — synthetic story fixtures driving each gate state:
  auth-gated with and without a classification line; schema-introduces with and
  without a mgmt story / exception phrase; a stub-tripping story; a fully clean
  story. For each, assert the `{ok, blocked_reason}` signal set the worker is
  handed, and assert **spawn-vs-not per DP2**: schema/auth trip ⇒ the resolver
  emits `spawn-gate-worker`; stub trip ⇒ `await-user:gate-blocked:stub` (no
  worker); clean ⇒ no worker (proceed).
- **Injected-verdict routing** — feed each grammar value and each per-gate map as
  an **injected** verdict (never a live worker) and assert the routed action per
  the DP3/DP4 aggregation: any `block` ⇒ `await-user gate-blocked:<gate(s)>` with
  the worker reason carried; any `flag` ⇒ proceed + `meta.warnings[]`; all
  `clean` ⇒ proceed (`spawn-builder`). Cover the mixed map
  `{"auth": "clean", "schema": "block:..."}`.
- **Grammar round-trip** — the DP3 fixture (WORKER-001's
  `gate_verdict_grammar.json`): every valid verdict map round-trips through
  `json.loads(json.dumps(...))` unchanged and validates; every invalid entry
  yields a non-empty violation list.
- **DP1.3 input-bound guard** — assert the worker's input set **excludes
  accumulated loop state**: the gate-worker procedure/shell (and the
  spawn-gate-worker action's `scalar`) reference only the three `check-*` signal
  outputs, the single story under evaluation, and the relevant diff/frontmatter —
  not phase history, prior-attempt transcripts, or orchestrator state. This is
  the "context can't become a liability" property encoded as a test.
- **CF-1 regression** — Row 5 emitted model ==
  `select_builder_model(<code story>, ..., attempt_number=2)[0]`
  (selector-sourced, not hardcoded); Row 2 first-attempt model stays attempt-1.
- A short module docstring states the **LLM-judgment gap explicitly** (deliberate,
  not silent): judgment quality is out of scope for unit assertion; validated by
  prompt + manual review.
- *(Optional, non-gating)* golden eval fixtures (story + signals → expected
  verdict) may be seeded for manual validation; they must be clearly marked
  non-gating and must not cause a build failure if the LLM's judgment differs.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes
  (review-checklist item 10).

## Instructions

- Reuse `tests/pairmode/resolver_fixtures.py` (`make_resolver_project`) for the
  synthetic durable-state trees — it already parameterises auth/schema/stub gate
  states; extend it only if a needed signal combination is unreachable (declared
  in `touches`). Prefer table-driven `pytest.mark.parametrize` so the DP8 matrix
  reads as one artifact.
- All verdict routing is tested with **injected** verdict maps fed to
  RESOLVER-005's aggregation helper — never a live worker spawn and never an API
  call. If any test path would hit the model, the test is wrong.
- For the DP1.3 input-bound guard, inspect the WORKER-002 procedure/shell text
  and the `spawn-gate-worker` action shape for the **absence** of accumulated-state
  references (assert the negative), and the **presence** of the bounded input set
  — mirror how the existing compose guard asserts on source text.
- Keep golden eval fixtures, if added, in a clearly-named non-gating file or
  marked with a skip/xfail-by-default so a judgment difference never reds the
  build gate.

## Tests

This story **is** the consolidated isolation suite. Run:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_gate_worker_isolation.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: the full DP8.1 matrix present and green (signal collection,
injected-verdict routing, grammar round-trip, DP1.3 input-bound guard, CF-1
regression); LLM-judgment gap documented; any golden evals non-gating; full
suite green.

### Out of scope

- Any change to `next_action.py` / `gate_verdict.py` / the worker scaffold
  behaviour — fix real defects under the owning story (WORKER-001/002,
  RESOLVER-005/006), then resume this one.
- Asserting LLM judgment quality (deliberate gap — DP8.2).
- States belonging to later phases (builder/reviewer/loop-breaker conversion,
  checkpoint decomposition, spec-writer) — HARNESS003–005.
- Wiring into the live `CLAUDE.build.md` loop (the flip — HARNESS006).
