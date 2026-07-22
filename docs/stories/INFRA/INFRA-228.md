---
id: INFRA-228
rail: INFRA
title: Match hook blocks by basename not full path — fix duplicate hook registration on plugin_root migration
status: draft
phase: "97"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/bootstrap.py
  - tests/pairmode/test_bootstrap.py
touches: []
---

## Context

Live-hit twice this session, in two different fleet projects mid-migration
to pairmode 0.3.0:

- **caddy**: the builder ran `pairmode_sync.py sync-all --apply --yes` and
  found it silently added a full second, duplicate set of hook wirings to
  `.claude/settings.json` (`PreToolUse`, `UserPromptSubmit`, `SessionStart`,
  `PostToolUse`) pointing at `/mnt/work/flex-harness/hooks/*.py`, alongside
  the pre-existing set pointing at `/mnt/work/flex/hooks/*.py`. The builder
  correctly treated this as an unauthorized protected-file change (Instructions
  §5's documented failure mode) and rolled back rather than merging it.
- **forqsite**: already migrated (`INFRA-020`), and confirmed this session to
  already carry this exact duplicate wiring live — every one of the four
  hook events fires twice per turn, once via `/mnt/work/flex`'s copy and once
  via `/mnt/work/flex-harness`'s copy. That project's own checkpoint notes
  flagged it as "transitional" rather than a bug requiring immediate fix.

Root cause, confirmed by direct code read: `bootstrap.py`'s
`_register_pretooluse_hook` (`bootstrap.py:323-381`) and
`_register_context_budget_hooks` (`bootstrap.py:409-471`) both locate the
"already registered" block by scanning for an inner hook entry whose
`command` string is an **exact match** to the freshly computed
`f"uv run python {plugin_root}/hooks/<file>.py"`. Their docstrings describe
this as "by-command find/migrate idempotency" intended to catch a legacy
matcher variant "found alike" — but that only accounts for the *matcher*
changing (e.g. `Task` → `Task|Agent|Edit|Write|Read`), not the `plugin_root`
itself changing. When a project migrates from pairmode 0.2.0 (hooks pointing
at `/mnt/work/flex`) to 0.3.0 (hooks pointing at `/mnt/work/flex-harness`,
per DP5/Option Y — see `docs/harness-cutover-runbook.md`), the computed
command string changes, the exact-match lookup fails to find the existing
entry, and a brand-new sibling block/command is appended instead of the
stale one being migrated in place — producing dual registration and every
hook firing twice per event.

This is the exact scenario DP5's migration design creates on purpose (every
`sync-all` run against a project already on a different `plugin_root` is a
migration, not a fresh install) — the idempotency logic was written for
matcher upgrades within a stable `plugin_root`, not for a `plugin_root`
change itself.

## Requires

- `bootstrap.py::_register_pretooluse_hook` and
  `bootstrap.py::_register_context_budget_hooks` in their current form
  (confirmed present and reproducing the bug this session).
- Existing tests `TestRegisterPretooluseHook` and
  `TestRegisterContextBudgetHooks` in `tests/pairmode/test_bootstrap.py`
  (confirmed present) — this story's fix must not break any of their
  existing assertions (idempotency, matcher migration, sibling-hook
  preservation).

## Ensures

- `_register_pretooluse_hook`: when `.claude/settings.json` already has a
  `PreToolUse` block whose command's **basename** is `pre_tool_use.py` but
  whose full path differs from the newly computed command (i.e. it points
  at a different `plugin_root`), that block's command is updated **in
  place** to the new computed command — no second `PreToolUse` block or
  duplicate command is created.
- `_register_context_budget_hooks`: the same in-place migration applies
  independently to each of the three specs (`UserPromptSubmit`,
  `SessionStart`, `PostToolUse` `Task|Agent`) — a stale command whose
  basename matches (`user_prompt_submit.py`, `session_start.py`,
  `post_tool_use.py` respectively) but whose full path differs is updated in
  place, not duplicated.
- The existing "never touch an unrelated sibling hook for a different
  command" guarantee is preserved — e.g. a project's own local
  `PostToolUse` pytest-runner hook (a different basename entirely) is left
  untouched by this migration logic.
- All pre-existing idempotency behavior is preserved: calling either
  function twice with the **same** `plugin_root` still results in exactly
  one block, one command, no duplication (existing
  `test_register_pretooluse_hook_idempotent` /
  `TestRegisterContextBudgetHooks`'s idempotency test must still pass
  unmodified).
- The existing matcher-migration behavior is preserved: a legacy
  `"Task"`-only `PreToolUse` block is still upgraded in place to the
  canonical `PRETOOLUSE_MATCHER` (existing
  `test_register_pretooluse_hook_migrates_stale_task_block` must still pass
  unmodified).
- Two new regression tests exist reproducing the exact live-hit shape:
  1. `_register_pretooluse_hook`: given a `.claude/settings.json` whose
     `PreToolUse` block's command points at `plugin_root_a/hooks/pre_tool_use.py`,
     calling the function with `plugin_root_b` (a different root) results in
     exactly **one** `PreToolUse` block with **one** command, now pointing at
     `plugin_root_b`'s path — not two blocks/commands.
  2. `_register_context_budget_hooks`: given a `.claude/settings.json` whose
     `UserPromptSubmit`/`SessionStart`/`PostToolUse` blocks already carry
     commands rooted at `plugin_root_a`, calling the function with
     `plugin_root_b` results in exactly one command per event, each now
     rooted at `plugin_root_b` — not two.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

1. In `skills/pairmode/scripts/bootstrap.py`, add a small shared helper (or
   inline the same logic in both functions if a shared helper doesn't fit
   cleanly given their slightly different block shapes) that, given a list
   of hook-block dicts and a hook file's basename (e.g. `"pre_tool_use.py"`),
   finds an inner hook entry whose `command` ends with that basename
   (`command.rsplit("/", 1)[-1] == basename` or equivalent — do not use a
   bare `.endswith(basename)` string check if it could false-positive on a
   different file sharing a suffix; match the full final path segment).
2. In `_register_pretooluse_hook` (`bootstrap.py:323-381`): change the
   block-finding loop so that, if no block is found whose command is an
   **exact** match (the current, already-correct fast path), fall back to
   searching for a block whose command's basename matches
   `"pre_tool_use.py"`. If found, update that inner hook entry's `command`
   value in place to the newly computed command (this is the migration
   path) and continue with the existing matcher-upgrade logic on that same
   block. Only if neither an exact match nor a basename match is found
   should a new block be appended.
3. In `_register_context_budget_hooks` (`bootstrap.py:409-471`): apply the
   same fallback (exact match → basename match → append new) independently
   per `CONTEXT_BUDGET_HOOK_SPECS` entry, being careful to only search
   within blocks/entries relevant to that event (do not let a
   `PostToolUse` `post_tool_use.py` basename match accidentally touch a
   sibling `PostToolUse` block for an unrelated command — the basename
   check itself already provides this isolation, since an unrelated hook
   has a different basename).
4. Run the full existing `TestRegisterPretooluseHook` and
   `TestRegisterContextBudgetHooks` test classes and confirm every existing
   test still passes unmodified.
5. Add the two new regression tests described in Ensures to
   `tests/pairmode/test_bootstrap.py`, following the existing classes'
   fixture conventions (`tmp_path`, `_plugin_root()`-style helpers already
   used in that file).
6. Run the full suite and confirm green.

## Out of scope

- Actually cleaning up the already-duplicated hooks in forqsite's live
  `.claude/settings.json` — that is separate, direct, per-project
  remediation (re-sync once this fix lands, or manual cleanup), not part of
  this flex-harness code fix.
- Retrying caddy's `PAIRMODE-001` story — that happens in caddy's own
  session once this fix is confirmed landed here.
- Any change to `_merge_allow_rules` or other unrelated `bootstrap.py`
  functions.
- Any change to which hooks are registered (`CONTEXT_BUDGET_HOOK_SPECS`,
  `PRETOOLUSE_MATCHER`) — this story only fixes the idempotency/migration
  logic, not the set of hooks themselves.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: full suite green, including all pre-existing
`TestRegisterPretooluseHook`/`TestRegisterContextBudgetHooks` tests
unmodified, plus the two new plugin_root-migration regression tests.
