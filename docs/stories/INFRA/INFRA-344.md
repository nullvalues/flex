---
id: INFRA-344
rail: INFRA
title: Commit spec-writer output before create-story-worktree branches off HEAD
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - skills/pairmode/scripts/flex_build.py
touches:
  - docs/architecture.md
  - tests/pairmode/test_flex_build.py
  - tests/pairmode/test_stage_integration.py
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

HIGH finding F10 of `docs/build-loop-cold-eyes-review-20260801.md` (opus), matching a pre-existing
operator-memory item ("commit spec before worktree — worktree snapshots git HEAD, not the working
tree") that confirms the harness itself still has no enforcement for a gap the operator already had
to learn about live. Row 2 dispatches the spec-writer against the main worktree; the spec-writer's
own procedure explicitly says "Never commit — the orchestrator does that"; but neither
`CLAUDE.build.md` copy actually instructs the orchestrator to commit the elaborated spec before the
next step. Next poll: `needs_spec` reads False from the working tree (the file exists on disk), so
`spawn-builder` dispatches, and `create-story-worktree` branches from `HEAD` (`flex_build.py`) —
which does not include the uncommitted spec elaboration. The builder's worktree contains the
pre-elaboration stub, not the spec it was actually elaborated to. The test helper
`_create_worktree` in `test_flex_build.py` currently enshrines this broken pattern (creates a
worktree without first committing a pending spec change) and asserts success — that assertion will
need updating alongside the fix.

Fix direction: either add an explicit commit step to `CLAUDE.build.md`'s dispatch flow right after
a `spawn-spec-writer` action returns (before the next poll), or have `create-story-worktree` itself
detect and refuse/auto-commit an uncommitted change to the target story's own spec file before
branching. Extend INFRA-336's integration-test harness to cover this sequence
(`spawn-spec-writer → create-story-worktree` and assert the worktree's spec file matches the
elaborated content, not the stub).

**Decision this story is built on (resolved by investigation, not left open for the
builder):** fix both layers, not either/or, because they close different halves of the
gap and this session's own live workaround already proves the prose-only layer needs a
human to remember it every time.

1. **`CLAUDE.build.md`'s dispatch flow (option a) is the primary fix**, because it is
   the layer that must actually run on every real dispatch, not just the layer that
   catches the miss after the fact. Fresh read of the current `while true` loop
   (`CLAUDE.build.md:17-30`, twice-modified this phase by INFRA-340/INFRA-341) confirms
   there is still no `spawn-spec-writer` branch — it falls through the generic `else`
   (`CLAUDE.build.md:27-28`), which spawns the leaf worker and does nothing else before
   the loop's next `next-action` poll. This story adds an explicit `spawn-spec-writer`
   branch, mirroring the explicit `spawn-gate-worker` branch INFRA-341 already
   established as this file's precedent for "spawn, then do one more thing with the
   result before re-polling" — the branch commits the single story file the spec-writer
   wrote, scoped to that one path, before the loop's next iteration.
2. **`create-story-worktree`'s own refuse-check (option b) is a required second layer,
   not an optional alternative**, because `CLAUDE.build.md` is prose an orchestrator
   agent executes, not code the harness enforces — the exact gap this story exists to
   close was itself created by a prose promise (`CLAUDE.build.md`'s own comment: "the
   orchestrator does that") that nothing actually implemented for three phases. This is
   also the only reading consistent with `docs/ideology.md`'s "Never silently pass
   contradictions" constraint ("flex must never allow a development action to proceed
   without validating it against previous decisions... Silent bypass is never
   permitted") and its established fail-loud precedent in this exact function
   (INFRA-296/CER-115: a missing permissions artifact tears the worktree down and exits
   1, not a warning while the worktree is handed out anyway). `create-story-worktree`
   gains a check, before it creates anything, for an uncommitted change (staged,
   unstaged, or untracked) to the target story's own spec file only — not the whole
   working tree — and refuses (exit 1, no worktree, no branch) rather than silently
   branching a builder off a HEAD that predates the elaboration.
3. **The spec-writer procedure's "Never commit — the orchestrator does that"
   (`skills/pairmode/skills/spec-writer/procedure.md:295`) is correct and is NOT
   corrected by this story.** It already correctly names the orchestrator as the
   committer — the gap was that `CLAUDE.build.md` never implemented what that line
   promises, not that the line promises the wrong thing. This session's live workaround
   (the orchestrator manually telling spec-writer *agents* to self-commit with a
   `spec(ID): ...` prefix) is the operator improvising around the missing
   `CLAUDE.build.md` step, not evidence the procedure's non-negotiable is stale —
   spec-writer stays a non-committing role (its own Non-negotiables section: "Write
   only to `docs/stories/<RAIL>/<scalar>.md`. No other files." — a spec-writer that also
   ran `git commit` would already violate that write-target boundary). Fixing
   `CLAUDE.build.md` (Instructions 1-2 below) removes the need for the workaround; no
   change to `skills/pairmode/skills/spec-writer/procedure.md` is in scope.
4. **The commit fires unconditionally**, regardless of the returned `SPEC-RESULT`
   `status` (`"done"` or `"revised"`) — `needs_spec`'s Ensures-count check
   (`next_action.py`, RESOLVER-009) reads the working-tree file directly and does not
   consult `status` at all, so an uncommitted `"revised"` elaboration is exactly as
   exploitable a gap as an uncommitted `"done"` one the moment a human later approves it
   and the loop resumes.

## Requires

1. **INFRA-336's stage-to-stage integration-test harness merged**
   (`6dd03878`, `tests/pairmode/test_stage_integration.py`) — `_scaffold_project`,
   `_invoke`, `_next_action_json`, and the module's own docstring naming INFRA-344 as
   one of the stories expected to add sibling test functions here. This story extends
   that harness rather than building a new one.
2. `_story_path` and `_run_git` (`flex_build.py`, INFRA-224) as the existing primitives
   the new refuse-check reuses — no new path-resolution or git-invocation helper is
   introduced.
3. `cmd_create_story_worktree`'s existing INFRA-296/CER-115 all-or-nothing, fail-loud
   shape (permissions-generation failure tears the worktree down and exits 1 before
   handing anything to a builder) as the precedent this story's new check follows in
   both placement (before any worktree/branch mutation) and failure style (loud exit,
   not a stderr warning while proceeding).
4. `ACTION_SUBAGENT_TYPE`'s existing `spawn-gate-worker: gate-worker` entry
   (`CLAUDE.build.md:15`) and INFRA-341's explicit `spawn-gate-worker` branch
   (`CLAUDE.build.md:26`) as the structural template for this story's new
   `spawn-spec-writer` branch — same "explicit branch before the generic `else`,
   with one follow-up action before the next poll" shape.

## Ensures

1. **`CLAUDE.build.md`'s `while true` loop gains an explicit `spawn-spec-writer`
   branch** (before the generic `else`, alongside the existing `spawn-builder` and
   `spawn-gate-worker` branches): it spawns the `spec-writer` leaf worker exactly as
   the generic `else` did, then — regardless of the returned `SPEC-RESULT` `status` —
   runs, in the main project directory (never inside a worktree; spec writes are
   documented as not worktree-scoped), `git add docs/stories/<RAIL>/<scalar>.md && git
   commit -q -m "spec(<scalar>): elaborate stub story"` before the loop's next
   `next-action` poll. Verifiable: `grep -n 'spawn-spec-writer' CLAUDE.build.md` shows
   an explicit `elif`/`if` branch (not only the `ACTION_SUBAGENT_TYPE` map entry), and
   that branch's line(s) name a `git commit` with the `spec(` prefix. Forbidden proxy:
   a comment describing the commit without an actual `git add`/`git commit` invocation
   in the pseudocode — this file's own convention (INFRA-341's `spawn-gate-worker`
   branch) is to name the exact command, not just describe intent in prose.
2. **The commit is scoped to exactly the one story file** — never `git add -A` or
   `git add docs/`. Verifiable: the branch's `git add` argument is the single resolved
   story path, not a directory or wildcard.
3. **`skills/pairmode/templates/CLAUDE.build.md.j2` carries the same branch**, using
   `{{ pairmode_scripts_dir }}`-style templating consistent with the rest of that file,
   and its `ACTION_SUBAGENT_TYPE` map gains `spawn-spec-writer: spec-writer` (currently
   absent from the `.j2` map, unlike the live `CLAUDE.build.md`'s map, which already has
   it) — mirroring INFRA-341's precedent of bringing only the pieces a story's own new
   branch needs into `.j2`, not the full reconciliation (INFRA-342's job, sequenced
   after this story per the phase Ordering note). Verifiable:
   `grep -n 'spawn-spec-writer' skills/pairmode/templates/CLAUDE.build.md.j2` shows both
   the branch and the map entry.
4. **`create-story-worktree` (`cmd_create_story_worktree`, `flex_build.py`) refuses,
   before creating any worktree or branch, when the target story's own spec file has an
   uncommitted change against `HEAD`** (staged, unstaged, or untracked — any non-empty
   `git status --porcelain -- <path>` for exactly that one path). On refusal: exit 1,
   stderr names the exact story spec path, no `.pairmode-worktrees/<ID>/` directory and
   no `pairmode/<ID>` branch exist afterward (byte-identical git state to before the
   call, mirroring the existing `test_c4_permissions_failure_leaves_git_state_byte_identical`
   assertion shape), and nothing is written to stdout. Forbidden proxy: a stderr warning
   while `git worktree add` still runs — the INFRA-296 precedent (Requires 3) is fail
   loud and stop, not warn and proceed.
5. **The check is scoped to exactly the target story's own spec file, not the whole
   working tree.** An uncommitted change to an unrelated file (a different story's
   spec, a source file, anything outside `docs/stories/<RAIL>/<ID>.md`) does not trigger
   the refusal. Verifiable via a new test that dirties an unrelated file, then confirms
   `create-story-worktree` still succeeds for a story whose own spec file is clean.
6. **A committed, clean spec file (no diff against `HEAD` for that one path) is
   unaffected** — `create-story-worktree` succeeds exactly as it did before this story,
   with no new preconditions for the already-passing path. No existing
   `create-story-worktree` test in `tests/pairmode/test_flex_build.py` or
   `tests/pairmode/test_stage_integration.py` may change its asserted `returncode`/
   `exit_code` as a result of this story landing (Instructions 6-8 name exactly which
   test helpers must gain a commit step so this holds).
7. **`tests/pairmode/test_flex_build.py`'s `_create_worktree` helper commits the story
   spec it writes.** When the helper writes a minimal story spec (the `if not (...).exists():
   _write_story(...)` branch), it commits that one file (`git add` the resolved path,
   `git commit -q -m ...`) before invoking `create-story-worktree` — closing exactly the
   gap this story's Context names ("the test helper currently enshrines this broken
   pattern"). Verifiable: reading the updated helper shows the write followed by a
   commit of that same path before the `_run("create-story-worktree", ...)` call.
8. **`TestCreateStoryWorktreeAtomicity`'s `_write_raw_story` helper commits the raw
   story it writes**, for the same reason as Ensures 7 — its four call sites
   (`test_c4`, `test_c5`, `test_c6`, `test_b4_check_story_scope_...`) write a story spec
   directly (not via `_create_worktree`) and then call `create-story-worktree` (or
   `check-story-scope`) expecting the *content* of that spec (malformed vs. corrected
   frontmatter) to be judged — not a dirty-git refusal that would short-circuit before
   the content is ever read. `test_c4`'s and `test_c5`'s existing assertions (malformed
   frontmatter fails with a permissions error; the corrected rewrite on the second call
   succeeds) continue to exercise the permissions-parsing path they name in their own
   docstrings, not the new refuse-check.
9. **`tests/pairmode/test_stage_integration.py`'s `_scaffold_project` commits every
   file it writes** (the index, phase, and story spec written by `_write_index`/
   `_write_phase`/`_write_story`) before returning, so its three existing callers
   (`TestEscalationLadderAdvancesAfterDiscard`,
   `TestEscalationLadderAdvancesAfterDiscardMarker`, and this story's own new test) keep
   calling `create-story-worktree` against a clean spec. `TestRow8ContextPauseRemoved`'s
   manual scaffold sequence (which does not call `_scaffold_project`) gains the same
   commit step at the equivalent point, immediately before its first
   `create-story-worktree` call.
10. **A new end-to-end test in `tests/pairmode/test_stage_integration.py` drives the
    exact sequence named in this story's Context**: elaborate a stub story's spec
    in-process (simulating the spec-writer's Step 6 write — overwrite the scaffolded
    story file with elaborated content distinguishable from the stub, e.g. a marker
    string in a new `## Ensures` line), commit it exactly as the new `CLAUDE.build.md`
    branch would (Ensures 1), then call `create-story-worktree` via `_invoke` and assert
    the worktree's checked-out copy of `docs/stories/<RAIL>/<ID>.md` contains the
    elaborated marker string, not the pre-elaboration stub content. A second assertion
    in the same test (or a sibling test) proves the negative: calling
    `create-story-worktree` on an *uncommitted* elaboration (same write, no commit)
    exits non-zero and no worktree is created — proving Ensures 4 fires in the exact
    dispatch-flow shape (spec-writer write → \[missing commit\] → create-story-worktree)
    the F10 finding describes, not merely in a synthetic unit fixture.
11. **`docs/architecture.md`'s "Pairmode build loop" § worktree section gets a dated
    INFRA-344 addendum** (following the file's existing append-only convention for this
    section), recording: `create-story-worktree` now refuses when the target story's
    own spec file has an uncommitted change against `HEAD`, and `CLAUDE.build.md`'s
    `spawn-spec-writer` branch commits the elaborated spec before the next poll —
    together closing the gap where a worktree could be created from a HEAD that
    predates the spec-writer's elaboration.
12. **No regression.** Full suite green without `-x` (project lesson: `-x` can mask a
    pre-existing failure): `uv run pytest tests/pairmode/ -q` (no `-x`).
13. **Grammar-unchanged.** No new action type, no `ACTIONS`/`_SPAWN_ACTIONS` membership
    change, no `SCHEMA_VERSION` bump — this story is dispatch-flow prose plus one new
    precondition check inside an existing CLI command, not a resolver-grammar change.

## Instructions

1. Read `CLAUDE.build.md`'s current `while true` loop (`CLAUDE.build.md:17-30`) fresh —
   it has been modified twice this phase (INFRA-340, INFRA-341); do not trust line
   numbers cited elsewhere in this spec. Read `skills/pairmode/skills/spec-writer/procedure.md`
   in full (confirm the "Never commit" non-negotiable and the single-file write-target
   boundary this story relies on, per Context decision 3). Read `cmd_create_story_worktree`
   (`flex_build.py`) in full, including its INFRA-296 permissions-failure teardown path,
   as the fail-loud precedent for the new check.
2. In `CLAUDE.build.md`, add an explicit `elif a.action == "spawn-spec-writer":` branch
   (before the generic `else`), mirroring the existing `spawn-gate-worker` branch's
   inline-comment density: spawn the leaf worker, then name the exact
   `git add docs/stories/<RAIL>/<scalar>.md && git commit -q -m "spec(<scalar>):
   elaborate stub story"` command run in the main project directory, and note this
   happens regardless of the returned `SPEC-RESULT` `status` and before the loop's next
   `next-action` poll (Ensures 1, 2, 4-decision). Reference INFRA-344 and F10 in the
   trailing comment, matching this file's existing citation style. Update
   `ACTION_SUBAGENT_TYPE`'s trailing comment if the new branch changes what the generic
   `else` covers.
3. Apply the same branch, in the same relative position, to
   `skills/pairmode/templates/CLAUDE.build.md.j2`, using `{{ pairmode_scripts_dir }}` in
   place of the hardcoded absolute path (matching every other `.j2` line's templating
   convention), and add `spawn-spec-writer: spec-writer` to the `.j2`'s
   `ACTION_SUBAGENT_TYPE` map (Ensures 3) — do not otherwise reconcile the two files'
   other divergences; that is INFRA-342's job.
4. In `flex_build.py`'s `cmd_create_story_worktree`, immediately after
   `_validate_story_id_or_exit(story_id)` and before the `wt_abs.exists()` check, add
   the refuse-check (Ensures 4-6): resolve the story's spec path via `_story_path`,
   compute it relative to `project_path`, run
   `_run_git(["status", "--porcelain", "--", <rel_path>], project_path)`. If the git
   command itself fails (non-zero return, e.g. not a git repo) do not block on it — let
   the subsequent `git worktree add` call surface that failure with its own clearer
   error (this check's job is narrowly the uncommitted-spec case, not general git-repo
   validation). If it succeeds and `result.stdout.strip()` is non-empty, echo an error
   naming the exact story spec path and instructing the operator to commit it
   (`spec(<ID>): ...`) before retrying, and `sys.exit(1)` — do not create the worktree,
   do not stamp `current_story`, do not generate permissions.
5. Update `cmd_create_story_worktree`'s docstring to document the new precondition,
   alongside its existing INFRA-224/INFRA-238/INFRA-296 references.
6. In `tests/pairmode/test_flex_build.py`'s `_create_worktree` helper, add a commit of
   the story spec immediately after the `_write_story(project, story_id)` call, inside
   the `if not (...).exists():` branch (Ensures 7). Reuse the existing `_git`
   subprocess-invocation style already present in this file rather than introducing a
   new helper.
7. In the same file's `TestCreateStoryWorktreeAtomicity._write_raw_story`, add the same
   commit step after the write (Ensures 8) — every call site in that class calls
   `create-story-worktree` (or `check-story-scope`) immediately after, so committing
   inside the helper covers `test_c4`, `test_c5`, `test_c6`, and
   `test_b4_check_story_scope_exits_1_on_malformed_frontmatter` without touching each
   call site individually. Confirm `test_c5`'s second (corrected) write also gets its
   own follow-up commit via the same helper call.
8. In `tests/pairmode/test_stage_integration.py`, add a commit step to the end of
   `_scaffold_project` (after `_enable_effort_tracking`, committing `docs/` — `.companion/`
   is gitignored and need not be added) and to `TestRow8ContextPauseRemoved`'s manual
   scaffold sequence at the equivalent point (Ensures 9). Reuse `_init_git_repo`'s
   existing `subprocess.run(["git", ...])` style already present in this file.
9. Add the new end-to-end test named in Ensures 10 to `tests/pairmode/test_stage_integration.py`,
   as a new test class/function reusing `_scaffold_project`/`_invoke` per the module's
   own stated purpose (its docstring already names INFRA-344 as an expected extender).
10. Add the negative-path unit test named in Ensures 5 (unrelated-file dirt does not
    block) and confirm the existing `TestStoryWorktreeLifecycle`/
    `TestCreateStoryWorktreeProvisioning`/`TestCreateStoryWorktreeAtomicity` suites in
    `test_flex_build.py` still pass unchanged after steps 6-7 (Ensures 6).
11. Update `docs/architecture.md` per Ensures 11.
12. Run the full suite without `-x` and confirm green (Ensures 12).

**Do not:** modify `skills/pairmode/skills/spec-writer/procedure.md`'s "Never commit"
non-negotiable or its single-file write-target boundary (Context decision 3 — it is
correct as written); make the spec-writer *agent* itself run `git commit` (that would
violate the same write-target boundary and duplicate the fix at the wrong layer);
widen the refuse-check to the whole working tree or to any file outside the one target
story's own spec path (Ensures 5's forbidden case); use `git add -A` or a directory
argument for the new `CLAUDE.build.md` commit step (Ensures 2's forbidden proxy);
auto-commit on behalf of the operator inside `create-story-worktree` itself — the
chosen shape is refuse-and-instruct (fail loud, per Requires 3's INFRA-296 precedent),
not silently commit-on-their-behalf, which would hide a possibly-unwanted change under
an automated commit message; perform the full `CLAUDE.build.md`/`.j2` reconciliation
or add a dispatch-parity drift check between them (INFRA-342's job).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_build.py -q 2>&1 | tail -40
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_stage_integration.py -q 2>&1 | tail -40
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -10
```

Acceptance: green, no `-x` (project lesson: a known pre-existing failure must not be
masked).

Reviewer negative checks:
(a) `grep -n "spawn-spec-writer" CLAUDE.build.md` shows an explicit branch with a
    `git commit` naming the `spec(` prefix, not only the `ACTION_SUBAGENT_TYPE` map
    entry.
(b) `grep -n "spawn-spec-writer" skills/pairmode/templates/CLAUDE.build.md.j2` shows
    both the new branch and the new map entry.
(c) `grep -n "git status" skills/pairmode/scripts/flex_build.py` shows a call site
    inside `cmd_create_story_worktree`, positioned before the `worktree add` call.
(d) A test in `tests/pairmode/test_flex_build.py` proves the refusal: write a story
    spec, commit it, then dirty it again (uncommitted), call `create-story-worktree`,
    and assert exit 1, no worktree, no branch, and the story path named in stderr.
(e) A test proves the negative scope (Ensures 5): dirty an unrelated file, confirm
    `create-story-worktree` still succeeds for a story whose own spec is clean.
(f) The new `test_stage_integration.py` test (Ensures 10) fails against the
    pre-fix `CLAUDE.build.md`-shaped sequence (spec-writer write, no commit,
    create-story-worktree) — confirm by temporarily skipping the commit step in the
    test and observing either a stale checked-out spec (pre-Ensures-4 behavior) or,
    once Ensures 4 lands, a refusal; either observable proves the test actually
    exercises the gap rather than passing vacuously.
(g) Every pre-existing `create-story-worktree`-calling test in both test files still
    asserts the same `returncode`/`exit_code` it did before this story (Ensures 6) —
    confirm via the full-suite run, not by inspection alone.

## Out of scope

- Modifying `skills/pairmode/skills/spec-writer/procedure.md`'s "Never commit"
  non-negotiable — Context decision 3 resolves this as already correct; the gap was
  `CLAUDE.build.md` never implementing what that line promises, not the promise itself.
- The full `CLAUDE.build.md`/`.j2` reconciliation and an automated dispatch-parity
  drift check between the two files — INFRA-342, sequenced after this story per the
  phase Ordering note. This story only adds the `spawn-spec-writer`-specific pieces its
  own fix needs to `.j2`.
- Auto-committing on the operator's behalf inside `create-story-worktree` (an
  auto-commit variant of option b) — the chosen shape is refuse-and-instruct, matching
  the INFRA-296 fail-loud precedent; silently committing a possibly-unwanted working-
  tree change under a generated message is a different (and riskier) behavior this
  story does not adopt.
- Any change to `merge-story-worktree`/`discard-story-worktree`'s own commit or
  teardown behavior — this story's refuse-check lives entirely inside
  `create-story-worktree`'s precondition gate.
- CER-136 / the merge-status-flip gap (a story's frontmatter `status:` not flipping to
  `complete` on merge) — that is INFRA-347, a related but independent gap this story's
  fix does not touch.
- Extending the new refuse-check to any file other than the target story's own spec
  (e.g. a general "worktree must branch from a fully-committed working tree" check) —
  scoped narrowly to the one gap this story's Context names.

## Evidence

Spec-preflight note (INFRA-190/191, INFRA-320 § C): the scan flags
`skills/pairmode/skills/spec-writer/procedure.md` as named in this spec but outside
declared scope. This is intentional — the file is read for context (Context decision 3
and Instructions 1 both require reading it fresh to confirm its "Never commit"
non-negotiable and single-file write-target boundary) but is explicitly listed in "Do
not" as unmodified by this story: the decision this story is built on is that the
procedure's existing text is already correct, and the gap it closes lives entirely in
`CLAUDE.build.md`/`.j2`/`flex_build.py` instead.
