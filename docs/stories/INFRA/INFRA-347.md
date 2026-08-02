---
id: INFRA-347
rail: INFRA
title: merge-story-worktree must flip a landed story's status to complete (CER-136)
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/scripts/story_update.py
touches:
  - tests/pairmode/test_flex_build.py
  - tests/pairmode/test_index_integrity.py
  - docs/cer/backlog.md
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

CER-136 (already open, backlog HIGH): `cmd_merge_story_worktree` rebases, fast-forward-merges, and
tears down a story's worktree/branch on reviewer PASS, but never flips the landed story's `status:`
frontmatter or its Status cell in the phase doc's Stories table — both stay `draft` forever unless
someone hand-edits them. Live-hit repeatedly this project: Phase 114's checkpoint stalled on
exactly this (13 stale rows, fixed by INFRA-330); this session's own Phase 115 and Phase 116
checkpoints (2026-07-31/2026-08-01) both required a manual orchestrator-side status sync across
every landed story before `checkpoint-tag` would clear the phase-incomplete guard — the same unfixed
gap, twice, in the very session that commissioned `docs/build-loop-cold-eyes-review-20260801.md`.
That review's own §5 independently corroborates this via `index_integrity.check_index`'s
status-drift check having zero automated callers anywhere in the loop, so the drift is caught only
when a human happens to look.

This is the single most-repeated manual-fixup this project has needed at checkpoint time. Era 004's
own stated goal (`docs/eras/004-flex-operational-closeout-and-0-3-1.md`) is "zero unresolved
operational findings" — this finding is about as operational as they get.

Fix direction (per CER-136's own note): have `cmd_merge_story_worktree` flip the story's frontmatter
`status:` and its phase-doc Status cell to `complete` as part of the same merge operation
(mirroring `mark-phase-complete`'s existing phase-index flip), so a merged story is never
observably `draft`. This story should also mark CER-136 resolved in `docs/cer/backlog.md` once
landed.

**Recon finding that changes the shape of this fix:** `skills/pairmode/scripts/story_update.py`
already contains exactly the two functions this story needs — `update_story_status(story_id,
project_dir, status)` (rewrites the story file's frontmatter `status:` line in place) and
`update_phase_story_status(story_id, project_dir, status)` (locates the story's declared phase doc
via its own `phase:` frontmatter field, and rewrites the matching row's Status cell in that doc's
`## Stories` table). Both are fully implemented, tested (`tests/pairmode/test_story_update.py`), and
exposed as a standalone `story_update` CLI — but grep across the whole `skills/pairmode/scripts/`
tree shows **zero non-test callers of either function outside `story_update.py` itself**. Nothing in
`flex_build.py`'s `cmd_merge_story_worktree` (or anywhere else in the build loop) ever calls them.
This story is therefore a wiring fix, not new logic: `cmd_merge_story_worktree` needs to call the
two already-correct `story_update` functions at the point in its own flow where the merge has
already landed and it is clearing the other per-story stamps (`clear_attempt_count`,
`clear_story_bump_markers`, `_clear_active_story`, `clear_permissions_artifact`,
`_clear_gate_verdict`) — see `## Instructions` for the exact insertion point.

**Retroactive-fix decision (documented, not deferred silently):** all 11 stories already merged in
this very phase (INFRA-336 through INFRA-346) still read `status: draft` in their own frontmatter —
this is the exact CER-136 gap manifesting live in this session, not a hypothetical, and it will
still block phase 117's `checkpoint-tag` step (which checks phase completion via story status) even
after this story lands, because this fix only changes behavior for merges that happen *after* it is
built — it does not rewrite history for stories merged before it. This story deliberately does
**not** perform that retroactive bulk correction, for the same reason INFRA-330 was split out as its
own story rather than folded into a hypothetical earlier "fix the harness" story for phase 114: this
story's own `primary_files` (`flex_build.py`, `story_update.py`) and the 11 stale stories'
`primary_files` (11 unrelated `docs/stories/INFRA/*.md` files plus `docs/phases/phase-117.md`) do
not overlap, and folding a metadata-only bulk correction into a code-wiring story raises this
story's merge-conflict surface against any other phase-117 story landing concurrently for no
benefit — see `## Out of scope`. The bulk correction is called out explicitly there as required
follow-up work before phase 117 can checkpoint, not left unaddressed.

## Requires

## Ensures

<!-- State the correct signal AND the forbidden proxy (INFRA-314): e.g. "the
     write is absent after refusal; forbidden proxy: a warning line while the
     write happens anyway." -->

- `cmd_merge_story_worktree` in `skills/pairmode/scripts/flex_build.py` calls
  `story_update.update_story_status(story_id, project_path, "complete")` and
  `story_update.update_phase_story_status(story_id, project_path, "complete")` inside the same
  merge-lock critical section, after the existing per-story stamp clears (`clear_attempt_count`,
  `clear_story_bump_markers`, `_clear_active_story`, `clear_permissions_artifact`,
  `_clear_gate_verdict`) and before the final `click.echo(f"merged {branch} into {main_branch}")` —
  i.e. as part of the same command invocation that performs the merge, not a separate follow-up
  step a caller must remember to run. Forbidden proxy: a second CLI command, a `CLAUDE.build.md`
  loop instruction to call `story_update` manually after `merge-story-worktree`, or any fix that
  requires an external caller to remember an extra step — CER-136 explicitly names and rejects that
  as the weaker alternative fix direction.
- Given a merged story with a real `docs/stories/<RAIL>/<ID>.md` file whose frontmatter `status:` is
  not already `complete` (e.g. `draft` or `planned`), after `merge-story-worktree` exits 0 that
  file's frontmatter `status:` line reads `complete`. Forbidden proxy: `merge-story-worktree`
  exiting 0 while the file's `status:` is left unchanged from before the merge — the exact CER-136
  bug.
- Given that same merged story's own `phase:` frontmatter field names a phase doc
  (`docs/phases/phase-<phase>.md`) whose `## Stories` table has a row for that story ID, after
  `merge-story-worktree` exits 0 that row's Status cell reads `complete`. Forbidden proxy: the row
  left at its pre-merge value (`draft`/`planned`) while the story's own file already reads
  `complete` — the two surfaces drifting from each other is a narrower version of the same bug
  CER-136 named for both surfaces together.
- Given a merged `story_id` with **no** `docs/stories/<RAIL>/<ID>.md` file at all (the shape every
  pre-existing `TestStoryWorktreeLifecycle` test in `tests/pairmode/test_flex_build.py` uses — bare
  IDs like `WT-004`, `WT-100`, `WT-101` with no real story doc anywhere in the fixture),
  `merge-story-worktree` still exits 0, the commit still lands on the main branch, and the worktree
  and branch are still torn down — exactly as before this story. Forbidden proxy: `merge-story-
  worktree` exiting non-zero, or aborting/rolling back an already-landed merge, because the new
  status-flip call raised `FileNotFoundError`/`ValueError` for a story with no doc to flip — the
  merge has already landed at that point in the function and must not be treated as failed.
- `skills/pairmode/scripts/story_update.py`'s `update_story_status`/`update_phase_story_status`
  functions themselves are **not modified** by this story — recon (see `## Context`) confirms they
  already implement the correct rewrite behavior and already have their own passing test coverage
  in `tests/pairmode/test_story_update.py`; this story only adds a caller.
- `index_integrity.check_index`'s `status-drift` check (`skills/pairmode/scripts/
  index_integrity.py`) reports zero `status-drift` violations for a story that has both a merged
  `feat(story-<ID>)` commit and a `docs/stories/<RAIL>/<ID>.md` file, when that story was merged via
  `merge-story-worktree` after this fix lands, in a test fixture built for that purpose. Forbidden
  proxy: the check still reporting drift for a freshly-merged story because the flip only touched
  one of the two surfaces, or touched neither.
- `docs/cer/backlog.md`'s CER-136 row gains an appended `**RESOLVED Phase 117 — INFRA-347: ...**`
  sentence describing the landed fix, mirroring the CER-152/CER-153 `**RESOLVED Phase 117 — ...**`
  annotation convention already present elsewhere in the same Do Now table. No other cell or column
  in that row (Source, Date, Phase, or the rest of the finding prose) changes, and no other row in
  `docs/cer/backlog.md` is touched.
- `docs/stories/INFRA/INFRA-336.md` through `docs/stories/INFRA/INFRA-346.md` and
  `docs/phases/phase-117.md`'s Status cells for those 11 stories are **unchanged** by this story's
  build — this story's Instructions and Tests never write to any of those 12 files. (The retroactive
  correction they need is named as required follow-up work in `## Out of scope`, not performed
  here.)
- `docs/architecture.md:2675` (the story-status frontmatter data-flow row) no longer states that
  updating a story's `status:` frontmatter is "manual/advisory" with "no build-loop step call[ing]
  it automatically" — it instead accurately states that `cmd_merge_story_worktree` calls
  `story_update.update_story_status`/`update_phase_story_status` automatically on every reviewer-PASS
  merge, as of this story. Forbidden proxy: softening the sentence (e.g. "may be called
  automatically") without naming the actual caller and trigger condition.
- `tests/pairmode/test_index_integrity.py`'s modifications made necessary by this story's fix (any
  fixture/assertion that previously encoded the pre-fix "status never auto-flips" behavior) are
  committed alongside the rest of the story's declared scope — not left uncommitted in the worktree.
- `docs/architecture.md`'s **second** description of this same fact, in the "Current status
  (corrected — ...)" paragraph a few sections earlier than the line-2675 data-flow row (as of this
  writing, ~lines 1733-1741, in the phase-manifest-registration-failure discussion), is also
  updated in the same commit. That paragraph currently states "frontmatter/phase-table story
  status is not written automatically by any orchestrator step today" and that `story_update.py`
  "is just not wired into the build loop as an automatic post-commit step" — both sentences must be
  corrected to name `cmd_merge_story_worktree` as the automatic caller, consistent with the
  line-2675 fix. Search the whole file for every occurrence of "not written automatically" /
  "not wired into the build loop" / "manual/advisory" describing story-status frontmatter before
  considering this Ensures item satisfied — do not assume there are only two locations. Forbidden
  proxy: fixing only one of the two (or more) locations, leaving the file internally
  self-contradictory.

## Instructions

1. Read `cmd_merge_story_worktree` in `skills/pairmode/scripts/flex_build.py` in full (currently
   ~lines 4860-4989). Confirm the post-teardown clear sequence inside the `with _merge_lock(...)`
   block: `residue = _teardown_story_worktree(...)`, then `clear_attempt_count(...)`,
   `clear_story_bump_markers(...)` (INFRA-336), `_clear_active_story(...)`,
   `clear_permissions_artifact(...)`, `_clear_gate_verdict(...)` (INFRA-341), then
   `click.echo(f"merged {branch} into {main_branch}")`, then the `if residue:` block that may
   `sys.exit(1)`. All of this happens after the merge has already landed on `main` — nothing in
   this region can roll the merge back.

2. Read `skills/pairmode/scripts/story_update.py` in full. Confirm `update_story_status(story_id,
   project_dir, status)` rewrites the frontmatter `status:` line in `docs/stories/<RAIL>/<ID>.md`
   (raising `FileNotFoundError` if the file does not exist, `ValueError` for a malformed
   `story_id`) and `update_phase_story_status(story_id, project_dir, status)` locates the phase
   doc(s) via the story's own `phase:` field (falling back to scanning `docs/phases/*.md` only if
   the story declares no `phase:`) and rewrites the matching `## Stories` table row's Status cell —
   returning `[]` (never raising) when no phases dir, no declared phase, or no matching row exists.
   Do not modify either function — they are already correct for this story's purpose.

3. Add a module-level import to `flex_build.py`, alongside the other sibling-module imports (e.g.
   next to `from table_utils import split_table_row`):

   ```python
   from story_update import update_story_status, update_phase_story_status  # noqa: E402
   ```

   `story_update.py` imports only `schema_validator`, `state_utils`, and `table_utils` — it does not
   import `flex_build`, so this introduces no circular import (confirmed by reading
   `story_update.py`'s own imports).

4. Immediately after `_clear_gate_verdict(project_path, story_id)` and before
   `click.echo(f"merged {branch} into {main_branch}")` in `cmd_merge_story_worktree`, add:

   ```python
   # INFRA-347 (CER-136): the merge already landed — flip the two status
   # surfaces CER-136 found perpetually stale: the story's own frontmatter
   # status: and its phase-doc Stories-table Status cell. Mirrors
   # mark-phase-complete's phase-index flip (_mark_phase_complete_in_index)
   # at the story level. Fail-open: a synthetic worktree with no real
   # docs/stories/docs/phases tree (the pre-existing merge tests use bare
   # story IDs like WT-004 with no story doc at all) must not turn an
   # already-landed merge into a command failure.
   try:
       update_story_status(story_id, project_path, "complete")
   except (FileNotFoundError, ValueError) as exc:
       click.echo(
           f"warning: merge-story-worktree: could not flip status for "
           f"{story_id}: {exc}",
           err=True,
       )
   else:
       # update_phase_story_status never raises for a missing phases dir or
       # an absent/unmatched Stories-table row (returns [] instead) — only
       # gated on update_story_status having succeeded so the two writes
       # stay ordered and a genuine story-id/story-file problem skips both.
       update_phase_story_status(story_id, project_path, "complete")
   ```

5. Do not add a second CLI command or a `CLAUDE.build.md` post-merge instruction — the chosen fix
   direction is the in-command flip inside `cmd_merge_story_worktree` itself (Ensures 1).

6. Add new tests to `tests/pairmode/test_flex_build.py` in `TestStoryWorktreeLifecycle` (the class
   already containing the other `merge-story-worktree` tests), reusing the file's existing
   `_write_story`, `_write_phase_manifest`, `_init_git_repo`, `_create_worktree`, `_commit_in`
   helpers:
   a. `_write_story` currently hardcodes `status: planned` in the frontmatter it writes with no
      `status` parameter — add an optional `status: str = "planned"` keyword argument to `_write_story`
      and use it to build the frontmatter's `status:` line, so fixtures can start a story at `draft`
      without hand-rolling frontmatter text. This is the single, minimal extension needed; do not
      otherwise change `_write_story`'s existing behavior or signature order (keep it keyword-only
      via the existing `*`).
   b. `test_merge_story_worktree_flips_story_status_to_complete` — write a story doc with
      `_write_story(tmp_path, "WT-200", phase="200", status="draft")`, write a matching phase
      manifest with `_write_phase_manifest(tmp_path, "200", [("WT-200", "title", "draft")])`, then
      `_init_git_repo`, `_create_worktree(tmp_path, "WT-200")`, commit a file in the worktree, and
      run `merge-story-worktree`. Assert `result.returncode == 0`, that the story file's frontmatter
      now contains `status: complete`, and that the phase manifest's `WT-200` row's Status cell now
      reads `complete`.
   c. `test_merge_story_worktree_without_story_doc_still_succeeds` — no `docs/stories` file for the
      merged story_id at all (mirrors the existing `WT-004`-style fixtures already in this class).
      Assert `merge-story-worktree` still exits 0, the commit still lands on `main`, and the
      worktree/branch are still gone — i.e. this story's fix does not regress any pre-existing test
      in `TestStoryWorktreeLifecycle`.
   d. `test_merge_story_worktree_flips_status_even_without_matching_phase_row` — write a story doc
      via `_write_story` (declaring a `phase` value) but do not write any matching phase manifest
      (or write one with no row for that story ID). Assert the story frontmatter still flips to
      `status: complete` after the merge — the story-level write must succeed independently of
      whether a phase-doc row exists to update.

7. Add one test (in `tests/pairmode/test_index_integrity.py`, which already exists) that builds a
   fixture with a merged story's `feat(story-<ID>)` commit and a `docs/stories/<RAIL>/<ID>.md` file
   whose `status:` is `complete` (post-fix state), and asserts `index_integrity.check_index` returns
   no `status-drift` violation for that story ID — confirming the fixed status surfaces are exactly
   what the existing drift check expects.

8. In `docs/cer/backlog.md`, locate CER-136's row in the `## Do Now` table (it currently ends
   "**Absorbed at spec time by INFRA-347 (Phase 117)** — resolution annotation lands when that
   story completes."). Append a `**RESOLVED Phase 117 — INFRA-347: `cmd_merge_story_worktree` now
   calls `story_update.update_story_status`/`update_phase_story_status` after every successful
   merge, flipping both the story's frontmatter `status:` and its phase-doc Status cell to
   `complete` in the same command invocation.**` sentence, mirroring the CER-152/CER-153 annotation
   style already present in the same file, immediately before the trailing
   `| <source> | <date> | <phase> |` cells of that row. Do not alter any other cell in that row or
   any other row in the file.

9. Do not edit `docs/stories/INFRA/INFRA-336.md` through `docs/stories/INFRA/INFRA-346.md` or their
   rows in `docs/phases/phase-117.md` — see `## Out of scope` for why, and flag to the operator (in
   the build/review summary, not by editing those files) that a dedicated retroactive-correction
   story is still needed before phase 117's `checkpoint-tag` step, mirroring INFRA-330's role for
   phase 114.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_build.py -k "merge_story_worktree" -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_story_update.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_index_integrity.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Acceptance: the new `merge-story-worktree` tests (6b/6c/6d above) pass, the new `check-index`
fixture test (7 above) passes, `test_story_update.py`'s pre-existing suite is unaffected (this story
does not modify `story_update.py`), and the full `tests/pairmode/` suite is green — in particular
every pre-existing `TestStoryWorktreeLifecycle` test (the bare-ID `WT-004`/`WT-100`/`WT-101`-style
fixtures with no real story doc) must still pass unchanged, proving the fail-open contract in
Ensures holds.

## Out of scope

- Retroactive bulk-correction of INFRA-336 through INFRA-346's already-stale `status: draft`
  frontmatter and their `docs/phases/phase-117.md` Status cells. This is a deliberate decision, not
  an oversight: this story's fix only prevents the gap for merges that happen after it lands; it
  does not rewrite history. The 11 stale stories still need a dedicated metadata-only correction
  story before phase 117's `checkpoint-tag` step can pass its phase-completion check, mirroring
  INFRA-330's precedent for phase 114's 13 stale rows. That follow-up story should be scoped the
  same way INFRA-330 was: pure status-value edits to the 11 story files plus `phase-117.md`, no
  `flex_build.py` change, verified via `check-index` reporting zero remaining INFRA-3xx
  `status-drift` violations and `next-action --json` no longer returning
  `checkpoint-guard-failed:phase-incomplete` for phase 117.
- Wiring `index_integrity.check_index` into an automated pre-checkpoint gate. Its `status-drift`
  check having zero automated callers is a real, separately-findable gap (independently corroborated
  by `docs/build-loop-cold-eyes-review-20260801.md` §5) — this story only ensures the check has
  nothing new to report for future merges; it does not add a caller that runs it automatically.
- CER-136's named alternative fix direction — "add an explicit post-merge step to the
  `CLAUDE.build.md` loop that calls a dedicated status-flip command right after
  `merge-story-worktree` succeeds." This story implements the other, chosen direction (the in-command
  flip inside `cmd_merge_story_worktree` itself) instead; no `CLAUDE.build.md` or template change is
  made.
- Any change to `discard-story-worktree`'s behavior. A discarded story never lands on `main`, so no
  status flip applies there — `discard-story-worktree` is unrelated to CER-136's finding.
- Any change to `story_update.py`'s own logic, its standalone CLI, or its existing test coverage in
  `tests/pairmode/test_story_update.py` — recon confirms both functions are already correct; this
  story only adds a caller in `flex_build.py`.

<!-- SPEC-PREFLIGHT NOTE: the scan flags tests/pairmode/test_story_update.py and
     docs/stories/INFRA/INFRA-336.md..INFRA-346.md as named-but-not-in-scope. Both are
     intentional: test_story_update.py is run (Tests §3) as a no-regression check on a file
     this story does not edit, so it is correctly absent from primary_files/touches; the
     INFRA-336..346 story files are named only to say explicitly that this story does NOT
     edit them (Instructions 9, Out of scope) — adding them to touches would incorrectly
     declare them in scope for writes this story deliberately never makes. -->
