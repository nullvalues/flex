---
id: INFRA-374
rail: INFRA
title: Wire the missing context_current_tokens_source writer in post_tool_use.py (CER-135)
status: draft
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - hooks/post_tool_use.py
touches:
  - tests/pairmode/test_post_tool_use.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-135 (LOW): `context_current_tokens_source` (introduced by INFRA-321 § C6) has only two of its
three intended writers stamped — `user_turn_seq.record_user_turn()` (stamps
`"user-prompt-submit"`) and `flex_build.py`'s `set-context-tokens`/`bump-context-tokens` (stamps
`"manual"`). The third and highest-frequency writer, `hooks/post_tool_use.py`'s Task/Agent branch —
the write path that runs after every builder/reviewer/auditor spawn — does not stamp
`"post-tool-use"`, because `hooks/**` is a protected path and INFRA-321 explicitly named this edit
as the one exception requiring a hook change, instructing the builder to report `BUILDER BLOCKED`
rather than touch it directly (which is what happened). Consequence is observability-only: a
`context_current_tokens` value most recently written by PostToolUse currently carries no source
stamp, and `context_budget.decide()` doesn't gate on this field either way, so there's no
functional gap. Fix direction: a small hook-scoped story adding the one-line stamp
(`state["context_current_tokens_source"] = "post-tool-use"`) inside `post_tool_use.py`'s existing
Task/Agent read-modify-write, mirroring the write already added to `user_turn_seq.record_user_turn`,
plus a regression test asserting the stamp appears after a Task/Agent PostToolUse observation.
File: `hooks/post_tool_use.py`.

Picked up now as part of era 004's Phase 119 goal of draining the CER backlog to zero unresolved
operational findings.

## Requires

- INFRA-321 complete: `context_model.CONTEXT_CURRENT_TOKENS_SOURCE_KEY` and
  `CONTEXT_CURRENT_TOKENS_SOURCES` exist, and the two live writers
  (`user_turn_seq.record_user_turn`, `flex_build.py set-context-tokens`/`bump-context-tokens`)
  already stamp their values. Both hold today.
- **Frontmatter gap — blocking, operator must resolve before build.** This stub has no
  `primary_files:` and an empty `touches:`. `hooks/**` is in `scope_guard.PROTECTED_GLOBS`
  and fails closed: the *only* authorization path for a protected file is that exact
  repo-relative path appearing in the story's `primary_files`/`touches` (see
  `scope_guard.check_path`). Without the edit below, the builder will be denied on
  `hooks/post_tool_use.py` exactly as INFRA-321's builder was. Required frontmatter:

  ```yaml
  primary_files:
    - hooks/post_tool_use.py
  touches:
    - skills/pairmode/scripts/context_model.py
    - skills/pairmode/scripts/user_turn_seq.py
    - tests/pairmode/test_post_tool_use.py
    - tests/pairmode/test_context_model.py
  ```

  `docs/architecture.md` and `docs/cer/backlog.md` are standing shared surfaces
  (`scope_guard.STANDING_SURFACES`) and must **not** be added to `touches`.
  `spec-preflight` therefore reports `scope:` findings for `hooks/post_tool_use.py` and the
  test files above — expected, and resolved by applying the block above (the spec-writer may
  not edit `primary_files`/`touches` itself). `tests/pairmode/test_flex_build.py` is cited
  read-only (an existing test that must still pass) and needs no scope entry.

## Ensures

- `hooks/post_tool_use.py`'s Task/Agent branch stamps `state["context_current_tokens_source"] = "post-tool-use"`
  inside the existing `_mutate` read-modify-write, within the `if live_tokens is not None:`
  branch only. A Task/Agent event whose token measurement is unavailable
  (`live_tokens is None`) leaves the key untouched. Forbidden proxy: stamping
  unconditionally, so the field claims a measurement write that never happened.
- The stamped literal equals `context_model.CONTEXT_CURRENT_TOKENS_SOURCES[0]` — a test
  asserts this against the constant, not against a second hardcoded string.
- The Task/Agent branch still makes exactly one `state_utils.update_state_json` call per
  invocation and still exits 0 with empty stdout; the existing `TestHookStaysThin` tests in
  `tests/pairmode/test_post_tool_use.py` pass **unmodified**. Forbidden proxy: adding
  `import context_model` (or any new delegated call) to the hook to reference the constant.
- `context_model.py`'s comment block above `CONTEXT_CURRENT_TOKENS_SOURCES` no longer states
  that `"post-tool-use"` has no live writer / is deferred to a follow-up story; the tuple's
  value is unchanged.
- `grep -rn "only_two_are_live" tests/ skills/` returns no matches — `tests/pairmode/test_context_model.py`'s
  `test_context_current_tokens_sources_names_all_three_but_only_two_are_live` is renamed to
  state that all three named writers are live.
- `user_turn_seq.record_user_turn`'s docstring § C6 no longer claims `"post-tool-use"` has no
  live writer. No executable line of `user_turn_seq.py` changes.
- `docs/architecture.md`'s **Writer provenance (`context_current_tokens_source`)** paragraph
  lists all three writers as live and no longer contains "NOT yet wired" or the
  `BUILDER BLOCKED`/deferred-follow-up language for this field.
- `docs/cer/backlog.md`'s CER-135 row carries a resolution annotation naming INFRA-374.
- A new end-to-end regression test in `tests/pairmode/test_post_tool_use.py` runs the hook as a
  subprocess with a Task event and a readable transcript, and asserts the resulting
  `.companion/state.json` has `context_current_tokens_source == "post-tool-use"`.
- `context_budget.decide()` is untouched; `test_decide_ignores_context_current_tokens_source`
  in `tests/pairmode/test_flex_build.py` still passes.

## Instructions

1. In `hooks/post_tool_use.py`, inside the Task/Agent branch's `_mutate(state)` closure, add
   one line in the `if live_tokens is not None:` block writing
   `state["context_current_tokens_source"] = "post-tool-use"`, with a short comment naming
   `context_model.CONTEXT_CURRENT_TOKENS_SOURCE_KEY` / `CONTEXT_CURRENT_TOKENS_SOURCES` as the
   canonical definitions. Write the key and value as literals — do not import `context_model`
   into the hook. Write to `state` (top level), mirroring `user_turn_seq.record_user_turn`'s
   § C6 stamp, not to the per-session `view`.
2. Ideology note (Step 4a, resolved inline): the "Hooks are thin relays only" / "Sidebar owns
   all state writes" constraints are preserved in rationale, not just letter — this adds **no**
   new state write, module import, delegated call, or blocking logic; it adds one field to the
   single pre-existing `update_state_json` call (INFRA-182/236). Any implementation that adds a
   second write or a new import violates the constraint the rule protects.
3. Update the stale claims left behind by INFRA-321's deferral: the `context_model.py` comment
   block, `user_turn_seq.record_user_turn`'s § C6 docstring paragraph, and
   `docs/architecture.md`'s Writer-provenance paragraph. Keep the field's semantics as stated:
   additive, observability-only, never gated on.
4. Annotate the CER-135 row in `docs/cer/backlog.md` as resolved by INFRA-374 (append to the
   row; do not delete the original finding text).
5. Tests: rename the `only_two_are_live` test in `tests/pairmode/test_context_model.py` and keep
   its tuple assertion. Add to `tests/pairmode/test_post_tool_use.py` (a) the end-to-end stamp
   assertion, (b) an assertion that the hook's stamped literal equals
   `context_model.CONTEXT_CURRENT_TOKENS_SOURCES[0]`, and (c) an assertion that a Task event
   with an unreadable/absent transcript (no measurable tokens) does not write the key.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_post_tool_use.py \
  tests/pairmode/test_post_tool_use_hook.py tests/pairmode/test_context_model.py \
  tests/pairmode/test_user_turn_seq.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: both runs green (no `-x`, so a pre-existing failure cannot mask a new one), with
the three new/renamed assertions in item 5 present and passing.

## Out of scope

- Any gating, alerting, or resolver behaviour keyed on `context_current_tokens_source` —
  `context_budget.decide()` stays indifferent to the field.
- Stamping provenance into the per-session `context_sessions` view (a session-scoped
  provenance field is a separate design change).
- Any other hook under `hooks/` — in particular `hooks/user_prompt_submit.py`.
- Adding a fourth source value, or building any observability/UI surface that renders the field.
- Changing `scope_guard.PROTECTED_GLOBS` or relaxing protected-path enforcement for `hooks/**`.
