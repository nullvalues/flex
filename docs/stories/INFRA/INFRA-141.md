---
id: INFRA-141
rail: INFRA
title: "`permissions-create` story_id validation + output path containment"
status: complete
phase: "55"
story_class: code
primary_files:
  - skills/pairmode/scripts/flex_build.py
touches:
  - tests/pairmode/test_flex_build_permissions_create.py
---

# INFRA-141 — `permissions-create` story_id validation + output path containment

## Background

CER-036 (Phase 55 security audit): `cmd_permissions_create` takes `STORY_ID` as a positional
argument and uses it unsanitised to construct both input path (`docs/stories/<rail>/<id>.md`)
and output path (`docs/phases/permissions/<id>.json`). A crafted `story_id` with `..` segments
can escape the project root. The permissions file is the source of truth for `scope_guard.py`
hook enforcement — write-side path traversal undermines scope integrity.

## Ensures

- `cmd_permissions_create` validates `story_id` at entry with:
  ```python
  import re as _re
  _STORY_ID_RE = _re.compile(r"^[A-Z][A-Z0-9_]*-\d{3}$")
  ```
  If `story_id` does not match, print an error to stderr and `sys.exit(1)`.
- After constructing `story_path`, verify containment:
  ```python
  if not story_path.resolve().is_relative_to(project_path / "docs" / "stories"):
      click.echo("permissions-create: story_id escapes project root", err=True)
      sys.exit(1)
  ```
- After constructing `out_path`, verify containment:
  ```python
  if not out_path.resolve().is_relative_to(project_path / "docs" / "phases" / "permissions"):
      click.echo("permissions-create: output path escapes permissions dir", err=True)
      sys.exit(1)
  ```
- All existing tests continue to pass (no regression).

## Out of scope

- Fixing `_story_path()` (CER-034, separate finding, LOW severity).
- Other CLI argument sanitisation beyond `permissions-create`.

## Instructions

### 1. Add `_STORY_ID_RE` constant near the top of `flex_build.py`

Place it after the module-level imports, before `flex_build = click.group(...)`:

```python
_STORY_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*-\d{3}$")
```

`re` is already imported (or add `import re` if not present).

### 2. Add validation + containment to `cmd_permissions_create`

At the top of the function body, before any path construction:

```python
if not _STORY_ID_RE.match(story_id):
    click.echo(f"permissions-create: invalid story_id format: {story_id!r}", err=True)
    sys.exit(1)
```

After `story_path` is constructed:

```python
stories_root = project_path / "docs" / "stories"
try:
    story_path.resolve().relative_to(stories_root.resolve())
except ValueError:
    click.echo(f"permissions-create: story spec path escapes project root", err=True)
    sys.exit(1)
```

After `out_path` is constructed:

```python
try:
    out_path.resolve().relative_to(out_dir.resolve())
except ValueError:
    click.echo(f"permissions-create: output path escapes permissions dir", err=True)
    sys.exit(1)
```

## Tests

Add to `tests/pairmode/test_flex_build_permissions_create.py`:

1. `test_permissions_create_rejects_invalid_story_id_format`
   — pass `story_id="invalid"` (no rail prefix); assert exit code non-zero and stderr
   contains "invalid story_id".

2. `test_permissions_create_rejects_traversal_story_id`
   — pass `story_id="../../etc/passwd"` or similar with `..`; assert exit code non-zero.

3. `test_permissions_create_accepts_valid_story_id`
   — pass `story_id="INFRA-999"` with a real story file; assert exit 0 (existing tests cover this).
