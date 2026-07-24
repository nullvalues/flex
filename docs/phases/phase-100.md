# Phase 100 — Scope-guard fail-closed completion (CER-048 close-out)

**Intent:** Finish CER-048's shipped-but-residual fix direction so the
story-scoped permissions system is the single, genuinely fail-closed
protection surface, and settings.json is tooling-only. Single-story
remediation phase, spec'd from the post-cp99 audit (2026-07-24) at operator
direction.

**Origin:** cp99 intent review flagged CER-048's forcing function (two
operator-applied bypasses in phase 99); operator audit then found the
scope_guard fail-open hole, the four redundant settings.json denies, and the
stale CER row. Operator confirmed the intended end-state: per-story
authorization via spec `touches` → permissions artifact → scope_guard only;
normal build cycles touch neither `.claude/settings.json` nor
`.claude/settings.local.json`, avoiding the harness-level auto-mode
classifier entirely.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-253 | Close scope_guard fail-open hole for protected paths; retire redundant settings.json denies; resolve CER-048 | complete |
| INFRA-254 | Restore live expected_step_tokens from observed orchestrator growth; growth-based gate re-arm past threshold | complete |

**Sequencing:** independent of phase 97 (fleet re-sync), but should land
before it — phase 97's sync runs will exercise downstream settings.json
writes, and CER-048's corrected row plus the architecture.md doctrine are
the reference for how the fleet's deny lists should end up.

### CP-100 Cold-eyes checklist

— filled by the checkpoint orchestrator at phase completion —

**Mid-phase addition (2026-07-24):** INFRA-254 added pre-checkpoint after the
operator's live test (hand-edited `expected_step_tokens: 111` persisted
unchallenged) exposed that HARNESS-003's CER-053 fix severed the live
estimation path entirely rather than re-sourcing it, and after the gate's
102k→174k silent gap showed story-boundary-only re-arming misses the
post-150k drift window. Restores the INFRA-127 live-estimate intent with a
DP7-clean source (orchestrator context deltas, never effort.db).

**Cold-resume warning for the cp100 checkpoint:** the resolver's
`checkpoint_step` state still contains phase-99's recorded gate steps
(CER-066 — state is not cleared at tag time), so `next-action` will resolve
straight to `checkpoint-tag` after the last story completes. Do NOT tag on
that basis: run all three gate workers (security, intent, docs) explicitly
for phase 100, then checkpoint-report, then tag `cp100-*`.
