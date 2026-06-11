---
era: "002"
---

# flex — Phase 65: Context budget per-story drift fix

← [Phase 64: Observability SPA hardening — cold-eyes review fixes](phase-64.md)

**Parent phase:** Phase 64 left behind zero deferred stories; this phase is a clean follow-on.

## Goal

Fix the context budget gate's silent drift failure (CER-045): the gate never fires
on multi-story phases because three interlocking bugs defeat it.

## Root cause analysis

CER-027 → 039 → 041 → 045 is a chain of successive gap closures. Phase 47 added the
hook; Phase 58 replaced transcript parsing with a state.json contract; Phase 59 added
TTL-based staleness to catch cross-session stale values. None addressed the
within-session drift case. Three bugs work together to defeat the gate:

**Bug 1 — `story_context.py --clear` erases the token count.**
`clear_current_story()` (added in Phase 59 CER-041 as belt-and-suspenders alongside
TTL) pops `context_current_tokens` and `context_current_tokens_recorded_at` after
every story. The intended effect: force a fresh `/context` check at the next Context
gate. The actual effect: the orchestrator re-estimates from scratch every story.

**Bug 2 — The re-estimate is always wrong.**
The Context gate says "call `/context` and read the current token count." Claude cannot
invoke `/context` programmatically; it produces a one-time estimate (e.g., 25k for a
fresh post-/clear session) and calls `set-context-tokens --tokens 25000` at the start
of every story. The hook always sees 25k + 53k = 78k < 132k ceiling → never blocks.

**Bug 3 — Estimation fallback is blind.**
`story-cost-estimate` requires ≥5 PASS samples for (rail, story_class). New phases
and low-volume rails almost always show "insufficient data," so the threshold
comparison the Context gate is supposed to make is missing.

## The fix

**Part A — stop erasing token count between stories (INFRA-170).**
Remove the `context_current_tokens` pops from `clear_current_story()`. The TTL
(CER-041, default 60 min) remains as the cross-session staleness backstop. The
running total now SURVIVES story transitions.

**Part B — accumulate actual story cost (INFRA-169).**
New `flex_build.py bump-context-tokens --cost N` command. Called in Step 6 (after
`record_attempt.py`, before `story_context.py --clear`). Adds N — the real
`total_tokens` from the `<usage>` block — to `context_current_tokens`. The running
total grows by each story's actual cost, not a static estimate.

**Part C — redesign the Context gate (BUILD-027).**
The primary gate should READ the accumulated value from state.json, not try to call
`/context`. If the key is present and non-stale: show it, check threshold, proceed.
If absent (first story of a fresh session, or TTL expired): emit CONTEXT CHECK
REQUIRED — user provides the real count once per session via `set-context-tokens`.
Remove the `set-context-tokens` call from the gate body (it would overwrite the
accumulated value with a fresh wrong estimate).

**Part D — estimation fallback (INFRA-171).**
`estimate_next_step_tokens()`: if per-phase rows < 5, fall back to global all-phases
median. `_query_story_cost_samples()` / `story-cost-estimate`: if per-rail+story_class
rows < 5, try all rails same story_class; if still < 5, use all PASS rows. Both retain
`seeded_default` (53k) as the last resort.

## Cross-session stale handling

After a user `/clear`, state.json retains the accumulated token count. Two cases:
- **Accumulated ≥ threshold:** Context gate reads it and blocks → user must run
  `set-context-tokens --tokens N` with the real post-/clear count to unblock. This
  is the desired behaviour: the user explicitly provides the fresh count.
- **Accumulated < threshold:** Gate proceeds. The running total may drift slightly
  above the real count, causing a conservative (early) block. User runs
  `set-context-tokens --tokens N` to re-anchor. This is safe — false blocks are
  recoverable; missed blocks are the dangerous failure.

## Decisions recorded

**D1 — Don't stop clearing in story_context.py:** The clear was a deliberate design
choice (CER-041). We retain it conceptually but change its semantics: instead of
clearing on every story end, we ONLY clear when the session genuinely restarts. We
implement this by removing the pops from `clear_current_story()` and relying on the
TTL for genuine cross-session staleness detection. See INFRA-170.

**D2 — set-context-tokens vs bump-context-tokens at Context gate:** The Context gate
no longer calls `set-context-tokens` as part of its normal flow. `set-context-tokens`
becomes a manual recovery command: run it when CONTEXT CHECK REQUIRED fires (session
start or TTL expiry). `bump-context-tokens` handles the between-story advancement.

**D3 — Estimation fallback waterfall:** The fallback order for `story-cost-estimate`
is (rail+class) → (all-rails, same class) → (all PASS rows) → seeded_default. Using
all-rails for a given story_class is more appropriate than cross-class mixing since
story_class (code/doc/lesson) is a strong cost predictor.

**D4 — forqsite sync:** `forqsite/CLAUDE.build.md` is synced in BUILD-027.

**D5 — Phase index transition was never implemented.** `phase_new.py` writes `planned`
on row creation; no code path or checkpoint instruction ever writes `complete`. The
parsing infrastructure exists (`_parse_index_phases`) but the write path is missing.
Fix: `mark-phase-complete --phase N` command (INFRA-172) called in checkpoint step 7
(BUILD-028). Retroactive fix applied to forqsite (dozens of phases checkpointed but
still showing `planned`).

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-169 | `flex_build.py bump-context-tokens` — per-story context estimate advance | complete |
| INFRA-170 | `story_context.py --clear` — retain token count between stories | complete |
| INFRA-171 | Estimation fallback — cross-phase and cross-rail global median | complete |
| INFRA-172 | `flex_build.py mark-phase-complete` — write `complete` status to phase index | complete |
| BUILD-027 | `CLAUDE.build.md` — accumulated context gate + `bump-context-tokens` in Step 6 | planned |
| BUILD-028 | `CLAUDE.build.md` checkpoint step 7 — call `mark-phase-complete`; retroactive index fix | planned |
