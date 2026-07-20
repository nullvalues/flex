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
| INFRA-208 | Generalize `bootstrap.py` downstream hook registration to wire the three load-bearing context-budget-gate hooks (`UserPromptSubmit`, `SessionStart`, `PostToolUse` `Task\|Agent` block) into `.claude/settings.json` alongside the existing `PreToolUse` registration — flowing through both the `bootstrap` and `sync.py` call sites, mirroring `_register_pretooluse_hook`'s by-command find/migrate idempotency, explicitly deferring the four companion/sidebar blocks (`Stop`, `PermissionRequest`/`ExitPlanMode`, `PostToolUse` `Write\|Edit\|MultiEdit`, `SessionEnd`) as opt-in with stated reason, plus migrated/added tests | planned |
| INFRA-209 | Re-run the fleet rollout of the newly-registered context-budget-gate hooks across every already-bootstrapped sibling repo's `.claude/settings.json` (via `pairmode sync`/`sync-all` per repo, same mechanical pattern as the manual INFRA-206 rollout), verifying each fleet project now carries the `UserPromptSubmit`/`SessionStart`/`PostToolUse` `Task\|Agent` registrations | planned |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-95 Cold-eyes checklist

— developer fills in after phase completion —
