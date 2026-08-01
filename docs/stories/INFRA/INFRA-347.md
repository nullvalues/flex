---
id: INFRA-347
rail: INFRA
title: merge-story-worktree must flip a landed story's status to complete (CER-136)
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

CER-136 (already open, backlog HIGH): `cmd_merge_story_worktree` rebases, fast-forward-merges, and
tears down a story's worktree/branch on reviewer PASS, but never flips the landed story's `status:`
frontmatter or its Status cell in the phase doc's Stories table — both stay `draft` forever unless
someone hand-edits them. Live-hit repeatedly this project: Phase 114's checkpoint stalled on
exactly this (13 stale rows, fixed by INFRA-330); this session's own Phase 115 and Phase 116
checkpoints (2026-07-31/2026-08-01) both required a manual orchestrator-side status sync across
every landed story before `checkpoint-tag` would clear the phase-incomplete guard — the same unfixed
gap, twice, in the very session that commissioned `docs/build-loop-cold-eyes-review-20260801.md`.
That review's own §5 independently corroborates this via `index_integrity.check_index`'s
status-drift check having zero automated callers anywhere in the loop, so the drift is caught only
when a human happens to look.

This is the single most-repeated manual-fixup this project has needed at checkpoint time. Era 004's
own stated goal (`docs/eras/004-flex-operational-closeout-and-0-3-1.md`) is "zero unresolved
operational findings" — this finding is about as operational as they get.

Fix direction (per CER-136's own note): have `cmd_merge_story_worktree` flip the story's frontmatter
`status:` and its phase-doc Status cell to `complete` as part of the same merge operation
(mirroring `mark-phase-complete`'s existing phase-index flip), so a merged story is never
observably `draft`. This story should also mark CER-136 resolved in `docs/cer/backlog.md` once
landed.

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
