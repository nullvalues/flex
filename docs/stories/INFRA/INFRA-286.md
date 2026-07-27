---
id: INFRA-286
rail: INFRA
title: "Merge robustness: return-code checks, failed-merge cleanup contract, merge serialization; amend serialism doc debt (CER-098)"
status: draft
phase: "109"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
touches:
  - docs/architecture.md
  - docs/cer/backlog.md
  - tests/pairmode/test_flex_build.py
  - docs/stories/INFRA/INFRA-286.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

This is the last story of Phase 109 and the only one that touches the **git**
side of concurrency. INFRA-280..285 made the *loop's* coordination state
story- and phase-keyed (resolver claims, `current_stories`, the attempt
counter, `checkpoint_steps`, effort.db WAL, session-scoped context
accounting). What none of them touched is the moment two of those parallel
stories actually **land**: `merge-story-worktree`. CER-098 names three gaps
there, all of which are invisible while the loop is serial and all of which
become live the moment the capability this phase exists to restore is used.

**(a) The cleanup block ignores both return codes.** After a successful
`--ff-only` merge, `cmd_merge_story_worktree` fires
`_run_git(["worktree", "remove", "--force", ...])` and
`_run_git(["branch", "-D", branch])` back to back
(`flex_build.py:3184-3185`) and inspects neither result. Every other git call
in the same function checks `returncode` and surfaces git's own text
(`:3101-3107`, `:3166-3173`, `:3176-3182`), and the sibling
`discard-story-worktree` checks both of these exact calls
(`:3230-3245`) — the merge path is the outlier. On failure the command still
prints `merged <branch> into <main>` and exits 0. The residue is not inert:
`.pairmode-worktrees/<ID>/` **is** the in-flight claim
(`claimed_story_ids`, `flex_build.py:207-241`, INFRA-280), so a leftover
directory silently pins the story as forever-claimed and the resolver keeps
skipping it; a leftover branch makes the story's next
`create-story-worktree` exit 1 with `error: branch already exists`, a message
that names the symptom and not the cause.

**(b) A lost `--ff-only` race leaves an undocumented state.** The rebase and
the merge are two separate git invocations against a shared main branch. If
another `merge-story-worktree` lands between them, the `--ff-only` merge
fails and the command exits 1 (`:3176-3182`) with the story branch rebased
onto a now-stale tip, the worktree still present, and the counter /
`current_stories` / permission-artifact stamps still set. Git state and loop
state have diverged and nothing tells the operator (or the harness) what the
recovery is. The finding calls this "no documented recovery", and the fix is
mostly a **contract decision that must be recorded**, not code: on a failed
land, *nothing* is torn down and *nothing* is cleared, because the story's
commits exist only on `pairmode/<ID>` — releasing the claim or clearing the
scope stamps would orphan them and free the resolver to hand the same story
to a second dispatch. Re-running the command is the recovery: it rebases
again onto the new tip and lands. That is already true by construction; it is
simply not stated anywhere, so an operator staring at exit 1 cannot know it.

**(c) Parallel merges are not serialized.** Two concurrent
`merge-story-worktree` calls contend on the repository's `index.lock`; the
loser fails loudly at an arbitrary point (rebase or merge), which is
survivable but pushes the operator into (b) for a reason that has nothing to
do with the story. INFRA-285 built exactly the primitive this needs —
`state_utils.state_lock` (`state_utils.py:163-224`), a bounded, advisory,
**fail-open** `flock` — so this story consumes it rather than inventing a
second locking scheme. It is deliberately not a queue and not a retry loop:
a bounded wait converts the common two-way collision into a short pause,
and the uncommon case still falls through to (a)/(b)'s now-precise error
paths. The doc must say that plainly; INFRA-285's own CER row already warns
"this row must not be read as a stronger guarantee than was built", and the
same discipline applies here.

**(d) Doc debt the other stories deliberately left.** Two prose claims that
the era's serial build loop is a safety argument are now false, and both
were explicitly assigned here rather than to the story that obsoleted them:

- `docs/architecture.md:2503-2510` — the `next_attempt_number` paragraph
  ("the era's no-nested-spawning invariant keeps the build loop serial (one
  worker in flight at a time), so the race cannot occur in practice"). INFRA-284
  fixed the underlying derivation (`insert_attempt_derived`, `BEGIN IMMEDIATE`,
  `COALESCE(MAX(attempt_number), 0) + 1`) and corrected the in-code comment,
  and its CER note states the architecture prose is INFRA-286's.
- `docs/cer/backlog.md:184` — CER-050's "Concurrent writers are not expected
  in normal operation." CER-097 names it as no longer true and CER-098
  assigns retiring it here.

A third, smaller one is in scope because it is the same class and one line
away: `docs/architecture.md:768` still describes the advisory state lock as
"INFRA-285's ... deliberately deferred", written before INFRA-285 landed.

## Requires

- **INFRA-280, INFRA-281, INFRA-282, INFRA-283, INFRA-284 and INFRA-285 are
  complete and merged**, and this story's worktree is cut from a `HEAD` that
  contains all six. This story is last in the phase's `## Ordering` precisely
  because it rewrites the prose the others obsolete; building it against an
  earlier tip would retire claims that are still true. Verify before building:
  `git log --oneline --grep 'INFRA-285'` returns a commit reachable from
  `HEAD`, and `grep -n 'def state_lock' skills/pairmode/scripts/state_utils.py`
  prints a line.
- `skills/pairmode/scripts/flex_build.py` defines `_run_git`,
  `_worktree_paths`, `_validate_story_id_or_exit`, `_current_branch`,
  `_stamp_active_story`, `_clear_active_story`, `clear_attempt_count`,
  `clear_permissions_artifact`, `claimed_story_ids`, and the three
  subcommands `create-story-worktree`, `merge-story-worktree`,
  `discard-story-worktree`.
- `skills/pairmode/scripts/state_utils.py` exports `state_lock` (a
  `@contextmanager` yielding a `bool`) and `STATE_LOCK_TIMEOUT_SECONDS`.
  `flex_build.py` currently imports only `_atomic_write_json` from it
  (`flex_build.py:65`).
- `docs/architecture.md` contains the sentence fragment
  `loop serial (one worker in flight at a time)` at line ~2506 and the phrase
  `deliberately deferred rather than pre-empted here` at line ~768.
- `docs/cer/backlog.md` contains a `CER-098` row with a `Phase` cell of `109`
  and a `CER-050` row (under `## Do Never` / the marginal quadrant) containing
  `Concurrent writers are not expected in normal operation.`
- `tests/pairmode/test_flex_build.py` contains
  `class TestStoryWorktreeLifecycle` and the module-level helpers `_run`,
  `_init_git_repo`, `_git`, `_commit_in`.

## Ensures

Grouped by item. Every assertion is checkable from the diff or by running a
command.

### A — CER-098(a): cleanup return codes are checked

**A1. Teardown is a single named function.** `flex_build.py` defines
`_teardown_story_worktree(project_path: Path, story_id: str) -> list[str]`
which runs `git worktree remove --force <wt_rel>` and, **only if that
succeeded**, `git branch -D pairmode/<story_id>`, and returns a list of
human-readable residue strings — empty on full success. It never calls
`sys.exit`, never writes state, and never raises. (`_teardown_story_worktree`
does not exist in the source tree today; `spec-preflight` flagging it as
unverifiable is expected and intentional — this story creates it.)

**A2. A failed worktree removal short-circuits the branch delete.** When
`worktree remove` returns non-zero, `_teardown_story_worktree` does **not**
invoke `git branch -D`, and its returned list contains exactly two entries:
one naming the worktree path that remains and one naming the branch that
consequently remains. Verified by a test that monkeypatches
`flex_build._run_git` to fail the `worktree remove` call and asserts no
`branch` invocation was recorded.

**A3. A failed branch delete is reported alone.** When `worktree remove`
succeeds and `branch -D` returns non-zero, the returned list has exactly one
entry, naming `pairmode/<story_id>`.

**A4. Residue text carries git's own message and a repair command.** Each
residue string includes the stripped `stderr` (falling back to `stdout`, then
to a fixed fallback sentence) of the failing git call, and the returned list's
rendering by the caller (A5) includes the literal repair commands
`git worktree remove --force .pairmode-worktrees/<story_id>` and
`git branch -D pairmode/<story_id>` for whichever items remain.

**A5. `merge-story-worktree` clears loop state and then reports residue.**
After a successful `--ff-only` merge, `cmd_merge_story_worktree`:
calls `_teardown_story_worktree`; **then unconditionally** runs
`clear_attempt_count(project_path, story_id)`,
`_clear_active_story(project_path, story_id)` and
`clear_permissions_artifact(story_id, project_path)` — in that order,
unchanged from today; then echoes `merged <branch> into <main_branch>` to
stdout. If the residue list is non-empty it additionally echoes each residue
line plus the repair commands to **stderr** and exits `1`; otherwise it exits
`0`. The ordering is load-bearing and must be commented: the merge already
landed, so the story *is* done and the loop stamps must not survive a cleanup
hiccup — but the residue is still an error the operator has to clear.

**A6. `discard-story-worktree` delegates to the same function.**
`cmd_discard_story_worktree`'s two open-coded `_run_git` calls
(`flex_build.py:3227-3245`) are replaced by one
`_teardown_story_worktree` call. On a non-empty residue list it echoes the
same rendering to stderr and exits `1` **before** clearing any state — the
discard path's existing behaviour (`:3230-3245` exits before
`_clear_active_story`) is preserved exactly, because on a discard nothing has
landed and the stamps must stay put for the retry.

**A7. Existing worktree-lifecycle tests pass unchanged.** Every test in
`tests/pairmode/test_flex_build.py::TestStoryWorktreeLifecycle` still exists
under its original name and still passes. A successful merge and a successful
discard both still exit `0`, and a successful merge's stdout still contains
`merged pairmode/<ID> into <branch>`.

**A8. No new CLI subcommand, option, or exit code is introduced.**
`tests/pairmode/test_cli_surface_freeze.py` passes with no edit to its
expected surface. The only exit codes either command produces remain `0` and
`1`.

### B — CER-098(b): the failed-land contract is explicit and documented

**B1. A failed `--ff-only` merge tears down nothing and clears nothing.**
The `if merge.returncode != 0:` branch contains no call to
`_teardown_story_worktree`, `clear_attempt_count`, `_clear_active_story`, or
`clear_permissions_artifact`. Asserted both by reading the diff and by a test
(B3).

**B2. A failed land prints a structured, greppable recovery block.** Both the
rebase-failure branch and the merge-failure branch echo, after git's own error
text, a block whose lines each begin with the literal prefix `recovery: ` and
which names, for the merge-failure case: that `pairmode/<story_id>` still
holds the story's commits and nothing was discarded; that
`.pairmode-worktrees/<story_id>/` still exists and still holds the in-flight
claim; that the attempt counter, `current_stories` entry and permission
artifact are deliberately untouched; and the exact re-run command
`flex_build.py merge-story-worktree --story-id <story_id> --project-dir <dir>`
as the supported recovery. The rebase-failure block names the same residue
and states that the conflict must be resolved in the worktree first.

**B3. The lost-race path is tested end to end.** A test creates two story
worktrees (`WT-201`, `WT-202`) from the same tip, commits a *different* file
in each, lands `WT-201`, then lands `WT-202` and asserts it **succeeds**
(exit 0) — the rebase absorbs the intervening commit, which is the normal
serialized-by-lock outcome and must not regress. A second test forces the
genuine ff-only failure by committing on the main branch *after*
`WT-203`'s rebase would have run — simulated by monkeypatching
`flex_build._run_git` so the `merge --ff-only` invocation returns a non-zero
`CompletedProcess` — and asserts: exit code `1`; stdout does **not** contain
`merged`; stderr contains `recovery: `; `.pairmode-worktrees/WT-203/` still
exists; `refs/heads/pairmode/WT-203` still resolves; and
`.companion/attempt_counter.json`'s entry for `WT-203` is unchanged.

**B4. Re-running after a failed land is idempotent.** A test that lets the
merge fail once (B3's monkeypatch), then removes the monkeypatch and re-runs
`merge-story-worktree` for the same story, asserts exit `0`, the file landing
on the main branch, and the worktree and branch both gone. No manual repair
step is performed between the two runs.

### C — CER-098(c): merges and discards serialize on a bounded advisory lock

**C1. A merge lock constant and helper exist.** `flex_build.py` defines
`MERGE_LOCK_TIMEOUT_SECONDS: float = 120.0` at module level with a comment
giving the number's reason (it matches `_run_git`'s own 120 s subprocess
timeout, `flex_build.py:177` — a waiter must not give up before the holder's
longest single git call can finish), and a `@contextmanager`
`_merge_lock(project_path: Path)` that yields the `bool` from
`state_utils.state_lock(project_path / ".companion" / "merge",
timeout_seconds=MERGE_LOCK_TIMEOUT_SECONDS)`. `flex_build.py`'s import at
line 65 is extended to `from state_utils import _atomic_write_json,
state_lock`. (Both `MERGE_LOCK_TIMEOUT_SECONDS` and `_merge_lock` are created
by this story; `spec-preflight` warnings for them are expected.)

**C2. The lock file lives beside the other companion state and its directory
is best-effort created.** `_merge_lock` attempts
`(project_path / ".companion").mkdir(parents=True, exist_ok=True)` inside a
`try/except Exception: pass` before locking, so a project without a
`.companion/` directory degrades to "no lock" rather than erroring. The lock
file is `.companion/merge.lock` (`state_lock` appends `.lock` to the path it
is given). After a merge in a fresh repo, `.companion/merge.lock` exists.

**C3. Both commands hold the lock across their whole critical section.**
`cmd_merge_story_worktree`'s body from the `_current_branch` check through
the final echo, and `cmd_discard_story_worktree`'s body from
`_teardown_story_worktree` through its final echo, execute inside
`with _merge_lock(project_path) as locked:`. The pre-flight
`_validate_story_id_or_exit` and worktree-existence checks may sit outside it.

**C4. Non-acquisition is fail-open and warned, never fatal.** When `locked`
is `False` the command proceeds exactly as it does today and echoes one line
to stderr beginning `warning: merge lock not acquired`. It does not retry, does
not queue, and does not exit early. A test monkeypatches `flex_build.state_lock`
with a contextmanager yielding `False` and asserts the merge still exits `0`,
still lands the commit, and emits the warning.

**C5. The weakness is stated in the helper's docstring.**
`_merge_lock`'s docstring states that the lock **narrows** the window in which
two `merge-story-worktree` calls contend on the repository `index.lock`; that
it does not make concurrent merges safe against an external `git` process or a
second orchestrator (out of scope, `docs/phases/phase-109.md` § Scope
statement); and that "make it reliable" changes — an unbounded wait, a retry
loop, a lock daemon — are regressions for the same reason
`state_utils.state_lock`'s own docstring gives (`state_utils.py:180-194`):
they trade a rare loud failure for a common stall.

**C6. Two concurrent merges do not both corrupt.** A test spawns two
`merge-story-worktree` subprocesses for two different stories concurrently
(`subprocess.Popen` × 2, then `communicate()`), and asserts that **both**
exit `0`, that both stories' files are present on the main branch, and that
neither `.pairmode-worktrees/` entry survives. If the environment lacks
`fcntl`, the test is skipped with an explicit reason rather than being
weakened.

### D — CER-098(d): the serialism doc debt is retired

**D1. The `next_attempt_number` serialism paragraph is corrected.**
`docs/architecture.md`'s paragraph currently beginning "The derivation is a
read-then-write with no transaction spanning both steps" (≈ lines 2503-2510)
no longer contains the string `loop serial (one worker in flight at a time)`
and no longer presents the race as "accepted, not fixed". Its replacement
states, in at most one short paragraph, that INFRA-284 (CER-096) replaced the
read-then-write with `insert_attempt_derived`'s single
`BEGIN IMMEDIATE` transaction deriving
`COALESCE(MAX(attempt_number), 0) + 1`, that `next_attempt_number` survives as
an advisory read-only helper, and that the serial-loop justification is retired
because Phase 109's target capability is parallel story builds under one
orchestrator. `grep -c 'loop serial (one worker in flight at a time)'
docs/architecture.md` returns `0`.

**D2. The deferred-lock forward pointer is closed.**
`docs/architecture.md`'s "**Accepted limitation:**" passage at ≈ line 768
(ending `deliberately deferred rather than pre-empted here to avoid a second,
competing locking scheme`) gains a following clause or sentence stating that
the lock now exists (`state_utils.state_lock` / `update_state_json`,
INFRA-285) and that it is bounded, advisory and fail-open — so a reader is not
left believing the work is still outstanding. The historical sentence itself is
not deleted or rewritten; only extended.

**D3. The merge-robustness behaviour is documented.**
`docs/architecture.md` § Pairmode build loop gains one paragraph (bolded lead
in the style of the neighbouring **Per-story worktree isolation** /
**Worktree as in-flight claim** paragraphs, ≈ lines 172-207) titled for
merge robustness and citing `INFRA-286, CER-098`. It records: both cleanup
return codes are now checked and residue is reported with repair commands
after the state clears (A5); the failed-land contract — nothing torn down,
nothing cleared, re-run is the recovery, and *why* (releasing the claim would
orphan the story's only copy of its commits and free the resolver to
re-dispatch it); and the merge lock with its explicit non-guarantee (C5). No
new `##`-level heading is added.

**D4. CER-050's doctrine note is retired.** `docs/cer/backlog.md`'s `CER-050`
row's Finding cell has the sentence `Concurrent writers are not expected in
normal operation.` replaced by, or immediately followed by, a bolded
`**AMENDED Phase 109 — INFRA-286 …**` note stating that concurrent writers
*are* now expected (single-orchestrator parallel story builds), that
INFRA-285 added the bounded advisory `state_lock` and converted every writer
CER-097 named, and that the lock narrows rather than closes the
read-modify-write window. The row keeps its existing `**RESOLVED
HARNESS015-main (INFRA-202) …**` note, its `Phase` cell (`68`), and its
quadrant — no row is deleted or moved (`docs/cer/backlog.md:6-7`).
`grep -c 'Concurrent writers are not expected in normal operation\.$'` against
the CER-050 line is not the check; the check is that the phrase no longer
stands unqualified.

**D5. CER-098 carries a RESOLVED note.** The `CER-098` row gains a bolded
`**RESOLVED Phase 109 — INFRA-286 …**` note appended to its Finding cell
naming what was actually done for (a), (b), (c) and the doc amendments, and
explicitly stating that (c) is a *bounded advisory* lock, not a queue and not a
multi-orchestrator guarantee. Its `Phase` cell stays `109`. The note must not
claim retry-or-queue semantics were implemented, because they were not.

### Cross-cutting

**E1. No behaviour outside the three worktree commands changes.** The diff
contains no edit to `create-story-worktree`, `claimed_story_ids`,
`_stamp_active_story`, `_clear_active_story`, `clear_attempt_count`,
`clear_permissions_artifact`, `story_context.py`, `next_action.py`,
`next_story.py`, `scope_guard.py`, `effort_db.py`, or any hook.

**E2. `schema_introduces` stays `false`.** `.companion/merge.lock` is a
zero-byte advisory lock file, not persistent state: it holds no data, is never
read for content, and has no human-editable field. No management-surface row is
owed in `docs/phases/phase-109.md` § Schema delivery. State it in the
architecture paragraph (D3) so a later reader does not mistake it for state.

**E3. The full test suite is green** (`tests/pairmode/`), run once without
`-x`.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Build in order A → C → B → D and run the suite after A and after C — B's tests
depend on the lock being in place, and D is prose that should be written last,
against what actually shipped.

**0. Rebase check.** Confirm INFRA-280..285 are all in your `HEAD`
(`## Requires`). Read the current bodies of `cmd_merge_story_worktree`,
`cmd_discard_story_worktree` and `_run_git` as they exist *now* — the line
numbers throughout this spec are anchors, not coordinates. If a sibling story
changed one of these functions, layer on top of its version; never revert it
to make an assertion here easier to satisfy. If a genuine conflict exists,
stop and report `FAIL-CAUSE` rather than resolving it by deleting its work.

**1. (A) Extract the teardown.** Add `_teardown_story_worktree` next to
`_worktree_paths`. Shape:

```python
def _teardown_story_worktree(project_path: Path, story_id: str) -> list[str]:
    """Remove a story's worktree and branch; return residue descriptions.

    Returns [] on full success. Never raises, never exits, never writes
    companion state — the caller decides what a residue means, because it
    means opposite things on the merge path (the story landed; clear the
    stamps anyway) and the discard path (nothing landed; leave them).
    """
```

Run `worktree remove --force <wt_rel>` first. Only on `returncode == 0` run
`branch -D <branch>`. On a failed removal, append **two** residue strings
(worktree and branch) and skip the delete entirely — git will refuse to delete
a branch that is still checked out in a worktree, and a second, guaranteed,
misleading error helps nobody (A2). Each residue string carries the failing
call's `(stderr or stdout).strip()` or a fixed fallback.

Add a small renderer next to it — e.g.
`_residue_lines(story_id, residue) -> list[str]` — producing the residue
strings followed by the two literal repair commands for whichever artifacts
remain (A4). Both commands use it so the operator sees identical text from
either path.

**2. (A) Rewire the two call sites.** In `cmd_merge_story_worktree`, replace
`flex_build.py:3184-3185` with a `_teardown_story_worktree` call whose result
is held, **then** run the three existing clears unchanged, **then** echo the
success line, **then** — if residue — echo the rendered lines to stderr and
`sys.exit(1)`. Put the ordering rationale in a comment: the `--ff-only` merge
is the durable "this story landed" fact; letting a failed `git worktree remove`
skip `clear_attempt_count` would carry a stale FAIL count into the next story,
re-creating the INFRA-237 bug from a cleanup hiccup. In
`cmd_discard_story_worktree`, replace `:3227-3245` with the same call but keep
the existing *early* exit: residue → render to stderr → `sys.exit(1)` **before**
`_clear_active_story` / `clear_permissions_artifact`. Do not "unify" the two
orderings; the asymmetry is the point and needs a comment saying so.

**3. (C) Add the merge lock.** Extend the `state_utils` import at
`flex_build.py:65`. Define `MERGE_LOCK_TIMEOUT_SECONDS` and `_merge_lock` per
C1/C2/C5, near the other worktree helpers. Wrap both commands' critical
sections (C3). Emit the C4 warning on non-acquisition and continue. Write C5's
docstring before you write the code — if you cannot state the non-guarantee
plainly, the design is wrong.

Do **not** add a retry loop, an unbounded wait, a PID/TTL lock record, or a
queue file. CER-098 asks for "retry-or-queue semantics, not manual repair";
the answer this story gives is *a bounded wait plus a precise, re-runnable
failure* (B2/B4), which satisfies "not manual repair" without inventing a
second coordination substrate that would then need its own staleness,
crash-recovery and observability story. Say that in the architecture paragraph
(D3) so the deviation from the finding's literal wording is on the record.

**4. (B) Write the failed-land contract.** Leave both failure branches
structurally as they are — they already tear down nothing — and add the
`recovery: `-prefixed block after git's error text (B2). Build the message
from the story ID and project dir so it is copy-pasteable. Add a comment above
the merge-failure branch stating why nothing is cleared: the story's commits
exist only on `pairmode/<ID>`; clearing `current_stories` disables scope
enforcement for a builder that may still be alive, and removing the worktree
releases the INFRA-280 claim, freeing the resolver to hand the same story to a
second dispatch while its work sits unmerged on a branch nobody will look at.

**5. Tests.** Extend `tests/pairmode/test_flex_build.py`. Add a new class
`TestStoryWorktreeMergeRobustness` alongside `TestStoryWorktreeLifecycle`
rather than growing the existing one; follow the file's existing fixture style
(`_init_git_repo`, `_commit_in`, `_git`, `_run`).

- A1-A4 are unit tests: `import flex_build` (the file already does this at
  `:1443`), monkeypatch `flex_build._run_git` with a recorder that returns
  `subprocess.CompletedProcess` objects keyed on the git subcommand, and assert
  on the returned list and on which calls were recorded.
- A5-A7, B3, B4, C4, C6 are end-to-end through `_run` / `Popen`, except where a
  forced git failure is needed — for those, drive the CLI in-process with
  `click.testing.CliRunner` over the imported `flex_build` group so the
  monkeypatch applies (the `_run` subprocess helper cannot see it). There is
  precedent for both styles in `tests/pairmode/`.
- C6 must genuinely run two processes; guard it with
  `pytest.importorskip("fcntl")` (or an equivalent skip) rather than asserting
  something weaker on a platform without it.

**6. (D) The prose.** Write D1's replacement paragraph, D2's clause, D3's new
architecture paragraph, and D4/D5's CER-row notes. For CER-050, do not delete
the historical finding text — the row is a record of what was true in Phase 68;
amend it, and say when and why the doctrine changed. For CER-098, resist
overclaiming on (c): the note must read as "bounded advisory lock + precise
recoverable failure", never as "merges are serialized".

**7. Ideology note (Step 4a — resolved inline, no conflict).** Three entries
shaped this spec. *"Rationale-bearing decisions over bare rules"* is why the
comments demanded in steps 2 and 4 are Ensures rather than niceties: the
merge/discard clear-ordering asymmetry (A5 vs A6) and the deliberate
do-nothing-on-failure branch (B1) both look like oversights to a reader who
does not know the reason, and the obvious "cleanup" of either is a regression.
*"Never silently pass contradictions"* is the whole of item A — a command that
prints success while leaving a broken claim behind is precisely the false
confidence the constraint protects against. *"Hooks are thin relays only"*
does **not** bind here (nothing in this story runs on a hook path), but its
rationale — never stall the operator — is why the lock is bounded at 120 s and
fail-open rather than reliable (C4/C5); adopting `state_utils.state_lock`
rather than writing a stronger lock keeps one locking scheme in the codebase,
per the reasoning INFRA-281 and INFRA-283 already recorded in
`docs/architecture.md`.

## Tests

Run from the story worktree root. After item A, and again after item C:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_flex_build.py \
  tests/pairmode/test_cli_surface_freeze.py \
  -q 2>&1 | tail -30
```

Then the adjacent surface, to catch collateral damage in the loop-state
clears the merge path calls:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_flex_build_attempt_counter.py \
  tests/pairmode/test_flex_build_permissions_create.py \
  tests/pairmode/test_flex_build_check_story_scope.py \
  tests/pairmode/test_state_utils.py \
  tests/pairmode/test_story_context.py \
  tests/pairmode/test_next_action.py \
  -q 2>&1 | tail -30
```

(Skip any of the above that does not exist in the tree; do not create it.)

Then the full suite **without `-x`**, so a known failure cannot mask a new one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Machine-checkable Ensures:

```bash
# D1 — the serialism claim is gone
grep -c 'loop serial (one worker in flight at a time)' docs/architecture.md   # 0

# A1/C1 — the new symbols exist
grep -n '_teardown_story_worktree\|MERGE_LOCK_TIMEOUT_SECONDS\|_merge_lock' \
  skills/pairmode/scripts/flex_build.py

# A6 — the discard path no longer open-codes the two git calls
grep -n 'branch", "-D"' skills/pairmode/scripts/flex_build.py               # one site only

# B2 — the recovery block exists on both failure branches
grep -c 'recovery: ' skills/pairmode/scripts/flex_build.py                   # >= 2

# D5 — the CER row is closed
grep 'CER-098' docs/cer/backlog.md | grep -c 'RESOLVED Phase 109'            # 1
```

Acceptance:

- every new test from A1-A8, B1-B4, C1-C6, D1-D5 passes (C6 may report as
  skipped on a platform without `fcntl`; a skip is acceptable, a deletion is
  not);
- every pre-existing test in `TestStoryWorktreeLifecycle` passes under its
  original name (A7);
- `tests/pairmode/test_cli_surface_freeze.py` passes with no edit (A8);
- the full suite is green. If a failure appears, verify it reproduces on clean
  `HEAD` before attributing it elsewhere, and say so explicitly in the build
  result.

## Out of scope

- **Retry-or-queue semantics for merges.** CER-098's literal wording asks for
  them; this story deliberately answers with a bounded advisory lock plus a
  precise, idempotent, re-runnable failure (step 3's rationale). A real queue
  needs its own staleness, crash-recovery and observability design — that is a
  separate story with its own reversibility argument, not a clause here.
- **Multi-orchestrator safety.** Explicitly out of scope for the whole phase
  (`docs/phases/phase-109.md` § Scope statement). The lock reduces contention
  between two calls from one loop; it is not a distributed lock and must not be
  documented as one.
- **Auto-resolving rebase conflicts, or any change to the rebase branch's
  abort-and-exit behaviour.** INFRA-224 semantics; this story only adds the
  `recovery: ` block to its output.
- **Changing `claimed_story_ids`' rule that a leftover branch without a
  directory is not a claim** (`flex_build.py:217-221`). Item A makes that
  leftover *loud* rather than silent, which is the correct fix; widening the
  claim definition would make the resolver hide a story for a condition
  `create-story-worktree` already reports.
- **A repair/GC subcommand** (`flex_build.py prune-worktrees`, `git worktree
  prune` wrapping, or automatic cleanup of pre-existing residue). This story
  reports residue with exact repair commands; automating the repair is a new
  destructive command that needs its own spec.
- **Retroactive cleanup of any residue currently in flex's own
  `.pairmode-worktrees/`.** The new checks apply from the next merge onward.
- **Rewriting the historical serialism sentence in
  `docs/stories/INFRA/INFRA-257.md`.** Completed story files are the record of
  what was decided when; only `docs/architecture.md` and `docs/cer/backlog.md`
  carry current doctrine and only they are amended (D1/D2/D4).
- **Any further `docs/cer/backlog.md` grooming** beyond the CER-050 and CER-098
  rows named in D4/D5. Other rows this phase touched were closed by their own
  stories.
