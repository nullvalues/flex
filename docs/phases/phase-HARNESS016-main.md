---
era: "003"
---

# flex-harness — Phase HARNESS016-main: Final fold — pre-fold gate, merge to main, re-sync

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Execute the unexecuted tail of docs/harness-cutover-runbook.md: reconcile main drift into
fold-prep, run the DP8 pre-fold discovery gate as a hard block, fold fold-prep into
/mnt/work/flex main with tag v0.3.0, re-sync migrated projects to the canonical checkout,
and retire the flex-harness worktree.

## Background

Surfaced 2026-07-15/16 while planning the fold: `fold-prep` had fallen behind `main`
by 31 commits since RELEASE-008's reconciliation, including three commits
(INFRA-192, INFRA-193, INFRA-199) that harden the exact context-budget `PreToolUse`
gate subsystem that blocked a recent builder spawn attempt in this worktree, and one
commit (INFRA-195) that changes `audit.py`/`sync.py` — the tooling the fold's own
re-sync stories (RELEASE-015/017) depend on. RELEASE-014 must land before those
budget-gate/sync-tooling changes can be trusted during the rest of this phase.

Separately, live discovery (`fleet_discovery.py`) shows the DP8 pre-fold gate
currently **fails**: all 9 fleet projects remain on pairmode 0.2.x, and neither
flex nor flex-harness has self-synced. HARNESS013-main's "Fleet Migration" phase
shipped the migration *tooling*, not the migrations themselves — that campaign is
separate, cross-repo, operator-driven work that must complete before RELEASE-015
can pass.

Further surfaced 2026-07-17: a cold-eyes architectural review (requested ahead of
the fold, to check that pairmode's enforcement mechanisms — context budget gate,
scope guard, cold-read guard — actually read as "hygiene and guideline, not law"
rather than either a hollow claim or an inescapable trap) found:

1. `main` has drifted a **second** time since RELEASE-014's merge — now 36
   commits ahead of `fold-prep` (verified via `git log fold-prep..main
   --oneline`), including INFRA-205/206/207 and checkpoints 91-94. This batch
   is load-bearing for the review's own findings (see RELEASE-019).
2. Two enforcement/flexibility gaps that are independent of the drift and
   still present on `main` at HEAD: `flex_factor` (the documented per-story
   context-ceiling override) never reaches `context_budget.decide()`
   (RELEASE-020); and the `CONTEXT CHECK REQUIRED` gate variant is an
   unacknowledgeable hard block whose own message promises a self-heal that
   cannot happen, with no real exit named (RELEASE-021).
3. Documentation staleness that undermines the "system of record" claim:
   README era status, `architecture.md`'s pre-flip build-loop description and
   "advisory-only until HARNESS006" annotations (HARNESS006 shipped), and the
   reviewer procedure's self-contradictory input-scope contract (RELEASE-022).

Two findings from the same review — dead-code `scope_guard`/`cold_read_guard`
dispatch (no matching `PreToolUse` matcher registered) and a stale
`bootstrap.py` matcher — turned out to already be fixed on `main`
(INFRA-205, INFRA-206) and are resolved as a byproduct of RELEASE-019, not
tracked as separate stories. A third finding (this repo's own
`.claude/settings.json` pointing at `/mnt/work/flex` instead of this
worktree, with only a bare `Task` matcher) is the expected pre-self-sync
state already covered by RELEASE-015/017's gate and re-sync work — not a new
story.

## Stories

| ID | Title | Status |
|----|-------|--------|
| RELEASE-014 | Pre-fold reconciliation — merge main (31 commits, incl. INFRA-192/193/195/199) into fold-prep | complete |
| RELEASE-023 | Fix `_has_story_commit()` commit-message matching in `next_story.py` (resolver loop bug) | complete |
| RELEASE-019 | Second pre-fold reconciliation — merge main (36 commits, incl. INFRA-205/206/207) into fold-prep | complete |
| RELEASE-020 | Wire `flex_factor` into the context-budget `PreToolUse` gate | planned |
| RELEASE-021 | Fix the unacknowledgeable `CONTEXT CHECK REQUIRED` gate trap | planned |
| RELEASE-022 | Pre-fold doc sweep — era status, post-flip staleness, reviewer input-scope contradiction | planned |
| RELEASE-015 | Pre-fold discovery gate (DP8) — fresh fleet snapshot, hard block on un-migrated projects | planned |
| RELEASE-016 | Fold merge — fold-prep → main, tag v0.3.0 | planned |
| RELEASE-017 | Post-fold re-sync of migrated projects + RELEASE-002 status reconciliation | planned |
| RELEASE-018 | Worktree and branch retirement — remove /mnt/work/flex-harness | planned |

## Schema delivery

| Object | Management surface | Exception |
|---|---|---|
| _(none)_ | — | No new persistent schema objects introduced. |

---

### CP-HARNESS016-main Cold-eyes checklist

— developer fills in after phase completion —
