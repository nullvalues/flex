---
id: RELEASE-017
rail: RELEASE
title: Post-fold re-sync of migrated projects + RELEASE-002 status reconciliation
status: planned
phase: "HARNESS016-main"
story_class: documentation
auth_gated: false
schema_introduces: false
touches:
  - docs/cer/backlog.md
  - docs/fleet-snapshot.md
---

## Requires

- RELEASE-016 complete: `/mnt/work/flex` `main` is 0.3.0, tagged.
- Migrated projects' `CLAUDE.build.md` currently bake
  `pairmode_scripts_dir = /mnt/work/flex-harness/skills/pairmode/scripts` (set
  at migration time). Running `sync-all` *from* `/mnt/work/flex` rebinds them
  to the canonical path.
- CER-059(c) requires an explicit, checkable AC reconciling
  `docs/stories/RELEASE/RELEASE-002.md`'s status on `main`.

## Ensures

- For every project listed as migrated in the RELEASE-015 snapshot:
  `pairmode_sync.py sync-all --project-dir <P> --apply --yes`, invoked from
  `/mnt/work/flex` (now canonical), has been run, and the project's
  `CLAUDE.build.md` `pairmode_scripts_dir` now resolves under
  `/mnt/work/flex/skills/pairmode/scripts`.
- Verification uses the canonical checkout's `fleet_discovery.py` (Signal-1 is
  checkout-relative): a fresh run shows `binding: scripts` (or `both`) for
  every re-synced project, and an updated `docs/fleet-snapshot.md` is
  committed on `/mnt/work/flex` `main`.
- At least two project builds are spot-checked post-re-sync (one full story
  cycle each).
- `grep "^status:" docs/stories/RELEASE/RELEASE-002.md` on `/mnt/work/flex`
  `main` reads `status: complete`, not `deferred`. If it reads `deferred`,
  investigate the merge before proceeding to RELEASE-018.
- CER-059 is annotated RESOLVED in `docs/cer/backlog.md` (parts a, b, c all
  closed by this point).

## Instructions

Iterate the migrated-project list from the RELEASE-015 snapshot; dry-run then
apply `sync-all` per project from `/mnt/work/flex`; re-run fleet discovery from
`/mnt/work/flex` and commit the refreshed snapshot; run the RELEASE-002 status
grep; annotate CER-059. Each per-project apply is operator-confirmed — these
are writes to other repositories; the project owner commits in their own repo.

## Tests

`TEST RUN: documentation/operational story — evidence is the refreshed
docs/fleet-snapshot.md on main (all projects binding: scripts under
/mnt/work/flex) and the RELEASE-002 status grep output.`
