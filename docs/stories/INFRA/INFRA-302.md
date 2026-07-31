---
id: INFRA-302
rail: INFRA
title: Worktree build-environment provisioning; untrack tsconfig.tsbuildinfo
status: complete
phase: "114"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - .gitignore
touches:
  - tests/pairmode/test_flex_build.py
  - tests/pairmode/test_vendored_payload_tracked.py
  - skills/observability/ui/tsconfig.tsbuildinfo
  - docs/architecture.md
  - docs/cer/backlog.md
  - docs/stories/INFRA/INFRA-302.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

`create-story-worktree` (INFRA-224) hands the builder a `git worktree` cut from
`HEAD`. A git worktree contains exactly what git tracks — so every path a
project deliberately keeps *out* of git is absent from it. For flex itself the
big one (`node_modules`) was solved by vendoring the payload into the repo
(INFRA-261, CER-090). For every downstream project it is not solved at all:
`node_modules` and `.env.local` are gitignored by design, so each fresh
worktree arrives without them, and every builder and reviewer re-discovers the
same gap and re-applies the same ad-hoc `ln -s` workaround. CER-075 records
this from the forqsite Era-3 build — *every* HOME story paid the tax — and
names the cost precisely: repeated wasted agent effort, plus habituation to
"known failures", which is the more expensive half. A reviewer who has learned
that three test files always fail in a worktree has stopped reading those
failures.

The fix CER-075 sketches is a `worktree_provision` list — a small, opt-in,
project-level configuration naming paths to link into a fresh worktree from the
main checkout. This story builds exactly that, and nothing wider: no implicit
`node_modules` default, no package-manager invocation, no copying. A symlink is
the right primitive because it is cheap, obviously non-authoritative (the
worktree does not own the bytes), and disappears with the worktree.

The second half is CER-070's residue. CER-070's root cause — the root
`.gitignore`'s `dist/`/`build/` patterns swallowing vendored package payload —
was fixed by INFRA-261, which committed 7333 payload files and added the
`node_modules`-anchored negations still present at `.gitignore:31-38`. What
survived is the addendum: `skills/observability/ui/tsconfig.tsbuildinfo` is
**tracked** (`git ls-files` returns it; it is the repo's only tracked
`.tsbuildinfo`) and is rewritten by `tsc -b` on every UI build gate run,
including failing ones. A tracked file that a test run rewrites is a tracked
file that dirties the worktree, and `merge-story-worktree`'s
`git rebase` (`flex_build.py:3618`) then refuses with "You have unstaged
changes" — a manual `git checkout` before every affected merge. There is a
second, quieter reason to untrack it: `ui/tsconfig.json` sets `noEmit: true`,
so this file is a pure incremental *typecheck* cache whose companion output
(`ui/dist`) is deliberately ignored. Shipping one half of an incremental pair
in git and ignoring the other is how a `tsc -b` gets talked out of doing any
work at all. The file is regenerated on demand and has no reader.

The two halves belong in one story because they are the same sentence from two
sides: **a fresh worktree should be usable without manual repair.** One adds
what git cannot carry; the other removes what git should never have carried.

## Requires

- **INFRA-296 (phase 113) is complete and merged.** This story edits
  `cmd_create_story_worktree`, which INFRA-296 also edits, and INFRA-296 lands
  first (closeout plan § C.7; `docs/stories/INFRA/INFRA-296.md` § Instructions
  step 6, which confines that story's edit to the `except
  PermissionsCreateError` block and forbids restructuring the function
  precisely so this story layers on cleanly). Build against the **post-merge**
  shape: after INFRA-296, the `except PermissionsCreateError` block echoes an
  `error:` line, calls `_teardown_story_worktree`, echoes `_residue_lines(...)`
  and `sys.exit(1)` — it no longer falls through to the stdout echo. Every
  anchor below that mentions that block means its post-296 form. If INFRA-296
  has **not** merged when this story is dispatched, stop and say so rather than
  re-implementing its teardown here.
- `skills/pairmode/scripts/flex_build.py` defines `_stamp_active_story`
  (`:77`), `_clear_active_story` (`:112`), `_run_git` (≈ `:190`),
  `_worktree_paths` (`:203`), `_teardown_story_worktree` (`:215`),
  `_residue_lines` (`:250`), `PermissionsCreateError` (`:520`),
  `generate_permissions_artifact` (`:524`), `cmd_create_story_worktree`
  (`:3504`, decorated at `:3497`) and `cmd_merge_story_worktree` (`:3575`,
  whose rebase is issued at `:3618`).
- In `cmd_create_story_worktree` the pre-296 ordering is: validate id (`:3520`)
  → `_worktree_paths` (`:3522`) → existence/branch guards (`:3524-3534`) →
  `git worktree add -b` (`:3536-3546`) → `_stamp_active_story` in a warning-only
  `try/except` (`:3555-3558`) → `generate_permissions_artifact` in a
  `try/except PermissionsCreateError` (`:3560-3563`) → `click.echo(str(wt_abs))`
  (`:3565`). **Stdout carries exactly one line — the worktree path** — because
  callers capture it; this is the contract § Ensures C2 protects.
- `flex_build.py` today contains **no** `node_modules`, symlink or
  `worktree_provision` handling: `grep -n 'node_modules\|symlink\|os.symlink\|worktree_provision' skills/pairmode/scripts/flex_build.py`
  → no output. Re-run before building.
- `.companion/pairmode_context.json` is the project-level operator config file
  written once by `bootstrap.py:1381` and read (never written) by
  `audit.py:235`, `pairmode_drift_report.py:188`, `global_session_check.py:28`
  and `next_action.py:445-480`. The last of these is the direct precedent this
  story copies: `_run_build_gate_subprocess` reads `test_command` from it, and
  treats *absent file / unreadable / invalid JSON / missing key* as one
  fall-through case. **flex itself has no `pairmode_context.json`**
  (`ls .companion/` → `effort.db`, `effort_recording.log`, `merge.lock`,
  `state.json`, `state.json.lock`), which is expected and is why § Ensures C's
  default path is the one this repo's own suite exercises.
- `.companion/state.json` is runtime state under a single-writer discipline
  (`story_context.py:47-150`, `state_utils.state_lock`), holding story-keyed
  `current_stories` (INFRA-281) and budget keys. It is **not** the config
  surface — see § Ensures A1's argument.
- `skills/observability/ui/tsconfig.tsbuildinfo` is tracked and is the only
  tracked `.tsbuildinfo` in the repo (`git ls-files | grep tsbuildinfo` → one
  line). `skills/observability/ui/tsconfig.json` sets `"noEmit": true`;
  `ui/package.json`'s `build` script is `tsc -b && vite build`.
- `.gitignore`'s vendored-payload block (`:31-38`) carries the CER-090
  negations `!**/node_modules/**/dist/`, `!**/node_modules/**/build/` and the
  `obj/`/`obj.target/` re-exclusions, above a "Do not remove these lines to
  clean up the file" comment.
- `tests/pairmode/test_vendored_payload_tracked.py` defines
  `ALLOWED_IGNORED_SUFFIXES` (`:46-49`, matched with `str.endswith`) and
  `ALLOWED_IGNORED_EXACT` (`:51-55`, matched with `in`, three
  trailing-slash directory entries), consumed by
  `test_no_vendored_payload_is_gitignored` (`:106-133`) whose source is
  `git ls-files --others --ignored --exclude-standard --directory -- skills/observability`.
  That command's current output is exactly five lines
  (`api/dist/`, two `better-sqlite3` `obj*` dirs, `scripts/__pycache__/`,
  `ui/dist/`) — all allow-listed. Note the allow-list comment block (`:29-45`)
  explicitly says widening it without confronting the reason is the thing the
  guard exists to stop; § Ensures D3 therefore requires the new entry to carry
  its own reason.
- **Coordination with INFRA-307 (phase 115) — both directions.** INFRA-307
  edits the same two constants: it adds a **pattern** tolerating
  `.claude/` artifact dirs under vendored `node_modules` (CER-093) and deletes
  `test_extension.node` (CER-094). This story adds **one exact-path entry** for
  `skills/observability/ui/tsconfig.tsbuildinfo` to `ALLOWED_IGNORED_EXACT` and
  changes nothing else in that file. The edits do not overlap: different
  constant semantics (exact literal vs. pattern), different paths, different
  CER rows. This story lands first (closeout plan § C.7); INFRA-307's spec must
  be written against a `test_vendored_payload_tracked.py` that already contains
  the tsbuildinfo entry, and must not remove or restructure it while adding the
  `.claude/` pattern. Conversely, this story must not pre-empt INFRA-307: do
  **not** convert `ALLOWED_IGNORED_EXACT` to patterns, do not touch
  `test_extension.node`, do not touch `ALLOWED_IGNORED_SUFFIXES`.
- **Suite baseline, measured on `610af2a3` in the main checkout on 2026-07-29:**
  `uv run pytest tests/pairmode/ -q` → `4116 passed, 211 skipped` in ~166 s.
  **There is no known failing test on main.** The closeout plan's "known
  `test_observability_ui` failure" is worktree-only — the CER-090 vendored
  payload gap — and its remedy is to rsync the payload from the main checkout,
  **never** `pnpm install` (which rewrites the lockfile;
  `docs/architecture.md:3299-3301`). See § Tests.

## Ensures

Grouped by item. Every assertion is checkable from the diff, by running the
command given, or by running the named test. § Ensures E is the one deliberate
exception (an evidence block, not an assertion) and states its own verification
path.

### A — the configuration surface

**A1. The list is read from `.companion/pairmode_context.json`, not
`state.json`.** `cmd_create_story_worktree` reads an optional
`worktree_provision` key from `<project_dir>/.companion/pairmode_context.json`.
The choice is deliberate and must be recorded in a comment on the reader
function, in these terms:

- `state.json` is **runtime state under single-writer ownership**
  (`docs/ideology.md:124-132` — "Sidebar owns all state writes"; the writers
  take `state_lock` in `story_context.py:97`/`:147`). `worktree_provision` is
  durable **operator intent**, hand-authored and never machine-written. Putting
  a hand-edited key inside a lock-protected, machine-rewritten file invites the
  exact class of lost update that discipline exists to prevent, and mixes
  intent with ephemera (`current_stories` entries expire; budget keys churn
  every session).
- `pairmode_context.json` is already the project-level operator config file:
  written once at bootstrap (`bootstrap.py:1381`), read-only thereafter, and
  already the home of the sibling build-environment key `test_command`, which
  `next_action._run_build_gate_subprocess` (`:445-480`) reads with precisely
  the absent-or-malformed → fall-through rule this story reuses. Adding a third
  config surface when the second one already holds `build_command`,
  `test_command` and `test_dir` would be duplicate state, which is exactly what
  `docs/phases/phase-114.md`'s CP-114 checklist asks about.
- Both files live under the gitignored `.companion/`, so either choice is
  machine-local — which is required, since the paths being linked are
  machine-local by definition. That symmetry is *why* the deciding argument is
  writer-ownership rather than location.

**A2. A named reader exists and is total.**
`flex_build.py` defines a module-level
`_read_worktree_provision(project_path: Path) -> list[str]`. It returns `[]`
when the file is absent, unreadable, not valid JSON, or has no
`worktree_provision` key; it returns `[]` and emits **one** stderr warning
naming the file when `worktree_provision` is present but is not a list of
non-empty strings. It never raises and never exits. Non-string or empty-string
members of an otherwise-valid list are dropped with a per-entry warning
(§ Ensures B1). Its docstring cites `CER-075` and states the A1 rationale in
one sentence.

**A3. The declared shape is project-relative paths.** Each member is a path
relative to the project (main checkout) root — e.g.
`["node_modules", ".env.local", "apps/web/node_modules"]`. The docstring and
the architecture note (§ Ensures F1) both give that example verbatim, and both
state that absolute paths and paths containing a `..` segment are rejected
(§ Ensures B1), not normalised.

### B — provisioning is contained, and skips rather than aborts

**B1. A named provisioner exists with the full rule set.** `flex_build.py`
defines
`_provision_story_worktree(project_path: Path, wt_abs: Path, entries: list[str]) -> list[str]`,
which returns a list of human-readable warning lines (empty on full success)
and **never raises and never exits**. For each entry, in declaration order, it
skips — appending exactly one warning line naming the entry and the reason —
when any of the following holds, and only creates the link when none does:

| # | Skip condition | Warning must say |
|---|---|---|
| 1 | entry is not a non-empty `str` | not a path string |
| 2 | entry is absolute, or any of its parts is `..` | must be a project-relative path without `..` |
| 3 | `project_path / entry` does not exist | not present in the main checkout |
| 4 | `(project_path / entry).resolve()` is not `project_path.resolve()` itself or below it | resolves outside the main checkout |
| 5 | `wt_abs / entry` already exists (including a broken symlink — test with `lexists`) | already present in the worktree |
| 6 | `(wt_abs / entry).parent` does not exist, or resolves outside `wt_abs.resolve()` | parent directory missing in the worktree |
| 7 | the path is tracked by git in the worktree (`git -C <wt_abs> ls-files --error-unmatch -- <entry>` exits 0) | tracked by git; refusing to shadow tracked content |
| 8 | `os.symlink` raises `OSError` | the OS error text |

**B2. Containment is checked on the resolved target, and its reason is
commented.** Condition 4 uses `Path.resolve()` on the source and compares with
`is_relative_to` against the resolved project root, so a *symlink in the main
checkout* that points outside the project is rejected too, not merely a literal
`../`. The comment states the reason: the permission artifact
(`docs/phases/permissions/<id>.json`) is the Layer 1 allow-list `scope_guard.py`
enforces, and it is written in terms of project-relative paths; a link that
silently escapes the checkout would let a scope-allowed write land outside
every path the guard believes it is enforcing. Config is operator-authored, so
this is a footgun guard rather than a trust boundary — say that too, rather
than overclaiming a security property.

**B3. Condition 7 exists because of the other half of this story.** The comment
on the tracked-path check states that shadowing a tracked path with a symlink
makes the worktree permanently dirty and `merge-story-worktree`'s rebase
(`flex_build.py:3618`) refuse — the same failure mode the tsbuildinfo half of
this story removes (§ Ensures D).

**B4. Symlink targets are absolute.** The created link's target is
`(project_path / entry).resolve()`, so it survives regardless of the worktree's
depth relative to the main checkout. Asserted by a test reading
`os.readlink`.

**B5. Nothing here can fail the command.** No skip condition, and no
accumulation of them, changes the exit code or prevents the worktree path from
being printed. A test configures four simultaneously-bad entries (missing,
escaping, absolute, tracked), asserts exit `0`, asserts stdout is exactly the
worktree path, and asserts four distinct warning lines on stderr. The
provisioning call site is wrapped in a `try/except Exception` that degrades to a
single warning, so even an unanticipated failure inside the provisioner cannot
strand a created worktree.

**B6. Provisioning runs last, after the permissions gate.** The call sits
**after** INFRA-296's `except PermissionsCreateError` block and **immediately
before** `click.echo(str(wt_abs))`. Rationale, commented: a worktree that is
about to be torn down for a missing permission artifact must not be provisioned
first, and provisioning must not run before the story's Layer 1 allow-list
exists.

**B7. A duplicate entry is a no-op, not an error.** The second occurrence of a
path hits condition 5 and produces its warning; the first link survives.

### C — the default path is byte-identical

**C1. No config, no behaviour change.** With no `.companion/pairmode_context.json`
(flex's own case) or with the file present but carrying no
`worktree_provision` key, `create-story-worktree` performs **zero** filesystem
operations beyond those it performs today: no directory is created, no symlink
is made, no warning is emitted, stdout and stderr are unchanged, and the exit
code is unchanged. Pinned by a test that snapshots
`sorted(p.relative_to(wt_abs) for p in wt_abs.rglob('*'))` and compares it
against the same run on a build of the pre-story code path — in practice,
against the set produced with the feature disabled — and by asserting stderr
contains no `worktree_provision` substring.

**C2. Stdout stays one line.** Every warning goes to stderr (`err=True`).
A test asserts `result.stdout.strip().splitlines() == [str(wt_abs)]` in both
the provisioned and the unprovisioned case. Callers capture stdout as a path;
a chatty stdout is a silent breakage of every one of them.

**C3. No implicit `node_modules` default.** The code contains no default list
and no name-based special case; `grep -n "node_modules" skills/pairmode/scripts/flex_build.py`
returns only comment/docstring occurrences that are illustrative. A project
that wants `node_modules` linked says so. (Rationale for the architecture note:
flex itself must *not* get it — its `node_modules` is deliberately tracked
payload, INFRA-261, and a symlink over it would trip condition 7 anyway.)

**C4. The CLI surface is frozen.** No new subcommand, option, flag or exit
code. `tests/pairmode/test_cli_surface_freeze.py` passes with no edit. The
feature is config-driven precisely so that it is not a flag every caller must
learn.

**C5. Every existing worktree-lifecycle test passes under its original name.**
`tests/pairmode/test_flex_build.py::TestStoryWorktreeLifecycle`,
`::TestStoryWorktreeActiveStoryStamping`, `::TestScopedActiveStoryClear`,
`::TestStoryWorktreeMergeRobustness` and `::TestClaimedStoryIds` are
unmodified.

### D — `tsconfig.tsbuildinfo` leaves git

**D1. The file is untracked.**
`git ls-files -- skills/observability/ui/tsconfig.tsbuildinfo` prints nothing.
Removal is `git rm --cached` (index only) — the working-tree file stays on
disk; it is a regenerable cache, not a deletion.

**D2. The file is ignored, by an anchored exact path.** `.gitignore` gains
`/skills/observability/ui/tsconfig.tsbuildinfo` — a single anchored path, not
`*.tsbuildinfo`. `git check-ignore -q skills/observability/ui/tsconfig.tsbuildinfo`
exits 0. The line sits **below** the vendored-payload negation block
(`.gitignore:31-38`) with a two-line comment giving both reasons: `tsc -b`
rewrites it on every UI-build-gate run (including failing ones), which dirties
a story worktree and makes `merge-story-worktree`'s rebase refuse
(CER-070 addendum); and with `noEmit: true` in `ui/tsconfig.json` it is a pure
incremental *typecheck* cache whose paired output (`ui/dist`) is already
ignored — tracking one half of an incremental pair is how a `tsc -b` gets
talked out of doing any work.

**D3. The payload guard still passes, with a reasoned allow-list entry.**
`ALLOWED_IGNORED_EXACT` in `tests/pairmode/test_vendored_payload_tracked.py`
gains the exact string `"skills/observability/ui/tsconfig.tsbuildinfo"` — **no
trailing slash**, because `git ls-files --others --ignored --directory` prints
a bare file path without one, while the three existing entries are directories.
The module-level comment block (`:29-45`) gains a third numbered category
naming this file, why it is ignored (D2), and — the point the block insists on
— why it is *not* the CER-090 defect class: it is our own generated cache, not
vendored package payload, and it lives outside every `node_modules` tree.
`test_no_vendored_payload_is_gitignored` passes; its `git ls-files --others
--ignored --exclude-standard --directory -- skills/observability` output is the
previous five lines plus this one, and every line is allow-listed.

**D4. Two new guard assertions pin the state.** New tests in
`tests/pairmode/test_vendored_payload_tracked.py` assert (a)
`git ls-files -- skills/observability/ui/tsconfig.tsbuildinfo` is empty and (b)
`git check-ignore -q` on that path exits 0. They skip under the file's existing
`_require_git()` convention. Together they make a future re-add fail a test
rather than resurface as a merge-time surprise.

**D5. `test_no_untracked_files_under_observability` still passes.** Untracking
without ignoring would break it (the file would be untracked *and* unignored);
D1 and D2 must land in the same commit.

**D6. Nothing else in the vendored payload changes.** No other path is
untracked, no `.node` binary is touched, `ALLOWED_IGNORED_SUFFIXES` is
unmodified, and the `.gitignore` negation block (`:31-38`) is byte-identical.
Verified by `git diff --stat`.

### E — fresh-worktree evidence (recorded, not asserted)

**E1. A fresh worktree cut from clean `HEAD` runs the full suite to the same
result as the main checkout.** After D lands, the builder cuts a worktree from
the story branch's tip, runs the full suite there **without `-x`**, and pastes
into the build result: the `git worktree add` command, the pytest tail (passed
/ skipped counts), and the elapsed time. Acceptance is *same counts as the main
checkout run in § Tests*, not "green modulo known failures" — on `610af2a3`
main has no failing test.

**E2. If `tests/pairmode/test_observability_ui.py` fails in the worktree, the
remedy is recorded, and it is not `pnpm install`.** That failure is CER-090's
incomplete vendored payload, not this story's code. Rsync the payload from the
main checkout, re-run, and record both the failure and the remedy verbatim.
Never run `pnpm install` (`docs/architecture.md:3299-3301` — it can rewrite the
lockfile and resolve different versions). Do not weaken, skip or xfail the
test, and do not report a provisioning gap as a code failure.

**E3. The worktree is clean after the UI build gate.** After running
`tests/pairmode/test_observability_ui.py` in the fresh worktree,
`git -C <worktree> status --porcelain` shows **no** modification to
`skills/observability/ui/tsconfig.tsbuildinfo`. Output pasted. This is the
CER-070 addendum symptom, directly measured: before this story the file appears
as ` M`; after it, it does not appear at all. If the payload had to be rsynced
(E2), say so — the point of this item is the tsbuildinfo line, not the rest.

**E4. The provisioning path is exercised once for real.** In the fresh
worktree, with a temporary `.companion/pairmode_context.json` in a scratch
fixture project (not in flex's own `.companion/`), run `create-story-worktree`
and paste the stderr warnings and the `ls -l` of the created link. Automated
coverage is § Ensures B; this item exists because a symlink feature that has
only ever run under `tmp_path` has never been seen.

### F — the record

**F1. The architecture doc gains the provisioning contract.**
`docs/architecture.md`'s worktree/`create-story-worktree` material gains a short
paragraph — no new `##`-level heading — stating: the optional
`worktree_provision` list in `.companion/pairmode_context.json`; that entries
are project-relative paths symlinked from the main checkout into the fresh
worktree; that everything is skip-with-warning and nothing aborts the command;
that absent config is a byte-identical no-op with no implicit `node_modules`
default; and the A1 reason for choosing `pairmode_context.json` over
`state.json` in one sentence. Cites `INFRA-302, CER-075`.

**F2. The vendoring note records the tsbuildinfo exclusion.**
`docs/architecture.md:3286-3301`'s **Vendored dependency payload** paragraph is
extended (not rewritten) with one or two sentences naming
`skills/observability/ui/tsconfig.tsbuildinfo` as deliberately untracked and
ignored, the D2 reasons, and the fact that it is the sole exception outside the
node-gyp intermediates — so a future reader does not "restore" it. Cites
`INFRA-302, CER-070`.

**F3. CER-075 carries a RESOLVED note.** `docs/cer/backlog.md`'s CER-075 row
(`:80`) gains a bolded `**RESOLVED Phase 114 — INFRA-302 …**` note appended to
its Finding cell, naming the config key, the file it lives in, and the
opt-in/skip-never-abort semantics. It must **not** claim the worktree
environment is now automatic for every project — it claims that the convention
is now expressible in config instead of re-invented per story. The row is not
deleted or moved (`docs/cer/backlog.md:6-7`).

**F4. CER-070 carries a RESOLVED note naming both halves.** The CER-070 row
(`:89`) gains a bolded `**RESOLVED Phase 114 — INFRA-302 …**` note recording
that the root cause was fixed by INFRA-261 (payload committed, `.gitignore`
negations) and that this story closes the addendum by untracking and ignoring
`tsconfig.tsbuildinfo`. It must not claim that worktree UI-build failures are
now impossible — CER-090's payload-completeness question is INFRA-307's, and
the note says so.

### G — cross-cutting

**G1. No other module is edited.** The diff touches only the files in
`primary_files` and `touches`. No hook, no template, no
`merge-story-worktree`/`discard-story-worktree` body, no
`_teardown_story_worktree`/`_residue_lines`/`_worktree_paths`,
no `story_context.py`, no `bootstrap.py`.

**G2. `schema_introduces` stays `false`.** `worktree_provision` is an optional
key in an existing operator-authored config file, not persistent state with a
writer — no management-surface row is owed in `docs/phases/phase-114.md`
§ Schema delivery. (`bootstrap.py` is *not* taught to write the key: § Out of
scope.)

**G3. The full test suite is green**, run once **without `-x`**
(`tests/pairmode/`), against the § Requires baseline of `4116 passed, 211
skipped` plus INFRA-296's and INFRA-301's additions. The new tests raise the
passed count; the skipped count must not rise. If any test fails, verify it
reproduces on clean `HEAD` **in the same worktree** before attributing it
elsewhere, and say so explicitly in the build result.

**G4. INFRA-307's surface is left alone.** `git diff tests/pairmode/test_vendored_payload_tracked.py`
shows only: the new `ALLOWED_IGNORED_EXACT` member, the comment-block addition,
and the two new tests (D4). No change to `ALLOWED_IGNORED_SUFFIXES`, to
`_vendored_roots`, to the `.node` binaries, or to any existing test body.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Build in order D → A → B → then E, and write F last against what actually
shipped. D first because it is small, independent, and makes your own worktree
clean for the rest of the story.

**0. Re-read before you write.** The line numbers in this spec are anchors, not
coordinates, and INFRA-296 has since moved some of them. Read, as they exist
*now*: `cmd_create_story_worktree` in full (≈ `:3497-3570`, including
INFRA-296's rewritten `except PermissionsCreateError` block);
`_worktree_paths`/`_teardown_story_worktree`/`_residue_lines` (≈ `:203-270`);
`next_action._run_build_gate_subprocess` (`:440-485`) — copy its
absent/malformed config handling, do not invent a second dialect;
`tests/pairmode/test_vendored_payload_tracked.py:29-133`;
`tests/pairmode/test_flex_build.py:1165-1440` (the `_init_git_repo`,
`_git`, `_commit_in`, `_run` helpers and `TestStoryWorktreeLifecycle`).
Re-run the § Requires greps (no `node_modules`/symlink handling in
`flex_build.py`; one tracked `.tsbuildinfo`; the five-line ignored-paths
listing) before touching anything. Confirm INFRA-296 is in your `HEAD`
(`git log --oneline | grep INFRA-296`); if it is not, stop.

**1. (D) The tsbuildinfo.** In this order, in one commit:
`git rm --cached skills/observability/ui/tsconfig.tsbuildinfo` (never plain
`git rm` — the on-disk cache stays); add the anchored `.gitignore` line with
its two-reason comment, placed below the vendored-payload block and **without
touching** the negation lines above it; add the `ALLOWED_IGNORED_EXACT` member
and the third numbered paragraph in the allow-list comment; add D4's two tests.
Then run `git ls-files --others --ignored --exclude-standard --directory --
skills/observability` and check the output is the previous five lines plus
exactly one new one.

**2. (A) The reader.** Add `_read_worktree_provision` near the other
module-level helpers in `flex_build.py` (beside `_worktree_paths` is the
natural home). Mirror `next_action._run_build_gate_subprocess`'s structure:
`path.exists()` → `json.loads` inside a bare `try/except Exception` →
type-check the value → fall through to `[]`. Write the A1 rationale comment
**before** the code: if you cannot state plainly why the key does not live in
`state.json`, the choice is not yet made. Do not import `next_action` for this
— the two readers share a convention, not a function; a shared helper across
those two modules is a refactor with its own blast radius and is out of scope.

**3. (B) The provisioner.** Add `_provision_story_worktree` beside the reader.
Implement B1's eight conditions in the table's order — the cheap syntactic
checks before any filesystem or `git` call — using `os.path.lexists` for
condition 5 (a broken symlink must count as present) and `Path.resolve()` +
`is_relative_to` for conditions 4 and 6. Condition 7 uses `_run_git` with
`-C <wt_abs> ls-files --error-unmatch -- <entry>` and treats a zero exit as
"tracked". Create the link with `os.symlink(src_resolved, dst)`; do **not**
create missing parent directories (condition 6 skips instead) — a provisioner
that invents directory structure is a provisioner that can quietly reshape a
worktree.

Wire it in `cmd_create_story_worktree` at B6's position — after INFRA-296's
`except PermissionsCreateError` block, immediately before
`click.echo(str(wt_abs))` — as:

```python
try:
    for line in _provision_story_worktree(
        project_path, wt_abs, _read_worktree_provision(project_path)
    ):
        click.echo(line, err=True)
except Exception as exc:  # noqa: BLE001
    # CER-075: provisioning is a convenience layered on a worktree that is
    # already valid. Nothing here may strand or fail it.
    click.echo(f"warning: worktree provisioning failed: {exc}", err=True)
```

Do not restructure the rest of the function, rename its locals, or extract
helpers from it. Do not add a CLI flag.

**4. Tests.** Add a new class `TestCreateStoryWorktreeProvisioning` to
`tests/pairmode/test_flex_build.py`, alongside `TestStoryWorktreeLifecycle`
rather than growing it, using the existing `_init_git_repo`/`_git`/`_commit_in`/
`_run` helpers. Cover: C1 (no config → no symlink, no `worktree_provision`
warning, unchanged stdout), C2 (stdout is exactly one line, both cases), the
happy path (link created, `os.readlink` is the absolute resolved source — B4),
each of B1's conditions 2, 3, 4, 5, 6 and 7 as its own test with its own
warning-substring assertion, B5's four-bad-entries case (exit 0, four
warnings), B7 (duplicate entry), and A2's malformed cases (absent file, invalid
JSON, `worktree_provision: "node_modules"` as a string, list containing a
non-string). For condition 4, build the escape two ways: a literal `../…`
entry, and an entry naming a symlink *inside* the fixture project whose target
is `tmp_path` outside it — the second is the one a naive `startswith` check
would miss.

**5. (E) The evidence.** Run E1-E4 last, from a real fresh worktree, and paste
the outputs into the build result. E4's fixture project is a scratch directory,
not flex's own `.companion/` — do **not** create
`/mnt/work/flex/.companion/pairmode_context.json` (it would change this repo's
build-gate behaviour via `next_action`, which is not this story's business).

**6. (F) The prose.** Write F1 and F2 against the shipped code, then F3 and F4.
Resist overclaiming in both CER notes: CER-075 becomes *expressible in config*,
not *solved everywhere*; CER-070's addendum closes, but CER-090's payload
completeness remains INFRA-307's.

**7. Sequencing notes.** (a) INFRA-296 is upstream — see § Requires; build
against its post-merge `cmd_create_story_worktree`. (b) INFRA-307 is downstream
and edits the same test module's allow-list constants; keep your edit to the
one exact entry plus the comment and the two new tests (§ Ensures G4), so 307's
`.claude/` pattern applies cleanly on top. (c) INFRA-305 is strictly last in
phase 114 and annotates rows; your F3/F4 notes are yours to write, not 305's.

**8. Ideology note (Step 4a — resolved inline, no conflict).** Three entries
shaped this spec. *"Sidebar owns all state writes"* (`docs/ideology.md:124-132`)
is the whole of A1: the constraint's rationale is single-writer integrity, so
routing an operator-authored key into the lock-protected, machine-written
`state.json` would respect the rule's letter (we only *read*) while violating
its reason; `pairmode_context.json`, whose only writer is bootstrap, honours
both. *"Never silently pass contradictions"* (`:102-110`) is why every skip in
B1 emits a warning naming the entry and the reason — a provisioner that
silently drops half its config gives exactly the false confidence that
constraint protects against — and it is also why the skips are loud but
non-fatal: the contradiction is in the config, not in the worktree, so
refusing to hand back a valid worktree would punish the wrong thing.
*"Rationale-bearing decisions over bare rules"* is why B2, B3, C3 and D2 are
Ensures rather than niceties: the containment check, the tracked-path check,
the absent default and the single anchored ignore line all read as arbitrary or
over-cautious to someone who does not know the reason, and the obvious
"cleanup" of any of them is a regression. *"Hooks are thin relays only"* was
checked and does not bind — no hook is touched.

## Tests

Run from the story worktree root. After item D:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_vendored_payload_tracked.py \
  -q 2>&1 | tail -20
```

After items A and B:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_flex_build.py \
  tests/pairmode/test_cli_surface_freeze.py \
  tests/pairmode/test_vendored_payload_tracked.py \
  -q 2>&1 | tail -30
```

Then the neighbours of the state/config surfaces this story reads, to catch
collateral damage:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_story_context.py \
  tests/pairmode/test_next_action.py \
  tests/pairmode/test_bootstrap.py \
  tests/pairmode/test_observability_ui.py \
  -q 2>&1 | tail -30
```

(Skip any of the above that does not exist in the tree; do not create it.)

Then the full suite **without `-x`**, so nothing is masked:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Machine-checkable Ensures:

```bash
# A2/B1 — the new symbols exist
grep -n 'def _read_worktree_provision\|def _provision_story_worktree' \
  skills/pairmode/scripts/flex_build.py

# C3 — no implicit default
grep -n 'node_modules' skills/pairmode/scripts/flex_build.py   # comments/docstrings only

# C4 — CLI surface frozen
grep -c 'click.option' skills/pairmode/scripts/flex_build.py   # unchanged vs HEAD~

# D1 — untracked
git ls-files -- skills/observability/ui/tsconfig.tsbuildinfo   # empty

# D2 — ignored
git check-ignore -q skills/observability/ui/tsconfig.tsbuildinfo && echo ignored

# D3 — the guard's input, one new allow-listed line only
git ls-files --others --ignored --exclude-standard --directory -- skills/observability

# D6/G1/G4 — nothing else moved
git diff --stat HEAD~1
git diff tests/pairmode/test_vendored_payload_tracked.py

# F3/F4 — the CER rows are closed
grep 'CER-075' docs/cer/backlog.md | grep -c 'RESOLVED Phase 114'   # 1
grep 'CER-070' docs/cer/backlog.md | grep -c 'RESOLVED Phase 114'   # 1
```

Evidence commands for § Ensures E, run in a fresh worktree cut from the story
branch tip (outputs pasted into the build result):

```bash
git worktree add /tmp/infra302-fresh HEAD
cd /tmp/infra302-fresh
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -10
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_observability_ui.py -q 2>&1 | tail -10
git -C /tmp/infra302-fresh status --porcelain
```

Acceptance:

- every new test from A1-A3, B1-B7, C1-C5, D1-D6 passes;
- every pre-existing test in `TestStoryWorktreeLifecycle`,
  `TestStoryWorktreeActiveStoryStamping`, `TestScopedActiveStoryClear`,
  `TestStoryWorktreeMergeRobustness`, `TestClaimedStoryIds` and in
  `tests/pairmode/test_vendored_payload_tracked.py` passes under its original
  name (C5, G4);
- `tests/pairmode/test_cli_surface_freeze.py` passes with no edit (C4);
- the full suite is green against the § Requires baseline (`4116 passed, 211
  skipped` on `610af2a3`, plus INFRA-296's and INFRA-301's additions), with the
  passed count higher and the skipped count unchanged;
- § Ensures E1-E4 are recorded in the build result; E3's `git status
  --porcelain` shows no `tsconfig.tsbuildinfo` line.

**On the "known failure".** There is no failing test on main as of 2026-07-29.
If `tests/pairmode/test_observability_ui.py` fails in your worktree, that is
CER-090's incomplete vendored payload: rsync the payload from the main
checkout, **never** run `pnpm install`, re-run, and record what you did (E2).

## Out of scope

- **Copying, rsyncing, or installing anything.** Provisioning creates symlinks
  and nothing else. A copy would double the disk cost per concurrent worktree
  and, worse, would drift from the main checkout mid-story; running a package
  manager would make `create-story-worktree` network-dependent and able to
  rewrite a lockfile — the failure mode `docs/architecture.md:3299-3301`
  already prohibits for the repair path. The one-off rsync remedy for CER-090
  stays a manual, documented step (§ Tests).
- **Teaching `bootstrap.py` to write `worktree_provision`.** Bootstrap would
  have to guess the project's gitignored build inputs; the key is opt-in and
  hand-authored precisely so that its contents are a decision someone made. A
  bootstrap prompt for it is a reasonable later story with its own template and
  audit-parity surface.
- **A `--provision`/`--no-provision` flag or any CLI surface change** (C4). If
  an escape hatch is ever needed, removing the key is already one.
- **Provisioning on `merge-story-worktree`/`discard-story-worktree`,** or
  cleaning links up on teardown. `git worktree remove --force` deletes the
  worktree directory and the symlinks inside it; the link targets are in the
  main checkout and are never followed for deletion. `_teardown_story_worktree`
  is not edited (INFRA-286 semantics).
- **Making any skip fatal, or adding a strict/validate mode.** B5 is the
  contract: a misconfigured entry must never cost an operator a worktree.
- **`*.tsbuildinfo` as a glob in `.gitignore`.** Rejected in favour of the
  single anchored path (D2): a depth-matching glob would also ignore any
  `.tsbuildinfo` shipped inside a vendored `node_modules` tree, which is the
  CER-090 defect class the payload guard exists to catch. If a second workspace
  starts emitting one, it gets its own anchored line and its own allow-list
  entry, each with a reason — which is the point.
- **Deleting the `tsconfig.tsbuildinfo` file from disk.** `git rm --cached`
  only (D1); the local cache is harmless and regenerable.
- **CER-093's `.claude/` allow-list pattern and CER-094's
  `test_extension.node` deletion.** INFRA-307, phase 115 — which edits the same
  two constants and lands after this story (§ Requires, § Ensures G4).
- **CER-090's remaining payload-completeness question** (whether a fresh
  worktree can build the UI without a manual rsync). This story records the
  evidence (E1-E3); closing it belongs to INFRA-307's fresh-worktree evidence
  block.
- **Any further `docs/cer/backlog.md` grooming** beyond the CER-075 and CER-070
  rows named in F3/F4. The era's remaining rows are closed by their own
  stories, and the backlog truth pass is INFRA-310.
- **A shared config-reading helper between `flex_build.py` and
  `next_action.py`.** The two readers share a convention, not a function
  (Instructions step 2); extracting one touches the build gate's behaviour and
  needs its own regression evidence.
