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
RELEASE-030 (Repo-G) remains excluded — parked at `backlog` pending unscoped
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
| RELEASE-043 | Fleet migration — sync Repo-H to pairmode 0.3.0 | superseded — resolved by Repo-H's own hand-migrated session (commit d40c44b), verified via RELEASE-071 fleet sweep |
| RELEASE-044 | Fleet migration — sync Repo-I to pairmode 0.3.0 | superseded — resolved by Repo-I's own hand-migrated session (PM057-main), verified via RELEASE-071 fleet sweep |
| RELEASE-045 | Fleet migration — sync base56 to pairmode 0.3.0 | superseded — resolved by phase-106 RELEASE-069 (decommissioned, not migrated, per operator directive) |
| RELEASE-046 | Fleet migration — sync Repo-C to pairmode 0.3.0 | superseded — resolved by phase-106 RELEASE-065 |
| RELEASE-047 | Fleet migration — sync Repo-A to pairmode 0.3.0 | superseded — resolved by Repo-A's own hand-migrated session (story-INFRA-045), verified via RELEASE-071 fleet sweep |
| RELEASE-048 | Fleet migration — sync Repo-E to pairmode 0.3.0 | superseded — resolved by Repo-E's own hand-migrated session (story-INFRA-020), verified via RELEASE-071 fleet sweep |
| RELEASE-049 | Fleet migration — sync Repo-D to pairmode 0.3.0 | superseded — resolved by phase-106 RELEASE-066 |
| RELEASE-050 | Fleet migration — sync Repo-F to pairmode 0.3.0 | superseded — resolved by phase-106 RELEASE-067 |
| RELEASE-051 | Fleet migration — sync Repo-J to pairmode 0.3.0 | superseded — resolved by phase-106 RELEASE-064 |
| RELEASE-052 | Fleet migration — sync Repo-B to pairmode 0.3.0 | superseded — resolved by phase-106 RELEASE-063 (campaign canary) |
| RELEASE-053 | Fleet migration — sync Repo-K to pairmode 0.3.0 | superseded — resolved by phase-106 RELEASE-068 (canon-only, proof-deferred) |
| RELEASE-054 | Fleet migration — sync Repo-L to pairmode 0.3.0 | superseded — resolved by Repo-L's own hand-migrated session (story-MU-128), verified via RELEASE-071 fleet sweep |
| RELEASE-055 | Fleet migration — sync Repo-M to pairmode 0.3.0 | superseded — resolved by Repo-M's own hand-migrated session (RK011-ante1), verified via RELEASE-071 fleet sweep |
| RELEASE-056 | Fleet migration — sync Repo-N to pairmode 0.3.0 | superseded — resolved by Repo-N's own hand-migrated session (story-INFRA-014), verified via RELEASE-071 fleet sweep |
| RELEASE-057 | Fleet migration — sync Repo-O to pairmode 0.3.0 | superseded — resolved by Repo-O's own hand-migrated session (INFRA-210/211), verified via RELEASE-071 fleet sweep |
| RELEASE-058 | Pre-fold discovery gate (DP8) — fresh fleet snapshot, hard block on un-migrated projects | deferred |
| RELEASE-059 | Fold merge — fold-prep into main, tag v0.3.0 | complete |
| RELEASE-060 | Post-fold re-sync of migrated projects + RELEASE-002 status reconciliation | draft |
| RELEASE-061 | Worktree and branch retirement — remove /mnt/work/flex-harness | skipped (superseded by RELEASE-062, phase 105 — see § Deferred stories) |
| INFRA-225 | Port startswith("complete") annotated-status fallback into next_action.py's _resolve_active_phase | complete |
| INFRA-226 | Add fable as an escalation-tier model; document mandatory custom-model entry at model-upgrade gates | complete |
| INFRA-227 | Port Model-upgrade prompts subsection into CLAUDE.build.md.j2 sync template | complete |
| INFRA-228 | Match hook blocks by basename not full path — fix duplicate hook registration on plugin_root migration | complete |
| INFRA-229 | Reword Model-upgrade prompts section to avoid banned await-user phrase in CLAUDE.build.md.j2 | complete |
| INFRA-230 | Fix CER-072 — checkpoint build-gate guard hardcodes flex-only pytest path, blocking every downstream checkpoint | complete |
| INFRA-231 | Update fleet_discovery.py's hardcoded candidate list to include 7 missing fleet projects | complete |
| INFRA-232 | Fix README era-status and production-readiness contradictions; remove stale duplicate readme.md | complete |
| INFRA-233 | Register context-budget-gate hooks in flex-harness's own settings.json — never dogfooded on itself | complete |
| INFRA-234 | Drop redundant Write(docs/phases/permissions/\*\*) deny rule from settings.json | complete |
| INFRA-235 | Stop generating invalid Write(path) permission rules across bootstrap.py, permission_scope.py, denylist_deriver.py | complete |

## Deferred stories

RELEASE-043 through RELEASE-057 (the 15 per-project fleet-migration stories)
were deferred on 2026-07-22, mid-execution, after a scope-check the operator
requested surfaced two problems with running them directly from this repo:

1. **Numbering-convention risk.** RELEASE-043 (Repo-H) was already built and
   merged directly from this repo before the check — a follow-up 15-project
   survey confirmed no actual collision occurred there, but the other 14
   fleet projects use at least six distinct, mutually incompatible
   phase/story-numbering conventions (bare integers, `PM0NN-{suffix}`,
   `EH0NN-{suffix}`, `RK0NN-{suffix}`, `SB0NN-{suffix}`, era-prefixed
   `{MVP/GA}0NN`/`{FPS/MU/LF}0NN`/`MN0NN`), several with stale
   index.md "next to build" pointers or doc/tooling drift. Building directly
   from flex-harness risked silently colliding with a project's real next
   phase number or convention.
2. **Concurrency risk.** Several projects (Repo-I, Repo-K) had unpushed commits
   or in-flight human-gated work (Repo-K's Phase 2 is gated on a human UAT
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
- **Repo-H**: furthest along — `sync-all`/`to-030`/Signal-1 discovery all
  verified working there (see RELEASE-043's build history); blocked only on
  step 6 (one proven story cycle), which was blocked by the
  `_resolve_active_phase` annotated-status bug, now fixed (INFRA-225,
  merged). Repo-H's own next session can likely complete the migration in one
  pass. A dedicated Repo-H-local proposed-phase file was not dropped (its
  phase-numbering convention was already confirmed collision-free and real
  migration progress already exists there) — its own operator should resume
  directly.
- **Repo-I, Repo-K**: had uncommitted/unpushed state at survey time; resolved by
  the operator directly (Repo-I: nothing to reconcile; Repo-K: uncommitted
  canonical-template sync committed as-is, prototype repo).
- **base56**: `docs/phases/index.md` is stale relative to real phase/story
  state and `main`'s git history appears squashed — flagged in its proposed
  file for reconciliation before sequencing.
- **Repo-C, Repo-E**: each had unrelated pre-existing working-tree drift
  (a checkpoint tail-end; an unrelated era-ledger bookkeeping gap) — both
  resolved separately by their own operators/orchestrators, unrelated to
  this phase.
- **The other 9 projects** (Repo-A, Repo-D, Repo-F, Repo-J,
  Repo-B, Repo-L, Repo-M, Repo-N, Repo-O) were clean or had unrelated,
  independently-resolved drift (Repo-L's deploy config, Repo-A's scratch
  directory) at survey time; each has a committed proposed-phase file ready
  for its own next session.

Resumed per-project, in each project's own session, as described above — no
target phase number in *this* repo, since the work no longer happens here.
RELEASE-058 (DP8 gate) remains blocked, correctly, until the fleet actually
migrates via this new per-project path.

**RELEASE-061** (*"Worktree and branch retirement — remove
/mnt/work/flex-harness"*) is superseded by **RELEASE-062** (phase 105), not
awaiting resume. `/mnt/work/flex-harness` turned out to be the permanent
release channel (phase 102, `complete`), not a temporary worktree, so the
teardown this story would have performed must never be executed — see
`docs/stories/RELEASE/RELEASE-061.md` § *Superseded* and
`docs/architecture.md` § *Release channel — flex-harness*.

**Named individually (INFRA-310, check-index deferred-without-section fix,
2026-08-01).** The prose range "RELEASE-043 through RELEASE-057" above did
not satisfy `check-index` check 4's per-ID substring match for the thirteen
IDs it does not spell out literally. Each of the following resumes
post-0.3.1 at the fold, per this section's own resolution above, and each is
already dispositioned by the story or phase named:
- **RELEASE-044** (Repo-I) — superseded by Repo-I's own hand-migrated session
  (`PM057-main`).
- **RELEASE-045** (base56) — superseded by phase-106 RELEASE-069
  (decommissioned, not migrated).
- **RELEASE-046** (Repo-C) — superseded by phase-106 RELEASE-065.
- **RELEASE-047** (Repo-A) — superseded by Repo-A's own hand-migrated
  session (`story-INFRA-045`).
- **RELEASE-048** (Repo-E) — superseded by Repo-E's own hand-migrated
  session (`story-INFRA-020`).
- **RELEASE-049** (Repo-D) — superseded by phase-106 RELEASE-066.
- **RELEASE-050** (Repo-F) — superseded by phase-106 RELEASE-067.
- **RELEASE-051** (Repo-J) — superseded by phase-106 RELEASE-064.
- **RELEASE-052** (Repo-B) — superseded by phase-106 RELEASE-063 (campaign
  canary).
- **RELEASE-053** (Repo-K) — superseded by phase-106 RELEASE-068
  (canon-only, proof-deferred).
- **RELEASE-054** (Repo-L) — superseded by Repo-L's own hand-migrated session
  (`story-MU-128`).
- **RELEASE-055** (Repo-M) — superseded by Repo-M's own hand-migrated
  session (`RK011-ante1`).
- **RELEASE-056** (Repo-N) — superseded by Repo-N's own hand-migrated
  session (`story-INFRA-014`).
- **RELEASE-058** (DP8 pre-fold discovery gate) — waived by the 2026-07-23
  operator override recorded in `## DP8 gate override` below and in
  `docs/stories/RELEASE/RELEASE-058.md` § *Resolution*; its gate tooling was
  never built and this is not a resume-later item, it is a closed waiver.

## DP8 gate override

2026-07-23: the DP8 gate check was run manually against the fresh fleet
snapshot — verdict BLOCK (8/16 projects at 0.3.0) — and the operator explicitly
overrode the block because the per-project migration path is not working
reliably; un-migrated projects will break at the flip and be manually patched
post-fold. RELEASE-058 is waived (status `backlog`), its gate tooling unbuilt —
see the `## Resolution — operator override (2026-07-23)` section in
`docs/stories/RELEASE/RELEASE-058.md`. RELEASE-059 (the fold merge) proceeds
under this override.

## Closed (2026-07-29, RELEASE-071)

Phase closed by phase-106's RELEASE-071 (campaign close). All 15 deferred
fleet-migration stubs (RELEASE-043..057) are superseded — 7 by phase-106's
own driven campaign stories (RELEASE-063..069), 8 by each project's own
independent hand-migrated session, all verified via a fresh
`fleet_discovery.py --no-snapshot` sweep recorded in RELEASE-071's
`## Evidence`. RELEASE-058 (DP8 gate) remains waived per the 2026-07-23
operator override above — not reopened. See `docs/phases/phase-106.md` and
`docs/stories/RELEASE/RELEASE-071.md` for the full disposition.

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-97 Cold-eyes checklist

— developer fills in after phase completion —
