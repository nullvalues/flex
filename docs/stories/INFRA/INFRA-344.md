---
id: INFRA-344
rail: INFRA
title: Commit spec-writer output before create-story-worktree branches off HEAD
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

HIGH finding F10 of `docs/build-loop-cold-eyes-review-20260801.md` (opus), matching a pre-existing
operator-memory item ("commit spec before worktree — worktree snapshots git HEAD, not the working
tree") that confirms the harness itself still has no enforcement for a gap the operator already had
to learn about live. Row 2 dispatches the spec-writer against the main worktree; the spec-writer's
own procedure explicitly says "Never commit — the orchestrator does that"; but neither
`CLAUDE.build.md` copy actually instructs the orchestrator to commit the elaborated spec before the
next step. Next poll: `needs_spec` reads False from the working tree (the file exists on disk), so
`spawn-builder` dispatches, and `create-story-worktree` branches from `HEAD` (`flex_build.py`) —
which does not include the uncommitted spec elaboration. The builder's worktree contains the
pre-elaboration stub, not the spec it was actually elaborated to. The test helper
`_create_worktree` in `test_flex_build.py` currently enshrines this broken pattern (creates a
worktree without first committing a pending spec change) and asserts success — that assertion will
need updating alongside the fix.

Fix direction: either add an explicit commit step to `CLAUDE.build.md`'s dispatch flow right after
a `spawn-spec-writer` action returns (before the next poll), or have `create-story-worktree` itself
detect and refuse/auto-commit an uncommitted change to the target story's own spec file before
branching. Extend INFRA-336's integration-test harness to cover this sequence
(`spawn-spec-writer → create-story-worktree` and assert the worktree's spec file matches the
elaborated content, not the stub).

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
