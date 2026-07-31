---
id: INFRA-330
rail: INFRA
title: Correct stale draft status on 13 merged, reviewer-PASSed phase-114 stories
status: complete
phase: "114"
story_class: doc
auth_gated: false
schema_introduces: false
touches:
  - docs/phases/phase-114.md
  - docs/stories/INFRA/INFRA-301.md
  - docs/stories/INFRA/INFRA-302.md
  - docs/stories/INFRA/INFRA-303.md
  - docs/stories/INFRA/INFRA-304.md
  - docs/stories/INFRA/INFRA-305.md
  - docs/stories/INFRA/INFRA-319.md
  - docs/stories/INFRA/INFRA-321.md
  - docs/stories/INFRA/INFRA-322.md
  - docs/stories/INFRA/INFRA-324.md
  - docs/stories/INFRA/INFRA-325.md
  - docs/stories/INFRA/INFRA-326.md
  - docs/stories/INFRA/INFRA-327.md
  - docs/stories/INFRA/INFRA-328.md
  - docs/stories/INFRA/INFRA-330.md
---

<!-- SPEC-WRITER NOTE (frontmatter): `touches:` is block-style per CER-115 —
     flow-style `[a, b]` parses as a string and crashes create-story-worktree's
     `generate_permissions_artifact`. This story is pure metadata correction,
     not a build-loop fix: `cmd_merge_story_worktree` in flex_build.py never
     flips story/phase status after a fast-forward merge — that harness gap
     is explicitly out of scope here and is a separate future INFRA story.
     This spec only corrects the 13 stale fields left behind by that gap. -->

## Context

`check-index` (`PATH=$HOME/.local/bin:$PATH uv run python
/mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py check-index
--project-dir .`) reports a `status-drift` violation for 13 of phase 114's
14 stories: INFRA-301, INFRA-302, INFRA-303, INFRA-304, INFRA-305,
INFRA-319, INFRA-321, INFRA-322, INFRA-324, INFRA-325, INFRA-326,
INFRA-327, INFRA-328. Each has a merged `feat(story-INFRA-XXX)` commit on
`main`, a reviewer PASS, but still reads `status: draft` in its own
`docs/stories/INFRA/<ID>.md` frontmatter and `draft` in its Status cell in
`docs/phases/phase-114.md`'s Stories table. `INFRA-323` already correctly
shows `complete` in both places — it is unaffected by the drift and must
not be touched by this story.

Root cause: `cmd_merge_story_worktree` in `flex_build.py` never flips
story/phase status after a fast-forward merge. That is a harness gap, not
in scope here — fixing it is a future INFRA story. This story exists only
to correct the 13 stale fields so they match what already happened on
`main`, and to unblock `next-action`'s checkpoint guard, which currently
returns `checkpoint-guard-failed:phase-incomplete` for phase 114 because
of these 13 false-draft readings.

## Requires

- Each of the 13 stories' `feat(story-INFRA-XXX)` commit is confirmed
  present on `main` before its status is flipped (do not flip a status for
  a story that turns out not to actually be merged — verify with `git log
  --oneline main | grep 'feat(story-INFRA-'` or equivalent before editing).
- `INFRA-323` is read-only in this story — its frontmatter and its
  phase-114.md Status cell (`complete`) are left exactly as they are.
- No other field in any of the 14 touched story files or in
  `phase-114.md` changes — this is a pure status-value edit, not a content
  rewrite. Titles, Context/Requires/Ensures/Instructions/Tests sections,
  other frontmatter keys, and table columns other than Status are
  untouched.

## Ensures

- Each of the 13 stories' frontmatter `status:` field reads `complete`
  (changed from `draft`).
- Each of the 13 stories' Status cell in `docs/phases/phase-114.md`'s
  Stories table reads `complete` (changed from `draft`).
- `INFRA-323`'s frontmatter and Stories-table Status cell remain
  unchanged (`complete` in both, as they already are).
- No content other than these status values changes in any of the 14
  touched story files or in `phase-114.md`.
- `PATH=$HOME/.local/bin:$PATH uv run python
  /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py check-index
  --project-dir .` reports zero `status-drift` violations for any INFRA-3xx
  story. Pre-existing, unrelated violations (e.g. `OBS-006`, `RELEASE-058`,
  cross-link/orphan-story findings) are explicitly out of scope and must
  still be present afterward — this story does not touch or suppress them.
- `PATH=$HOME/.local/bin:$PATH uv run python
  /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py next-action
  --project-dir . --json` no longer returns
  `checkpoint-guard-failed:phase-incomplete` for phase 114 — once all 14
  phase-114 stories (the 13 here plus the already-complete INFRA-323) read
  `complete`, it should return a checkpoint-appropriate action instead.

## Instructions

1. For each of the 13 IDs (INFRA-301, 302, 303, 304, 305, 319, 321, 322,
   324, 325, 326, 327, 328): confirm its `feat(story-INFRA-XXX)` commit
   exists on `main`, then edit only its `docs/stories/INFRA/<ID>.md`
   frontmatter `status:` line from `draft` to `complete`. No other line in
   the file changes.
2. In `docs/phases/phase-114.md`'s Stories table, change each of the same
   13 rows' Status cell from `draft` to `complete`. Leave every other
   column and the INFRA-323 row untouched.
3. Run `check-index` and confirm zero `status-drift` violations remain for
   INFRA-3xx stories, and that the pre-existing unrelated violations
   (OBS-006, RELEASE-058, cross-link/orphan-story) are still present
   (i.e. this story did not accidentally touch them).
4. Run `next-action --json` and confirm it no longer returns
   `checkpoint-guard-failed:phase-incomplete` for phase 114.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py check-index \
  --project-dir .
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py next-action \
  --project-dir . --json
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -10
```

This story adds no new Python code and no new test file — it is a
metadata correction. Acceptance is the `check-index`/`next-action` output
above (zero INFRA-3xx `status-drift`, no
`checkpoint-guard-failed:phase-incomplete`) plus an unaffected full
`pytest tests/pairmode/` run.

## Out of scope

- Fixing `cmd_merge_story_worktree` in `flex_build.py` to auto-flip status
  on merge — this is the harness root cause and belongs to its own future
  INFRA story.
- Any pre-existing, unrelated `check-index` violation (OBS-006,
  RELEASE-058, cross-link/orphan-story findings) — left exactly as found.
- Any change to INFRA-323's status fields — already correct, untouched.
- Any rewrite of story content beyond the single `status:`/Status-cell
  value per file.
