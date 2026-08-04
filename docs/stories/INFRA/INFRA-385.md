---
id: INFRA-385
rail: INFRA
title: Isolate test_pairmode_migrate.py/test_sync.py PreToolUse-registration tests from real ~/.claude/plugins/ state
status: complete
phase: "120"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - tests/pairmode/test_pairmode_migrate.py
  - tests/pairmode/test_sync.py
  - skills/pairmode/scripts/hook_view.py
  - skills/pairmode/scripts/bootstrap.py
touches:
  - tests/pairmode/test_hook_view.py
  - tests/pairmode/test_bootstrap.py
  - docs/cer/backlog.md
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

`hook_view.py`'s `plugin_hook_files` defaults `home=None → Path.home()` and scans the
real `~/.claude/plugins/` tree; `bootstrap.py`'s `_plugin_registered_hook_pairs` calls it
without any test-fixture isolation. Three PreToolUse-registration tests were written when
no dev machine had a real flex plugin install, so they asserted the no-plugin-installed
behaviour while silently reading host state. INFRA-383 (same phase) made a marketplace
install of flex the required dogfooding setup, so `~/.claude/plugins/cache/nullvalues-flex/
flex/0.3.1/hooks/hooks.json` now exists on this machine, the INFRA-288/CER-104/CER-127
dedup guard correctly skips settings-level registration, and the three tests go red. The
dedup logic is right; the test isolation is the defect.

## Requires

- INFRA-383 complete (the marketplace install that surfaced the failures).
- The three named tests fail on a machine with a real flex plugin installed.

## Ensures

The three PreToolUse-registration tests
(`test_pairmode_migrate.py::test_to030_relocates_stale_hook_command`,
`test_pairmode_migrate.py::test_to030_relocates_stale_hook_command_when_plugin_root_named_flex_harness`,
`test_sync.py::TestSyncRegistersPreToolUseHook::test_sync_registers_pretooluse_hook`)
resolve their plugin tree from a fixture-scoped home rather than the real `Path.home()`,
and the full `tests/pairmode/` suite is green both with and without a real flex plugin
installed under `~/.claude/plugins/`. Forbidden proxy: assertions edited to match this
host's current dedup-skip behaviour while the test still reads the real `Path.home()`.

## Instructions

1. Read the current signatures of `plugin_hook_files` (`hook_view.py`) and
   `_plugin_registered_hook_pairs` (`bootstrap.py`, ~lines 551 and 641) before choosing
   an approach. If an explicit `home=` parameter is not already threaded from the
   registrar call sites down to `plugin_hook_files`, add one (defaulting to the existing
   `Path.home()` behaviour so production callers are unchanged).
2. Isolate the three tests against a `tmp_path`-based fake home — either by passing the
   isolated `home=` through, or by monkeypatching `Path.home()` for the test — so they
   exercise the empty-plugin-tree path deterministically regardless of host state. Keep
   the original assertions' intent; do not flip them to match today's host.
3. Add a test that exercises the opposite case explicitly: a fixture home containing a
   plugin `hooks.json` that registers flex's hooks, asserting the dedup guard skips
   settings-level PreToolUse registration.
4. Audit `tests/pairmode/` for sibling tests with the same coupling (any test reaching
   `plugin_hook_files`/`_plugin_registered_hook_pairs`/`Path.home()`-derived plugin
   state without isolation, notably in `test_hook_view.py` and `test_bootstrap.py`) and
   isolate them the same way.
5. Add a CER backlog entry to `docs/cer/backlog.md` recording the host-state-coupled
   test-isolation gap, following the file's existing inline-RESOLVED convention for
   findings fixed in the phase they were found (resolved by INFRA-385).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: green (run without `-x` so no failure is masked). Additionally verify
host-independence by running the three named tests with `HOME` pointed at an empty
temporary directory — they must pass there too.

## Out of scope

- The dedup logic itself (INFRA-288/CER-104/CER-127) — it behaves correctly and must
  not change; only test isolation and any additive `home=` plumbing are in scope.
- A general project-wide `HOME`-isolation fixture for the whole suite — this story
  isolates only the plugin-tree-reading tests identified in the audit.
