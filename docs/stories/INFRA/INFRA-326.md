---
id: INFRA-326
rail: INFRA
title: Dual-active-era tie-break silently skips the wrong era ledger row (INFRA-267 no-op)
status: complete
phase: "114"
story_class: code
auth_gated: false
schema_introduces: false
touches:
  - skills/pairmode/scripts/flex_build.py
  - tests/pairmode/test_flex_build.py
  - docs/architecture.md
  - docs/phases/phase-114.md
  - docs/stories/INFRA/INFRA-326.md
  - tests/pairmode/test_flex_build_mark_phase_complete.py
---

<!-- SPEC-WRITER NOTE (frontmatter): `touches:` is block-style per CER-115 —
     flow-style `[a, b]` parses as a string and crashes create-story-worktree's
     `generate_permissions_artifact`. The exact test file name
     (`test_flex_build.py`) is a best-guess based on where
     `_mark_phase_complete_in_era_ledger` and `record-checkpoint-step
     checkpoint-tag` are otherwise tested — confirm during Instructions
     step 1. `docs/cer/backlog.md` is NOT touched: this story was routed
     directly into phase 114 by explicit operator instruction, discovered
     live during phase 106's own checkpoint-tag step, not pulled from an
     existing CER backlog row. -->

## Context

Discovered live while checkpointing phase 106 (2026-07-29). Per
`record-checkpoint-step checkpoint-tag`'s documented behavior (INFRA-267,
CER-082), the step is supposed to flip a completed phase's row in **both**
`docs/phases/index.md` (the phase index) and the active era doc's `##
Phases` ledger table, keeping the two in parity. `docs/phases/index.md`'s
phase-106 row correctly flipped to `complete`. The era ledger row did not
— `docs/eras/003-flex-orchestrator-as-harness.md`'s phase-106 row was left
reading `planned` after the checkpoint-tag step completed, discovered only
because the orchestrator manually diffed `docs/eras/` after the step (per
`CLAUDE.build.md`'s "commit both paths" instruction) and noticed no file in
that directory had changed.

Root cause, traced in `flex_build.py`'s
`_mark_phase_complete_in_era_ledger` (~line 1541): the function collects
every era doc under `docs/eras/*.md` whose frontmatter `status` field
equals `"active"`, and when more than one qualifies, picks the
**highest-ID one** ("more than one: highest ID wins (last in sorted
order)", per its own docstring) as the single target to search for the
phase's row. In this repo, **both** `docs/eras/003-flex-orchestrator-as-harness.md`
and `docs/eras/004-flex-operational-closeout-and-0-3-1.md` currently carry
`status: active` in their frontmatter simultaneously. Phase 106 belongs to
era 003's ledger (its row lives there, not in era 004's table — era 004's
ledger has no `106` row at all, confirmed via
`grep -n "106" docs/eras/004-flex-operational-closeout-and-0-3-1.md`
returning nothing). The tie-break's "highest ID wins" rule picked era 004
as the sole target, searched its ledger table for a phase-106 row, found
none, and — per the function's own documented idempotent-no-op contract
("no ledger row's first cell equals *phase_key*" is one of the listed
no-op conditions) — silently returned `False` and wrote nothing. No error,
no warning; `record-checkpoint-step`'s own output is empty on success, so
there was no signal at all that the era-ledger half of its two-file
contract had failed.

This was worked around live: the orchestrator manually corrected
`docs/eras/003-flex-orchestrator-as-harness.md`'s phase-106 row to
`complete` by hand before committing/tagging phase 106, and filed this
story rather than leaving the tooling gap unaddressed. The bug is
structural, not a one-off: **any** phase belonging to an era doc that is
not the highest-ID currently-`active` era doc will silently fail to have
its era-ledger row updated by every future `checkpoint-tag`, for as long
as two era docs carry `status: active` simultaneously (a state this repo
is evidently in right now, and which nothing currently prevents or flags).

## Requires

- `_mark_phase_complete_in_era_ledger`'s existing docstring and no-op
  contract (`skills/pairmode/scripts/flex_build.py`, ~line 1541) as the
  function to fix — its behavior when exactly one era doc is `active`
  must not change; only the multi-`active`-era case needs correcting.
- The actual two-active-era state in this repo
  (`docs/eras/003-flex-orchestrator-as-harness.md` and
  `docs/eras/004-flex-operational-closeout-and-0-3-1.md`, both
  `status: active`) as a live reproduction fixture, or an equivalent
  synthetic one in tests.


## Scope widenings

| path | reason | widened_at |
| --- | --- | --- |
| tests/pairmode/test_flex_build_mark_phase_complete.py | add INFRA-326 regression tests for multi-active-era ledger flip to the existing era-ledger test file | 2026-07-31T04:02:40Z |

## Ensures

- `_mark_phase_complete_in_era_ledger` (or its caller,
  `record-checkpoint-step checkpoint-tag`) no longer silently no-ops when
  a phase's row exists in a *different* active era doc than the one the
  "highest-ID wins" tie-break selects. Correct behavior (pick one,
  consistent with the function's job — "flip *phase_key*'s row wherever it
  actually lives among the active era docs"): search **all** currently-
  `active` era docs for a row whose first cell equals `phase_key`, and flip
  that row in whichever doc actually contains it, rather than committing to
  a single pre-chosen target before searching. If the phase key is found in
  more than one active era doc's ledger (a genuine ambiguity, not this
  story's normal case), that is a louder failure than a silent no-op —
  either flip both (safest, matches "keep the ledger in parity with the
  index" framing) or raise/report, but never silently skip.
- A **separate, louder signal** exists for the underlying anomaly this
  bug surfaced: two (or more) era docs simultaneously carrying
  `status: active` is itself an unusual, likely-unintentional state (only
  one era is normally "current"). Add a warning-level surfacing of this
  condition — e.g. `record-checkpoint-step`'s own output, a
  `fleet_discovery`/`audit` finding, or a dedicated check — so a future
  occurrence is visible rather than only discoverable by manually diffing
  `docs/eras/`. Do not silently "fix" this repo's current two-active-era
  state as part of this story unless doing so is trivially safe and
  explicitly justified — determining which era doc should actually be
  `status: active` (vs. `complete`/other) may be an operator decision, not
  a mechanical one; if genuinely ambiguous, record it as a finding for the
  operator rather than resolving it unilaterally.
- `docs/eras/003-flex-orchestrator-as-harness.md`'s phase-106 row (already
  manually corrected to `complete` live, ahead of this story) is confirmed
  still `complete` — this story's fix must not regress it back to
  `planned` or otherwise touch it beyond what's already correct.
- `tests/pairmode/test_flex_build.py` (or the correct existing test file
  for `_mark_phase_complete_in_era_ledger`, confirm during Instructions
  step 1) gains a regression test reproducing the exact failure shape:
  two era docs both `status: active`, the target phase's row present only
  in the non-highest-ID one, and asserting the row gets flipped (not
  silently skipped).
- No existing test in `tests/pairmode/` regresses (full suite run without
  `-x`, per this project's pytest-no-x-before-merge convention).
- `docs/architecture.md`'s description of `_mark_phase_complete_in_era_ledger`
  / the INFRA-267 era-ledger-parity mechanism (if documented there) is
  updated to describe the corrected multi-active-era search behavior.

## Instructions

1. Locate the exact existing test file covering
   `_mark_phase_complete_in_era_ledger` / `record-checkpoint-step
   checkpoint-tag` (best guess `tests/pairmode/test_flex_build.py` — grep
   for the function name to confirm) before assuming the file listed in
   this story's `touches:`.
2. Read `_mark_phase_complete_in_era_ledger` in full
   (`skills/pairmode/scripts/flex_build.py`, ~line 1541 onward) and its
   caller site(s) (~line 1689, ~line 3638-3640).
3. Change the active-era selection logic: instead of picking one target
   era doc up front via the highest-ID tie-break and only then searching
   its table, search every currently-`active` era doc's ledger table for
   the phase-key row and flip it wherever found, per the Ensures above.
   Decide and implement the correct behavior for the genuine-ambiguity
   case (row present in more than one active era doc) per the Ensures
   guidance — prefer the louder/safer option over silently picking one.
4. Add the warning-level surfacing for the "more than one era doc is
   `status: active` simultaneously" condition, per the Ensures above —
   choose the lightest-weight mechanism that gets it in front of an
   operator (e.g. printed to `record-checkpoint-step`'s own stdout is
   probably sufficient; do not over-build a dedicated audit subsystem for
   this).
5. Confirm `docs/eras/003-flex-orchestrator-as-harness.md`'s phase-106 row
   still reads `complete` (already fixed live) and is untouched by this
   story's changes.
6. Write the regression test(s) per the Ensures above.
7. Update `docs/architecture.md` if it documents this mechanism.
8. Run `uv run pytest tests/pairmode/ -q` (no `-x`) and confirm no
   regressions.

## Tests

The regression test(s) added in step 6, plus a full
`uv run pytest tests/pairmode/ -q` (no `-x`) run before merge.
