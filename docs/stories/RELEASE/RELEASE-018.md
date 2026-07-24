---
id: RELEASE-018
rail: RELEASE
title: Worktree and branch retirement — remove /mnt/work/flex-harness
status: planned
phase: "HARNESS016-main"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - docs/harness-cutover-runbook.md
---

## Requires

- RELEASE-017 complete: no project's `CLAUDE.build.md` references
  `/mnt/work/flex-harness` (verified by grep across the snapshot's project list).
- Correct sequence is `git worktree remove /mnt/work/flex-harness` (removing
  the directory first breaks worktree bookkeeping — the runbook's step 5 has
  this backwards and must be corrected).
- Branches in play: `fold-prep` (fully merged by RELEASE-016) and its frozen
  ancestor `harness`; both are fully reachable from `main` after the fold.

## Ensures

- `/mnt/work/flex-harness` no longer exists; `git -C /mnt/work/flex worktree list`
  shows only `/mnt/work/flex`.
- Branch decision recorded in the runbook: `fold-prep` and `harness` either
  deleted (`git branch -d` succeeds — both merged into `main`) or kept as
  historical refs, with a one-sentence rationale.
- Runbook step 5's command order is corrected.
- Pre-deletion safety check: a grep sweep across every project in the
  RELEASE-015/017 snapshot list confirms no `CLAUDE.build.md` still references
  `flex-harness`.

## Instructions

Run the pre-deletion grep sweep; execute
`git -C /mnt/work/flex worktree remove /mnt/work/flex-harness` (use `--force`
only if the tree is unexpectedly dirty — stop and investigate first instead of
forcing); apply the branch-retention decision; commit the runbook corrections
on `main`.

## Tests

`TEST RUN: operational story — evidence is git worktree list output and the
pre-deletion grep sweep transcript recorded in the story completion note.`
