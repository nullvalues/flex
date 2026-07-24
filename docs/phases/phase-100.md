# Phase 100 — Scope-guard fail-closed completion (CER-048 close-out)

**Intent:** Finish CER-048's shipped-but-residual fix direction so the
story-scoped permissions system is the single, genuinely fail-closed
protection surface, and settings.json is tooling-only. Began as a
single-story remediation phase, spec'd from the post-cp99 audit (2026-07-24)
at operator direction; grew to three stories via two documented mid-phase
additions (INFRA-254, INFRA-255 — see notes below).

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
| INFRA-255 | scope_guard relative-path containment — resolve and contain all file_path inputs before glob/permission checks | complete |

**Sequencing:** independent of phase 97 (fleet re-sync), but should land
before it — phase 97's sync runs will exercise downstream settings.json
writes, and CER-048's corrected row plus the architecture.md doctrine are
the reference for how the fleet's deny lists should end up.

### CP-100 Cold-eyes checklist

- **checkpoint-security** — PASS (after one fix cycle). First run FAILed HIGH:
  `scope_guard._normalise()` never resolved/contained *relative* `file_path`
  inputs, so `../../../etc/passwd`-style traversal paths bypassed all scope
  enforcement through the same fail-open branches INFRA-253 had just hardened
  for the protected-glob case (verified live by the auditor). Fixed via
  mid-phase story INFRA-255, then re-ran clean: 0 CRITICAL / 0 HIGH, prior
  repro now denied (`path escapes project root`), full suite 3324 passed /
  0 failed. One informational note filed as CER-084 (security-auditor
  procedure's post_tool_use exception list lags INFRA-254's second delegated
  write).
- **checkpoint-intent** — ALIGNED, all three stories (including both
  mid-phase additions, each with documented provenance). No pivots; ideology
  convictions ("never silently pass contradictions", "hooks are thin relays
  only") directly honored by INFRA-255's fail-closed containment and
  INFRA-254's thin delegated hook call.
- **checkpoint-docs** — PASS after a pre-tag docs commit fixing its findings:
  duplicate CER-066 ID renumbered to CER-083 with the cp99 root cause added
  (raw `git tag` never records `checkpoint-tag`, so the RESOLVER-017 reset
  never fires); INFRA-255 mid-phase note + intent paragraph updated; CP-100
  checklist filled; Phase 100 CHANGELOG entry added; module-map scope_guard
  one-liner brought current; LOW items filed as CER-085/CER-086.
- **Stale-state note:** the cold-resume warning below fired exactly as
  predicted — `next-action` resolved straight to `checkpoint-tag` after
  INFRA-254 merged; the orchestrator cleared `checkpoint_step` manually and
  ran all three gates. Root cause and durable fix direction recorded as
  CER-083.

**Mid-phase addition (2026-07-24):** INFRA-254 added pre-checkpoint after the
operator's live test (hand-edited `expected_step_tokens: 111` persisted
unchallenged) exposed that HARNESS-003's CER-053 fix severed the live
estimation path entirely rather than re-sourcing it, and after the gate's
102k→174k silent gap showed story-boundary-only re-arming misses the
post-150k drift window. Restores the INFRA-127 live-estimate intent with a
DP7-clean source (orchestrator context deltas, never effort.db).

**Mid-phase addition (2026-07-24):** INFRA-255 added mid-checkpoint after the
CP-100 security audit's first run found a HIGH relative-path traversal bypass
in `scope_guard._normalise()` (relative inputs never resolved/contained
against the project root). Filed as a phase-100 story per the
fix-before-checkpoint rule for HIGH findings; spec also folded in the
`_norm_str()` character-class `lstrip("./")` laundering bug and the
fail-closed no-active-story branch.

**Cold-resume warning for the cp100 checkpoint:** the resolver's
`checkpoint_step` state still contains phase-99's recorded gate steps
(CER-066 — state is not cleared at tag time), so `next-action` will resolve
straight to `checkpoint-tag` after the last story completes. Do NOT tag on
that basis: run all three gate workers (security, intent, docs) explicitly
for phase 100, then checkpoint-report, then tag `cp100-*`.
