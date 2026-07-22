---
id: INFRA-233
rail: INFRA
title: Register context-budget-gate hooks in flex-harness's own settings.json — never dogfooded on itself
status: complete
phase: "97"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - .claude/settings.json
touches: []
---

## Context

A cold-eyes review this session found this repo's own `.claude/settings.json`
was never brought up to date with its own context-budget-gate hook rollout
(INFRA-208/209, Phase 95), which was rolled out to every *downstream* fleet
project but never applied to flex-harness itself. Confirmed by direct
inspection this session: the file currently has only two hook entries —

- `PreToolUse` → `uv run python /mnt/work/flex/hooks/pre_tool_use.py` (a
  stale entry pointing at `/mnt/work/flex`, predating this worktree's own
  DP1 existence — never repointed at `/mnt/work/flex-harness`).
- `PostToolUse` → a hand-written shell one-liner that runs
  `pytest tests/pairmode/` when a `.py` file is edited — an unrelated,
  bespoke pre-commit-style check, not the context-budget dispatcher.

There is no `UserPromptSubmit` hook and no `SessionStart` hook at all, and
no `PostToolUse` `Task|Agent` block for the context-budget dispatcher
(`hooks/post_tool_use.py`). This means the three load-bearing
context-budget-gate hooks (`user_prompt_submit.py` incrementing
`context_budget_user_turn_seq`, `session_start.py` resetting
`context_current_tokens` on `/clear`, `post_tool_use.py`'s `Task|Agent`
branch writing `context_current_tokens` from a live transcript read) have
never fired in this repo's own sessions — the mechanical gate has been
decorative here the entire time, exactly the failure mode CER-067 already
fixed for every downstream project but never applied to this repo itself.
Live symptom confirmed this session: `.companion/state.json`'s
`context_current_tokens` reads 669,030 — over 5x the ~132k gate
ceiling — with no corresponding block ever having fired.

`bootstrap.py::_register_pretooluse_hook` and
`_register_context_budget_hooks` (the same functions INFRA-228 just fixed
to migrate stale entries by basename rather than duplicating them) are the
correct, already-tested mechanism to fix this — called directly against
this repo's own `.claude/settings.json` with `plugin_root =
Path("/mnt/work/flex-harness")`. Thanks to INFRA-228, this call will
correctly migrate the stale `/mnt/work/flex`-pointing `PreToolUse` entry to
`/mnt/work/flex-harness` in place (not duplicate it), and freshly add the
three missing context-budget hooks (no migration needed there — they don't
exist yet in any form).

## Requires

- INFRA-228 complete (confirmed merged this session) — its basename-based
  migration fix is what makes registering these hooks against this
  already-partially-configured file safe (in-place migration, not
  duplication).
- `bootstrap.py::_register_pretooluse_hook` and
  `_register_context_budget_hooks` in their current (INFRA-228-fixed) form.

## Ensures

- `.claude/settings.json`'s `PreToolUse` block's command is migrated from
  `/mnt/work/flex/hooks/pre_tool_use.py` to
  `/mnt/work/flex-harness/hooks/pre_tool_use.py`, in place — exactly one
  `PreToolUse` block remains (no duplicate).
- `.claude/settings.json` gains exactly one `UserPromptSubmit` hook entry
  (`uv run python /mnt/work/flex-harness/hooks/user_prompt_submit.py`).
- `.claude/settings.json` gains exactly one `SessionStart` hook entry
  (`uv run python /mnt/work/flex-harness/hooks/session_start.py`).
- `.claude/settings.json` gains a `PostToolUse` `Task|Agent` block for
  `uv run python /mnt/work/flex-harness/hooks/post_tool_use.py`, added as a
  **sibling** of the existing hand-written pytest-on-`.py`-edit
  `PostToolUse` block — that existing block is left completely untouched
  (different command, different purpose; `_register_context_budget_hooks`
  is documented to preserve unrelated sibling blocks).
- No other content in `.claude/settings.json` (the deny list, any other
  permissions) is modified.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` passes (run
  without `-x`; report every failure, confirm only the known CER-070
  environmental one remains) — this change doesn't touch any Python source,
  so no test should be affected, but confirm nothing depends on the old
  settings.json shape.

## Instructions

1. Write and run a small one-off script (inline `python3 -c` invocation via
   Bash, or a temporary throwaway script file you delete afterward — do not
   leave a new permanent script file in the repo) that imports
   `_register_pretooluse_hook` and `_register_context_budget_hooks` from
   `skills/pairmode/scripts/bootstrap.py` and calls both against
   `Path(".claude/settings.json")` with `plugin_root =
   Path("/mnt/work/flex-harness")` (resolved absolute).
2. Inspect the resulting `.claude/settings.json` diff. Confirm: the
   `PreToolUse` command changed in place (no new block), three new hook
   entries appeared (`UserPromptSubmit`, `SessionStart`, `PostToolUse`
   `Task|Agent`), and the existing hand-written `PostToolUse` pytest-runner
   block is untouched and still present as a sibling.
3. If anything looks wrong (a duplicate block, the existing pytest-runner
   block altered or removed), stop and report rather than committing.
4. Run the full test suite without `-x` and confirm the only failure is the
   known CER-070 environmental one.
5. Commit only `.claude/settings.json`.

## Out of scope

- Any change to `bootstrap.py` or `sync.py` themselves — this story only
  *calls* their existing, already-tested registration functions once
  against this repo's own settings file.
- Registering any of the four companion/sidebar-relay hooks (`Stop`,
  `PermissionRequest`/`ExitPlanMode`, `PostToolUse`
  `Write|Edit|MultiEdit`, `SessionEnd`) — INFRA-208 deliberately deferred
  those as opt-in; this story mirrors that same scope.
- Investigating or resetting the stale `context_current_tokens: 669030`
  value in `.companion/state.json` — that's a separate follow-up once the
  hooks are actually live and can maintain it correctly going forward (a
  fresh `/clear` after this story lands will exercise `session_start.py`'s
  reset path naturally).
- Any change to the existing hand-written `PostToolUse` pytest-on-edit hook
  itself.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental
failure — run without `-x` and report every failure seen, not just the
first. Manually inspect the `.claude/settings.json` diff and confirm it
matches the Ensures exactly.
