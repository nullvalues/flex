---
id: RESOLVER-009
rail: RESOLVER
title: "`spawn-spec-writer` action + `needs_spec` Position flag"
status: complete
phase: "HARNESS005-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
  - tests/pairmode/test_needs_spec.py
touches:
  - tests/pairmode/test_next_action_states.py
  - tests/pairmode/resolver_fixtures.py
---

## Context

The RESOLVER half of HARNESS005 (agreements DP3): the resolver detects story stubs (`needs_spec`
Position flag) and emits `spawn-spec-writer` instead of proceeding to `spawn-gate-worker`/
`spawn-builder`. After this story the build loop is fully resolver-driven: every action the
harness takes originates from `next-action`, including spec-writing for stub stories.

## Requires

- WORKER-012 complete (HARNESS004 done): the checkpoint decomposition is complete.

## Ensures

- **`needs_spec` in Position:** `infer_position` sets `position["needs_spec"] = True` when the
  next story file has `status: planned` AND the `## Ensures` section is absent or contains
  fewer than 5 non-blank lines (stub heuristic). Otherwise `needs_spec = False`.
- **New ACTIONS entry** in `next_action.py`:
  - `SPAWN_SPEC_WRITER = "spawn-spec-writer"` added to `ACTIONS` and `_SPAWN_ACTIONS`.
  - `SCHEMA_VERSION` bumped from 3 to 4.
- **Row-2 branch** in `resolve_next_action`: when `position["needs_spec"]` is True, emit
  `make_action(SPAWN_SPEC_WRITER, scalar=story_id, model="opus", reason="needs-spec")`.
  Otherwise proceed as today (emit `spawn-gate-worker` or `spawn-builder`).
- **After `SPEC-RESULT{status: "done"}` injected** (in tests): re-reading `infer_position` on
  the same story file (now expanded) yields `needs_spec = False`; the resolver emits the normal
  next action. (Validated by injecting an expanded story fixture.)
- **After `SPEC-RESULT{status: "revised"}` injected**: the harness would emit `await-user`
  (the spec-writer flagged human review needed). This routing is tested in WORKER-014.
- Pure-read: `infer_position` and `resolve_next_action` make no writes. `grep` confirms.
- `tests/pairmode/test_needs_spec.py` asserts (synthetic story fixtures):
  - A story file with no `## Ensures` section → `needs_spec: True` → resolver emits
    `spawn-spec-writer`.
  - A story file with a stub `## Ensures` (3 non-blank lines) → `needs_spec: True`.
  - A story file with a complete `## Ensures` (≥5 non-blank lines) → `needs_spec: False` →
    resolver proceeds to `spawn-gate-worker` or `spawn-builder`.
  - `SCHEMA_VERSION == 4`; `"spawn-spec-writer"` in `ACTIONS` and `_SPAWN_ACTIONS`.
- RESOLVER-004 matrix passes unchanged (Row 2 gains a branch; verify Row 2's existing cases
  all still resolve correctly when `needs_spec == False`).
- `test_cli_surface_freeze.py` green.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- The `needs_spec` heuristic: count non-blank lines between `## Ensures` and the next `##`
  heading. If count < 5 or section absent → `needs_spec = True`. Keep it a one-function helper
  (pure-read, deterministic). Do not look at `## Instructions` or other sections.
- The Row-2 branch is a simple `if position["needs_spec"]: return make_action(SPAWN_SPEC_WRITER, ...)`.
  No other rows change.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_needs_spec.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action_states.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: `needs_spec` detection (stub, absent, complete); Row-2 branch; `SCHEMA_VERSION == 4`;
new ACTIONS entry; pure-read; RESOLVER-004 matrix green; freeze green; suite green.

### Out of scope

- The spec-writer leaf worker and procedure skill (WORKER-013).
- `SPEC-RESULT` routing post-spec-write (WORKER-014 isolation suite).
- Wiring into live `CLAUDE.build.md` (HARNESS006).
