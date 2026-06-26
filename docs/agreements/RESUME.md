# Resume point — HARNESS001-ante1 complete; next is HARNESS001-main

**Written:** 2026-06-26. Update/delete once HARNESS001-main agreements are walked
and its first story is in flight.

## One-line status

Era 003 is `active`. **Phase HARNESS001-ante1 (preflight) is COMPLETE and tagged
`cp-HARNESS001-ante1`** — build gate 2255 passed, security 0 CRITICAL/HIGH, intent
review ALIGNED. All work committed/pushed to `origin/main` (and `harness`).

## What shipped in HARNESS001-ante1

- **RELEASE-001** (operator git): `v0.2.0` rollback-anchor tag at main HEAD; `harness`
  branch + `/mnt/work/flex-harness` worktree (worktree `CLAUDE.build.md` points at its
  own scripts). main untouched, still 0.2.x.
- **RELEASE-002** (harness-only): pairmode → `0.3.0-dev`, plugin/marketplace → `0.3.0`
  + match-guard test. Built on `harness` (`175925d`); **`deferred` on main** (lands at
  the fold, HARNESS006).
- **RELEASE-003**: CLI-surface freeze guard test. **RELEASE-004**: "Era 003 additive
  contract" section in `docs/architecture.md`. **RELEASE-005**: `fleet_discovery.py` +
  `docs/fleet-snapshot.md` (9 projects). **RELEASE-006**: `docs/harness-cutover-runbook.md`.
- **INFRA-185**: gate-blocker fix — isolated `lesson_review` CLIOutputClarity tests
  from live drift promotion (CER-057).

## The next action

Phase **HARNESS001-main — Resolver foundation (deterministic skeleton)**, RESOLVER rail.
Two things differ from ante1, both important:

1. **Agreements first.** Per the era doc, each phase gets its own agreements doc walked
   point-by-point BEFORE any story is specced. So the next step is to draft/walk
   `docs/agreements/HARNESS001-main.md` (open threads: the full resolver state set;
   signal/verdict boundary; leaf-worker return contract — see the era doc § "Open design
   threads"). Do NOT jump straight to `phase_new.py`.
2. **Built on `harness`, in the worktree.** From HARNESS001-main onward, refactor code is
   breaking and lands on the `harness` branch in `/mnt/work/flex-harness` (DP1), exercised
   only by its own tests until the flip (HARNESS006). The additive contract (DP4) +
   CLI-surface freeze test (RELEASE-003) guard the fleet during this window.

## Open backlog tied to this era (see docs/cer/backlog.md)

- **CER-059** (Do Later, HARNESS006): `fleet_discovery` shows 0 Signal-1 hits across the
  fleet — diagnose before the pre-fold gate (it gates fold blast-radius); + add a Signal-1
  verification step to the runbook; + HARNESS006 needs an explicit AC to reconcile
  RELEASE-002 `deferred → complete` on main at the fold.
- **CER-058** (Do Later): `meander` appeared in `registered_projects` without the operator
  running registration — investigate which bootstrap path writes it.

## Housekeeping notes

- `flex_eph/` untracked — leave it.
- Recurring guardrail: never estimate orchestrator context headroom from effort.db cost
  totals (effort.db ≠ context-control; now documented in `architecture.md` § Era 003
  additive contract). `context_current_tokens` reads a stale 25k (CER-054, deferred to
  Phase G) — the budget hook is not a reliable gauge.
- The stray `flex_build.py` edit did NOT reappear this session after the initial revert.
