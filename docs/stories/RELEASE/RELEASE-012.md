---
id: RELEASE-012
rail: RELEASE
title: Per-project sync-all to Era 3 with Signal-1 verification
status: complete
phase: "HARNESS013-main"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - docs/harness-cutover-runbook.md
touches: []
---

## Requires

- RELEASE-008 (gate-worker/bootstrap-sync wiring), RELEASE-009
  (`pairmode_scripts_dir` fix), RELEASE-010 (fleet discovery + Signal-1), and
  RELEASE-011 (`to-030` normalizer) all complete — the 6-step procedure this
  story documents assumes each of those tools already exists.

## Ensures

- **CER-059(b) update**: `docs/harness-cutover-runbook.md` §Per-project
  mechanic is updated to the 6-step Era 3 procedure:
  1. Confirm inter-story seam (RELEASE-013 gate).
  2. `pairmode_sync.py sync-all --project-dir P --dry-run` → review diff.
  3. `pairmode_sync.py sync-all --project-dir P --apply --yes`.
  4. `pairmode_migrate.py to-030 --project-dir P --apply` (RELEASE-011).
  5. `fleet_discovery.py discover --project-dir P` → require `binding: scripts`
     (Signal-1 present).
  6. Run one complete story cycle; confirm `pairmode_version: 0.3.0` in
     `state.json`; commit and push.
- **Rollback note added**: If step 5 or 6 fails, the rollback procedure is:
  restore `.companion/state.json` from git, restore `CLAUDE.build.md` from git
  (`git checkout HEAD -- CLAUDE.build.md .companion/state.json`), and re-run
  the Era 2 build loop. The sync-all changes to `CLAUDE.md` are cosmetic and
  do not affect the Era 2 loop.
- **DP8 gate section updated**: The runbook §DP8 pre-fold gate explicitly
  states: "Run `fleet_discovery.py` across all registered projects and confirm
  every bound project shows `pairmode_version: 0.3.0` and `binding: scripts`.
  Any project not at `0.3.0` blocks the fold."
- The runbook correctly references RELEASE-011 (`to-030` normalizer) and
  RELEASE-009 (`pairmode_scripts_dir` fix in CLAUDE.build.md) as prerequisites
  for steps 4 and 5 respectively.
- `TEST RUN: documentation story — no test file expected`.

## Instructions

Read `docs/harness-cutover-runbook.md` in full. Update three sections:

1. **§Per-project mechanic** — replace the existing steps with the 6-step
   procedure above. Add rollback note after step 6.
2. **§DP8 pre-fold gate** — add explicit `pairmode_version: 0.3.0` and
   `binding: scripts` requirements.
3. **§Prerequisites** (or add one if absent) — list RELEASE-008, RELEASE-009,
   RELEASE-010, RELEASE-011 as required completed before any fleet project
   migration begins.

Do not add content beyond what is specified — the runbook already has a
strong structure; only amend the three sections.
