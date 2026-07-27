---
era: "003"
phase_class: production
---

# project — Phase 109: Single-orchestrator parallel build concurrency

← [Phase 104: Recording and checkpoint correctness](phase-104.md) — build-order predecessor (index-ordered; numbering is non-sequential)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Restore the intended single-orchestrator parallel story/phase build capability by replacing single-slot coordination state with story/phase-keyed state, making the resolver in-flight aware, and hardening effort.db, hooks, and merge paths against concurrent tool calls and side sessions. Closes CER-095/096/097/098. Builds between cp-104 and phase 105 (index-ordered, not numeric).

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-280 | Resolver in-flight claim: next-action skips stories with a live worktree, claim semantics documented (CER-095.1) | complete |
| INFRA-281 | Story-keyed current_story and scope_guard resolution; merge/discard clear only their own key (CER-095.2) | complete |
| INFRA-282 | Story-keyed attempt counter with per-key escalation and E9 guard compatibility (CER-095.3) | complete |
| INFRA-283 | Phase-keyed checkpoint step state on top of INFRA-265's explicit phase key (CER-095.4) | complete |
| INFRA-284 | effort.db concurrency: WAL, busy_timeout, atomic attempt-number derivation, sweep ownership and cursor (CER-096) | complete |
| INFRA-285 | Side-session safety: session-scoped context accounting, atomic state writers, advisory state lock (CER-097) | complete |
| INFRA-286 | Merge robustness: return-code checks, failed-merge cleanup contract, merge serialization; amend serialism doc debt (CER-098) | complete |

**Position note:** numbered 109 (scaffolded 2026-07-25, after 105–108 already existed) but
index-ordered directly after 104 — it builds between cp-104 and phase 105. The full
concurrency audit evidence lives in CER-095..098 (`docs/cer/backlog.md`), filed from the
2026-07-25 parallel-build audit; spec-writers should read those rows first.

**Scope statement:** the target capability is **one orchestrator, parallel story/phase
builds** — an original design intent previously exercised "to some extent". Multi-
orchestrator operation stays out of scope (CER-097's session-safety work protects a
build loop from *side sessions*, not from a second full loop).

## Ordering

INFRA-280 (resolver claim) and INFRA-281 (keyed current_story/scope_guard) first, in
either order — they are the enabling pair. INFRA-282 (keyed counter) after 281.
INFRA-283 (keyed checkpoint state) any time after 280. INFRA-284 (effort.db) and
INFRA-285 (side-session safety) independent; INFRA-284 rebases on phase-104's
INFRA-264/266 changes to the same files. INFRA-286 (merge robustness + doc-debt
amendments) last — it rewrites the serialism comments the other stories obsolete.

## Checkpoint proves

Two stories of a test phase (or two synthetic stories in tests) build concurrently under
one orchestrator: the resolver offers different stories to consecutive next-action calls
while one is in flight; each builder's writes are scope-checked against its own story's
allow-list; parallel FAILs escalate independently; effort.db records every attempt under
WAL with correct attempt numbers; a mid-build side session leaves the loop's context
counter and pending rows untouched; and a failed merge leaves a documented, recoverable
state instead of a silent success.

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-109 Cold-eyes checklist

Filled by the orchestrator at cp-109 (2026-07-27).

- **CER-095 closed, all four items (INFRA-280..283):** (1) the resolver now reads
  `.pairmode-worktrees/` as an in-flight claim (`flex_build.claimed_story_ids`,
  opt-in `claimed=` filter in `find_next_story`, `await-user`/`all-stories-claimed`
  ahead of Row 9); (2) `current_story` became a story-keyed `current_stories`
  record with per-call `scope_guard.resolve_call_story` resolution that refuses to
  guess on ambiguity — landing one story no longer wipes a sibling's scope
  enforcement; (3) the attempt counter is story-keyed with scoped clears (merge
  clears only its own key, discard clears nothing so the count survives to
  escalate); (4) checkpoint step state is phase-keyed (`checkpoint_steps`), with
  the flat pair kept as a derived mirror and the CER-083 stale-stamp rule demoted
  to the legacy-only path.
- **CER-096 closed (INFRA-284):** WAL + busy_timeout via a single `_connect`,
  per-process `ensure_db` cache, atomic `BEGIN IMMEDIATE` write-side
  attempt-number derivation, and a two-ended ownership-filtered reconcile sweep.
- **CER-097 closed (INFRA-285):** session-keyed `context_sessions` accounting
  (flat keys as display-only mirror), session-resolved `context_budget.decide`,
  sweep ownership exclusion, and a bounded (2s) advisory fail-open
  `state_utils.state_lock` adopted by every named `state.json` writer. Explicitly
  NOT a multi-orchestrator guarantee — the row and architecture.md both say so.
- **CER-098 closed (INFRA-286):** return-code-checked `_teardown_story_worktree`
  shared by merge/discard with deliberate clear-vs-residue ordering asymmetry,
  `recovery:`-prefixed failed-land blocks with exact re-run commands, and a
  bounded `.companion/merge` advisory lock around both critical sections;
  CER-050's "concurrent writers are not expected" doctrine amended.
- **Builder deviations adjudicated at review (all upheld):** INFRA-281's
  worktree-path directory-existence requirement (closes a self-corroborating
  path-impersonation bypass); INFRA-285's ring-buffer pin
  (`setdefault(context_step_growth_samples, [])` prevents cross-session mirror
  re-inheritance), session_start no-op skip preserving INFRA-175 byte-identity,
  and two CER-096 source-assertion tests rewritten per INFRA-284's own deferral
  note; INFRA-286's D5 grep discrepancy traced to the pre-existing CER-097 row.
- **Gates:** security PASS (0 findings at any severity; informational notes on
  the advisory lock's bounded/fail-open design and parameterized SQL). Intent
  ALIGNED (all seven stories trace to spec; no scope creep; downstream note for
  Phase 105's INFRA-271 spec-writer to read the new keyed scope-guard model).
  Docs PASS on second run (first run failed on a missing CHANGELOG entry, added
  at checkpoint as `docs(phase-109)`).
- **Known process gaps this checkpoint:** story statuses were flipped
  post-merge by the orchestrator (no worker in the loop owns the flip — same as
  cp-104); one MEDIUM reviewer finding on INFRA-285
  (`test_post_tool_use_hook.py` modified but undeclared in `touches`).
- **New backlog from this phase:** CER-101 (checkpoint-report reads "no attempts
  recorded" for a fully-built phase because spawn rows were still pending
  reconciliation, and the sweep and `classify_pending_reason` disagree about
  reconcilability of the same rows).
