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
| RELEASE-043 | Fleet migration — sync aab to pairmode 0.3.0 | deferred |
| RELEASE-044 | Fleet migration — sync asp to pairmode 0.3.0 | deferred |
| RELEASE-045 | Fleet migration — sync base56 to pairmode 0.3.0 | deferred |
| RELEASE-046 | Fleet migration — sync caddy to pairmode 0.3.0 | deferred |
| RELEASE-047 | Fleet migration — sync coherra to pairmode 0.3.0 | deferred |
| RELEASE-048 | Fleet migration — sync forqsite to pairmode 0.3.0 | deferred |
| RELEASE-049 | Fleet migration — sync forqsite.help to pairmode 0.3.0 | deferred |
| RELEASE-050 | Fleet migration — sync halfhorse to pairmode 0.3.0 | deferred |
| RELEASE-051 | Fleet migration — sync lumin to pairmode 0.3.0 | deferred |
| RELEASE-052 | Fleet migration — sync meander to pairmode 0.3.0 | deferred |
| RELEASE-053 | Fleet migration — sync pokus to pairmode 0.3.0 | deferred |
| RELEASE-054 | Fleet migration — sync radar to pairmode 0.3.0 | deferred |
| RELEASE-055 | Fleet migration — sync rockue to pairmode 0.3.0 | deferred |
| RELEASE-056 | Fleet migration — sync stackabid to pairmode 0.3.0 | deferred |
| RELEASE-057 | Fleet migration — sync ud to pairmode 0.3.0 | deferred |
| RELEASE-058 | Pre-fold discovery gate (DP8) — fresh fleet snapshot, hard block on un-migrated projects | draft |
| RELEASE-059 | Fold merge — fold-prep into main, tag v0.3.0 | draft |
| RELEASE-060 | Post-fold re-sync of migrated projects + RELEASE-002 status reconciliation | draft |
| RELEASE-061 | Worktree and branch retirement — remove /mnt/work/flex-harness | draft |
| INFRA-225 | Port startswith("complete") annotated-status fallback into next_action.py's _resolve_active_phase | complete |
| INFRA-226 | Add fable as an escalation-tier model; document mandatory custom-model entry at model-upgrade gates | complete |

## Deferred stories

RELEASE-043 through RELEASE-057 (the 15 per-project fleet-migration stories)
were deferred on 2026-07-22, mid-execution, after a scope-check the operator
requested surfaced two problems with running them directly from this repo:

1. **Numbering-convention risk.** RELEASE-043 (aab) was already built and
   merged directly from this repo before the check — a follow-up 15-project
   survey confirmed no actual collision occurred there, but the other 14
   fleet projects use at least six distinct, mutually incompatible
   phase/story-numbering conventions (bare integers, `PM0NN-{suffix}`,
   `EH0NN-{suffix}`, `RK0NN-{suffix}`, `SB0NN-{suffix}`, era-prefixed
   `{MVP/GA}0NN`/`{FPS/MU/LF}0NN`/`MN0NN`), several with stale
   index.md "next to build" pointers or doc/tooling drift. Building directly
   from flex-harness risked silently colliding with a project's real next
   phase number or convention.
2. **Concurrency risk.** Several projects (asp, pokus) had unpushed commits
   or in-flight human-gated work (pokus's Phase 2 is gated on a human UAT
   step, TEST-002) at survey time — dispatching a builder directly into
   those repos risked interleaving with work already in progress there,
   invisible to this orchestrator.

**Resolution:** a read-only survey of all 14 remaining fleet projects (2026-07-22)
found no other numbering collisions, but confirmed the convention diversity
above. Rather than build fleet migrations directly from flex-harness, each
project now gets a **proposed-phase file**
(`docs/phases/phase-proposed-pairmode-030-migration-20260722[-001].md`,
committed 2026-07-22) seeding the migration intent in that project's own
idiom. The actual migration for each project is resumed **in that project's
own session**, following its own `CLAUDE.build.md` Spec workflow: `spec next
phase migrate to pairmode 0.3.0` → sequence into a real project-numbered
phase → `build phase <N>` → runs the same 6-step mechanic (sync-all →
`to-030` migrate → Signal-1 discovery check → one proven story cycle) using
that project's own build loop and numbering. Once migrated, that project's
`CLAUDE.build.md` becomes the thin dispatch loop and its own "continue
building" resolves through `next-action` from then on — same as this repo.

Per-project state at time of deferral:
- **aab**: furthest along — `sync-all`/`to-030`/Signal-1 discovery all
  verified working there (see RELEASE-043's build history); blocked only on
  step 6 (one proven story cycle), which was blocked by the
  `_resolve_active_phase` annotated-status bug, now fixed (INFRA-225,
  merged). aab's own next session can likely complete the migration in one
  pass. A dedicated aab-local proposed-phase file was not dropped (its
  phase-numbering convention was already confirmed collision-free and real
  migration progress already exists there) — its own operator should resume
  directly.
- **asp, pokus**: had uncommitted/unpushed state at survey time; resolved by
  the operator directly (asp: nothing to reconcile; pokus: uncommitted
  canonical-template sync committed as-is, prototype repo).
- **base56**: `docs/phases/index.md` is stale relative to real phase/story
  state and `main`'s git history appears squashed — flagged in its proposed
  file for reconciliation before sequencing.
- **caddy, forqsite**: each had unrelated pre-existing working-tree drift
  (a checkpoint tail-end; an unrelated era-ledger bookkeeping gap) — both
  resolved separately by their own operators/orchestrators, unrelated to
  this phase.
- **The other 9 projects** (coherra, forqsite.help, halfhorse, lumin,
  meander, radar, rockue, stackabid, ud) were clean or had unrelated,
  independently-resolved drift (radar's deploy config, coherra's scratch
  directory) at survey time; each has a committed proposed-phase file ready
  for its own next session.

Resumed per-project, in each project's own session, as described above — no
target phase number in *this* repo, since the work no longer happens here.
RELEASE-058 (DP8 gate) remains blocked, correctly, until the fleet actually
migrates via this new per-project path.

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-97 Cold-eyes checklist

— developer fills in after phase completion —
