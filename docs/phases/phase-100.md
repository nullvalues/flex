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
| INFRA-253 | Close scope_guard fail-open hole for protected paths; retire redundant settings.json denies; resolve CER-048 | planned |

**Sequencing:** independent of phase 97 (fleet re-sync), but should land
before it — phase 97's sync runs will exercise downstream settings.json
writes, and CER-048's corrected row plus the architecture.md doctrine are
the reference for how the fleet's deny lists should end up.

### CP-100 Cold-eyes checklist

— filled by the checkpoint orchestrator at phase completion —
