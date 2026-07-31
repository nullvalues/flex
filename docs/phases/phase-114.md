---
era: "004"
phase_class: production
---

# project — Phase 114: Build-loop closeout: worktrees, scaffolding, migration tooling, doc currency

← [Phase 113: Shared blockers: frontmatter, resolver evidence, recording determinism](phase-113.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Remove recurring build-loop friction (unprovisioned worktrees, interactive scaffolding prompts, silent phase-manifest drift, incomplete migration rules) and bring build-loop procedure and architecture docs back to truth so the next cold-eyes audit reads a correct contract.

**Backlog pull at spec time.** INFRA-319 was pulled into this phase from CER-127 (operator-flagged 2026-07-29, fleet portability — machine-bound and pre-rename hook command paths in consuming repos' `.claude/settings.json`). CER-127 named this phase's migration work as its candidate home; the row's phase column now reads 114 and its resolution annotation lands when INFRA-319 completes. Recorded as AG-8 in `docs/closeout-agreements-20260729.md`.

**Second backlog pull at spec time.** INFRA-321 was pulled into this phase from CER-129 (operator report 2026-07-29, context accounting — story/subagent token spend attributed to the orchestrator's context window while the orchestrator's own between-spawn accumulation goes unmeasured, so the context-health prompt fires on the wrong quantity in both directions). It lands in 114 rather than 116 because phase 116's INFRA-316 plans to wire `context_budget_check.py` into `next-action`'s between-story pause, which would promote the mis-attribution into the resolver's live cadence decision; the track boundary must exist first. CER-129's phase column now reads 114 and its resolution annotation lands when INFRA-321 completes. Recorded as AG-10 in `docs/closeout-agreements-20260729.md`.

**Third backlog pull at spec time.** INFRA-322 was pulled into this phase from CER-130 (operator report 2026-07-29, phase-35 checkpoint on a consuming repo — the `cer-do-now` checkpoint guard's bare, case-sensitive substring test reads a title-case `Resolved` backlog as permanently unresolved and reads `UNRESOLVED` as resolved). It lands in 114 because this phase already owns build-loop truth-restoration and doc-currency work, and because the defect is live fleet-blocking: the observed remedy was a manual `checkpoint-tag` bypass of the gate, the CER-067 failure class. CER-130's phase column now reads 114 and its resolution annotation lands when INFRA-322 completes. Recorded as AG-11 in `docs/closeout-agreements-20260729.md`.

**Fourth backlog pull at spec time.** INFRA-323 was pulled into this phase from CER-134 (operator report 2026-07-29, bootstrap session lifecycle — Claude Code loads agent definitions, plugin/skill registrations and hook blocks at session start only, while `bootstrap`, `migrate`, `to-030`, `sync-agents`/`sync-all` and `audit-hooks` all write those surfaces mid-session and say nothing about it, so a freshly bootstrapped or migrated repo reads as a failed bootstrap until the operator happens to exit and relaunch). It lands in 114 because this phase already owns build-loop friction removal and doc-currency work, and because the forcing function is immediate: RELEASE-068's canon-only pokus migration (phase 106) creates `gate-worker.md` and rewrites seven agent shells mid-session, verifying only that the files are on disk. CER-134's phase column reads 114 and its resolution annotation lands when INFRA-323 completes. Recorded as AG-12 in `docs/closeout-agreements-20260729.md`.

## Ordering

**Group 1 — phase's own original scope, build first.** INFRA-301..305 in
numeric order: non-interactive scaffolding, worktree provisioning,
migration-tooling parity, spec_preflight containment parity, and the
doc/procedure currency sweep. No cross-dependencies among them beyond
numeric order; INFRA-305 (doc sweep) benefits from running last within
this group since earlier stories in the group may themselves touch docs
that need re-sweeping.

**Group 2 — standalone, low-risk, build anytime after Group 1.** INFRA-326
(era-ledger tie-break fix) first — small, self-contained, unblocks
nothing but blocks nothing either. Then INFRA-319 (portable hook-command
paths) — the most load-bearing backlog pull, directly referenced by
RELEASE-068's and RELEASE-070's field findings (phase 106) and by
INFRA-323 below. Then INFRA-323 (session-lifecycle restart notices) —
sequenced after INFRA-319 since both touch `bootstrap.py`/`sync`/`migrate`
adjacent surfaces and INFRA-323's restart-notice wording should reflect
INFRA-319's corrected hook-path behavior, not the pre-fix one.

**Group 3 — independent backlog pulls, any order.** INFRA-321 (two-track
context accounting) and INFRA-322 (CER resolution-marker grammar) — no
dependency on each other or on Groups 1/2.

**Group 4 — docs-reviewer wiring.** INFRA-325 (wire docs-reviewer into
canonical scaffold/dispatch) — independent, but do before Group 5 since
Group 5's INFRA-324 also touches the checkpoint/dispatch surface and a
correctly-wired docs-reviewer should exist before further checkpoint-path
changes land, to avoid two dispatch-table edits colliding in review.

**Group 5 — hooks/pre_tool_use.py changes, build together, in this order.**
INFRA-324 (reviewer Bash allowlist — adds a new `Bash` dispatch branch)
then INFRA-327 (loop-breaker context-budget exemption — edits
`BUILD_CYCLE_SUBAGENTS`) — both touch `hooks/pre_tool_use.py`; sequencing
them adjacently (324 first, since it adds a new branch entirely, 327
second, since it only edits an existing set) keeps each diff small and
easy to review against the other.

**Group 6 — the actual loop-breaker fix, highest priority within this
phase's backlog pulls.** INFRA-328 (surface `fail_cause` into
`spawn-loop-breaker`'s dispatch) — this is the confirmed root cause of the
live operator-reported behavior ("loop-breaker should run automatically
after two failed attempts; human intervention is only needed if its fix
doesn't work"). INFRA-327 (Group 5) is a real, separately-valid gap but
was confirmed *not* the cause of what was observed — INFRA-328 is. Build
after Group 5 (no file conflict — INFRA-328 touches `next_action.py`, not
`hooks/pre_tool_use.py` — but sequenced last so its regression tests can
exercise a `hooks/pre_tool_use.py` already carrying Group 5's changes).

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-301 | Non-interactive scaffolding: create-rail flag; surface phase-manifest registration failures | complete |
| INFRA-302 | Worktree build-environment provisioning; untrack tsconfig.tsbuildinfo | complete |
| INFRA-303 | Migration tooling: rules 9/10 name parity; expected_step_tokens opt-out and honest CER-111 disposition | complete |
| INFRA-304 | Containment parity for spec_preflight; reviewer-template revert-assertion residue | complete |
| INFRA-305 | Build-loop doc and procedure currency sweep | complete |
| INFRA-319 | Portable hook-command paths: plugin-root/settings.local registration, migrate rewrite of machine-absolute and pre-rename hook commands, audit finding | complete |
| INFRA-321 | Two-track context accounting: orchestrator-window occupancy vs story/subagent spend; health verdict re-based on the orchestrator track; between-spawn coverage; surfaces labeled (pulled from CER-129) | complete |
| INFRA-322 | Anchored, case-insensitive CER resolution-marker grammar: shared `cer.is_resolution_marked` predicate, cer-do-now guard stops reading `Resolved` as unresolved and `UNRESOLVED` as resolved, grammar published for consuming repos (pulled from CER-130) | complete |
| INFRA-323 | Session-lifecycle notices for agent-registration writes: RESTART REQUIRED at the end of bootstrap/migrate/sync paths that changed agent shells or hook registrations, restart step in the runbooks and SKILL.md flows, SessionStart staleness advisory (pulled from CER-134) | complete |
| INFRA-324 | Bash dispatch/allowlist for reviewer subagent git commands (reviewer FAIL-path improvisation gap) | complete |
| INFRA-325 | Wire docs-reviewer (WORKER-011) into canonical scaffold and checkpoint dispatch — role is fully specced but never created | complete |
| INFRA-326 | Dual-active-era tie-break silently skips the wrong era ledger row (INFRA-267 no-op) | complete |
| INFRA-327 | Exempt loop-breaker from the context-budget gate — it is the deterministic double-fail step, not discretionary | complete |
| INFRA-328 | next-action's spawn-loop-breaker carries no fail_cause — orchestrator can't fill the required LOOP-BREAKER input | complete |
| INFRA-330 | Correct stale draft status on 13 merged, reviewer-PASSed phase-114 stories | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-114 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
