---
id: LESSON-008
rail: LESSON
title: Repoint _AFFECTS_TO_TEMPLATE map to procedure.md files
status: planned
phase: "HARNESS014-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/lesson_review.py
touches:
  - tests/pairmode/test_lesson_review.py
---

## Requires

- `9acb914` (story HARNESS-002) deleted `skills/pairmode/templates/agents/builder.md.j2`
  and `reviewer.md.j2` as part of the thin-loop cutover; role procedures now
  live at `skills/pairmode/skills/{role}/procedure.md`.
- `lesson_review.py:37-48` still hardcodes the pre-cutover map:
  ```python
  _AFFECTS_TO_TEMPLATE = {
      "reviewer_checklist": "skills/pairmode/templates/CLAUDE.md.j2",
      "builder_agent": "skills/pairmode/templates/agents/builder.md.j2",
      "orchestrator": "skills/pairmode/templates/CLAUDE.build.md.j2",
      "checkpoint_sequence": "skills/pairmode/templates/CLAUDE.build.md.j2",
  }
  _ALL_TEMPLATE_FILES = [
      "skills/pairmode/templates/CLAUDE.md.j2",
      "skills/pairmode/templates/agents/builder.md.j2",
      "skills/pairmode/templates/CLAUDE.build.md.j2",
  ]
  ```
  `"builder_agent"` and the second entry of `_ALL_TEMPLATE_FILES` point at a
  file that no longer exists.
- `apply_template_change()` (lesson_review.py:139-164) opens its target path
  in `"a"` mode. Python's `open(..., "a")` creates a missing file rather than
  raising, and `agents/.gitkeep` keeps the `agents/` directory present — so
  today, approving a `builder_agent`-affects lesson silently recreates an
  orphan `builder.md.j2` outside the render pipeline instead of failing. This
  gives false confidence that the lesson was folded in. That silent-recreate
  behavior is the actual bug this story fixes, not just the stale path.
- Current `affects` values used across `lessons.json` that have **no** entry
  in `_AFFECTS_TO_TEMPLATE` at all (so `propose_template_change()` already
  returns `template_file: ""` for them via `.get(affects_value, "")`):
  `audit.py`, `hooks`, `sidebar`, `bootstrap`,
  `pairmode-builder-reviewer-loop`, `pairmode-methodology-evolution`,
  `pairmode-template-propagation`, `cross-project consistency`,
  `lesson_utils.py`, `CLAUDE.build.md`, `tooling`, `build-loop`, `reviewer`.
  This story is scoped to fixing the dangling/incorrect map entries
  (`builder_agent`, `_ALL_TEMPLATE_FILES`) and adding a hard failure for any
  unmapped `affects` value; it does not attempt to map every historical
  `affects` string used so far — that free-text drift is a separate,
  pre-existing looseness in how lessons are captured (`lesson.py`'s
  `affects` input has no controlled vocabulary) and is out of scope here.

## Ensures

- `_AFFECTS_TO_TEMPLATE["builder_agent"]` is repointed to
  `skills/pairmode/skills/builder/procedure.md`.
- A new `"reviewer"` key is added mapping to
  `skills/pairmode/skills/reviewer/procedure.md` (covers L017's `affects:
  ["build-loop", "reviewer"]` — `build-loop` stays unmapped per Requires).
- `_ALL_TEMPLATE_FILES`'s stale `agents/builder.md.j2` entry is replaced with
  `skills/pairmode/skills/builder/procedure.md`.
- `apply_template_change()` raises `FileNotFoundError` with a message naming
  the missing path if `proposal["template_file"]` does not already exist on
  disk, or if `proposal["template_file"]` is `""` (unmapped `affects`
  value) — in both cases, before attempting to open/write anything. No more
  silent file creation for a mapping miss.
- `propose_template_change()` behavior for `affects: "all"` is unchanged in
  shape (still iterates `_ALL_TEMPLATE_FILES`), just with the corrected file
  list.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_lesson_review.py -x -q` passes.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

Edit `_AFFECTS_TO_TEMPLATE` and `_ALL_TEMPLATE_FILES` in
`skills/pairmode/scripts/lesson_review.py` per the Ensures above. In
`apply_template_change()`, add a resolved-path existence check immediately
after the templates-boundary check (lesson_review.py:154-159) and before the
`open(template_path, "a")` call:

```python
if not proposal.get("template_file"):
    raise FileNotFoundError(
        f"No template mapping for affects={proposal.get('affects')!r} "
        f"(lesson {proposal.get('lesson_id')}) — add an _AFFECTS_TO_TEMPLATE "
        f"entry or fold this lesson manually."
    )
if not template_path.exists():
    raise FileNotFoundError(
        f"Mapped template file does not exist: {template_path} "
        f"(lesson {proposal.get('lesson_id')}, affects={proposal.get('affects')!r})"
    )
```

Do not attempt to re-fold L004/L005 (already `applied`, already reflected in
current template/procedure content per L003-era code, not re-run) — this
story only fixes the mapping and the write-time guard for future lesson
approvals.

## Tests

- `test_lesson_review.py`: `apply_template_change()` on a proposal targeting
  `skills/pairmode/skills/builder/procedure.md` succeeds (file exists,
  append happens).
- `apply_template_change()` on a proposal with `template_file: ""` raises
  `FileNotFoundError` and writes nothing.
- `apply_template_change()` on a proposal targeting a deliberately
  nonexistent path (e.g. a tmp-dir fixture) raises `FileNotFoundError` and
  creates no file — regression test for the silent-recreate bug.
- `propose_template_change()` for a lesson with `affects: ["all"]` returns
  proposals whose `template_file` values no longer include
  `agents/builder.md.j2`.
