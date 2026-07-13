---
id: INFRA-194
rail: INFRA
title: "permissions-create idempotency — skip write when allowed_paths unchanged"
status: complete
phase: "86"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
touches:
  - tests/pairmode/test_flex_build_permissions_create.py
---

## Requires

- Current (buggy) behavior, verified directly in this repo's
  `skills/pairmode/scripts/flex_build.py::cmd_permissions_create` (lines
  232–299):
  - Computes `allowed_paths` from the story's `primary_files` + `touches`
    frontmatter (deduplicated, story spec path appended if absent).
  - Unconditionally calls `out_path.write_text(...)` with a fresh
    `generated_at` timestamp on every invocation, regardless of whether
    `allowed_paths` differs from what is already on disk at
    `docs/phases/permissions/<STORY_ID>.json`.
  - `docs/phases/permissions/**` is a Layer 1 protected path under the
    orchestrator's auto-mode deny rules (documented in `CLAUDE.build.md`'s
    two-layer permission model, established INFRA-137 / Phase 81). The
    unconditional write means every story build re-triggers a write to a
    protected path, re-opening the auto-mode authorization gate even when
    the story's scope hasn't changed since phase inception — defeating the
    "one toggle covers the whole phase" design intent and forcing
    unnecessary re-authorization on every story.
  - `tests/pairmode/test_flex_build_permissions_create.py` already has a
    `test_permissions_create_idempotent` test, but it only asserts
    `allowed_paths`/`story_id`/`story_spec` equality across two runs — it
    does NOT assert `generated_at` is preserved (i.e. it does not catch the
    unconditional-rewrite bug this story fixes).
- `_STORY_ID_RE`, path-traversal guards (`story spec path escapes project
  root`, `output path escapes permissions dir`), and the missing-story-spec
  error path are all correct as-is and must be preserved unchanged.

## Ensures

- `cmd_permissions_create` reads the existing `docs/phases/permissions/<STORY_ID>.json`
  (if present) before writing. If it exists, is valid JSON, and its
  `allowed_paths` list is equal (same elements, same order) to the freshly
  computed `allowed_paths`, the function no-ops: it does NOT call
  `write_text`, does NOT touch `generated_at`, and prints a distinct stdout
  message indicating no change was needed (e.g.
  `permissions: docs/phases/permissions/<STORY_ID>.json unchanged (N paths)`)
  instead of the existing `wrote ...` message.
- If the existing file is absent, unreadable, not valid JSON, or its
  `allowed_paths` differs from the freshly computed value, behavior is
  unchanged from today: write the file with a fresh `generated_at` and print
  the existing `permissions: wrote docs/phases/permissions/<STORY_ID>.json (N paths)`
  message.
- `story_spec` and `story_id` fields are not part of the equality check
  (only `allowed_paths` reflects actual permission scope; `story_spec` and
  `story_id` are derived from the story_id argument itself and cannot drift
  independently of it).
- All existing tests in `tests/pairmode/test_flex_build_permissions_create.py`
  continue to pass unmodified, EXCEPT `test_permissions_create_idempotent`,
  which gains an explicit `generated_at` equality assertion (see Tests).
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

**1. Update `cmd_permissions_create` in `flex_build.py`.**

Insert a read-and-compare step immediately before the existing
`out_path.write_text(...)` call (after `payload` is constructed but before
it is written — construct `allowed_paths` first, then check, then build the
full `payload` with `generated_at` only on the write path):

```python
    out_dir = project_path / "docs" / "phases" / "permissions"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{story_id}.json"

    try:
        out_path.resolve().relative_to(out_dir.resolve())
    except ValueError:
        click.echo("permissions-create: output path escapes permissions dir", err=True)
        sys.exit(1)

    existing_allowed: list[str] | None = None
    if out_path.exists():
        try:
            existing_payload = json.loads(out_path.read_text(encoding="utf-8"))
            existing_allowed = existing_payload.get("allowed_paths")
        except (json.JSONDecodeError, OSError):
            existing_allowed = None

    if existing_allowed == allowed:
        click.echo(
            f"permissions: docs/phases/permissions/{story_id}.json unchanged ({len(allowed)} paths)"
        )
        return

    payload = {
        "story_id": story_id,
        "story_spec": story_spec_rel,
        "allowed_paths": allowed,
        "generated_at": _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    click.echo(
        f"permissions: wrote docs/phases/permissions/{story_id}.json ({len(allowed)} paths)"
    )
```

Note `existing_allowed == allowed` relies on list equality (order-sensitive).
`allowed` is built by iterating `primary_files + touches` in frontmatter
order, so a reordering in the story spec's frontmatter — even with the same
set of paths — is treated as a change and triggers a rewrite. This is
intentional: it's simpler and safer than order-insensitive comparison, and
frontmatter reordering without an actual scope change is not expected to
happen organically.

## Tests

Update `tests/pairmode/test_flex_build_permissions_create.py`:

- `test_permissions_create_idempotent` — add an assertion that
  `data1["generated_at"] == data2["generated_at"]` (the missing check that
  would have caught this bug — content equality alone was already passing
  before this fix).
- `test_permissions_create_noop_prints_unchanged_message(tmp_path)` — run
  `permissions-create` twice with an identical story spec; assert the
  second run's stdout contains `"unchanged"` and does NOT contain `"wrote"`.
- `test_permissions_create_rewrites_when_touches_changes(tmp_path)` — run
  `permissions-create` once; rewrite the story spec file with an added
  `touches` entry; run `permissions-create` again; assert the second run's
  stdout contains `"wrote"`, `allowed_paths` includes the new path, and
  `generated_at` differs from the first run's value.
- `test_permissions_create_rewrites_when_existing_file_is_corrupt(tmp_path)`
  — write invalid JSON (e.g. `"not json"`) directly to
  `docs/phases/permissions/<STORY_ID>.json` before running
  `permissions-create`; assert the command still succeeds (exit code 0) and
  overwrites the file with valid, freshly generated content.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_build_permissions_create.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```
