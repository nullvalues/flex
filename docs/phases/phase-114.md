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

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-301 | Non-interactive scaffolding: create-rail flag; surface phase-manifest registration failures | draft |
| INFRA-302 | Worktree build-environment provisioning; untrack tsconfig.tsbuildinfo | draft |
| INFRA-303 | Migration tooling: rules 9/10 name parity; expected_step_tokens opt-out and honest CER-111 disposition | draft |
| INFRA-304 | Containment parity for spec_preflight; reviewer-template revert-assertion residue | draft |
| INFRA-305 | Build-loop doc and procedure currency sweep | draft |
| INFRA-319 | Portable hook-command paths: plugin-root/settings.local registration, migrate rewrite of machine-absolute and pre-rename hook commands, audit finding | draft |
| INFRA-321 | Two-track context accounting: orchestrator-window occupancy vs story/subagent spend; health verdict re-based on the orchestrator track; between-spawn coverage; surfaces labeled (pulled from CER-129) | draft |
| INFRA-322 | Anchored, case-insensitive CER resolution-marker grammar: shared `cer.is_resolution_marked` predicate, cer-do-now guard stops reading `Resolved` as unresolved and `UNRESOLVED` as resolved, grammar published for consuming repos (pulled from CER-130) | draft |
| INFRA-323 | Session-lifecycle notices for agent-registration writes: RESTART REQUIRED at the end of bootstrap/migrate/sync paths that changed agent shells or hook registrations, restart step in the runbooks and SKILL.md flows, SessionStart staleness advisory (pulled from CER-134) | draft |
| INFRA-324 | Bash dispatch/allowlist for reviewer subagent git commands (reviewer FAIL-path improvisation gap) | draft |
| INFRA-325 | Wire docs-reviewer (WORKER-011) into canonical scaffold and checkpoint dispatch — role is fully specced but never created | draft |
| INFRA-326 | Dual-active-era tie-break silently skips the wrong era ledger row (INFRA-267 no-op) | draft |
| INFRA-327 | Exempt loop-breaker from the context-budget gate — it is the deterministic double-fail step, not discretionary | draft |
| INFRA-328 | next-action's spawn-loop-breaker carries no fail_cause — orchestrator can't fill the required LOOP-BREAKER input | draft |

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
