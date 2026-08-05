---
era: "003"
phase_class: production
---

# flex — Phase 99: Post-fold self-sync remediation

← [Phase 98: 0.2 → 0.3 regression remediation](phase-98.md)

**Parent context:** not a fork of an in-progress phase. This phase is a sibling
opened from a post-fold review of the live repo at `/mnt/work/flex` (session of
2026-07-24), triggered by the SessionStart banner announcing "Pairmode v0.2.0"
twice in a repo whose scaffold is v0.3.0. Phase-97 (fold resume — fleet
migration, re-sync) continues unpaused and retains all fleet-facing scope; this
phase is strictly **flex's own** post-fold hygiene — the repo never applied to
itself the sync it ships to the fleet.

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

The RELEASE-059 fold merged fold-prep into main as pairmode v0.3.0, but four
pieces of flex's own tooling still reflect the pre-fold world:

1. **Hooks are registered twice.** The plugin manifest (`hooks/hooks.json`,
   via `${CLAUDE_PLUGIN_ROOT}`) and the project `.claude/settings.json` both
   register SessionStart / UserPromptSubmit / PreToolUse / PostToolUse. Both
   fire every session — the duplicated v0.2.0 banner is the visible symptom.
2. **The settings.json registrations point at the wrong checkout.** All four
   commands reference absolute paths under `/mnt/work/flex-harness` — the old
   fold-prep working copy, currently byte-identical but on a branch that will
   drift or disappear. flex's gates must not depend on a sibling checkout.
3. **A duplicated UserPromptSubmit hook may double-increment the context
   counter** in `.companion/state.json`, making the context-budget gate trip
   early. Needs verification and, if confirmed, state repair.
4. **flex never self-synced.** `.companion/state.json` still records
   `pairmode_version: "0.2.0"`, and it carried a stale `current_story` /
   `story_scope.json` pinned to INFRA-209 (complete since phase-95) — stale
   enough that it blocked writing this very spec until manually cleared
   during spec-writing (the version key remains to fix). Separately,
   `pairmode_migrate.py` defaults `new_pairmode_version` to a hardcoded
   `"0.2.0"` instead of importing `PAIRMODE_VERSION` from `_version.py`, and
   `SKILL.md`'s migration table still documents 0.2.0 as the target.

**Scope boundary:** fleet projects (Repo-A, Repo-B, Repo-C, Repo-D,
and the wider phase-97 migration list) are explicitly out of scope here.
Phase-95/INFRA-209 already verified fleet hook registrations; fleet 0.3.0
re-sync belongs to phase-97 when it resumes. This phase must leave flex itself
correct so that phase-97's fleet rollout propagates a clean pattern.

**Recommended build order:** INFRA-247 → INFRA-248 → INFRA-251 → INFRA-249;
INFRA-250 is independent and may build at any point. INFRA-248 depends on
INFRA-247 because the double-increment audit must run against the
*deduplicated* hook registration to distinguish historical corruption from
ongoing corruption; INFRA-251 reconciles with INFRA-248's findings on the
shared turn-seq/counter keys.

**Mid-phase addition (2026-07-24):** INFRA-251 was added during the build when
the context-budget gate hard-blocked the phase's own builder spawns and the
operator confirmed the behavior is a weeks-old, fleet-wide era-2 regression
(stuck `expected_step_tokens`, acknowledgment that never clears, frozen
counter). A live-hit addition in the INFRA-222 / CER-066 mold: the phase's
purpose is post-fold self-correctness, and the gate defect is both in-theme
and this phase's direct blocker.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-247 | Single canonical hook registration for flex itself — dedupe plugin manifest vs settings.json, eliminate cross-checkout `/mnt/work/flex-harness` absolute paths | complete |
| INFRA-248 | Audit and correct context-counter double-increment caused by duplicated UserPromptSubmit hooks | complete |
| INFRA-249 | Self-sync flex's `.companion/state.json` — pairmode_version to 0.3.0, verify banner correctness | complete |
| INFRA-250 | Route `pairmode_migrate.py`'s version default through `_version.PAIRMODE_VERSION`; fix SKILL.md migration-target doc drift | complete |
| INFRA-251 | Context-budget gate remediation — acknowledgment that actually clears, live counter writes, non-fossil step estimate | complete |
| INFRA-252 | Authorize user_prompt_submit.py as fourth thin-delegation exception in security-auditor procedure | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-99 Cold-eyes checklist

- **checkpoint-security** — PASS (after one fix cycle). First run FAILed HIGH:
  INFRA-248's conversion of `hooks/user_prompt_submit.py` into a fourth thin
  dispatcher was documented in `docs/architecture.md` but absent from the
  security-auditor procedure's check-1/check-6 exception list — an
  authorization-doc gap, not a code hazard (the auditor itself recommended a
  procedure update, not a rollback). Fixed via mid-phase story INFRA-252
  (procedure-text-only), then re-ran clean: 0 CRITICAL / 0 HIGH, full suite
  3264 passed / 0 failed.
- **checkpoint-intent** — ALIGNED, all six stories. Operator/orchestrator-applied
  writes (INFRA-247 `.claude/settings.json`, INFRA-249 `.companion/state.json`)
  both anticipated by the stories' own Ensures fallbacks and documented in build
  notes. Two advisory findings surfaced to operator, not auto-filed: (1) two
  classifier-forced bypasses in one phase reinforce CER-048's fix direction;
  (2) `docs/ideology.md`'s "no override permitted" state-write constraints are
  unreconciled with the four architecture.md-documented hook exceptions (MEDIUM).
- **checkpoint-docs** — PASS with one HIGH that was mid-checkpoint state, not a
  gap: `docs/phases/index.md` still showed phase 99 `planned`; resolved by the
  tagging step itself. All architecture.md sections (state.json key inventory,
  context-budget contract, canonical-surface decision record) verified current.
- **Resolver-heuristic hazard confirmed live** — exactly as INFRA-247's build
  notes warned, the cold-resume resolver read commit `9521b74` as INFRA-247
  built and skipped to INFRA-248; the remainder had to be dispatched explicitly.
  The hazard note in the story doc is what caught it — worth keeping that
  pattern for any future operator-applied partial.
- **Scope-declaration gaps forced two mid-build spec amendments** — INFRA-248
  (new module + architecture.md not in `touches`; builder hard-blocked by
  scope_guard, worktree recreated) and INFRA-251 (architecture.md missing;
  permissions regenerated in place, builder resumed without losing its diff).
  Spec-writers should declare `docs/architecture.md` whenever a story alters a
  documented contract, and declare new-module paths explicitly.
- **Review quality** — INFRA-248 took three cycles (docs currency → thin-hook
  CRITICAL → PASS); the reviewer chain caught a genuine architecture violation
  (inline hook logic) that the builder's first restructure missed. All reviewer
  commit/revert claims were verified against `git log`/`git status` before
  being trusted (per the CP-96 reliability note; no discrepancies this phase).
- **Gate self-test** — the context-budget gate fixed in INFRA-251 fired live at
  this phase's own checkpoint boundary and its ack-clear worked as rebuilt: the
  operator's next genuine user turn cleared the block, first spawn after ack
  went through. Dogfood confirmation of the fix under real conditions.

**Mid-phase addition (2026-07-24, checkpoint remediation):** INFRA-252 was added
when the checkpoint security audit flagged (HIGH) that the security-auditor
procedure's thin-delegation exception list was not updated for INFRA-248's
conversion of `hooks/user_prompt_submit.py` into a fourth dispatcher hook —
an authorization-doc gap, not a code hazard; fix is procedure-text-only.
