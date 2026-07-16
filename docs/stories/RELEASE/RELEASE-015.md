---
id: RELEASE-015
rail: RELEASE
title: Pre-fold discovery gate (DP8) — fresh fleet snapshot, hard block on un-migrated projects
status: planned
phase: "HARNESS016-main"
story_class: documentation
auth_gated: false
schema_introduces: false
touches:
  - docs/fleet-snapshot.md
  - docs/harness-cutover-runbook.md
---

## Requires

- RELEASE-014 complete (this story must not run against pre-reconciliation tooling).
- `skills/pairmode/scripts/fleet_discovery.py` is a single `@click.command()`
  with options `--candidate-dir` (repeatable), `--candidates-file`,
  `--snapshot`/`--no-snapshot`, `--json`. It has no `discover` or
  `list-projects` subcommand and no `--scan-paths`/`--output`/`--project-dir`
  options — the runbook's DP8 command examples
  (`docs/harness-cutover-runbook.md` lines ~373-377, 276, 410) are stale
  pseudo-syntax and must be corrected as part of this story.
- Signal-1 matching is checkout-relative: it fires only when a project's
  `pairmode_scripts_dir` resolves under the *running* checkout's root. This
  gate run must therefore execute from `/mnt/work/flex-harness`, since
  migrated projects bind to the harness path until RELEASE-017 re-points them.
- The default candidate list is `registered_projects` plus 9 hardcoded names
  (coherra, forqsite, radar, asp, aab, cora, lumin, halfhorse, meander) — this
  does **not** scan `/mnt/work` exhaustively, so a stray 10th consumer would be
  invisible to the gate as configured.
- Live read 2026-07-16: all 9 named projects are still on pairmode
  0.2.0/0.1.0 with no `pairmode_scripts_dir` line; neither `/mnt/work/flex` nor
  `/mnt/work/flex-harness` has self-synced either. The gate currently fails.

## Ensures

- A fresh run of the harness checkout's `fleet_discovery.py` regenerates
  `docs/fleet-snapshot.md` with a current timestamp, committed on `fold-prep`.
- **Hard gate (DP8):** passes only if every bound project shows
  `pairmode_version: 0.3.0` AND `binding: scripts` (or `both`). Any project
  showing 0.2.x/0.1.x, or Signal-1 absent, blocks this story — it completes
  with verdict BLOCKED, and RELEASE-016/017/018 must not begin. An
  un-migrated project is a stop, not a warning. No partial folds.
- flex-harness's own dogfood binding is included: `/mnt/work/flex-harness`
  itself must show `pairmode_version: 0.3.0` in `.companion/state.json`,
  reflecting the runbook's unexecuted Phase 1 self-sync.
- The gate run additionally passes `--candidate-dir` for every directory under
  `/mnt/work` containing a `CLAUDE.build.md`, not just the 9 hardcoded names,
  so a stray consumer is not silently skipped. Any project found this way that
  isn't already in `registered_projects` is reported, not auto-registered.
- The runbook's DP8 and per-project Signal-1 verification command examples are
  corrected to the tool's actual CLI surface.
- The runbook's Final fold sequence steps referring to a branch named
  `harness` are corrected to `fold-prep` (the actual current branch — `harness`
  is a frozen ancestor of `fold-prep`, not a separate active line).
- A short **"Late-migrant procedure (post-fold)"** addendum is added to the
  runbook, covering: how a late project owner discovers they're behind
  (the `global_session_check.py` version-nag hook, once `SKILL.md` reads
  0.3.0 post-fold) and the exact command sequence they run to catch up.

## Instructions

1. Execute the seam-gate checklist (runbook §Seam gate) for flex-harness itself.
2. Run `fleet_discovery.py` from `/mnt/work/flex-harness`, both with `--json`
   for machine-readable output and without, to regenerate
   `docs/fleet-snapshot.md`; pass `--candidate-dir` for every `/mnt/work/*`
   directory containing a `CLAUDE.build.md` in addition to the default list.
3. Evaluate the gate per Ensures. If BLOCKED, list each un-migrated project by
   name and point at the runbook's §Seam gate + §Per-project mechanic — those
   migrations are operator work in other repositories, not performed by this
   story.
4. Apply the runbook corrections (CLI drift, branch name, late-migrant
   addendum) alongside the snapshot regeneration, in the same commit.

## Tests

`TEST RUN: documentation story — no test file expected`. Gate evidence is the
committed snapshot; every project section must show `pairmode_version: 0.3.0`
and Signal 1 present for the story to report PASS rather than BLOCKED.
