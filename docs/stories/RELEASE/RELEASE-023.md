---
id: RELEASE-023
rail: RELEASE
title: Fix _has_story_commit() commit-message matching in next_story.py
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

- `next_story.py`'s `_has_story_commit()` only counts a story as done if some
  commit message in `git log --oneline` contains the literal substring
  `story-<STORY_ID>` (case-insensitive). This is a deliberate safety net:
  `find_next_story()`'s docstring says a table row marked `complete` with no
  matching commit is still returned as next-up, with `git_verified=true`,
  so a phase doc can't silently claim a story is done with no git evidence.
- RELEASE-014 was merged via commit `3367750 merge(fold-prep): ... (RELEASE-014)`
  and a follow-up `1bb10c4 chore(orchestrator): RELEASE-014 status update`.
  Neither contains the literal substring `story-RELEASE-014`, so the resolver
  never recognizes RELEASE-014 as done — `next-action` returns it as the next
  unbuilt story on every loop iteration even though its frontmatter and the
  phase table both say `complete` and a builder re-verification confirmed the
  merge is fully landed with a green test suite. This will recur for any
  story whose landing commit doesn't happen to use the exact `story-<ID>:`
  conventional-commit prefix (e.g. merge commits, status-update chores).
- Existing tests in `tests/pairmode/test_next_story.py`
  (`test_skips_complete_story`, `test_git_commit_overrides_table_status`,
  `test_all_done_exits_1`) all commit with the `feat(story-INFRA-100): done`
  convention and must keep passing unchanged.

## Ensures

- `_has_story_commit()` recognizes a story as committed when the story ID
  appears as a whole token anywhere in a commit message (word-boundary
  match, case-insensitive) — not only when prefixed with the literal
  `story-`. This must match all of:
  - `feat(story-INFRA-100): done` (existing convention, must keep passing)
  - `merge(fold-prep): ... (RELEASE-014)` (parenthetical suffix)
  - `chore(orchestrator): RELEASE-014 status update` (bare mention)
- It must NOT match a different story ID that merely shares a numeric
  prefix, e.g. a commit mentioning `INFRA-1001` must not satisfy a lookup
  for `INFRA-100` (add a negative test case for this).
- All existing tests in `tests/pairmode/test_next_story.py` pass unchanged.
- A new test confirms RELEASE-014-style completion: a commit whose message
  contains the story ID without the `story-` prefix causes `find_next_story`
  to skip that story and advance to the next table row.
- Re-running `flex_build.py next-action --json --project-dir .` against this
  repo's actual `fold-prep` history+phase state after the fix returns
  RELEASE-019 (not RELEASE-014) as `next_story_id`.

## Instructions

In `skills/pairmode/scripts/next_story.py`, change `_has_story_commit()`'s
pattern from `r'story-' + re.escape(story_id)` to a word-boundary match on
the story ID itself (`re.compile(r'\b' + re.escape(story_id) + r'\b',
re.IGNORECASE)`), keeping the case-insensitive search over the full
`git log --oneline` text. Update the module docstring's description of the
matching rule to match. Add the negative-match and bare-mention test cases
described above to `tests/pairmode/test_next_story.py`.

## Tests

- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_story.py -x -q`
- Full suite: `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`
- Manual: `PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/flex_build.py next-action --json --project-dir .` returns `next_story_id: RELEASE-019` (verify via `resolver-state`, not `next-action` alone, since `next-action` may report a different action if RELEASE-019 needs a model-upgrade prompt of its own).
