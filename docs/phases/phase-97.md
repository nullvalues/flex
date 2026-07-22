---
era: "003"
phase_class: production
---

# flex-harness — Phase 97: Fold resume — pre-fold gate, fleet migration, merge to main, re-sync

← [Phase 96: Build-loop revert safety and worktree-per-cycle isolation](phase-96.md)

**Parent phase:** [HARNESS016-main](phase-HARNESS016-main.md). Picks up
HARNESS016-main's deferred stories: RELEASE-022 (doc sweep retry), the 17
fleet-migration stories (RELEASE-024/026-029/031-040), the DP8 pre-fold gate,
fold merge, post-fold re-sync, and worktree retirement (RELEASE-015-018).
RELEASE-030 (cora) remains excluded — parked at `backlog` pending unscoped
lesson-extraction work, not resumed here. Stories get new IDs per the
phase-continuity policy; `phase-HARNESS016-main.md` remains the historical
record for the original RELEASE-0NN IDs.

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Resume HARNESS016-main's deferred tail: retry the doc sweep, migrate the fleet to pairmode 0.3.0, run the DP8 pre-fold discovery gate, fold fold-prep into main as v0.3.0, re-sync migrated projects, and retire the flex-harness worktree.

## Stories

| ID | Title | Status |
|----|-------|--------|
| RELEASE-042 | Pre-fold doc sweep — era status, post-flip staleness, reviewer input-scope contradiction (retry, scoped to drop forbidden brief.md section) | complete |
| RELEASE-043 | Fleet migration — sync aab to pairmode 0.3.0 | blocked — NOT complete despite `next_story.py`'s git-commit heuristic possibly reading it as done (see note below) |
| RELEASE-044 | Fleet migration — sync asp to pairmode 0.3.0 | draft |
| RELEASE-045 | Fleet migration — sync base56 to pairmode 0.3.0 | draft |
| RELEASE-046 | Fleet migration — sync caddy to pairmode 0.3.0 | draft |
| RELEASE-047 | Fleet migration — sync coherra to pairmode 0.3.0 | draft |
| RELEASE-048 | Fleet migration — sync forqsite to pairmode 0.3.0 | draft |
| RELEASE-049 | Fleet migration — sync forqsite.help to pairmode 0.3.0 | draft |
| RELEASE-050 | Fleet migration — sync halfhorse to pairmode 0.3.0 | draft |
| RELEASE-051 | Fleet migration — sync lumin to pairmode 0.3.0 | draft |
| RELEASE-052 | Fleet migration — sync meander to pairmode 0.3.0 | draft |
| RELEASE-053 | Fleet migration — sync pokus to pairmode 0.3.0 | draft |
| RELEASE-054 | Fleet migration — sync radar to pairmode 0.3.0 | draft |
| RELEASE-055 | Fleet migration — sync rockue to pairmode 0.3.0 | draft |
| RELEASE-056 | Fleet migration — sync stackabid to pairmode 0.3.0 | draft |
| RELEASE-057 | Fleet migration — sync ud to pairmode 0.3.0 | draft |
| RELEASE-058 | Pre-fold discovery gate (DP8) — fresh fleet snapshot, hard block on un-migrated projects | draft |
| RELEASE-059 | Fold merge — fold-prep into main, tag v0.3.0 | draft |
| RELEASE-060 | Post-fold re-sync of migrated projects + RELEASE-002 status reconciliation | draft |
| RELEASE-061 | Worktree and branch retirement — remove /mnt/work/flex-harness | draft |
| INFRA-225 | Port startswith("complete") annotated-status fallback into next_action.py's _resolve_active_phase | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-97 Cold-eyes checklist

— developer fills in after phase completion —
