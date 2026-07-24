---
id: INFRA-248
rail: INFRA
title: Audit and correct context-counter double-increment caused by duplicated UserPromptSubmit hooks
status: planned
phase: "99"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - .companion/state.json
touches:
  - hooks/user_prompt_submit.py
  - tests/pairmode/test_user_prompt_submit_hook.py
---

## Context

Until INFRA-247 lands, every user prompt in this repo runs
`user_prompt_submit.py` twice — once via the plugin manifest
(`hooks/hooks.json`) and once via `.claude/settings.json`'s duplicate
registration. If that hook increments `context_current_tokens` (or any
per-prompt accounting) in `.companion/state.json`, the counter has been
advancing at roughly double the real rate for as long as both registrations
have been active, which makes the context-budget gate
(`context_budget.decide()`, threshold 120000 in current state) trip early and
distorts `expected_step_tokens` calibration.

This is an audit-first story: the double-fire is proven (the SessionStart
banner duplicates), but whether UserPromptSubmit's write path actually
double-counts — or is idempotent per prompt (e.g. guarded by a turn sequence
number like `context_budget_user_turn_seq`) — is not yet established. The
current `state.json` shows `context_budget_user_turn_seq: 143` against
`context_budget_acknowledged_user_turn_seq: 82`; whether that gap is organic
or inflation is part of the audit.

## Requires

- INFRA-247 complete (hook registration deduplicated), so the audit can
  distinguish historical corruption from ongoing corruption and any repair
  is not immediately re-corrupted.

## Ensures

1. A written determination (in this story file's `## Build notes` section on
   completion, or the phase doc's cold-eyes checklist) of whether the
   duplicated UserPromptSubmit registration double-incremented any
   `state.json` counter — with the specific code path cited
   (`hooks/user_prompt_submit.py` line refs), not asserted from behavior
   alone.
2. If double-increment is confirmed: the affected `state.json` keys
   (`context_current_tokens`, `context_budget_user_turn_seq`,
   `expected_step_tokens` if derived) are reset or corrected to defensible
   values, with the correction method recorded. A fresh-session reset (the
   SessionStart counter reset to 25000 already observed) is an acceptable
   correction for `context_current_tokens` if the audit shows staleness
   cannot outlive a session.
3. If double-increment is confirmed: `user_prompt_submit.py` gains an
   idempotency guard (e.g. skip if the current turn sequence was already
   recorded) so a future duplicate registration degrades to noise instead of
   corruption, with a pytest covering double-invocation on the same prompt
   producing a single increment.
4. If the audit shows the write path was already idempotent: no code change;
   the determination in (1) says so explicitly and this story completes as
   audit-only, with the idempotency mechanism named.
5. Existing pairmode tests pass.
