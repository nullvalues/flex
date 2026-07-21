---
id: INFRA-224
rail: INFRA
title: Per-build-cycle git worktree isolation for builder/reviewer story cycles
status: planned
phase: "96"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - CLAUDE.build.md
  - .gitignore
  - skills/pairmode/skills/builder/procedure.md
  - skills/pairmode/skills/reviewer/procedure.md
  - tests/pairmode/test_flex_build.py
touches:  # If this story changes any documented architecture, add docs/architecture.md to this list.
---

## Requires

- [[INFRA-223]] does not need to land first — the two stories are
  independent defense-in-depth layers (scoped revert protects the current
  same-worktree loop; this story adds physical isolation for a future
  worktree-per-cycle loop). Either can build first.
- `skills/pairmode/scripts/sync.py`'s `sync_project` / template-render
  mechanism exists and is the established way this project keeps its own
  `CLAUDE.build.md` in sync with the canonical
  `skills/pairmode/templates/CLAUDE.build.md.j2` source.

## Context

Today's build loop runs every builder and reviewer subagent inside the same
single working directory (`/mnt/work/flex-harness`). Because the loop is
strictly sequential (one story at a time — confirmed: `CLAUDE.build.md`'s
`while true` loop has no fan-out), no two story cycles are *currently*
racing on the same files. But nothing structurally prevents it: a future
change to fan out multiple `next-action` cycles concurrently (or a stray
concurrent session sharing this worktree) would let one story's builder edit
files a second story's builder is also touching, and — per the RELEASE-022
incident — a reviewer's revert in one story's cycle can already destroy
untracked content that has nothing to do with it, regardless of concurrency.

This story adds the structural half of the fix: each story's builder+reviewer
cycle runs in its own disposable `git worktree`, created fresh from the
current branch tip before the builder is spawned and torn down (merged on
PASS, discarded on FAIL) after the reviewer finishes. A worktree is a
separate working directory with its own file tree — a builder or reviewer
operating inside `.pairmode-worktrees/<story-id>/` cannot see, edit, or
`git clean` anything in the main worktree, full stop, independent of how
carefully any single agent's revert command is scoped. Combined with
[[INFRA-223]]'s scoped revert (defense-in-depth for the same-worktree case,
e.g. a legacy story with no declared scope), this closes both the current
same-worktree collateral-damage risk and the future cross-story concurrency
risk in one mechanism.

## Ensures

1. `flex_build.py create-story-worktree --story-id <ID> --project-dir .`
   creates a new git worktree at `.pairmode-worktrees/<story-id>/` on a new
   branch `pairmode/<story-id>` created from the current branch's HEAD, and
   prints the absolute worktree path to stdout (the orchestrator captures
   this and passes it to the builder/reviewer as the directory they must
   operate in).
2. `create-story-worktree` fails loudly (non-zero exit, clear stderr message)
   if a worktree or branch for that story ID already exists, rather than
   silently reusing or overwriting one.
3. `flex_build.py merge-story-worktree --story-id <ID> --project-dir .`
   (called after the reviewer commits inside the worktree, on PASS): rebases
   `pairmode/<story-id>` onto the current tip of the main worktree's branch,
   fast-forward-merges the rebased branch into the main worktree's branch,
   then removes the worktree (`git worktree remove`) and deletes the
   `pairmode/<story-id>` branch. Fails loudly with no partial state change if
   the rebase hits a conflict (the orchestrator surfaces this to the user;
   auto-resolution is out of scope).
4. `flex_build.py discard-story-worktree --story-id <ID> --project-dir .`
   (called on reviewer FAIL): removes the worktree — including any
   uncommitted or untracked content the builder created inside it — and
   deletes the `pairmode/<story-id>` branch, **without running any command
   against the main worktree's working directory**. This is the structural
   guarantee: a FAIL in a story's worktree cannot touch the main worktree's
   files, tracked or untracked, regardless of what the reviewer's revert
   logic does.
5. `.pairmode-worktrees/` is added to `.gitignore`.
6. `skills/pairmode/templates/CLAUDE.build.md.j2`'s build loop is updated so
   the orchestrator: calls `create-story-worktree` before spawning the
   builder; instructs the builder and reviewer subagent shells to operate
   inside the returned worktree path (not the main project directory); calls
   `merge-story-worktree` after a reviewer PASS commit, or
   `discard-story-worktree` after a reviewer FAIL.
7. This project's own `CLAUDE.build.md` (currently a synced artifact of the
   template, not independently hand-maintained) is re-synced from the
   updated template via the existing `sync.py` mechanism, so flex-harness's
   own build loop uses worktree isolation starting with this story's own
   checkpoint cycle.
8. The existing sequential build loop (one story at a time) continues to
   work end-to-end through a full builder → reviewer → commit cycle with
   worktree isolation wired in — verified by exercising it against a real
   throwaway story in a test fixture repo, not by running it against this
   live project.

## Instructions

1. Add three new commands to `skills/pairmode/scripts/flex_build.py`
   (mirroring the existing `@flex_build.command(...)` pattern used
   throughout the file, e.g. `cmd_current_phase` at line ~518):
   `create-story-worktree`, `merge-story-worktree`, `discard-story-worktree`.
   Each takes `--story-id` and `--project-dir` (default `.`).
2. Worktree path convention: `<project_dir>/.pairmode-worktrees/<story-id>/`.
   Branch convention: `pairmode/<story-id>`. Use `git worktree add -b
   pairmode/<story-id> .pairmode-worktrees/<story-id> HEAD` (or the
   project's current branch tip) for creation.
3. `merge-story-worktree`: run the rebase and fast-forward merge from the
   **main worktree's** directory (`project_dir`), not from inside the
   worktree being torn down. Use `git rebase` against the main worktree's
   current branch, then `git merge --ff-only`. On any non-zero exit from
   rebase, abort the rebase (`git rebase --abort`) and exit non-zero with
   the rebase's error output — do not attempt automatic conflict resolution.
4. `discard-story-worktree`: use `git worktree remove --force
   .pairmode-worktrees/<story-id>` (force, since the worktree may have
   uncommitted changes the builder never committed — that's expected and
   fine to discard, the whole point of the isolation) followed by `git
   branch -D pairmode/<story-id>`. Run both from `project_dir`; never `cd`
   into or run any command targeting the worktree path itself for this
   command.
5. Add `.pairmode-worktrees/` to `.gitignore` (top-level, near the existing
   `__pycache__/`/`.venv/` entries).
6. Update `skills/pairmode/templates/CLAUDE.build.md.j2`'s `## Build loop`
   section to reflect the worktree-wrapped cycle:
   ```
   while true:
       a = flex_build.py next-action --json --project-dir .
       if a.action == "done": break
       if a.action is a story-build action (spawn-builder/spawn-reviewer):
           wt = flex_build.py create-story-worktree --story-id a.scalar --project-dir .
           spawn leaf-worker-for(a.action) with scalar=a.scalar, model=a.model, cwd=wt
           on reviewer PASS: flex_build.py merge-story-worktree --story-id a.scalar --project-dir .
           on reviewer FAIL: flex_build.py discard-story-worktree --story-id a.scalar --project-dir .
       else:
           spawn leaf-worker-for(a.action) with scalar=a.scalar, model=a.model
       record result via flex_build.py record-attempt ...
   ```
   Checkpoint-stage workers (`checkpoint-security`, `checkpoint-intent`,
   `checkpoint-docs`) are read-mostly/advisory and never commit — they stay
   on the main worktree, unwrapped. Only `spawn-builder`/reviewer-equivalent
   actions that write and commit code get worktree isolation.
7. After updating the template, run this project's own `pairmode sync` (or
   the equivalent `sync.py` invocation used elsewhere in this repo's own
   history) to re-render `CLAUDE.build.md` from the updated template, so
   this repo's own build loop picks up worktree isolation starting next
   cycle. Confirm the resulting `CLAUDE.build.md` reads correctly (no
   template-render artifacts).
8. Builder/reviewer procedure docs
   (`skills/pairmode/skills/builder/procedure.md`,
   `skills/pairmode/skills/reviewer/procedure.md`) currently assume they
   operate against `project_dir`/the current working directory implicitly.
   Add one sentence to each's "Shell instruction" section noting that when
   the orchestrator supplies a worktree path, all file reads/writes/commits
   happen there instead of the main project directory — everything else in
   each procedure (input contract, checklist, commit logic) is unchanged.

## Out of scope

- **True concurrent multi-story dispatch** (running N builders in parallel
  against N worktrees at once). This story delivers the isolation
  *mechanism*, wired into the still-sequential existing loop. Actually
  fanning out `next-action` to select and lock multiple stories
  concurrently requires resolver-level changes (state.json concurrent
  access, attempt-counter races, story-selection locking) — a separate,
  larger follow-up story. File to `docs/cer/backlog.md` Do Later if not
  picked up immediately after this story.
- **Downstream fleet re-sync** of the updated `CLAUDE.build.md.j2` to the 14
  in-scope fleet projects — same rollout pattern as INFRA-209, a separate
  future story once this is proven in flex-harness's own loop.
- Worktree isolation for `security-auditor`, `intent-reviewer`, and
  `checkpoint-docs` workers — they don't write or commit, so they stay
  unwrapped on the main worktree (Instructions #6).

## Tests

Add to `tests/pairmode/test_flex_build.py` (new test class, e.g.
`TestStoryWorktreeLifecycle`), using a `tmp_path` git repo fixture (this repo
already has a git-fixture pattern elsewhere in the test suite — reuse it,
don't invent a new one):

- `test_create_story_worktree_creates_branch_and_directory`: after
  `create-story-worktree`, the worktree directory exists, `git worktree
  list` shows it, and the new branch exists.
- `test_create_story_worktree_fails_if_already_exists`: calling it twice for
  the same story ID exits non-zero on the second call.
- `test_worktree_edits_isolated_from_main_tree`: a file edited inside the
  worktree is not visible/changed in the main worktree's working directory
  until merged.
- `test_merge_story_worktree_lands_commit_on_main_branch`: commit a change
  inside the worktree, run `merge-story-worktree`, assert the commit is now
  on the main worktree's branch and the worktree/branch no longer exist.
- `test_merge_story_worktree_rebases_past_intervening_main_commits`: commit
  something new on the main branch *after* the worktree was created but
  *before* merging; assert the merge still succeeds (rebase handles it) and
  both commits are present in the final history.
- `test_merge_story_worktree_conflict_aborts_cleanly`: construct a rebase
  conflict; assert non-zero exit, the rebase is aborted (no lingering
  `.git/rebase-merge` state), and the main worktree is unaffected.
- `test_discard_story_worktree_removes_uncommitted_changes_only_in_worktree`:
  create untracked/uncommitted content inside the worktree, run
  `discard-story-worktree`, assert the worktree is gone and the main
  worktree's own untracked content (a fixture file created outside the
  worktree, mirroring the RELEASE-022 `docs/stories/CORE/`-style scenario)
  is untouched.

Run: `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`
