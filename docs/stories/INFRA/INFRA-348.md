---
id: INFRA-348
rail: INFRA
title: Wire or remove dead effort.db columns: tool_uses, duration_ms, story_class/model_selection_reason
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

CER-153 (LOW), filed from `docs/build-loop-cold-eyes-review-20260801.md`'s §5 (opus findings
M9/M10): several `effort.db` columns have no live writer or reader in the hook-driven recording
path: `tool_uses` is hard-coded `None` by `effort_recorder.py` with zero readers anywhere;
`duration_ms` is only populated on a file-fallback branch, not the primary reconcile path
(`subagent_transcript.py`), and also has zero readers outside tests; `story_class`/
`model_selection_reason` are populated only by the legacy `record_attempt.py` CLI writer that
`CLAUDE.build.md` says is not part of the live loop — only 49 of 575 live rows carry them,
degrading `pairmode_effort`'s decision-quality report section to a near-empty group on real data.
`effort_db.next_attempt_number` has zero callers — 43 lines of maintained dead code whose own
docstring warns against the racy pattern its existence invites.

For each column/function: decide keep-and-wire (give it a real writer and reader) or remove
(migration/schema change, plus updating whatever reports reference it) — don't leave a mix of dead
and half-alive columns in the schema. Note: if INFRA-345 (de-duplicating the legacy
`record_attempt.py` writer) retires that CLI path entirely, `story_class`/`model_selection_reason`'s
sole writer disappears with it — coordinate with INFRA-345's landed shape before deciding this
column's fate.

## Requires
<!-- Prior stories, system state, or file conditions that must hold before building. -->

## Ensures
<!-- Binary assertions the reviewer checks independently. One per line.
     Each must be verifiable without interpretation: file exists, command output
     contains X, function Y returns Z. -->
<!-- State the correct signal AND the forbidden proxy (INFRA-314): e.g. "the
     write is absent after refusal; forbidden proxy: a warning line while the
     write happens anyway." -->

## Instructions

## Tests
