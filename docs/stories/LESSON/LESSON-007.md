---
id: LESSON-007
rail: LESSON
title: enforced_by field on lesson schema and unenforced-backlog query
status: complete
phase: "HARNESS014-main"
story_class: methodology
auth_gated: false
schema_introduces: false
primary_files:
  - lessons/lessons.json
  - skills/pairmode/scripts/lesson_utils.py
  - skills/pairmode/scripts/lesson.py
  - skills/pairmode/scripts/lesson_review.py
touches:
  - lessons/LESSONS.md
---

## Requires

- `lessons/lessons.json` at its current 18-entry state (15 `applied`, 3
  `captured`); no entries have an `enforced_by` key today.
- `lesson_utils.save_lessons()` currently raises `ValueError` if any field
  other than `status` differs from the existing entry on disk (the
  append-only invariant in `lesson_utils.py:21-54`). This blocks a normal
  `save_lessons()`-mediated backfill of a brand-new field onto existing
  entries — the backfill must go around that path once, deliberately (see
  Instructions).

## Ensures

- `lessons.json` schema gains an `enforced_by` field on every lesson, one of
  `"lint" | "hook" | "skill" | "none"`.
- All 18 existing lessons are backfilled with a value (none left absent).
  Backfill classification:
  - `"lint"`: audit.py / bootstrap.py structural checks that flag or gate a
    condition without stopping the agent (L001, L002, L003, L006).
  - `"hook"`: behavior baked into a Claude Code hook, sync/render pipeline,
    or template so the violation is structurally impossible or auto-applied
    (L004, L005, L007, L009, L010, L011, L013).
  - `"skill"`: folded into a procedure.md checklist item a role is
    instructed to check every time, but not machine-gated (L008, L015).
  - `"none"`: prose-only, or captured/not yet folded (L012, L014, L016,
    L017, L018). **Note:** L014 itself documents that `lesson_utils.py` has
    no `__main__` block guarding against script-style invocation — as of
    this story's Requires, that guard still does not exist, so L014 is
    `"none"` despite `status: applied`. Do not silently reclassify L014 to
    a stronger tier just because its status says applied; status tracks
    whether the *learning* was acted on, not whether it is *enforced*. If
    disagreement arises for a specific lesson, prefer `"none"` — the whole
    point of the field is to surface uncertainty, not launder it.
- `lesson.py`'s capture flow accepts an `--enforced-by` option (default
  `"none"`) so every newly captured lesson gets a value at creation time,
  not as a follow-up chore.
- `lesson_review.py` gains a query surface (CLI flag, e.g.
  `--list-unenforced`) that prints every lesson with `status: applied` and
  `enforced_by: "none"` — the queryable backlog this story exists to create.
- `lesson_utils.generate_lessons_md()` includes the `enforced_by` value in
  each entry's rendered block in `LESSONS.md`.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_lesson_utils.py tests/pairmode/test_lesson_capture.py tests/pairmode/test_lesson_review.py -x -q` passes.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

**Backfill (one-time, not via `save_lessons()`):** `save_lessons()`'s
append-only invariant (lesson_utils.py:39-50) will reject adding a new key to
an existing entry, since `original.get(key) != value` is true for any key
that didn't exist before. Write the backfill as a small standalone step
(inline in this story's implementation, not a persisted script) that loads
`lessons.json` with plain `json.load`, sets `enforced_by` on each of the 18
entries per the classification table above, and writes it back directly with
`json.dump(..., indent=2)` plus a trailing newline (matching
`save_lessons()`'s existing format) — bypassing `save_lessons()` for this one
migration write only. After the backfill, every entry has the key, so all
*future* `save_lessons()` calls proceed normally (the invariant only fires on
a field that both exists in the old entry and differs).

**Going forward — extend `save_lessons()`'s invariant, don't loosen it
globally:** add `enforced_by` as an explicit exception in the field-diff loop
only for entries where `original` predates the field (i.e. `"enforced_by" not
in original`), so the one-time migration is legal but a lesson's
`enforced_by` still can't be silently rewritten afterward — it should only
ever change via the same override path other fields use, if one exists, or
stay append-only like `trigger`/`learning`.

**`lesson.py` capture flow:** add `--enforced-by` as a click option with
`type=click.Choice(["lint", "hook", "skill", "none"])`, default `"none"`.
Thread it into the new-lesson dict alongside the existing fields.

**`lesson_review.py` query:** add a function `list_unenforced_lessons()`
(mirrors the shape of `load_reviewable_lessons()`) that filters
`lesson_utils.load_lessons()["lessons"]` to `status == "applied" and
enforced_by == "none"`. Wire it to a `--list-unenforced` CLI flag that prints
`id`, `trigger`, and `methodology_change.description` for each hit, or "no
unenforced applied lessons" if empty.

## Tests

- `test_lesson_utils.py`: `generate_lessons_md` includes `enforced_by` in
  rendered output; `save_lessons` still rejects a genuine field mutation
  (e.g. changing `learning`) after the migration, but accepts adding
  `enforced_by` to an entry that lacks it.
- `test_lesson_capture.py`: capturing a lesson without `--enforced-by`
  defaults to `"none"`; capturing with `--enforced-by hook` stores `"hook"`;
  invalid value rejected by Click's choice validation.
- `test_lesson_review.py`: `list_unenforced_lessons()` returns only
  `status: applied` + `enforced_by: none` entries; `--list-unenforced` CLI
  output matches.
