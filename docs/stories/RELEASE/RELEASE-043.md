---
id: RELEASE-043
rail: RELEASE
title: Fleet migration — sync Repo-H to pairmode 0.3.0
status: deferred
phase: "97"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - docs/stories/RELEASE/RELEASE-043.md
touches: []
---

## Context

Phase 97 resumes HARNESS016-main's deferred tail: migrating the fleet of
registered sibling projects onto pairmode `0.3.0` (the Era 3 thin-harness loop)
before fold-prep is folded into `main`. This story migrates one project —
**Repo-H** — and is the new-ID resumption of the deferred `RELEASE-024` (Repo-H)
from `phase-HARNESS016-main.md`, which remains the historical record for that
original ID. Every un-migrated bound project blocks the DP8 pre-fold gate
(`RELEASE-058`), so each fleet project must reach `pairmode_version: 0.3.0`
with `binding: scripts` (Signal-1 present) and prove out one complete story
cycle. This is a cross-repo story: the build actions run against the Repo-H
project's own repository, not against flex-harness. The per-project mechanic
this story executes is the 6-step Era 3 procedure documented in
`docs/harness-cutover-runbook.md` (established by `RELEASE-012`).

## Requires
<!-- Prior stories, system state, or file conditions that must hold before building. -->

- The Era 3 migration tooling is complete and available: `RELEASE-008`
  (gate-worker / bootstrap-sync wiring), `RELEASE-009` (`pairmode_scripts_dir`
  fix), `RELEASE-010` (fleet discovery + Signal-1), and `RELEASE-011`
  (`to-030` normalizer).
- `RELEASE-042` (pre-fold doc sweep) complete — the runbook this story follows
  is current.
- The Repo-H project is a registered, git-clean project reachable on disk, and its
  current pairmode binding is discoverable via `fleet_discovery.py`.
- No build attempt is in flight in the Repo-H project (working tree at HEAD).

## Ensures
<!-- Binary assertions the reviewer checks independently. One per line.
     Each must be verifiable without interpretation: file exists, command output
     contains X, function Y returns Z. -->

- `fleet_discovery.py discover --project-dir <Repo-H>` reports `pairmode_version: 0.3.0` for the Repo-H project.
- `fleet_discovery.py discover --project-dir <Repo-H>` reports `binding: scripts` (Signal-1 present) for the Repo-H project.
- The Repo-H project's `.companion/state.json` contains `pairmode_version` set to `0.3.0`.
- The Repo-H project's working tree is clean (git status porcelain empty) after the migration commit.
- The migration commit exists in the Repo-H repository recording the sync to pairmode 0.3.0.
- One complete story cycle has been run in the Repo-H project post-sync without a binding or gate error.
- This story touches no files inside the flex-harness repository except this story file and the Phase 97 index/status updates the orchestrator records.

## Instructions

Execute the 6-step Era 3 per-project mechanic from
`docs/harness-cutover-runbook.md` §Per-project mechanic against the **Repo-H**
project. Do not hardcode a project path — resolve the Repo-H project directory
from the fleet registry / `fleet_discovery.py` output; refer to it below as
`<Repo-H>`.

1. Confirm the inter-story seam is safe (working tree at HEAD in `<Repo-H>`, no
   attempt in flight) — the `RELEASE-013` gate condition.
2. `pairmode_sync.py sync-all --project-dir <Repo-H> --dry-run` and review the
   diff. Confirm the changes are the expected Era 3 template/agent updates.
3. `pairmode_sync.py sync-all --project-dir <Repo-H> --apply --yes`.
4. `pairmode_migrate.py to-030 --project-dir <Repo-H> --apply` — normalizes
   `state.json` and cleans up stale agents (`RELEASE-011`).
5. `fleet_discovery.py discover --project-dir <Repo-H>` and require
   `binding: scripts` (Signal-1 present).
6. Run one complete story cycle in `<Repo-H>`; confirm `pairmode_version: 0.3.0`
   in `<Repo-H>/.companion/state.json`; commit and push in the Repo-H repository.

If step 5 or 6 fails, apply the runbook rollback: restore
`.companion/state.json` and `CLAUDE.build.md` from git
(`git checkout HEAD -- CLAUDE.build.md .companion/state.json` inside `<Repo-H>`),
re-run the Era 2 loop, and return the story for human review rather than
forcing the migration.

Do not modify flex-harness source, templates, or scripts in this story — the
tooling is already shipped (see Requires). This story only *runs* that tooling
against the Repo-H project.

## Tests

This is a cross-repo migration story; verification is by fleet-discovery output
and the Repo-H project's state, not by a flex-harness pytest file:

```bash
PATH=$HOME/.local/bin:$PATH uv run python <pairmode-scripts-dir>/fleet_discovery.py \
  discover --project-dir <Repo-H>
```

Acceptance: the discovery output for Repo-H shows `pairmode_version: 0.3.0` and
`binding: scripts`, the Repo-H working tree is clean, and one post-sync story
cycle completed without a binding/gate error.

`TEST RUN: cross-repo migration story — no flex-harness test file expected.`

## Out of scope

- Migrating any other fleet project (Repo-I, base56, Repo-C, Repo-A, Repo-E,
  Repo-D, Repo-F, Repo-J, Repo-B, Repo-K, Repo-L, Repo-M, Repo-N, Repo-O)
  — each has its own story (`RELEASE-044`…`RELEASE-057`).
- The Repo-G project (`RELEASE-030`, parked at `backlog`) — explicitly excluded
  from Phase 97.
- The DP8 pre-fold discovery gate (`RELEASE-058`), the fold merge
  (`RELEASE-059`), post-fold re-sync (`RELEASE-060`), and worktree retirement
  (`RELEASE-061`).
- Any change to the flex-harness migration tooling itself — this story consumes
  it, it does not modify it.
