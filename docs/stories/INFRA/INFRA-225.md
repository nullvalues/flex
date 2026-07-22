---
id: INFRA-225
rail: INFRA
title: Port startswith("complete") annotated-status fallback into next_action.py's _resolve_active_phase
status: draft
phase: "97"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
touches: []
---

## Context

Discovered during RELEASE-043's fleet-migration retry against `aab`. `aab`'s
`docs/phases/index.md` carries annotated status strings on phases 15/16/17:
`complete (superseded — all 4 stories already implemented ...)`. Once `aab`
migrated onto the Era 3 thin dispatch loop, `next_action.py`'s
`_resolve_active_phase` (the helper `infer_position` uses to pick the active
phase) treated phase 15 as **active** rather than complete, because it calls
`index_integrity.is_phase_inactive(status)` directly — an exact-membership
test (`status in ("complete", "deferred", "backlog")`) — with no tolerance for
a parenthetical suffix. Phase 15 has zero unbuilt stories, so the resolver
routed straight to the checkpoint sequence; `record-checkpoint-step
checkpoint-tag` resets the tracker to `[]` on completion, but the index row
never reads as inactive, so `next-action` re-emits `checkpoint-security`
indefinitely — the checkpoint loop never terminates and no further story
cycle can ever run in that project.

The older `flex_build.py::resolve_current_phase` (used by the `current-phase`
CLI command) already solved this exact problem — it has an explicit fallback:

```python
if is_phase_inactive(normalised) or normalised.startswith("complete"):
    continue
```

with a comment noting the `startswith` check "adds main's terminal semantics
for annotated statuses like 'complete (partial)'". `next_action.py`'s
`_resolve_active_phase` was written later (RESOLVER-009/CER-056 era) as a
composition of `is_phase_inactive` directly, and the `startswith("complete")`
fallback was never ported over — a regression relative to the already-fixed
sibling function, not a new bug class.

This is a fleet-wide hazard: any project migrated onto the Era 3 loop whose
`docs/phases/index.md` carries an annotated `complete (...)` row (a common,
legitimate pattern for documenting superseded/partial phases — see `aab`'s
own history) will hit the same infinite checkpoint loop the moment it's
migrated. RELEASE-044 through RELEASE-057 (the remaining fleet migrations in
this phase) are all at risk.

## Requires

- `skills/pairmode/scripts/next_action.py::_resolve_active_phase` and
  `skills/pairmode/scripts/index_integrity.py::is_phase_inactive` exist in
  their current form (confirmed present this session).
- `skills/pairmode/scripts/flex_build.py::resolve_current_phase` is the
  reference implementation for the correct fallback semantics — do not change
  its behavior, only port its `startswith("complete")` check into the newer
  helper.

## Ensures

- `_resolve_active_phase` in `next_action.py` skips any phase row whose
  status string, after `.strip().lower()`, either satisfies
  `is_phase_inactive(...)` or starts with the literal string `"complete"` —
  matching `resolve_current_phase`'s existing fallback exactly.
- A phase row with status `"complete (superseded — all 4 stories already
  implemented via later rebuild phases; confirmed 2026-07-07)"` (the exact
  `aab` phase-15 shape) is treated as inactive by `_resolve_active_phase`,
  and the resolver's `infer_position`/`resolve_next_action` skip past it to
  the next non-inactive row (or return `active_phase_file: None` /
  action `"done"` if no other row is active).
- A bare `"complete"`, `"deferred"`, `"backlog"`, `"active"`, or `"planned"`
  status row behaves identically to current behavior (no regression) —
  covered by existing passing tests in `tests/pairmode/test_next_action.py`.
- A new regression test in `tests/pairmode/test_next_action.py` reproduces
  the exact `aab` shape: an index with one phase row whose status is
  `"complete (superseded — ...)"` and a second, later phase row that is
  genuinely `"planned"`; asserts `infer_position` resolves the active phase
  to the second (planned) row, not the first (annotated-complete) one.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

1. In `skills/pairmode/scripts/next_action.py`, find `_resolve_active_phase`
   (the loop that calls `_is_phase_inactive(status)` per row). Change the
   skip condition to mirror `flex_build.py::resolve_current_phase`'s:
   normalize the status (`status.strip().lower()` — check whether it's
   already normalized upstream by `_parse_index_phases`/`_pip`, and avoid a
   redundant double-normalize if so), then skip the row when
   `_is_phase_inactive(normalised) or normalised.startswith("complete")`.
2. Do not modify `index_integrity.is_phase_inactive` itself — its exact-match
   contract is used elsewhere and is correct for its own callers; this fix is
   scoped to `_resolve_active_phase`'s call site only.
3. Do not modify `flex_build.py::resolve_current_phase` — it already has the
   correct behavior and is the reference this story ports *from*.
4. Add the regression test described in Ensures to
   `tests/pairmode/test_next_action.py`, in or near the existing
   `TestInferPositionActivePhase` class (or a new
   `TestResolveActivePhaseAnnotatedStatus` class if that reads more clearly).
   Use the module's existing `_write_index`/`_write_phase`/`_write_story`
   fixture helpers.
5. Run the full pairmode suite and confirm green.

## Out of scope

- Fixing `aab`'s own `docs/phases/index.md` content — that is a separate,
  aab-side concern (already resolved for phases 15/16/17 as an unrelated
  matter; this story is the flex-harness tooling fix only).
- Any change to `is_phase_inactive`'s own contract or its other call sites.
- Re-attempting RELEASE-043 — that happens after this story merges, as its
  own dispatch.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: full suite green, including the new regression test asserting
that an annotated `"complete (superseded — ...)"` status row is treated as
inactive by `_resolve_active_phase`.
