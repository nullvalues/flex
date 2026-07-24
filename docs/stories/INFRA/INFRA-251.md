---
id: INFRA-251
rail: INFRA
title: Context-budget gate remediation — acknowledgment that actually clears, live counter writes, non-fossil step estimate
status: planned
phase: "99"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - hooks/pre_tool_use.py
touches:
  - hooks/post_tool_use.py
  - skills/pairmode/scripts/context_budget.py
  - tests/pairmode/test_pre_tool_use_hook.py
  - tests/pairmode/test_context_budget.py
  - docs/architecture.md
---

## Context

Operator-reported (2026-07-24, confirmed live against `.companion/state.json`
during this phase's build): the context-budget gate has three compounding
defects that together make it a hard wall instead of the operator-choice
checkpoint it was designed to be. The operator reports the same behavior
"in every project for weeks" — this predates the fold and is believed to be
an era-2 regression that was never revisited while 0.3 harness work moved.

1. **Acknowledgment never clears.** `decide()`'s contract (INFRA-193) is:
   block → hook writes `context_budget_acknowledged_at` → a genuine operator
   turn (`user_turn_seq > acknowledged_user_turn_seq`) converts the next
   attempt into a pass. Observed live: a genuine user turn occurred, the
   retry blocked again, and the hook re-stamped
   `acknowledged_user_turn_seq = context_budget_user_turn_seq = 150` at the
   moment of the new block — so the clear condition can never become true.
   "Say: Continue building" in the block message is currently a lie.
2. **The counter writer is dead in-session.** `context_current_tokens`
   stayed frozen at 91489 (`recorded_at` 13:44:29Z) across 25+ minutes of
   Edit/Write/Task events that the plugin-manifest PostToolUse hook
   (INFRA-182's designated writer) should each have refreshed. Two
   identically-worded blocks 20 minutes apart quoted byte-identical numbers.
   Root cause to be diagnosed (matcher gap, transcript-path derivation
   failure inside the plugin-root context, or early-exit in
   `post_tool_use.py`).
3. **`expected_step_tokens` is a fossil.** State carries a static 53000 that
   has not changed in weeks across all fleet projects (suspiciously equal to
   a rounded historical builder median — live effort.db median is 53996).
   Whatever recompute path existed no longer runs; the ceiling arithmetic
   (`current + expected > threshold × (1 + overrun)`) therefore compares a
   stale counter against a dead constant.

Relationship to siblings: INFRA-248 audits *inflation* of the counter
(double-increment); this story fixes the gate's *decision loop and liveness*.
INFRA-245/246 (phase 98) narrowed staleness triggers and exempted reviewer
spawns; neither touched the acknowledgment-clear path or the writer's
in-session liveness. Overlap in state keys (`context_budget_user_turn_seq`
jumped 143 → 150 across a single genuine operator turn this session — likely
the same duplicate-fire inflation INFRA-248 audits) must be reconciled with
INFRA-248's findings, not fixed twice.

## Requires

- INFRA-247 complete (single hook registration surface), so writer-liveness
  diagnosis runs against the deduplicated plugin-manifest registration.
- Build after (or jointly reconcile with) INFRA-248 — both stories touch the
  turn-sequence and counter keys.
- `hooks/` is a protected path; it is unlocked for this story via
  `primary_files` (INFRA-246 precedent).

## Ensures

1. **Acknowledgment clears.** After a block, one genuine operator turn makes
   the next identical spawn attempt pass (advisory acknowledged), without
   requiring token growth past `reprompt_margin` and without the hook
   re-stamping the acknowledgment turn-seq on re-block in a way that
   invalidates the pending acknowledgment. A pytest reproduces the exact
   observed sequence (block → user turn → retry) and asserts the retry
   passes.
2. **Re-block only on real growth.** After an acknowledged pass, the gate
   re-blocks only when `context_current_tokens` has genuinely advanced ≥
   `reprompt_margin` past the acknowledged level (the INFRA-193 intent,
   now actually reachable).
3. **Writer liveness.** The PostToolUse writer updates
   `context_current_tokens` on every event its registration matches; the
   in-session freeze observed 2026-07-24 is root-caused (finding recorded in
   build notes) and covered by a regression test.
4. **Live step estimate.** `expected_step_tokens` derives from current
   effort.db data (e.g. role-median refresh at spawn time or checkpoint) or,
   if a static default is deliberately retained, it is documented as such in
   `docs/architecture.md` and the stale per-project 53000 values are
   corrected. The recompute path has a test.
5. The gate's block message no longer instructs an action ("Continue
   building") that cannot succeed; message text matches the implemented
   contract.
6. Existing pairmode tests pass; `docs/architecture.md`'s context-budget
   section is updated to the corrected contract, with the era-2 regression
   noted.
