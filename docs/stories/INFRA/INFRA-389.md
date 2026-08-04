---
id: INFRA-389
rail: INFRA
title: Fix bootstrap.py plugin-sourced-skip branches bypassing A7 stale-hook eviction (CER-169)
status: draft
phase: "121"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/bootstrap.py
touches:
  - tests/pairmode/test_bootstrap.py
  - tests/pairmode/test_pairmode_migrate.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

CER-169: `bootstrap.py`'s two hook registrars — `_register_pretooluse_hook` and
`_register_context_budget_hooks` — both return/skip on the plugin-sourced check
(INFRA-288/CER-104: an installed plugin's `hooks.json` already provides the
event) before ever reaching their own A7 stale-committed-entry eviction call
(`_evict_stale_committed_hook_entries`). `_register_pretooluse_hook` returns
`False` at its `if (..., plugin_registered): return False` check, dozens of
lines before its A7 call. `_register_context_budget_hooks` `continue`s past
the rest of its per-event loop body on the same check, so a skipped `(event,
basename)` pair is never appended to `registered_this_run` — and its A7
eviction loop only iterates `registered_this_run`. `pairmode_migrate.py`'s
`to-030 --hooks-only` (INFRA-386, what `sync-all`'s fifth step invokes) calls
exactly these two registrars as its only repair path for a detected stale
entry; it correctly detects the offending entry and echoes `[apply]
relocating ...`, but the eviction the message implies never happens. This
makes INFRA-387's "final re-scan clean for all 13 target repos" requirement
structurally unreachable on any repo where the plugin already provides these
hook events (the standard shape post-INFRA-383/384, confirmed to be every
scanned fleet repo). This story fixes both registrars so A7 eviction runs on
the plugin-sourced-skip path too, and adds the regression coverage that would
have caught the gap.

## Requires

- INFRA-386 complete (`to-030 --hooks-only` exists and is `sync-all`'s fifth
  step) — already true (phase-121 Stories table).
- `docs/cer/backlog.md`'s CER-169 row (root cause, evidence) exists — already
  true (filed alongside this spec).

## Ensures

1. `_register_pretooluse_hook`, when the plugin-sourced skip fires (an
   installed plugin's `hooks.json` already provides `PreToolUse` for
   `pre_tool_use.py`), still calls `_evict_stale_committed_hook_entries` for
   that `(event, basename)` pair before returning — a stale/duplicate/
   machine-absolute `PreToolUse`/`pre_tool_use.py` entry present in the
   project's committed `.claude/settings.json` is removed even though no new
   `settings.local.json` entry is written. Forbidden proxy: the function
   still returns `False`/echoes the "skipping ... registration" line while
   the stale committed entry is left in place.
2. `_register_context_budget_hooks`, for each `CONTEXT_BUDGET_HOOK_SPECS`
   entry that hits the plugin-sourced skip, still calls
   `_evict_stale_committed_hook_entries` for that spec's `(event, basename)`
   pair — eviction is no longer gated on membership in `registered_this_run`
   (which by construction excludes every skipped spec). A spec that was
   never offending (no stale committed entry to begin with) still produces
   zero writes — `_evict_stale_committed_hook_entries`'s existing "only
   rewrite when something was actually removed" behavior is unchanged.
3. Both registrars' non-plugin-sourced paths are byte-identical to today —
   this story only adds a call on the previously-unreached skip branch(es),
   it does not alter the already-passing eviction-after-write logic.
4. A new regression test in `tests/pairmode/test_bootstrap.py` reproduces the
   CER-169 gap directly: a project fixture with a plugin-sourced
   `PreToolUse` entry (per the existing
   `test_pretooluse_registration_skipped_when_plugin_provides_it` fixture
   shape) *and* a stale/machine-absolute `pre_tool_use.py` entry already
   present in the committed `.claude/settings.json` — after calling
   `_register_pretooluse_hook`, the stale entry is gone from the committed
   file. An equivalent test covers `_register_context_budget_hooks` for at
   least one `CONTEXT_BUDGET_HOOK_SPECS` entry (e.g. `SessionStart`).
5. A new regression test in `tests/pairmode/test_pairmode_migrate.py`
   exercises the full `to-030 --hooks-only --apply` path against a fixture
   carrying both a plugin-sourced `hooks.json` and a stale committed
   `.claude/settings.json` hook entry — after the run, the committed file no
   longer contains the stale entry (the exact end-to-end shape INFRA-387
   needs to be achievable).
6. `uv run pytest tests/pairmode/ -q` passes, including the full existing
   `test_bootstrap.py`/`test_pairmode_migrate.py` suites (no regression on
   the already-passing plugin-sourced-skip "no new local entry" assertions).

## Instructions

1. In `skills/pairmode/scripts/bootstrap.py::_register_pretooluse_hook`: on
   the `plugin_registered` skip branch (the `if (..., plugin_registered):
   ... return False` block), before returning, call
   `_evict_stale_committed_hook_entries(settings_path, "PreToolUse",
   pre_tool_use_path.name)` — mirroring the call already made on the normal
   (non-skip) path further down the function. Update the function's
   docstring to state that A7 eviction now also runs on the plugin-sourced
   skip path (the plugin's own registration is by definition the correct
   entry, so evicting a stale committed-settings.json duplicate is
   unconditionally safe once the plugin-sourced pair is confirmed).
2. In `skills/pairmode/scripts/bootstrap.py::_register_context_budget_hooks`:
   on the per-spec `if (spec["event"], hook_path.name) in plugin_registered:`
   branch (currently just echoes and `continue`s), add a call to
   `_evict_stale_committed_hook_entries(settings_path, spec["event"],
   hook_path.name)` before the `continue`. Do not add the skipped pair to
   `registered_this_run` — that list's existing meaning ("registered
   locally this run") stays correct for its other use (the `any_change`
   restart-surface signal, INFRA-323 § A/B); eviction on the skip path is a
   separate, unconditional action, not something that should make
   `any_change` return `True` for a pair whose local registration state
   never changed. Update the function's docstring accordingly.
3. Do not change `pairmode_migrate.py` — the fix at the registrar layer is
   sufficient; `to-030 --hooks-only`'s existing calls to
   `_register_pretooluse_hook`/`_register_context_budget_hooks` need no
   changes to pick up the new eviction behavior.
4. Add the two `test_bootstrap.py` regression tests from Ensures 4, adjacent
   to the existing `test_pretooluse_registration_skipped_when_plugin_provides_it`
   and `test_plugin_registered_posttooluse_is_skipped_twice`-style tests —
   reuse the existing `_isolated_home` fixture pattern (never touch the real
   `~/.claude/plugins/` tree, per CER-168/INFRA-385).
5. Add the `test_pairmode_migrate.py` regression test from Ensures 5,
   modeled on the existing `--hooks-only` fixtures in that file (e.g. near
   `test_to030_relocates_stale_hook_command_when_plugin_root_named_flex_harness`),
   combining a plugin-sourced `hooks.json` fixture with a stale committed
   entry fixture in one project directory.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_bootstrap.py tests/pairmode/test_pairmode_migrate.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: both commands green, including the new tests named in Ensures 4-5.

## Out of scope

- Re-running `sync-all --apply --yes` against the fleet (INFRA-387's own
  job, to be retried after this story lands).
- `SubagentStop`/`PostToolUse` classification changes or any other hook-view
  logic beyond the two named eviction call sites — this story only closes
  the A7-unreachable gap on the existing plugin-sourced-skip branches.
- Widening `_flex_hook_basenames`/`_repairable_basenames` in
  `pairmode_migrate.py` (session_end.py's deliberately-unrepairable WARN
  path, per that file's own comment) — untouched by this story.
