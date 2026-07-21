---
id: RELEASE-015
rail: RELEASE
title: Pre-fold discovery gate (DP8) — fresh fleet snapshot, hard block on un-migrated projects
status: planned
phase: "HARNESS016-main"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
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
- **Excluded from this gate's hard-block requirement (decided 2026-07-21):**
  - `anchor` — flex's frozen predecessor (flex was hard-forked from it); it
    will not be developed further and is not part of the managed fleet.
    Already absent from the 9-name hardcoded list above; the broadened
    `--candidate-dir` scan this story adds (Ensures) must explicitly skip
    `/mnt/work/anchor` rather than silently rediscovering and blocking on it.
  - `cora` — present in the hardcoded list, but deferred (RELEASE-030,
    `status: backlog`): combines the 0.1.0 schema gap with artifact-extraction
    work (build-loop lessons proven there, worth porting into flex before a
    routine sync overwrites them) that makes it larger than a standard
    migration. Excluded from this gate's pass/fail condition; resumed as its
    own dedicated story later.
  - Every other bound project remains a hard requirement — this exclusion
    list is deliberately narrow and must not be treated as a precedent for
    excluding a project without an equally explicit, documented reason.

## Ensures

- A fresh run of the harness checkout's `fleet_discovery.py` regenerates
  `docs/fleet-snapshot.md` with a current timestamp, committed on `fold-prep`.
- **Hard gate (DP8):** passes only if every bound project *other than the
  explicitly excluded `anchor` and `cora` (see Requires)* shows
  `pairmode_version: 0.3.0` AND `binding: scripts` (or `both`). Any
  non-excluded project showing 0.2.x/0.1.x, or Signal-1 absent, blocks this
  story — it completes with verdict BLOCKED, and RELEASE-016/017/018 must not
  begin. An un-migrated project is a stop, not a warning. No partial folds
  among the projects actually in scope.
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
   directory containing a `CLAUDE.build.md` in addition to the default list,
   **except `/mnt/work/anchor`** (excluded per Requires — do not pass it as a
   candidate).
3. Evaluate the gate per Ensures, excluding `anchor` (never scanned) and
   `cora` (scanned and reported, but not counted toward pass/fail) from the
   pass/fail condition. If BLOCKED on any other project, list it by name and
   point at the runbook's §Seam gate + §Per-project mechanic — those
   migrations are operator work in other repositories, not performed by this
   story.
4. Apply the runbook corrections (CLI drift, branch name, late-migrant
   addendum) alongside the snapshot regeneration, in the same commit.

## Tests

`TEST RUN: documentation story — no test file expected`. Gate evidence is the
committed snapshot; every project section must show `pairmode_version: 0.3.0`
and Signal 1 present for the story to report PASS rather than BLOCKED.
