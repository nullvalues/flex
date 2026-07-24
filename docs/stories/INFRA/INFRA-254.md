---
id: INFRA-254
rail: INFRA
title: Restore live expected_step_tokens from observed orchestrator growth; growth-based gate re-arm past threshold
status: planned
phase: "100"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/context_budget.py
touches:
  - hooks/post_tool_use.py
  - skills/pairmode/scripts/context_model.py
  - tests/pairmode/test_context_budget.py
  - tests/pairmode/test_expected_step_tokens_source.py
  - tests/pairmode/test_post_tool_use_hook.py
  - docs/cer/backlog.md
  - docs/architecture.md
---

## Context

`expected_step_tokens` was designed (INFRA-127) as a live waterfall estimate
(`estimate_next_step_tokens()`: per-phase median → global median → seed) but
its source was effort.db attempt costs — subagent spend, ~53k builder median —
while the thin orchestrator's window actually grows ~5k/step. CER-053 declared
that comingling a DP7 violation and HARNESS-003 (2e74e8a) severed the live
path entirely (`estimate_next_step_tokens(None, None, seed)`), leaving the
static state.json value. Operator test (2026-07-24): a hand-edited value of
111 persisted through multiple builds and distorted the gate's headroom
arithmetic — nothing at runtime writes the key. Separately, the gate re-arms
only at story-completion events: it fired at ~102k and next at ~174k, a 72k
silent gap spanning the post-150k range where orchestrator quality drift is
observed.

Operator intent: the estimate was never supposed to be a fixed value. Restore
liveness with the *correct* source — observed orchestrator window growth
(`context_current_tokens` deltas, trustworthy since INFRA-251's isSidechain
fix) — which honors both the original live-estimate intent and DP7 (no
effort.db in the context-control path). No new database table: history lives
in a bounded state.json ring buffer (no management-UI story required; state
is observable via the existing context route/companion surfaces).

## Ensures

1. A new module-level recording path in `skills/pairmode/scripts/context_budget.py`
   (called from `hooks/post_tool_use.py`'s existing thin delegation — no new
   inline hook logic) appends each observed orchestrator step delta
   (current `compute_context_tokens()` minus the previous recorded value,
   when both are valid and the delta is > 0) to a bounded ring buffer in
   state.json, key `context_step_growth_samples`, capped at 20 entries
   (oldest evicted).
2. `decide()` derives `expected_step_tokens` live: median of the ring-buffer
   samples when ≥ 5 exist; otherwise the stored `expected_step_tokens` seed;
   otherwise `THIN_HARNESS_STEP_TOKENS`. The derived value is written back to
   state.json `expected_step_tokens` on each gate evaluation, so the key is
   genuinely live (a hand-edited value is overwritten by the next derivation
   once ≥ 5 samples exist — this is the intended behavior).
3. DP7 preserved: `estimate_next_step_tokens` continues to receive
   `db_path=None` (no effort.db read anywhere in the derivation);
   `tests/pairmode/test_expected_step_tokens_source.py` gains an assertion
   that the new derivation path never opens effort.db, and the existing
   `test_context_budget_fallback_not_53000` guard still passes.
4. Growth-based re-arm: when the budget was acknowledged
   (`context_budget_acknowledged_at` set) and `context_current_tokens` has
   since grown by ≥ `context_budget_reprompt_margin` while still over
   threshold, `should_block()` blocks again (fresh acknowledgment required).
   Below threshold, acknowledgment clearing behavior is unchanged
   (INFRA-251 regression tests still pass).
5. The block message reports the estimate's provenance: sample count and
   median when ring-buffer-derived, or "seed" / "default" otherwise, so an
   operator can see at a glance whether the number is live or cold-start.
6. Tests cover: ring-buffer append/eviction and non-positive-delta skip;
   derivation tiers (≥5 samples → median; <5 → seed; absent seed → 5000);
   live overwrite of a hand-edited `expected_step_tokens`; growth-based
   re-arm fires at margin and not before; no-effort.db assertion; existing
   INFRA-251 ack-clear regressions unchanged.
7. `docs/architecture.md` context-budget section updated: new state key
   `context_step_growth_samples` in the key inventory, the live-derivation
   contract replacing the static-default doctrine (with the CER-053/DP7
   rationale retained — live from context deltas, never from effort.db), and
   the growth-based re-arm cadence.
8. `docs/cer/backlog.md` CER-053 row gains a follow-up note: liveness
   restored (this story) from orchestrator-growth samples; DP7 boundary
   intact.
9. Full `tests/pairmode/` suite passes (known pre-existing
   `test_observability_ui.py::test_ui_build_emits_dist_index_html`
   worktree-only failure acceptable if it reproduces on clean HEAD).
