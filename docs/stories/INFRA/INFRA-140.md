---
id: INFRA-140
rail: INFRA
title: "Fix sync regression: `sync.py` maintains deny list after sync"
status: planned
phase: "55"
story_class: code
primary_files:
  - skills/pairmode/scripts/sync.py
touches:
  - tests/pairmode/test_sync_deny_list.py
---

# INFRA-140 — Fix sync regression: `sync.py` maintains deny list after sync

## Background

`sync.py`'s apply path calls `_register_pretooluse_hook` (which merges the
PreToolUse hook entry into `.claude/settings.json`) but does **not** call
`_merge_deny_list`. The deny list — populated at bootstrap time by
`_merge_deny_list(settings_path, DEFAULT_DENY)` — is therefore not maintained
by subsequent syncs.

In practice this meant that any sync against a downstream project silently left
the deny list stale or missing (the regression the user observed on forqsite).
Because `_merge_deny_list` is additive and idempotent (it never removes
entries, only adds missing ones), calling it during sync is safe and has no
downside for projects where the deny list is already correct.

## Ensures

### `sync.py` calls `_merge_deny_list` after the hook registration

- `sync.py` imports `_merge_deny_list` and `DEFAULT_DENY` from
  `skills.pairmode.scripts.bootstrap` (alongside the existing
  `_register_pretooluse_hook` import).
- Immediately after the `_register_pretooluse_hook(settings_path, plugin_root)`
  call (around line 566), `sync.py` calls:
  ```python
  _merge_deny_list(settings_path, DEFAULT_DENY)
  ```
- Both calls are unconditional (not guarded by `--yes` or dry-run):
  `_register_pretooluse_hook` was already unconditional; `_merge_deny_list`
  follows the same convention.
- No other changes to `sync.py`.

### Import update

The existing import block in `sync.py` that reads:
```python
from skills.pairmode.scripts.bootstrap import (
    PAIRMODE_DEFAULT_RAILS,
    _infer_project_type,
    _validate_test_command,
    _register_pretooluse_hook,
)
```
gains `_merge_deny_list` and `DEFAULT_DENY`:
```python
from skills.pairmode.scripts.bootstrap import (
    DEFAULT_DENY,
    PAIRMODE_DEFAULT_RAILS,
    _infer_project_type,
    _merge_deny_list,
    _validate_test_command,
    _register_pretooluse_hook,
)
```

## Out of scope

- Removing stale deny entries that have been removed from `DEFAULT_DENY`
  (a separate pruning story if DEFAULT_DENY is ever simplified).
- Modifying `DEFAULT_DENY` contents (Phase 56 scope).
- Touching `pairmode_sync.py sync-all` (INFRA-136 is already shipped).

## Instructions

### 1. Update the import block in `sync.py`

Find the `from skills.pairmode.scripts.bootstrap import (` block and add
`DEFAULT_DENY` and `_merge_deny_list` in alphabetical order alongside the
existing symbols.

### 2. Add the `_merge_deny_list` call

Immediately after line:
```python
_register_pretooluse_hook(settings_path, plugin_root)
```
add:
```python
_merge_deny_list(settings_path, DEFAULT_DENY)
```

## Tests

File: `tests/pairmode/test_sync_deny_list.py`

Use `tmp_path` to create a minimal project tree. Call the `apply_sync` entry
point (or the relevant internal function) against the tmp project and assert on
the resulting `settings.json`.

1. `test_sync_adds_deny_list_to_empty_settings`
   — project has no `.claude/settings.json`; run sync apply; assert
   `settings.json` exists and `permissions.deny` contains all entries from
   `DEFAULT_DENY`.

2. `test_sync_adds_missing_deny_entries_to_existing_settings`
   — project has `.claude/settings.json` with a partial deny list (some
   `DEFAULT_DENY` entries missing); run sync apply; assert all `DEFAULT_DENY`
   entries are now present (existing entries preserved).

3. `test_sync_does_not_duplicate_existing_deny_entries`
   — project has `.claude/settings.json` with the full `DEFAULT_DENY` already
   present; run sync apply; assert no duplicates in `permissions.deny`.

4. `test_sync_preserves_non_default_deny_entries`
   — project settings.json has a custom deny entry not in `DEFAULT_DENY`; run
   sync apply; assert the custom entry is still present.
