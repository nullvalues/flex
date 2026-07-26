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
| INFRA-280 | Resolver in-flight claim: next-action skips stories with a live worktree, claim semantics documented (CER-095.1) | draft |
| INFRA-281 | Story-keyed current_story and scope_guard resolution; merge/discard clear only their own key (CER-095.2) | draft |
| INFRA-282 | Story-keyed attempt counter with per-key escalation and E9 guard compatibility (CER-095.3) | draft |
| INFRA-283 | Phase-keyed checkpoint step state on top of INFRA-265's explicit phase key (CER-095.4) | draft |
| INFRA-284 | effort.db concurrency: WAL, busy_timeout, atomic attempt-number derivation, sweep ownership and cursor (CER-096) | draft |
| INFRA-285 | Side-session safety: session-scoped context accounting, atomic state writers, advisory state lock (CER-097) | draft |
| INFRA-286 | Merge robustness: return-code checks, failed-merge cleanup contract, merge serialization; amend serialism doc debt (CER-098) | draft |

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

— developer fills in after phase completion —
