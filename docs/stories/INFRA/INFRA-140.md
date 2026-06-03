---
id: INFRA-140
rail: INFRA
title: "Fix sync regression + simplify DEFAULT_DENY so scope_guard is the sole file-scope enforcer"
status: complete
phase: "55"
story_class: code
primary_files:
  - skills/pairmode/scripts/sync.py
  - skills/pairmode/scripts/bootstrap.py
touches:
  - tests/pairmode/test_sync_deny_list.py
---

# INFRA-140 — Fix sync regression + simplify DEFAULT_DENY

## Background

Two separate but related problems need solving in one story because they are
load-bearing for the rest of Phase 55:

**Problem 1 — Sync regression:** `sync.py`'s apply path calls
`_register_pretooluse_hook` but not `_merge_deny_list`. The deny list set at
bootstrap time is therefore not maintained by subsequent syncs — the regression
the user observed on forqsite.

**Problem 2 — Deny-list gap blocks Phase 55:** Claude Code fires deny rules
*before* PreToolUse hooks. Files in the current `DEFAULT_DENY` (including
`CLAUDE.md`, `CLAUDE.build.md`, `hooks/**`, `.claude/agents/**`) are
hard-blocked before `scope_guard` ever runs. INFRA-139 lists `hooks/pre_tool_use.py`
and `CLAUDE.md` in its own `primary_files`. BUILD-024 removes the only mechanism
that previously overrode those deny rules (`write-permissions` allow-rule injection).

Without simplifying DEFAULT_DENY, Phase 55 ships a scope_guard that can never
enforce scope for protected files AND simultaneously removes the old escape hatch
— making those stories unbuildable.

**The fix:** Reduce DEFAULT_DENY to a single protected path —
`docs/phases/permissions/**` — which is the permissions files directory that
builders must never be able to modify (self-modification of permissions is the
attack vector the system is designed to prevent). Everything else that was in
DEFAULT_DENY becomes scope_guard's responsibility: a builder can only write to
a path if that path is declared in the story's `primary_files` or `touches`.

Removing entries from DEFAULT_DENY requires a `_prune_superseded_deny_entries`
migration in sync.py so existing downstream projects (like forqsite) have their
stale deny entries cleaned up on next sync, rather than accumulating dead rules
indefinitely.

## Ensures

### `bootstrap.py` — simplified `DEFAULT_DENY`

`DEFAULT_DENY` is replaced with the minimal set needed to protect the
permissions files directory:

```python
DEFAULT_DENY: list[str] = [
    "Edit(docs/phases/permissions/**)",
    "Write(docs/phases/permissions/**)",
]
```

The removed entries (CLAUDE.md, CLAUDE.build.md, .claude/agents/**, docs/architecture.md,
docs/phases/**, docs/brief.md, docs/ideology.md, docs/reconstruction.md,
docs/RECONSTRUCTION.md) are no longer needed because scope_guard enforces
story-scoped access at the hook level. A builder can only reach those files when
they are explicitly declared in the story spec's `primary_files` or `touches`.

Note: `docs/phases/**` was the old entry covering the permissions path. It is
replaced by the narrower `docs/phases/permissions/**` so that builders CAN write
to other `docs/phases/` files (e.g. `docs/phases/phase-55.md`) when those files
are declared in story scope.

### `bootstrap.py` — `_SUPERSEDED_DENY_ENTRIES` constant

A new module-level constant records the entries that were removed from
DEFAULT_DENY so that `_prune_superseded_deny_entries` (in sync.py) can clean
them from existing projects:

```python
_SUPERSEDED_DENY_ENTRIES: list[str] = [
    "Edit(CLAUDE.md)",
    "Write(CLAUDE.md)",
    "Edit(CLAUDE.build.md)",
    "Write(CLAUDE.build.md)",
    "Edit(.claude/agents/**)",
    "Write(.claude/agents/**)",
    "Edit(docs/architecture.md)",
    "Write(docs/architecture.md)",
    "Edit(docs/phases/**)",
    "Write(docs/phases/**)",
    "Edit(docs/brief.md)",
    "Write(docs/brief.md)",
    "Edit(docs/ideology.md)",
    "Write(docs/ideology.md)",
    "Edit(docs/reconstruction.md)",
    "Write(docs/reconstruction.md)",
    "Edit(docs/RECONSTRUCTION.md)",
    "Write(docs/RECONSTRUCTION.md)",
]
```

### `sync.py` — calls `_merge_deny_list` and `_prune_superseded_deny_entries`

- `sync.py` imports `_merge_deny_list`, `_prune_superseded_deny_entries`,
  `DEFAULT_DENY`, and `_SUPERSEDED_DENY_ENTRIES` from
  `skills.pairmode.scripts.bootstrap` (alongside the existing
  `_register_pretooluse_hook` import).
- Immediately after `_register_pretooluse_hook(settings_path, plugin_root)`,
  `sync.py` calls both functions in order:
  ```python
  _merge_deny_list(settings_path, DEFAULT_DENY)
  _prune_superseded_deny_entries(settings_path, _SUPERSEDED_DENY_ENTRIES)
  ```
- Both calls are unconditional (not guarded by `--yes` or dry-run).

### `bootstrap.py` — `_prune_superseded_deny_entries` function

A new function in `bootstrap.py` (alongside `_merge_deny_list`):

```python
def _prune_superseded_deny_entries(
    settings_path: pathlib.Path,
    entries_to_remove: list[str],
) -> None:
    """Remove deny entries that are no longer in DEFAULT_DENY from settings_path.

    Idempotent: entries already absent are silently skipped.
    Preserves any custom deny entries not in entries_to_remove.
    """
    if not settings_path.exists():
        return
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return

    permissions = data.get("permissions", {})
    deny: list[str] = permissions.get("deny", [])

    to_remove = set(entries_to_remove)
    new_deny = [e for e in deny if e not in to_remove]

    if new_deny == deny:
        return  # nothing to prune

    permissions["deny"] = new_deny
    data["permissions"] = permissions
    settings_path.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
```

## Out of scope

- Pruning entries from `settings.local.json` (only `settings.json` is managed here).
- Modifying `denylist_deriver.py` or spec-derived deny lists.
- Touching `pairmode_sync.py sync-all` (INFRA-136 is already shipped).

## Instructions

### 1. Edit `bootstrap.py` — replace `DEFAULT_DENY`

Find:
```python
# Default deny list written into .claude/settings.json
DEFAULT_DENY: list[str] = [
    "Edit(CLAUDE.md)",
    ...
    "Write(docs/RECONSTRUCTION.md)",
]
```

Replace the entire `DEFAULT_DENY` list with:
```python
# Default deny list written into .claude/settings.json.
# Kept minimal — scope_guard.py (Phase 55) enforces per-story file scope at
# the hook level. Only the permissions files directory is hard-denied here to
# prevent builders from self-modifying their own scope declarations.
DEFAULT_DENY: list[str] = [
    "Edit(docs/phases/permissions/**)",
    "Write(docs/phases/permissions/**)",
]

# Entries removed from DEFAULT_DENY in Phase 55. Kept here so sync.py can
# prune them from existing projects' settings.json on next sync.
_SUPERSEDED_DENY_ENTRIES: list[str] = [
    "Edit(CLAUDE.md)",
    "Write(CLAUDE.md)",
    "Edit(CLAUDE.build.md)",
    "Write(CLAUDE.build.md)",
    "Edit(.claude/agents/**)",
    "Write(.claude/agents/**)",
    "Edit(docs/architecture.md)",
    "Write(docs/architecture.md)",
    "Edit(docs/phases/**)",
    "Write(docs/phases/**)",
    "Edit(docs/brief.md)",
    "Write(docs/brief.md)",
    "Edit(docs/ideology.md)",
    "Write(docs/ideology.md)",
    "Edit(docs/reconstruction.md)",
    "Write(docs/reconstruction.md)",
    "Edit(docs/RECONSTRUCTION.md)",
    "Write(docs/RECONSTRUCTION.md)",
]
```

### 2. Add `_prune_superseded_deny_entries` to `bootstrap.py`

Add the function immediately after `_merge_deny_list` (around line 344), following
the same style and docstring conventions.

### 3. Update the import block in `sync.py`

Add `DEFAULT_DENY`, `_SUPERSEDED_DENY_ENTRIES`, `_merge_deny_list`, and
`_prune_superseded_deny_entries` to the existing bootstrap import block in
alphabetical order.

### 4. Add the calls in `sync.py`

Immediately after:
```python
_register_pretooluse_hook(settings_path, plugin_root)
```
add:
```python
_merge_deny_list(settings_path, DEFAULT_DENY)
_prune_superseded_deny_entries(settings_path, _SUPERSEDED_DENY_ENTRIES)
```

## Tests

File: `tests/pairmode/test_sync_deny_list.py`

1. `test_sync_adds_new_deny_entries_to_empty_settings`
   — project has no `.claude/settings.json`; run sync apply; assert
   `settings.json` exists and `permissions.deny` contains all entries from
   the new `DEFAULT_DENY`.

2. `test_sync_adds_missing_new_deny_entries_to_existing_settings`
   — project has `.claude/settings.json` with partial new deny list; run sync;
   assert all new `DEFAULT_DENY` entries now present.

3. `test_sync_does_not_duplicate_deny_entries`
   — project settings.json has the full new `DEFAULT_DENY` already; run sync;
   assert no duplicates in `permissions.deny`.

4. `test_sync_prunes_superseded_entries`
   — project settings.json contains old entries like `Edit(CLAUDE.md)` and
   `Write(docs/phases/**)` (from `_SUPERSEDED_DENY_ENTRIES`); run sync;
   assert those entries are gone from `permissions.deny` afterward.

5. `test_sync_preserves_custom_deny_entries`
   — project settings.json has a custom deny entry not in either `DEFAULT_DENY`
   or `_SUPERSEDED_DENY_ENTRIES`; run sync; assert the custom entry is still present.

6. `test_prune_superseded_is_idempotent`
   — call `_prune_superseded_deny_entries` twice on the same settings.json;
   assert no error and result is identical both times.

7. `test_prune_superseded_no_op_when_file_missing`
   — call `_prune_superseded_deny_entries` with a non-existent path;
   assert no exception raised.
