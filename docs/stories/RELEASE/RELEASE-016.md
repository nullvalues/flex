---
id: RELEASE-016
rail: RELEASE
title: Fold merge — fold-prep → main, tag v0.3.0
status: planned
phase: "HARNESS016-main"
story_class: code
auth_gated: false
schema_introduces: false
touches:
  - docs/harness-cutover-runbook.md
---

## Requires

- RELEASE-015 complete with a PASSING (not blocked) gate result.
- `/mnt/work/flex-harness` and `/mnt/work/flex` are two linked git worktrees of
  the *same* repository (`/mnt/work/flex/.git/worktrees/flex-harness`) — not
  separate clones. `main`'s commits are already present in `fold-prep`'s object
  store after RELEASE-014; this story only needs to make them reachable from
  `main`'s branch tip.
- `/mnt/work/flex` working tree is clean and on `main`.
- `skills/pairmode/scripts/_version.py` on `fold-prep` already reads
  `PAIRMODE_VERSION = "0.3.0"` (finalized, no `-dev` suffix).

## Ensures

- On `/mnt/work/flex`, `main` contains the full `fold-prep` history via
  `git merge --no-ff fold-prep -m "Era 003: fold fold-prep to main, pairmode 0.3.0"`;
  no unresolved conflict markers (RELEASE-014 should have made this
  conflict-free or near-trivial, since `main`'s content is already inside
  `fold-prep`).
- Annotated tag `v0.3.0` exists on the merge commit and is pushed along with
  `main`.
- Post-merge, `/mnt/work/flex`'s `_version.py` and `SKILL.md` frontmatter both
  read 0.3.0 — this is what flips the `global_session_check.py` version-nag
  hook for any still-un-migrated project.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes on
  `/mnt/work/flex` main after the merge, before pushing.
- `docs/harness-cutover-runbook.md`'s Final fold sequence steps referencing
  branch `harness` are corrected to `fold-prep` (should already be done by
  RELEASE-015; verify here and fix if missed).

## Instructions

Execute the runbook's Final fold sequence steps 1–2 with the corrected ref
name (`fold-prep`, not `harness`), from `/mnt/work/flex`. Run the test suite
between merge and push. Do not perform re-sync (RELEASE-017) or worktree
removal (RELEASE-018) in this story. Take this story at a fresh context seam.

## Tests

- `git -C /mnt/work/flex merge-base --is-ancestor fold-prep main` exits 0.
- `git -C /mnt/work/flex describe --tags` at `main` resolves to `v0.3.0`.
- Full suite green on `/mnt/work/flex` `main`.
