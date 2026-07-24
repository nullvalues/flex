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
  - skills/pairmode/scripts/user_turn_seq.py
  - tests/pairmode/test_user_prompt_submit_hook.py
  - tests/pairmode/test_user_turn_seq.py
  - docs/architecture.md
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

## Build notes

**Ensures (1) — audit determination.**

Confirmed: prior to INFRA-247's dedupe of the duplicate `UserPromptSubmit`
registration (`hooks/hooks.json` plugin manifest + `.claude/settings.json`'s
separate registration), every user prompt fired
`hooks/user_prompt_submit.py` twice per turn. The pre-INFRA-248 hook body
(`hooks/user_prompt_submit.py`, prior revision) performed an unconditional
read-modify-write on every invocation:

```
current = state.get("context_budget_user_turn_seq", 0)
state["context_budget_user_turn_seq"] = current + 1
state_path.write_text(json.dumps(state, indent=2))
```

with no invocation-identity check of any kind, so two firings of the hook
for the same `UserPromptSubmit` event advanced
`context_budget_user_turn_seq` by 2 instead of 1. This is a confirmed
double-increment of exactly one key, `context_budget_user_turn_seq` — no
other `state.json` counter is touched by this hook
(`context_current_tokens` is written only by `hooks/post_tool_use.py`'s
Task/Agent branch via `context_budget.read_current_tokens()`, and
`expected_step_tokens` is not derived from `user_turn_seq` anywhere in
`context_budget.py`).

**Functional-effect analysis.** `context_budget_user_turn_seq` has exactly
one consumer: `context_budget.should_block()`
(`skills/pairmode/scripts/context_budget.py:360-413`), which reads it as
the `user_turn_seq` parameter and compares it against
`acknowledged_user_turn_seq` — sourced from
`state["context_budget_acknowledged_user_turn_seq"]`, which
`hooks/pre_tool_use.py` writes as a *copy of the current
`context_budget_user_turn_seq` value* at block time
(`context_budget.py:616-620`; write site
`hooks/pre_tool_use.py`'s `Task`/`Agent` branch,
`context_budget_acknowledged_user_turn_seq` write). The only two branches
that consult these values (`context_budget.py:404-413`) are:

- `user_turn_seq <= acknowledged_user_turn_seq` → block (no turn since ack)
- `user_turn_seq > acknowledged_user_turn_seq` → fall through to the token
  check

Both comparisons are strictly ordinal (`<=` / `>`); neither branch reads the
*difference* or *magnitude* of either value. Because both
`context_budget_user_turn_seq` (the running counter) and
`context_budget_acknowledged_user_turn_seq` (a snapshot copy of that same
counter, taken while it was under the same doubled-increment regime) were
inflated by the identical uniform 2x scale factor for the entire period both
registrations were active, the ordinal relationship between them — "has at
least one genuine `UserPromptSubmit` fired since the last block" — is
preserved exactly under the doubling. **Determination: the duplicated
registration is confirmed to have double-incremented
`context_budget_user_turn_seq`, but this had no functional effect on any
`context_budget.should_block()` gate decision, past or present**, because
the comparison is ordinal-only and both sides of it scaled together.

**Ensures (2) — state.json correction.** No `state.json` value correction is
applied. `context_current_tokens` was never touched by this hook (ruled out
above) and needs no correction. `context_budget_user_turn_seq` and
`context_budget_acknowledged_user_turn_seq` are both inflated in absolute
terms relative to a world where the duplicate registration never existed,
but per the functional-effect analysis above their *relative* relationship —
the only thing any code path reads — was never distorted, so there is no
defensible "corrected" value to write: any downward rescaling would have to
guess how much of the historical count came from genuine turns vs.
duplicate firings, with no signal in `state.json` to reconstruct that split.
`.companion/state.json` is also gitignored, ephemeral, per-checkout runtime
state (not a committed artifact), and a routine SessionStart `/clear` /
`startup` reset already establishes a fresh, uninflated baseline for the
counter going forward (each session simply resumes incrementing from
whatever value was present — the counter's absolute value has never been
compared against a fixed threshold, only against its own prior value). No
code change or manual edit corrects `context_budget_user_turn_seq` for this
reason.

**Ensures (3) — idempotency guard implemented.** `context_budget_user_turn_seq`
is confirmed double-incremented (Ensures 1), so per Ensures (3) an
idempotency guard was added: `skills/pairmode/scripts/user_turn_seq.py`
(`record_user_turn()`) fingerprints each `UserPromptSubmit` payload
(sha256 of `session_id` + `prompt`) and skips the increment when the
fingerprint matches `state["context_budget_user_turn_seq_fingerprint"]`
from the immediately-preceding invocation. `hooks/user_prompt_submit.py`
now does zero state.json I/O itself and delegates the entire
read-modify-write to this module (thin-hook contract). Covered by
`tests/pairmode/test_user_turn_seq.py` (module-level) and
`tests/pairmode/test_user_prompt_submit_hook.py`
(`test_user_prompt_submit_duplicate_invocation_increments_once`,
subprocess-level, exercising the actual duplicate-registration scenario).
