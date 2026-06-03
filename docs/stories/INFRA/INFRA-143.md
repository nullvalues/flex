---
id: INFRA-143
rail: INFRA
title: "`phase_new.py` — string phase-id and `--suffix` flag"
status: complete
phase: "56"
primary_files:
  - skills/pairmode/scripts/phase_new.py
  - skills/pairmode/templates/docs/phases/phase.md.j2
  - skills/pairmode/templates/docs/phases/index.md.j2
touches:
  - tests/pairmode/test_phase_new.py
---

# INFRA-143 — `phase_new.py`: string phase-id and `--suffix` flag

## Context

Forqsite uses a `PM-NNN-main` / `PM-NNN-post1` / `PM-NNN-ante1` naming scheme for phase files
so that remediation or preflight phases sort correctly next to their parent on disk without
breaking the sort order. The convention is: alphabetical suffix order mirrors build order
(`-ante` < `-main` < `-post`). Currently `phase_new.py` only accepts an integer `--phase-id`
and always produces `phase-N.md`.

This story adds:
- String phase-id support (e.g. `--phase-id PM025`)
- Optional `--suffix` flag (e.g. `--suffix main`, `--suffix post1`)

## Acceptance criteria

1. `--phase-id` accepts any non-empty string (no longer `type=int`).
2. New optional `--suffix` flag accepts any non-empty string. No validation of specific values
   (projects choose their own predicates and suffixes).
3. When `--suffix` is given, the output filename is `phase-{phase_id}-{suffix}.md` and the
   index row ID column shows `{phase_id}-{suffix}`.
4. When `--suffix` is absent, filename is `phase-{phase_id}.md` (backwards-compatible).
5. Integer-style IDs (`--phase-id 56`) continue to produce `phase-56.md` unchanged.
6. `prev_phase` navigation is only attempted when `phase_id` is a pure integer string (matches
   `^\d+$`) AND no suffix is given. String IDs (PM025) skip prev_phase lookup entirely.
7. Phase heading in the rendered file: `# {project_name} — Phase {phase_key}: {title}` where
   `phase_key` is `{phase_id}-{suffix}` if suffix, else `{phase_id}`.
8. `_append_index_row` and `_create_index` use the full phase key (including suffix) in both
   the ID column and the filename link.
9. `_update_era_phases_table` uses the full phase key.
10. All new paths covered by tests in `test_phase_new.py`.

## Implementation notes

- **`phase_key`** is the canonical combined identifier: `f"{phase_id}-{suffix}"` if suffix else `phase_id`.
  Pass it to templates and index helpers instead of `phase_id` directly.
- The Jinja2 template `phase.md.j2` receives `phase_key` in place of `phase_id`.
  Change `Phase {{ phase_id }}` → `Phase {{ phase_key }}` in the heading and prev/next nav lines.
  The template variable `phase_id` can be dropped or kept as an alias — use `phase_key` as the
  single canonical name to avoid confusion.
- `index.md.j2` already uses `{{ phase.id }}` and `{{ phase.file }}` — no template change needed
  as long as callers pass the full phase_key as `id`.
- `prev_phase` look-up currently does `phases_dir / f"phase-{phase_id - 1}.md"` — this requires
  integer arithmetic. Change to: only attempt when `re.fullmatch(r"\d+", phase_id)` and no suffix.
  When it does attempt, cast `phase_id` to int for the arithmetic.
- `_read_phase_title` currently searches for `Phase {phase_id}` — it searches the file text so
  string IDs work without change (the regex already has a catch-all fallback).

## Out of scope

- Validation of specific suffix values (`main`, `post1`, etc.) — projects define their own.
- Changing how `schema_validator.py` parses phase frontmatter IDs.
- Updating `SKILL.md` or `CLAUDE.build.md.j2` (covered by INFRA-144).
