---
id: INFRA-223
rail: INFRA
title: Scope reviewer FAIL-path revert to the story's declared primary_files/touches instead of a blanket git checkout . && git clean -fd
status: complete
phase: "96"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/reviewer/procedure.md
touches:
  - docs/architecture.md
---

## Requires

- `skills/pairmode/skills/reviewer/procedure.md` exists with the "On FAIL,
  revert" block (lines ~354-357: `git checkout .` / `git clean -fd`) and the
  "RAIL SCOPE" checklist item (§9, lines ~230-241) which already reads the
  story's `primary_files`/`touches` frontmatter during the review.

## Context

RELEASE-022's FAIL revert ran `git checkout . && git clean -fd` — a
whole-working-tree operation — and deleted two untracked directories
(`docs/stories/CORE/`, `docs/stories/TEST/`) that had nothing to do with that
story's declared scope. They turned out to be empty (recovered by mirroring a
sibling worktree), but the same command against non-empty untracked content
unrelated to the story — a concurrent session's in-progress file, a
just-created-but-uncommitted story, a local experiment — would have destroyed
it irrecoverably with no git-based undo path.

The fix is not "check `git status` first and warn" (a check can be skipped or
raced); it is to make the revert **structurally incapable** of touching
anything outside the story's declared scope, the same `primary_files` +
`touches` list §9 (RAIL SCOPE) already reads during review, and the same list
the "On PASS, commit" block already scopes `git add` to.

## Ensures

1. The reviewer procedure's FAIL-path revert stages the story's declared
   `primary_files` + `touches` paths (read once, during "Starting a review",
   not re-derived ad hoc at revert time) and reverts/cleans only those paths —
   never a bare `git checkout .` / `git clean -fd` with no path arguments.
2. `git checkout -- <path>` is run per declared path (restores tracked
   modifications) and `git clean -fd -- <path>` is run per declared path
   (removes untracked new files/dirs the builder created), each scoped to a
   path prefix so a declared directory (not just a single file) is fully
   reverted.
3. When both `primary_files` and `touches` are empty or absent (legacy story
   with no declared scope), the procedure falls back to the current
   whole-tree `git checkout . && git clean -fd` — explicitly documented as
   the legacy-only path, mirroring the identical fallback already documented
   in the "On PASS, commit" section for `git add -A`.
4. The FAIL-CAUSE line and stop-at-first-CRITICAL behavior are unchanged —
   only the revert command block changes.
5. `docs/architecture.md`'s reviewer-role description (if it names the revert
   command) is updated to match; if it doesn't mention the specific command,
   no change needed there.

## Instructions

1. In `skills/pairmode/skills/reviewer/procedure.md`, in the "Before
   reviewing" section (§ before line 71), add an explicit step: read the
   story's `primary_files` and `touches` frontmatter fields once, up front
   (the same read that already happens for §9 RAIL SCOPE) — this becomes the
   single declared-scope list referenced by both the RAIL SCOPE check and the
   FAIL-path revert below, rather than two independent reads of the same
   fields.
2. Replace the "On FAIL, revert" block (currently):
   ```bash
   git checkout .
   git clean -fd
   ```
   with scoped revert logic. The reviewer is an LLM following prose, not a
   shell script, so write this as an instruction plus illustrative example
   rather than literal executable shell — but the example should make the
   intended commands unambiguous:

   > Revert only the story's declared scope (the `primary_files` + `touches`
   > paths read during "Before reviewing"), not the whole tree. For each
   > declared path, run `git checkout -- <path>` and `git clean -fd --
   > <path>`. Only when both `primary_files` and `touches` are empty or
   > absent (a legacy story with no declared scope) fall back to the
   > whole-tree form:
   > ```bash
   > git checkout .
   > git clean -fd
   > ```
   > This mirrors the `git add -A` fallback already used in the "On PASS,
   > commit" section above.
3. Do not change the "On PASS, commit" block — it already scopes `git add` to
   declared paths with the same fallback; only the FAIL-path revert needs
   this fix.
4. Do not touch `skills/pairmode/skills/loop-breaker/procedure.md` or any
   other worker procedure — grep confirms `git clean -fd` / `git checkout .`
   appear only in `reviewer/procedure.md` in this repo (the legacy
   `agents/reviewer.md.j2` Jinja template that once duplicated this text was
   already retired per HARNESS-002; `tests/pairmode/test_templates.py`'s
   `TestReviewerAgentTemplate` is `@pytest.mark.skip`-marked for that reason —
   do not un-skip it or add assertions there).

## Tests

This is a `story_class: doc` procedure-prose change with no Python execution
surface — `skills/pairmode/skills/reviewer/procedure.md` is a markdown skill
followed by an LLM subagent, not code, and the legacy Jinja-template test
class covering an equivalent string was retired (see Instructions #4). No new
test file is expected.

`PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` must still
pass (regression check that nothing else in the suite references the old
unscoped revert text), but this story adds no new test of its own.

Verification is manual/review-time: the reviewer (cold-eyes checking this
story's own diff) reads the updated procedure.md and confirms the revert
block is scoped as described in Ensures #1-3.
