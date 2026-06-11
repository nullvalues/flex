---
id: INFRA-172
rail: INFRA
title: "`flex_build.py mark-phase-complete` — write `complete` status to phase index"
status: complete
phase: "65"
story_class: code
primary_files:
  - skills/pairmode/scripts/flex_build.py
touches:
  - tests/pairmode/test_flex_build_mark_phase_complete.py
---

# INFRA-172 — `flex_build.py mark-phase-complete`

## Context

`docs/phases/index.md` has a `Status` column. `phase_new.py` writes `planned` on row
creation and nothing ever updates it. The parsing infrastructure already exists
(`_parse_index_phases`, `_is_aggregate_range`). This story adds the missing write path.

Confirmed drift: in forqsite, dozens of phases are checkpointed but still show
`planned`. In flex, the status was maintained manually.

## Acceptance criteria

1. `flex_build.py mark-phase-complete --phase N --project-dir .` updates the matching
   row's status cell from any value to `complete` in `docs/phases/index.md`.

2. The command operates by finding the `| N | ... | <status> | ... |` row and
   replacing `<status>` in-place. Only the status cell changes; title and tag columns
   are untouched.

3. If the phase row is NOT found in the index: print an error to stderr and exit 1.
   (Do not create a row — that's `phase_new.py`'s job.)

4. If the phase row is already `complete`: exit 0 silently (idempotent).

5. The command is safe to run on any status value (`planned`, `planned-pending-design`,
   etc.) — all transition to `complete`.

6. `--phase` accepts any phase key that `_parse_index_phases` would recognise: integer
   strings (`59`), suffixed keys (`PM037-main`), etc.

7. The atomic write pattern (NamedTemporaryFile + os.replace) is used for the write.

8. `tests/pairmode/test_flex_build_mark_phase_complete.py` covers all criteria.

## Implementation guidance

Add after `cmd_next_phase` in `flex_build.py`:

```python
@flex_build.command("mark-phase-complete")
@click.option("--phase", "phase_key", required=True, type=str,
              help="Phase key to mark complete (e.g. 59 or PM037-main).")
@click.option("--project-dir", required=True, type=str)
def cmd_mark_phase_complete(phase_key: str, project_dir: str) -> None:
    """Set the status cell of a phase row in docs/phases/index.md to 'complete'."""
    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    index_path = project_path / "docs" / "phases" / "index.md"
    if not index_path.exists():
        click.echo(f"mark-phase-complete: index not found: {index_path}", err=True)
        raise SystemExit(1)

    text = index_path.read_text(encoding="utf-8")
    rows = _parse_index_phases(text)
    found = any(ref == phase_key for ref, _ in rows)
    if not found:
        click.echo(f"mark-phase-complete: phase '{phase_key}' not in index", err=True)
        raise SystemExit(1)

    # Replace the status cell in the raw text.
    # Each data row looks like: | <ref> | <title> | <status> | <tag> |
    # We target the first matching row and replace its status cell only.
    ...
```

For the in-place status replacement, use a line-by-line scan:
- Parse each `|`-delimited row to find the matching phase_key in column 1
- Replace the value in column 3 with `complete`
- Reconstruct the row with the same column widths

Preserve original whitespace in unchanged cells. The simplest implementation: split on
`|`, strip each cell, compare, rebuild with `f"| {parts[1]} | {parts[2]} | complete | {parts[4]} |"`.
Exact whitespace in titles/tags may change slightly — that is acceptable.

If the row is already `complete`: detect and exit 0 without writing.

## Tests

File: `tests/pairmode/test_flex_build_mark_phase_complete.py`

Test cases:
1. `test_planned_becomes_complete` — index has a `planned` row for phase 59; command marks it complete; file updated.
2. `test_already_complete_is_idempotent` — row is already `complete`; exit 0, no file write.
3. `test_other_status_becomes_complete` — row has `planned-pending-design`; becomes `complete`.
4. `test_phase_not_found_exits_1` — phase key absent from index; exits 1, error on stderr.
5. `test_title_and_tag_preserved` — after marking complete, title and tag cells are unchanged.
6. `test_suffixed_phase_key` — key `PM037-main` works correctly.
7. `test_index_not_found_exits_1` — no index file; exits 1.
8. `test_atomic_write` — verify the write does not leave a partial file on disk (use a large index).
