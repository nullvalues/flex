---
id: RELEASE-061
rail: RELEASE
title: Worktree and branch retirement — remove /mnt/work/flex-harness
status: skipped
phase: "97"
story_class: code
auth_gated: false
schema_introduces: false
touches:  # If this story changes any documented architecture, add docs/architecture.md to this list.
---

## Superseded

Superseded by **RELEASE-062** (phase 105). `/mnt/work/flex-harness` is the
**permanent release channel** — see `docs/architecture.md`
§ *Release channel — flex-harness* — and is therefore never removed. The
disposition changed at phase 102 (*"Effort-recording smoke test and harness
release-channel fast-forward"*, status `complete`), which kept the harness
checkout alive and promoted it to the channel the fleet consumes flex from.

- This story's original premise — that `/mnt/work/flex-harness` is a
  temporary worktree to be torn down after the fold — no longer holds.
- The teardown this story would have performed (`git worktree remove
  /mnt/work/flex-harness`, deleting the `harness`/`fold-prep` branches) **must
  never be executed**.
- This file is retained, not deleted, per the project convention that
  superseded findings are annotated in place rather than erased
  (`docs/cer/backlog.md:6`).

## Requires
<!-- Prior stories, system state, or file conditions that must hold before building. -->

## Ensures
<!-- Binary assertions the reviewer checks independently. One per line.
     Each must be verifiable without interpretation: file exists, command output
     contains X, function Y returns Z. -->

## Instructions

## Tests
