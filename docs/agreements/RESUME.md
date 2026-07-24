# Resume point — HARNESS002-main agreements SETTLED; next is phase_new.py + story specs

**Written:** 2026-06-28. Update/delete once HARNESS002-main's first story is in flight.

## One-line status

Era 003 is `active`. **Phase HARNESS001-main (resolver foundation) is COMPLETE and
tagged `cp-HARNESS001-main`** — build gate 2361 passed, security 0 CRITICAL/HIGH,
intent review ALIGNED (1 MEDIUM carry-forward → CER-060). Committed/pushed to `harness`.
(Prior: HARNESS001-ante1 preflight COMPLETE, tagged `cp-HARNESS001-ante1`.)

## What shipped in HARNESS001-main

Four RESOLVER-rail stories built the **advisory-only** `flex_build.py next-action`
resolver (NOT wired into the live `CLAUDE.build.md` — DP7):
- **RESOLVER-001** (DP1): `next_action.py` action grammar — `make_action`,
  `validate_action`, `ACTIONS`, `SCHEMA_VERSION=1` + JSON Schema/samples fixtures.
- **RESOLVER-002** (DP3/DP5): pure-read `infer_position` composing
  `next_story`/`model_selector`/gate helpers; 5 signature-preserving `flex_build.py`
  extractions; no durable writes.
- **RESOLVER-003** (DP2/DP4/DP6): `resolve_next_action` 9-state machine + pure-read
  `next-action` subcommand (`--json`/`--warning`); judgment-handoffs → `await-user`.
- **RESOLVER-004** (DP8): synthetic-state fixtures + 9-row DP2 matrix + DP5 compose guard.

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

Phase **HARNESS002-main — Gate verdict extraction**, **WORKER rail (RESOLVER touch)**.
The agreements walk is DONE. Two things to remember, both important:

1. **Agreements SETTLED.** `docs/agreements/HARNESS002-main.md` is ✅ SETTLED — all 8 DPs
   AGREED, story outline finalized (committed `docs(HARNESS002-main): settle …`). The next
   step is `phase_new.py --phase-id HARNESS002 --suffix main` (phase-class `production`),
   then `story_new.py` for the five stories: **WORKER-001** (verdict grammar + fixture) →
   **RESOLVER-005** (`spawn-gate-worker` action + Row-4 split + routing) → **WORKER-002**
   (gate worker: thin shell + plugin procedure skill) → **RESOLVER-006** (CF-1/CER-060 fix)
   → **WORKER-003** (isolation suite). Build order is that sequence. **CF-1 (← CER-060)** is
   bundled as RESOLVER-006 — it closes on that build.
2. **Built on `harness`, in the worktree.** Refactor code is breaking and lands on the
   `harness` branch in `/mnt/work/flex-harness` (DP1), exercised only by its own tests
   until the flip (HARNESS006). The gate worker is **advisory-only** — NOT wired into the
   live `CLAUDE.build.md` this phase. The additive contract (DP4) + CLI-surface freeze test
   (RELEASE-003) guard the fleet during this window (no `check-*` signature change — DP6).

## Open backlog tied to this era (see docs/cer/backlog.md)

- **CER-060** (Do Later, HARNESS002): `resolve_next_action` Row 5 hardcodes `model="opus"`
  for the retry-upgrade path instead of delegating to `select_builder_model(attempt_number=2)`.
  Correct today, but two-places encoding + the DP5 compose guard only checks import-presence,
  not call-site coverage → silent-divergence risk. Folded forward as **CF-1** in
  `docs/agreements/HARNESS002-main.md` (resolve at walk time).
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
