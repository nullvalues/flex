---
id: RELEASE-018
rail: RELEASE
title: Worktree and branch retirement — remove /mnt/work/flex-harness
status: skipped
phase: "HARNESS016-main"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - docs/harness-cutover-runbook.md
---

## Superseded

Superseded by **RELEASE-062** (phase 105). This story was renumbered/resumed
as `RELEASE-061` under phase 97 (see `docs/phases/phase-HARNESS016-main.md`
§ Deferred stories), and RELEASE-061 is itself now superseded — see
`docs/stories/RELEASE/RELEASE-061.md` § *Superseded*. `/mnt/work/flex-harness`
is the **permanent release channel** (`docs/architecture.md`
§ *Release channel — flex-harness*), a disposition that changed at phase 102
(*"harness release-channel fast-forward"*, `complete`), and is therefore
**never removed**. The `## Requires`/`## Instructions` below are retained
verbatim as a **historical record only** of the original (now-abandoned)
plan; none of the commands in them may be executed.

## Requires — historical record, do not act on

> The block below reflects this story's original, now-abandoned premise and
> is retained only so a future reader can see what was once planned; it is
> superseded by RELEASE-062 (phase 105) — see `## Superseded` above.
>
> - RELEASE-017 complete: no project's `CLAUDE.build.md` references
>   `/mnt/work/flex-harness` (verified by grep across the snapshot's project list).
> - Correct sequence is `git worktree remove /mnt/work/flex-harness` (removing
>   the directory first breaks worktree bookkeeping — the runbook's step 5 has
>   this backwards and must be corrected).
> - Branches in play: `fold-prep` (fully merged by RELEASE-016) and its frozen
>   ancestor `harness`; both are fully reachable from `main` after the fold.

## Ensures — historical record, do not act on

> - `/mnt/work/flex-harness` no longer exists; `git -C /mnt/work/flex worktree list`
>   shows only `/mnt/work/flex`.
> - Branch decision recorded in the runbook: `fold-prep` and `harness` either
>   deleted (`git branch -d` succeeds — both merged into `main`) or kept as
>   historical refs, with a one-sentence rationale.
> - Runbook step 5's command order is corrected.
> - Pre-deletion safety check: a grep sweep across every project in the
>   RELEASE-015/017 snapshot list confirms no `CLAUDE.build.md` still references
>   `flex-harness`.

## Instructions — historical record, do not act on

> Run the pre-deletion grep sweep; execute
> `git -C /mnt/work/flex worktree remove /mnt/work/flex-harness` (use `--force`
> only if the tree is unexpectedly dirty — stop and investigate first instead of
> forcing); apply the branch-retention decision; commit the runbook corrections
> on `main`.
>
> **This instruction block is retired and must never be executed** —
> `/mnt/work/flex-harness` is the permanent release channel (RELEASE-062,
> phase 105).

## Tests

`TEST RUN: documentation story, retired — no action is ever taken on this
story's original Requires/Ensures/Instructions; see ## Superseded.`
