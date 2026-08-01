---
id: INFRA-345
rail: INFRA
title: De-duplicate attempt-recording writers: retire or reconcile the legacy record_attempt.py CLI path
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

HIGH finding F11 of `docs/build-loop-cold-eyes-review-20260801.md` (opus, with live examples): two
independent writers can both record a row for what should be the same spawn — the legacy
`record_attempt.py` CLI path and the hook-driven `subagent_transcript.record_attempt_from_transcript`
path. Opus found concrete live duplicates in flex's own `effort.db` (e.g. rows 473 vs 475 for the
same story/role/attempt-number triple: 33,380 tokens/PASS vs. 117,347 tokens/FAIL) — 12 such
duplicate `(story_id, agent_role, attempt_number)` triples exist today. `next_action.py`'s
loop-breaker `fail_cause` selection (`fail_rows[-1]["notes"]`) resolves which row "wins" by
insertion-order luck when duplicates exist. `CLAUDE.build.md` states recording is "fully hook-side
… no separate orchestrator-side recording step needed," but `skills/pairmode/skills/reviewer/procedure.md`
still instructs calling `record_attempt.py --notes` — two contradictory contracts writing to one
table.

Fix direction: determine whether `record_attempt.py` has any legitimate remaining live caller
(grep suggests it does not, only stale reviewer-procedure prose references it); if none, retire it
as a writer (either delete the CLI's write path or repoint the reviewer procedure to stop
mentioning it) so there is exactly one writer for a given spawn. If a legitimate caller does exist,
add a de-duplication/reconciliation mechanism (e.g. a uniqueness constraint or an explicit merge
rule) instead.

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
