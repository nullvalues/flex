---
id: RESOLVER-008
rail: RESOLVER
title: Checkpoint action routing — pre-checkpoint guards + step sequencing
status: complete
phase: "HARNESS004-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
  - tests/pairmode/test_checkpoint_routing.py
touches:
  - tests/pairmode/test_next_action_states.py
  - tests/pairmode/resolver_fixtures.py
---

## Context

The RESOLVER half of HARNESS004 part 2 (agreements DP2, DP3, DP5): `resolve_next_action` gains
the checkpoint routing rows. After this story the resolver correctly sequences the checkpoint
sub-actions (emitting each uncompleted step in order based on `position["checkpoint_step"]`)
and applies pre-checkpoint guards before entering the sequence. The temporary
`await-user:checkpoint-decomposition-pending-RESOLVER-008` stub from RESOLVER-007 is replaced
by the real routing.

## Requires

- RESOLVER-007 complete: `checkpoint_step` in Position; four checkpoint actions in `ACTIONS`.
- WORKER-011 complete: the checkpoint-docs leaf worker exists.

## Ensures

- **Pre-checkpoint guards** — `infer_position` (or a helper called by `resolve_next_action`)
  checks three guards when all phase stories are complete/deferred:
  1. Phase completion: all stories in the active phase are `complete` or `deferred`.
  2. CER Do Now clear: `docs/cer/backlog.md` has no unresolved Do Now items (a heuristic
     scan for rows without `RESOLVED` annotation under the `## Do Now` section).
  3. Build gate: `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q --tb=no`
     exits 0. (The guard runs this check synchronously; if it takes too long, it is advisory-only
     and the guard passes with a warning.)
  If any guard fails, `resolve_next_action` emits `await-user` with `reason="checkpoint-guard-failed:<which>"`.
- **Checkpoint step sequencing** — when all guards pass, `resolve_next_action` emits the next
  uncompleted checkpoint step from the ordered sequence `["checkpoint-security", "checkpoint-intent",
  "checkpoint-docs", "checkpoint-tag"]`, based on `position["checkpoint_step"]`.
- **`checkpoint-tag`** is emitted as an action; the harness executes it inline (not a leaf worker
  spawn). The resolver sets `model=None` for `checkpoint-tag` (not in `_SPAWN_ACTIONS`).
- **After `checkpoint-tag` completes**, the harness clears `state.json["checkpoint_step"]`
  (sets to `[]`) and updates the phase/story status to `complete`. The resolver re-reads next
  time and emits `done` (no more stories in the phase) or proceeds to the next phase's first story.
- **Pure-read:** `resolve_next_action` stays pure-read. The state.json write (`checkpoint_step`
  cleared, story status updated) is the harness's responsibility, not the resolver's.
- The RESOLVER-007 stub (`await-user:checkpoint-decomposition-pending-RESOLVER-008`) is removed.
- `tests/pairmode/test_checkpoint_routing.py` asserts (synthetic fixtures):
  - Pre-guard failure (incomplete stories) → `await-user:checkpoint-guard-failed:phase-incomplete`.
  - Pre-guard pass (all complete, CER clear, build gate green) + no `checkpoint_step` → emits
    `action: "checkpoint-security"`.
  - `checkpoint_step: ["checkpoint-security"]` → emits `"checkpoint-intent"`.
  - `checkpoint_step: ["checkpoint-security", "checkpoint-intent"]` → emits `"checkpoint-docs"`.
  - `checkpoint_step: ["checkpoint-security", "checkpoint-intent", "checkpoint-docs"]` → emits
    `"checkpoint-tag"` with `model=None`.
  - `checkpoint_step: ["checkpoint-security", "checkpoint-intent", "checkpoint-docs", "checkpoint-tag"]`
    → emits `done` (or next-phase first story if the phase stack has more). No live test run.
- Existing RESOLVER-004 matrix updated: any row that previously emitted `"checkpoint"` now
  reflects the correct replacement (guard-failed or the first checkpoint step).
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Implement pre-checkpoint guards as a helper function (pure-read, deterministic inputs);
  the build-gate check may be mocked in tests via dependency injection (pass a `gate_fn` parameter
  that defaults to the real pytest runner). Do not run pytest in unit tests.
- The checkpoint step sequence is the ordered list `["checkpoint-security", "checkpoint-intent",
  "checkpoint-docs", "checkpoint-tag"]`. Use `next(s for s in sequence if s not in checkpoint_step)`
  to find the next uncompleted step.
- Remove the RESOLVER-007 stub.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_checkpoint_routing.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action_states.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: guard-failure routing; step-sequence routing for all five states; `checkpoint-tag`
with `model=None`; pure-read; RESOLVER-004 matrix green; full suite green.

### Out of scope

- HARNESS004 isolation suite (WORKER-012).
- The harness's `state.json` write (clearing `checkpoint_step`) — not in `next_action.py`.
- Wiring into the live `CLAUDE.build.md` (HARNESS006).
