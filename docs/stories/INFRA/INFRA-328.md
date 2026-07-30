---
id: INFRA-328
rail: INFRA
title: next-action's spawn-loop-breaker carries no fail_cause — orchestrator can't fill the required LOOP-BREAKER input
status: draft
phase: "114"
story_class: code
auth_gated: false
schema_introduces: false
touches:
  - skills/pairmode/scripts/next_action.py
  - tests/pairmode/test_next_action.py
  - CLAUDE.build.md
  - docs/architecture.md
  - docs/phases/phase-114.md
  - docs/stories/INFRA/INFRA-328.md
---

<!-- SPEC-WRITER NOTE (frontmatter): `touches:` is block-style per CER-115 —
     flow-style `[a, b]` parses as a string and crashes create-story-worktree's
     `generate_permissions_artifact`. `CLAUDE.build.md` is a PROTECTED path and
     requires this explicit declaration plus a valid permissions artifact
     (INFRA-253) — deliberate. `docs/cer/backlog.md` is NOT touched: this story
     was routed directly into phase 114 by explicit operator instruction, not
     pulled from an existing CER backlog row. Superseded hypothesis: INFRA-327
     (filed the same day) proposed a context-budget-gate exemption as the cause
     of loop-breaker requiring human intervention instead of running
     automatically; the operator confirmed that was NOT the actual cause. This
     story is the corrected root-cause finding from a second investigation
     pass — INFRA-327 remains separately valid (loop-breaker genuinely isn't
     exempted like reviewer) but is not what the operator observed. -->

## Context

Operator report (2026-07-29): "loop-breaker used to, and should run
automatically after two failed build attempts — that's its purpose, to
break a loop. Human intervention is only required if loop-breaker's
supplied fix doesn't work to break the build failure." A first
investigation pass proposed the context-budget gate (INFRA-327) as the
cause; the operator confirmed that was not it and asked for the
investigation to continue.

Second pass found the actual mechanism. `next_action.py`'s FAIL ladder
(~line 1312, Row 6: `attempt_count == 2` and last outcome `FAIL` →
`spawn-loop-breaker`) constructs its action with `reason=""` — a bare
empty string. No error text, no failing file/line, no description of what
the builder tried. Confirmed via direct read: `grep -n "fail_cause\|notes"
skills/pairmode/scripts/next_action.py` returns zero hits — the module
never reads or surfaces either field anywhere.

But `CLAUDE.md`'s "Loop-breaker mode" section defines a specific required
input contract: `Invoked with: LOOP-BREAKER: [error] | FILE: [file:line] |
TRIED: [what failed]`. The loop-breaker's own procedure is built around
receiving that triple — "Analyse the error cold, from first principles" —
which is impossible to do meaningfully from `attempt=3, fail_rung=double-fail`
alone.

The data this input needs is not missing from the system — it is
captured and recorded, just never threaded through to this dispatch
point. On every reviewer FAIL, the reviewer procedure (`On FAIL, revert` /
`Notes on FAIL (FAIL-CAUSE capture — BUILD-043)`) emits a `FAIL-CAUSE:
[concise reason]` line and populates a `fail_cause` field in its
`REVIEW-RESULT` JSON. `subagent_transcript.py`'s `parse_worker_outcome`
extracts `(outcome, fail_cause)` from the transcript (confirmed at
multiple call sites, e.g. ~line 499, ~line 1548, ~line 1905, ~line 2488),
and `record_attempt_from_transcript()` writes it into `effort.db` as the
attempt row's `notes` field — all of this already wired and working,
`hooks/post_tool_use.py`'s Task/Agent branch does it automatically after
every spawn, no orchestrator action needed. `effort_db.query_by_story(path,
story_id)` (confirmed present, ~line 687) can retrieve a story's attempt
rows including `notes` directly.

So the fail_cause exists in `effort.db` by the time `next-action` is
asked what to do next, but `next_action.py`'s Row 6 never queries it — the
orchestrator receiving `spawn-loop-breaker` with an empty `reason` has no
principled way to fill the required `LOOP-BREAKER: [error] | FILE:
[file:line] | TRIED: [what failed]` template, and a reasonable orchestrator
facing that gap defers to a human to supply the missing context rather
than guessing or dispatching a loop-breaker with a garbage/empty error
description — which produces exactly the symptom reported: human
intervention where automatic dispatch should occur.

## Requires

- `effort_db.query_by_story(path, story_id)` (confirmed present,
  `skills/pairmode/scripts/effort_db.py` ~line 687) as the retrieval
  mechanism — do not build a new query path; reuse this one.
- The existing `fail_cause`/`notes` recording pipeline
  (`subagent_transcript.py`'s `parse_worker_outcome` and
  `record_attempt_from_transcript`) as already-correct, unmodified by this
  story — the gap is purely on the read/surface side in `next_action.py`.
- `CLAUDE.md`'s "Loop-breaker mode" input format
  (`LOOP-BREAKER: [error] | FILE: [file:line] | TRIED: [what failed]`) as
  the target shape `next-action`'s output should make trivially
  constructible.

## Ensures

- `next_action.py`'s Row 6 (`spawn-loop-breaker` construction, double-fail
  case) queries the most recent FAIL attempt's `notes`/`fail_cause` for
  the story via `effort_db.query_by_story` before building the action, and
  surfaces it — either in the `reason` field (replacing the current bare
  `""`) or a new `meta` key (e.g. `meta["fail_cause"]`), whichever better
  matches this module's existing conventions for passing dispatch-time
  context (check how `builder_model_reason` / other `reason` values are
  used elsewhere in this file before deciding).
- If a `FILE:`/location component is separately available anywhere in the
  recorded attempt data (check `effort_db`'s schema/row shape during
  Instructions — `notes` may already be a single free-text string
  combining error + file, in which case no further extraction is needed;
  do not invent a new schema column if the existing free-text note already
  carries enough signal).
- Fails open, matching this module's existing conventions: if
  `effort_db.query_by_story` raises, returns no rows, or the most recent
  row has no `notes`, the action still returns `spawn-loop-breaker`
  (never blocks or downgrades to `await-user` for this reason alone) —
  just with `reason=""` as it does today, so a missing/malformed
  effort.db degrades to current behavior rather than crashing `next-action`.
- `CLAUDE.build.md`'s spawn-loop-breaker dispatch instruction (wherever it
  currently just says "spawn leaf-worker-for(a.action)") is updated to
  tell the orchestrator to construct the `LOOP-BREAKER: [error] | FILE:
  [file:line] | TRIED: [what failed]` prompt from the new `reason`/`meta`
  field, so a human reading the build loop doc sees exactly how the
  surfaced fail_cause is meant to be used.
- `tests/pairmode/test_next_action.py` gains regression tests: (a) a
  double-fail scenario with a recorded `fail_cause` in `effort.db`
  produces a `spawn-loop-breaker` action whose `reason` (or `meta`)
  contains that fail_cause text; (b) a double-fail scenario with no
  recorded `fail_cause` (or a missing/corrupt effort.db) still produces a
  valid `spawn-loop-breaker` action with the current empty-string
  fallback, not a crash or a different action.
- No existing test in `tests/pairmode/` regresses (full suite run without
  `-x`, per this project's pytest-no-x-before-merge convention).
- `docs/architecture.md`'s description of the FAIL ladder / loop-breaker
  dispatch (if documented there) is updated to reflect fail_cause now
  being surfaced.

## Instructions

1. Read `next_action.py`'s Row 6 (~line 1312) and Row 5 (~line 1298, the
   attempt-1-fail → attempt-2-builder case) for the existing pattern of
   how `reason` is populated elsewhere in this file, to keep the new
   surfacing consistent with existing conventions.
2. Read `effort_db.py`'s `query_by_story` (~line 687) and confirm the
   exact shape of a returned attempt-row dict — specifically whether
   `notes` (the fail_cause) is a single free-text field or whether a
   `FILE:`/location component needs separate extraction from it (it may
   already be embedded in the free-text note, e.g. "FAIL-CAUSE:
   undeclared file: docs/architecture.md" naturally contains a file
   reference). Do not assume a schema shape not confirmed by reading the
   actual code/row.
3. Add the query + surfacing logic to Row 6, per the Ensures above,
   preserving the fail-open behavior on any error/absence.
4. Update `CLAUDE.build.md`'s spawn-loop-breaker dispatch instruction.
5. Write the regression tests per the Ensures above.
6. Update `docs/architecture.md` if it documents the FAIL ladder.
7. Run `uv run pytest tests/pairmode/ -q` (no `-x`) and confirm no
   regressions.

## Tests

`uv run pytest tests/pairmode/test_next_action.py -q` plus a full
`uv run pytest tests/pairmode/ -q` (no `-x`) run before merge.
