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

## Stories

| ID | Title | Status |
|----|-------|--------|
| RELEASE-014 | Pre-fold reconciliation — merge main (31 commits, incl. INFRA-192/193/195/199) into fold-prep | complete |
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
