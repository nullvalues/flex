---
era: "003"
---

# flex — Phase 95: Wire context-budget-gate hooks (UserPromptSubmit, SessionStart, PostToolUse Task/Agent) into downstream bootstrap registration

← [Phase 94: Fix escaped-pipe corruption in story_update.py phase-table row matching](phase-94.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

skills/pairmode/scripts/bootstrap.py has exactly one hook-registration function, _register_pretooluse_hook, which is the only one ever called during bootstrap or sync/sync-all. Flex own canonical hooks/hooks.json registers six event types across ten blocks, but every downstream bootstrapped project only ever gets the PreToolUse block -- confirmed by inspecting the full fleet. Consequence: user_prompt_submit.py (INFRA-192) never fires downstream, so context_budget_user_turn_seq never increments and the genuine-new-turn requirement INFRA-193 built to close the CER-047 self-clearing bug can never be satisfied by a normal reply in any downstream project; session_start.py reset never fires so context_current_tokens never resets on /clear; post_tool_use.py Task/Agent branch never fires so context_current_tokens is never actually written from a live transcript read. The context-budget gate is effectively decorative in every downstream project. Live symptom: an agent in the asp repo reported the gate can never self-clear via a normal Continue building reply and applied an undocumented, self-reinvented workaround (forging context_budget_acknowledged_at and context_budget_acknowledged_user_turn_seq directly into state.json) to unstick it, noting having hit this before -- no such workaround is documented anywhere in flex, meaning this is being silently reinvented and applied routinely to defeat a broken mechanical gate (CER-067). This phase generalizes bootstrap.py hook registration so it wires the load-bearing context-budget-gate hooks (UserPromptSubmit, SessionStart, PostToolUse Task/Agent branch) into every downstream bootstrapped project, evaluates whether the remaining companion/sidebar-oriented hooks (Stop, PermissionRequest/ExitPlanMode, PostToolUse Write/Edit/MultiEdit) should also be registered or stay opt-in, and re-rolls-out the fix to the fleet once shipped.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-208 | Generalize `bootstrap.py` downstream hook registration to wire the three load-bearing context-budget-gate hooks (`UserPromptSubmit`, `SessionStart`, `PostToolUse` `Task\|Agent` block) into `.claude/settings.json` alongside the existing `PreToolUse` registration — flowing through both the `bootstrap` and `sync.py` call sites, mirroring `_register_pretooluse_hook`'s by-command find/migrate idempotency, explicitly deferring the four companion/sidebar blocks (`Stop`, `PermissionRequest`/`ExitPlanMode`, `PostToolUse` `Write\|Edit\|MultiEdit`, `SessionEnd`) as opt-in with stated reason, plus migrated/added tests | complete |
| INFRA-209 | Re-run the fleet rollout of the newly-registered context-budget-gate hooks across every already-bootstrapped sibling repo's `.claude/settings.json` (via `pairmode sync`/`sync-all` per repo, same mechanical pattern as the manual INFRA-206 rollout), verifying each fleet project now carries the `UserPromptSubmit`/`SessionStart`/`PostToolUse` `Task\|Agent` registrations | complete |
| INFRA-222 | Fix escaped-pipe corruption in next_action.py's _check_phase_completion Stories-table status parse (CER-066 recurrence) | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-95 Cold-eyes checklist

- **checkpoint-security** — PASS. No CRITICAL/HIGH findings; no `hooks/` files touched by this phase's diff; spec safety, credential exposure, path traversal, and layer-violation checks all clean (`_register_context_budget_hooks` builds hook-command paths from fixed constants, not external input).
- **checkpoint-intent** — ALIGNED. INFRA-208, INFRA-209, INFRA-222 all built exactly to their `## Ensures`; INFRA-222's mid-phase scope addition (fixing the phase's own checkpoint-guard bug) is a legitimate live-hit, same pattern as CER-066/INFRA-207. One LOW/process note: INFRA-208 was independently built on two branches (`83bdd4e`, `66fcc87`) before reconciliation by merge `9fcef91` — final `bootstrap.py` is single-definition and fully tested, no drift.
- **checkpoint-docs** — PASS (after one fix cycle). First pass FAILed on two gaps: `docs/architecture.md` had no explicit Phase 95 reference, and `CHANGELOG.md` had no Phase 95 entry. Both fixed (commit `24f0512`); recheck PASSed clean.
- **CER Do Now** — CER-067 (the finding this phase was built to close) resolved with a Phase 95 note; no other unresolved Do Now items.
- **Fleet verification (INFRA-209)** — 13 of 14 in-scope fleet projects already carried the three context-budget-gate registrations by the time of verification (read-only audit, no commits needed); `cora` formally excluded as a known carve-out; `anchor` remains excluded as a non-pairmode-consumer sibling plugin repo; `asp`'s forged CER-067 workaround keys in `state.json` are still present, reset deferred as a follow-up (out of scope for this phase).
- **CER-069 filed** — the escaped-pipe `split("|")` bug class (CER-066 → INFRA-222 recurrence) has 6 more unaudited occurrences (`next_story.py`, `index_integrity.py`, `flex_build.py` ×3, `story_resolver.py`); filed to `docs/cer/backlog.md` Do Later for a follow-up audit, not fixed in this phase.
