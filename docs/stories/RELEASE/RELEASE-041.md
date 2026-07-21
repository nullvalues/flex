---
id: RELEASE-041
rail: RELEASE
title: Fix _has_story_commit() false-positive on spec-authoring commits
status: complete
phase: "HARNESS016-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_story.py
touches:
  - tests/pairmode/test_next_story.py
---

## Requires

- RELEASE-023 already broadened `_has_story_commit()` to whole-token,
  word-boundary matching anywhere in a commit message (not just the
  `story-<ID>:` prefix), to recognize merge suffixes and status-update
  chores as build evidence. That fix is correct for what it targeted, but it
  is now too permissive for a different case.
- This repo's spec-authoring convention prefixes commits with `spec(...)`
  (e.g. `spec(phase-95): scaffold phase and story specs [spec-mode]`,
  `spec(phase-HARNESS016-main): ...`) and is used exclusively for commits
  that create or edit story/phase specs — never for commits that build a
  story. Confirmed 2026-07-21: 54 of this repo's commits use the `spec(`
  prefix, and none of the sampled `feat(story-<ID>):` or
  `chore(orchestrator): <ID> status update` build/status commits use it.
- Live false-positive: commit `5ed0637` ("spec(phase-HARNESS016-main):
  correct RELEASE-019 status, add RELEASE-020/021/022 specs, ...") lists
  three story IDs in prose. `_has_story_commit('RELEASE-020', ...)` matches
  this commit's message (the `/` after `RELEASE-020` in `RELEASE-020/021/022`
  is a valid word boundary), so `next-action`/`next_story.py` currently
  reports `RELEASE-020` as already built and skips straight to `RELEASE-021`
  — RELEASE-020 is not built. Verified directly:
  `_has_story_commit('RELEASE-020', _git_log_oneline(Path('.')))` returns
  `True` on this repo's current history.

## Ensures

- `_has_story_commit()` ignores commits whose message starts with `spec(`
  when checking for build evidence — a spec-authoring commit mentioning a
  story ID in prose (e.g. listing several new specs together) must not
  cause that story to be treated as built.
- All existing behavior for non-`spec(` commits is unchanged: the
  `story-<ID>:` conventional prefix, parenthetical merge suffixes
  (`... (RELEASE-014)`), and bare mentions (`RELEASE-014 status update`)
  still count as build evidence exactly as RELEASE-023 established.
- All existing tests in `tests/pairmode/test_next_story.py` pass unchanged.
- A new regression test reproduces the exact live false positive: a
  `spec(phase-X): ... add RELEASE-020/021/022 specs ...`-style commit does
  NOT cause `find_next_story` to skip a `RELEASE-020`-style story, while a
  genuine `feat(story-RELEASE-020): ...` commit still does.
- Re-running `next_story.py docs/phases/phase-HARNESS016-main.md` (or
  `flex_build.py next-action`) against this repo's actual history after the
  fix returns `RELEASE-020` (not `RELEASE-021`) as the next story.

## Instructions

1. In `skills/pairmode/scripts/next_story.py`, change `_has_story_commit()`
   to iterate `git_log` line by line instead of doing a single blob-wide
   `pattern.search()`. For each line, skip it (treat as non-evidence) if its
   commit message (the text after the leading `<hash> ` from `git log
   --oneline`) starts with `spec(`. Otherwise apply the existing
   word-boundary regex to that line.
2. Update the function's docstring to note the `spec(` exclusion and why
   (spec-authoring commits legitimately reference multiple story IDs in
   prose without building any of them).
3. Add the regression test described in Ensures to
   `tests/pairmode/test_next_story.py`, following the existing
   `_make_project_layout`/`_write_phase`/`_write_story`/`_commit` helper
   pattern already in that file.
4. Do not change anything about how `find_next_story()` consumes
   `_has_story_commit()`'s return value — this story only tightens what
   counts as a match.

## Tests

- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_story.py -x -q`
  — all existing tests plus the new regression test pass.
- Manual: `PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/next_story.py docs/phases/phase-HARNESS016-main.md`
  returns `RELEASE-020`, not `RELEASE-021`.
