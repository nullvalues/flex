---
era: "003"
---

# project — Phase 101: Attempt recording and checkpoint reporting correctness

← [Phase 100: — Scope-guard fail-closed completion (CER-048 close-out)](phase-100.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Make effort.db attempt recording and checkpoint-time cost reporting truthful: the checkpoint rollup must be scoped to the phase it reports on, and repeated spawns for a story must record real attempt numbers.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-256 | Phase-scoped checkpoint cost rollup — filter effort rollup to the phase being checkpointed | complete |
| INFRA-257 | Truthful attempt_number recording — derive real attempt sequence for repeated same-story spawns | complete |
| INFRA-258 | Async-spawn effort recording — derive tokens and outcome at completion time; fix checkpoint-worker story misattribution | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-101 Cold-eyes checklist

- **checkpoint-security** — PASS across two runs. First run (INFRA-256/257
  diff): no findings at any severity; INFRA-257's `COUNT(*)` derivation
  verified indexed (`idx_attempts_story`), bounded, behind the
  `effort_tracking` early return; all new SQL bound-parameterized. Delta
  re-run (INFRA-258): 0 CRITICAL / 0 HIGH; the reconciliation sweep verified
  bounded (RECONCILE_MAX_ROWS=5 / RECONCILE_MAX_LINES=20000, line-streamed),
  `reconcile_attempt`'s SET clause built only from a fixed column allow-list,
  `hooks/post_tool_use.py` untouched, session_start.py's new call best-effort
  and unable to affect reset logic. Two non-blocking notes filed as CER-088
  (no index for the `pending_reconcilable` full-table scan on a hook path)
  and CER-089 (output_file opened without a containment check — harness-
  generated value, same trust category as hook-payload `cwd`).
- **checkpoint-intent** — ALIGNED across two runs, all three stories
  (including mid-phase INFRA-258), no pivots, no undeclared file touches.
  "Hooks are thin relays only" explicitly re-checked for both INFRA-257's
  one-query derivation and INFRA-258's second bounded delegated call in
  session_start.py — extension of the accepted INFRA-236/237/254 pattern,
  not new drift. Full suite 3400 passed / 0 failed. `phase:<key>` rows not
  yet surfaced in pairmode_effort.py reports or the observability SPA —
  explicitly deferred in INFRA-258's Out-of-scope, not a silent gap.
- **checkpoint-docs** — PASS after two pre-tag docs commits: first added the
  missing Phase 101 CHANGELOG entry and filled this checklist for
  INFRA-256/257; second (post-INFRA-258) added the INFRA-258 CHANGELOG
  bullet, updated this checklist for the enlarged diff, and filed
  CER-088/089. architecture.md verified accurate against shipped code at
  both passes (checkpoint-report scoping, `next_attempt_number`, async
  reconciliation mechanism, accepted-loss notes).
- **Mid-phase addition (2026-07-24):** INFRA-258 added pre-tag at operator
  direction after live verification of the new phase-scoped rollup showed
  async Agent spawns record token-less/outcome-less rows (PostToolUse fires
  on launch metadata; the subagent transcript doesn't exist yet), starving
  both rollups and the FAIL escalation ladder, and showed phase-level
  checkpoint workers misattributed to `story_id = INFRA-256`. The spec
  investigation also surfaced and fixed a token-inflation bug: streaming
  JSONL entries sharing a message.id were summed instead of deduped
  last-wins, inflating every token total the sync path ever recorded.
- **Provenance:** INFRA-256/257 filed from the operator's post-cp100 review
  of the misleading "builder: 19 attempt(s)" rollup (db-lifetime count read
  as phase cost) and the all-1s `attempt_number` rows (INFRA-247/248 shape);
  operator directed fixing both — then INFRA-258 — before continuing the
  fleet rollout.
