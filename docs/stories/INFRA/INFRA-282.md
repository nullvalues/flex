---
id: INFRA-282
rail: INFRA
title: Story-keyed attempt counter with per-key escalation and E9 guard compatibility (CER-095.3)
status: draft
phase: "109"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/scripts/subagent_transcript.py
touches:
  - docs/architecture.md
  - docs/cer/backlog.md
  - tests/pairmode/test_flex_build_attempt_counter.py
  - tests/pairmode/test_flex_build.py
  - tests/pairmode/test_subagent_transcript.py
  - tests/pairmode/test_next_action.py
  - docs/stories/INFRA/INFRA-282.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase 109 restores single-orchestrator parallel story builds. CER-095 names
four single-slot coordination structures that break under two concurrent
builders; INFRA-280 closed item (1) (resolver in-flight claim) and INFRA-281
closed item (2) (story-keyed `current_story` + per-call `scope_guard`
resolution). **This story closes item (3): the attempt counter.**

`.companion/attempt_counter.json` is a **single-slot whole-file rewrite**.
`write_attempt_count` (`skills/pairmode/scripts/flex_build.py` ~1182) writes
`{"story_id": ..., "attempt_count": ...}` — one story, whole file replaced.
`read_attempt_count` (~1216) returns `0` when the recorded `story_id` does not
match the requested one. `bump_attempt_count` (~1198) is read-then-write on top
of both. With two builders in flight the consequences are silent and
destructive:

- Story A FAILs at attempt 2 and stamps the file. Story B then FAILs, and its
  bump — reading `0` because of the story-ID mismatch — rewrites the whole file
  as `{B: 1}`. A's count is gone. The next `next-action` poll for A reads `0`,
  infers outcome `none` instead of `FAIL`, and re-dispatches A at attempt 1 on
  the *base* model. **The escalation ladder silently resets** — the loop-breaker
  and model-upgrade rows (`next_action.resolve_next_action` Rows 5/6/7,
  `attempt_count == 1` / `== 2`) can never be reached while a sibling story is
  also failing, so a story that should escalate loops forever at attempt 1.
- `clear_attempt_count` (~1270) unlinks the **whole file**, and
  `cmd_merge_story_worktree` calls it unconditionally on a successful land
  (~2939). Landing story A therefore wipes still-building story B's live count —
  the same class of cross-story clobber INFRA-281 fixed for the active-story
  stamp, where `_clear_active_story` gained a `--story-id`.

CER-095's fix line also requires that **INFRA-264's E9 guard be per-key**. That
guard is `subagent_transcript._story_accepts_late_bump` (~898), which gates the
*reconciliation-time* FAIL bump. Its rule 2 asks "is this story currently being
built?" by reading `state.json["current_story"]` — the flat slot that INFRA-281
demoted to a *derived mirror* of the authoritative `current_stories` map. With
two builders in flight the mirror names only one of them, so a legitimate late
FAIL bump for the *other* live story is refused whenever that story has no
counter entry yet — i.e. exactly on its first FAIL, the one that starts the
ladder. The guard must consult the keyed record, not the mirror.

The design follows INFRA-281's precedent exactly: a story-keyed record becomes
the authority, the legacy flat shape stays readable so no migration step is
required, and every clear is scoped to its own key. This is the era's
"harness holds nothing not reconstructable from `next-action`" invariant applied
to the counter: the counter is durable control state the resolver reads, so it
must be able to hold one entry per in-flight story rather than one globally.

## Requires

- INFRA-281 is complete on `main`: `skills/pairmode/scripts/story_context.py`
  defines `CURRENT_STORIES_KEY = "current_stories"`, `set_current_story`,
  `clear_current_story(companion_dir, story_id=None)` and
  `get_current_stories(companion_dir)`; `flex_build._clear_active_story` takes a
  story ID and both `merge-story-worktree` and `discard-story-worktree` pass
  their own. (`docs/phases/phase-109.md` § Ordering: "INFRA-282 (keyed counter)
  after 281".)
- `skills/pairmode/scripts/flex_build.py` defines, in the
  `# Per-story attempt counter (BUILD-022)` block: `_attempt_counter_path`
  (~1162), `write_attempt_count` (~1182), `bump_attempt_count` (~1198),
  `read_attempt_count` (~1216), `clear_attempt_count` (~1270), and the three
  Click commands `write-attempt-count`, `read-attempt-count`,
  `clear-attempt-count`.
- `flex_build.py` already imports `_atomic_write_json` from `state_utils`
  (~line 65). No new third-party import is needed.
- `skills/pairmode/scripts/next_action.py` composes `read_attempt_count` as a
  library call in `infer_position` (~782), passing the resolved story ID.
- `skills/pairmode/scripts/subagent_transcript.py` imports
  `bump_attempt_count` and `read_attempt_count` from `flex_build` through a
  dual try/except import (~76–81) that must keep working under the hook's flat
  `sys.path`, and defines `_story_accepts_late_bump` (~898) and its own
  `_read_state` helper.
- `tests/pairmode/resolver_fixtures.py` (~206–212) writes
  `attempt_counter.json` in the **legacy flat shape**. It is a shared fixture
  used by many resolver tests and must keep working **unmodified** — that is
  the story's built-in proof that legacy-shape reads still resolve.
- `docs/cer/backlog.md` contains row `CER-095` carrying `**INFRA-280 …**` and
  `**INFRA-281 …**` resolution notes and a sentence stating that items (3) and
  (4) "remain open under INFRA-282/INFRA-283".
- `docs/architecture.md` § `## Pairmode build loop` carries the INFRA-281
  `current_stories` paragraphs (~266–290).

## Ensures

Each assertion is independently checkable by reading a file or running a
command. Line numbers are orientation only; match on content.

### A — keyed storage with legacy read compatibility

1. **The on-disk shape is story-keyed.** After
   `write_attempt_count("INFRA-282", 2, p)` followed by
   `write_attempt_count("INFRA-283", 1, p)`, the JSON at
   `p/.companion/attempt_counter.json` contains a mapping under a single
   top-level key (name at builder's discretion, e.g. `"stories"`) with **both**
   `"INFRA-282" -> 2` and `"INFRA-283" -> 1` present in the same file. Neither
   write removed or altered the other story's entry.

2. **A keyed read helper exists and is pure.** A module-level helper in
   `flex_build.py` (e.g. `_read_attempt_counters(project_dir) -> dict[str, int]`)
   returns the full story-ID → count mapping, returns `{}` when the file is
   absent, unreadable, or malformed JSON, and performs **no writes on any
   path** (including when it normalises a legacy file).

3. **Legacy flat files still read correctly.** Given a file whose content is
   exactly `{"story_id": "INFRA-282", "attempt_count": 3}`,
   `read_attempt_count("INFRA-282", p)` returns `3` and
   `read_attempt_count("INFRA-999", p)` returns `0`. No migration write occurs
   on read — the file's bytes are unchanged after the read.

4. **Legacy files are upgraded in place on the next write.** After a write or
   bump against a legacy-shape file, the file is in the keyed shape and the
   pre-existing legacy entry is preserved as one of its keys.

5. **Reads are per-key and never cross-attribute.**
   `read_attempt_count(story_id, p)` returns the count stored under
   `story_id` only; a count stored for a different story never satisfies a
   read for `story_id` (returns `0`), and — the behaviour change — a count
   stored for `story_id` is returned even when other stories also have
   entries. Malformed per-key values (non-int, negative-typed, `None`) yield
   `0` for that key without affecting other keys.

6. **Bumps are independent.** With entries `{A: 2, B: 1}`,
   `bump_attempt_count(B, p)` returns `2`, leaves `A` at `2`, and
   `bump_attempt_count(A, p)` then returns `3`. A bump for a story with no
   entry returns `1` and leaves every other entry untouched.

7. **Writes are atomic.** `write_attempt_count` (and therefore
   `bump_attempt_count`) persists via `state_utils._atomic_write_json` —
   temp-file + `os.replace` — rather than `path.write_text`. Verifiable:
   `grep -n "write_text" skills/pairmode/scripts/flex_build.py` shows no
   `write_text` call inside the attempt-counter block.

### B — scoped clears

8. **`clear_attempt_count` accepts a story scope.** Its signature is
   `clear_attempt_count(project_dir: Path, story_id: str | None = None)`.
   With `story_id` given it removes **only** that story's entry, leaving every
   other entry intact and the file present; when removing the last entry it
   may delete the file. With `story_id` omitted it retains today's behaviour
   (whole file removed) — this unscoped path is what the `clear-attempt-count`
   CLI keeps offering for operator recovery.

9. **The CLI exposes the scope.** `flex_build.py clear-attempt-count` gains an
   **optional** `--story-id` option. `clear-attempt-count --project-dir <p>`
   with no `--story-id` still exits 0 and removes the file (unchanged
   behaviour); `clear-attempt-count --story-id A --project-dir <p>` exits 0 and
   removes only `A`'s entry. No other CLI signature changes; `--story-id` is
   validated by the same path as the other story-ID options in the file if one
   exists, otherwise unvalidated.

10. **Merge clears only its own story.** `cmd_merge_story_worktree` calls
    `clear_attempt_count(project_path, story_id)` — passing the story it just
    landed. Verifiable: with entries `{A: 2, B: 1}` present, merging `A`
    leaves `read_attempt_count("B", p) == 1`. The call site carries a comment
    naming `INFRA-282` / `CER-095.3` and stating the reason (an unconditional
    clear wipes a still-building sibling's escalation state), matching the
    INFRA-281 comment style two lines below it.

11. **Discard does not clear the counter.** `cmd_discard_story_worktree` still
    makes **no** `clear_attempt_count` call — a discarded attempt must keep its
    count so the ladder escalates on the retry. Verifiable:
    `grep -n "clear_attempt_count" skills/pairmode/scripts/flex_build.py`
    returns no line inside `cmd_discard_story_worktree`.

### C — per-key escalation through the resolver

12. **The resolver escalates each story on its own count.** With
    `attempt_counter.json` holding `{A: 0-absent, B: 2}` and both stories in
    a FAIL-shaped position, `next_action.resolve_next_action` selects the
    first-attempt row for `A` and the attempt-3 escalation row for `B` — i.e.
    `position["attempt_count"]` is `0` for `A` and `2` for `B` from the same
    file. `next_action.py` requires **no source change** for this: it already
    passes the resolved story ID to `read_attempt_count`. Verifiable:
    `git diff main -- skills/pairmode/scripts/next_action.py` is empty.

13. **A regression test pins the cross-clobber.**
    `tests/pairmode/test_flex_build_attempt_counter.py` contains a test whose
    name contains `parallel` (or `cross_story`) that reproduces the CER-095
    sequence end-to-end: bump `A` twice, bump `B` once, assert `A` is still
    `2`; then merge-clear `A` and assert `B` is still `1`. It fails against
    pre-story `flex_build.py`.

14. **The shared resolver fixture is unmodified.**
    `tests/pairmode/resolver_fixtures.py` is not edited by this story
    (`git diff main -- tests/pairmode/resolver_fixtures.py` is empty) and every
    test that consumes it still passes — the legacy-shape read path is
    exercised by the existing suite rather than by a new test alone.

### D — E9 guard per-key (INFRA-264 compatibility)

15. **The late-bump guard consults the keyed record.**
    `subagent_transcript._story_accepts_late_bump`'s "is the loop building
    this story?" check resolves `True` when `story_id` is a key of
    `state.json["current_stories"]`, and falls back to the flat
    `state.json["current_story"]["id"]` only when `current_stories` is absent
    (pre-INFRA-281 state files). It does **not** require the story to be the
    single/most-recent entry.

16. **Two live stories both pass the guard.** With
    `state.json["current_stories"]` holding entries for both `A` and `B` and no
    counter file at all, `_story_accepts_late_bump(p, "A")` and
    `_story_accepts_late_bump(p, "B")` both return `True`. Under the pre-story
    code exactly one of them returns `False`.

17. **The guard's other rules are unchanged.** A story whose frontmatter
    `status` is in `_LATE_BUMP_BLOCKED_STATUSES` still returns `False`; a story
    that is neither counter-recorded nor in `current_stories` still returns
    `False`; the helper is still pure-read, still never raises, and still
    returns `False` from its outer `except`. The synchronous PostToolUse-time
    bump in `record_attempt_from_transcript` remains **ungated** by this helper.

18. **No new import in the hook path.** The change to
    `_story_accepts_late_bump` reads the state dict the helper's existing
    `_read_state` call already returns; it adds **no** import of
    `story_context` (or any other module) to `subagent_transcript.py`.
    Verifiable: `git diff main -- skills/pairmode/scripts/subagent_transcript.py`
    contains no added `import` line.

### E — documentation and backlog

19. **Architecture records the keyed counter.** `docs/architecture.md` §
    `## Pairmode build loop` gains a short paragraph — placed adjacent to the
    INFRA-281 `current_stories` material — whose lead is a bolded label
    containing `INFRA-282` and `CER-095.3`, and whose body states: (a)
    `.companion/attempt_counter.json` is story-keyed, one entry per in-flight
    story; (b) the legacy flat shape is still read and is upgraded on the next
    write, so no migration step exists; (c) merge clears only its own key and
    discard clears nothing, with the reason for each; (d) the E9 late-bump
    guard resolves liveness from `current_stories`.

20. **The CLI inventory line stays truthful.** The `flex_build.py` entry in
    `docs/architecture.md` § `## Module structure` (~line 56) has its
    `clear-attempt-count` mention amended to note the optional `--story-id`
    scope. Existing content on that line is preserved; the clause is appended,
    not substituted.

21. **The CER row records the closure.** The `CER-095` row in
    `docs/cer/backlog.md` gains an `**INFRA-282 (Phase 109) — item (3)
    resolved:** …` note in the same house format as the existing INFRA-280 /
    INFRA-281 notes, stating what was done (keyed counter, scoped clears, E9
    guard per-key). The pre-existing sentence naming items (3) and (4) as open
    is amended so that only item (4) / INFRA-283 remains named as open. The row
    is not deleted, not moved between quadrants, its `Source`/`Date` cells are
    unchanged, and its trailing phase cell still reads `109` (CER-095 is not
    fully closed until INFRA-283 lands).

22. **The backlog table is not corrupted.** The edited row still parses as a
    table row with the same column count as its neighbours; any literal pipe in
    the new note is escaped as `\|`, matching the existing rows' convention.

### F — suite

23. **The suite is green.** `uv run pytest tests/pairmode/ -q` (run **without**
    `-x`) shows no new failures relative to clean `HEAD` — see `## Tests`.

## Instructions

Work inside this story's worktree. All paths are relative to the repo root.

### Part A — keyed storage (`flex_build.py`)

1. In the `# Per-story attempt counter (BUILD-022)` block, add a module-level
   constant for the container key (e.g. `_ATTEMPT_COUNTER_STORIES_KEY =
   "stories"`) and a pure reader:

   ```
   def _read_attempt_counters(project_dir: Path) -> dict[str, int]:
   ```

   It reads `_attempt_counter_path(project_dir)`, returns `{}` on
   absent/`OSError`/`JSONDecodeError`, and normalises **both** shapes:

   - keyed: `data[<stories key>]` is a dict → coerce each value with `int()`,
     dropping any key whose value will not coerce;
   - legacy: `data` has a string `"story_id"` → return
     `{data["story_id"]: int(data["attempt_count"])}` (dropping the entry if the
     count will not coerce).

   Never write from this function — normalisation is in-memory only
   (assertion 2/3). Update the block's header comment to name INFRA-282 /
   CER-095.3 alongside BUILD-022.

2. Rewrite `write_attempt_count(story_id, count, project_dir)` as
   read-modify-write over the keyed map: `counters = _read_attempt_counters(...)`,
   `counters[story_id] = count`, then persist via
   `_atomic_write_json(path, {<stories key>: counters})` after
   `path.parent.mkdir(parents=True, exist_ok=True)`. `_atomic_write_json` is
   already imported at line ~65 — do not add an import, and do not use
   `path.write_text` (assertion 7).

3. Leave `bump_attempt_count`'s body shape as-is
   (`read_attempt_count(...) + 1` then `write_attempt_count(...)`) — it becomes
   per-key for free once the two helpers are keyed. Update its docstring: the
   "a mismatched story_id resets the counter to 1" sentence is now **wrong** and
   must be replaced with the keyed semantics (each story has its own entry;
   another story's entry is neither read nor overwritten).

4. Rewrite `read_attempt_count(story_id, project_dir)` as
   `_read_attempt_counters(project_dir).get(story_id, 0)`. Keep the docstring's
   "pure read — no state writes" guarantee and note the legacy-shape
   compatibility.

5. Change `clear_attempt_count` to
   `clear_attempt_count(project_dir: Path, story_id: str | None = None)`:

   - `story_id is None` → unlink the file if present (today's behaviour,
     preserved for operator recovery);
   - `story_id` given → `counters = _read_attempt_counters(...)`;
     `counters.pop(story_id, None)`; if the result is empty, unlink the file;
     otherwise rewrite it atomically with the remaining entries. Missing file
     or missing key is a silent no-op.

   Document *why* the scoped form exists (a sibling builder's live escalation
   state), not just what it does.

6. Add `--story-id` as an **optional** Click option on `cmd_clear_attempt_count`
   and forward it. Keep the parameter order and every other option unchanged so
   existing invocations keep working.

7. In `cmd_merge_story_worktree`, change the `clear_attempt_count(project_path)`
   call (~2939) to `clear_attempt_count(project_path, story_id)` and extend the
   comment above it: keep the INFRA-237 rationale, append the INFRA-282 /
   CER-095.3 reason. Mirror the phrasing of the INFRA-281 comment on
   `_clear_active_story` a few lines below.

8. **Do not** add a `clear_attempt_count` call to `cmd_discard_story_worktree`
   (assertion 11) — a discarded attempt must keep its count so the retry
   escalates.

### Part B — E9 guard (`subagent_transcript.py`)

9. In `_story_accepts_late_bump`, replace the `is_current` computation. Today it
   reads `state.get("current_story")` and compares `current.get("id")`. Change
   it to check `state.get("current_stories")` first: when that is a dict,
   `is_current = story_id in current_stories`; only when it is absent or not a
   dict, fall back to the existing flat-`current_story` comparison. Keep the
   whole thing inside the existing `try/except` so a malformed state file still
   falls through to `is_current = False`. Add **no import** (assertion 18) — the
   hook loads this module under a flat `sys.path`, and the dual import block at
   ~76–81 exists precisely because that path is fragile.

10. Update the helper's docstring rule 2 to say the check is against the
    story-keyed `current_stories` record (INFRA-281's authority) with the flat
    key as a pre-INFRA-281 fallback, and why: with two builders in flight the
    flat mirror names only one of them, so keying on it refuses the other
    story's first late FAIL bump and stalls its ladder at attempt 1.

### Part C — tests

11. Extend `tests/pairmode/test_flex_build_attempt_counter.py` (the existing
    home of these CLI tests) with, at minimum: two-story coexistence
    (assertion 1); `_read_attempt_counters` on absent / malformed / legacy /
    keyed files (assertions 2–3); legacy upgrade-on-write (assertion 4);
    independent bumps (assertion 6); scoped clear leaves the sibling
    (assertion 8); unscoped clear still removes the file (assertion 8/9);
    `clear-attempt-count --story-id` CLI exit 0 and scoped effect
    (assertion 9); and the named cross-clobber regression test (assertion 13).
    Reuse the file's existing CliRunner/tmp_path helpers; do not add a new
    fixture framework.

12. Add the merge-clear scoping test near the existing
    `merge-story-worktree` tests in `tests/pairmode/test_flex_build.py`, reusing
    whatever git-repo fixture those tests already build. If that fixture does
    not exist, assert assertion 10 at the library level instead
    (`clear_attempt_count(p, "A")` with `{A, B}` present) and leave the CLI
    path to the existing merge tests — do not build a new git fixture for this.

13. Add the guard tests to `tests/pairmode/test_subagent_transcript.py`
    (assertions 15–17): two live stories in `current_stories` both pass; a
    story in neither `current_stories` nor the counter fails; a blocked-status
    story fails; a pre-INFRA-281 state file with only the flat `current_story`
    still passes for that story. Reuse the file's existing state-file helpers.

14. Add the per-key escalation test (assertion 12) to
    `tests/pairmode/test_next_action.py`, driving `resolve_next_action` through
    the same fixture pattern the surrounding tests use. Write the keyed counter
    file directly (or via `write_attempt_count`) rather than editing
    `resolver_fixtures.py` — that file must stay untouched (assertion 14).

### Part D — documentation and backlog

15. Add the architecture paragraph (assertion 19) and the § Module structure
    clause (assertion 20). Follow the surrounding prose style: bolded lead
    label, ticket reference, rationale stated next to the rule. Do not
    restructure the section or renumber its existing sequence.

16. Append the `**INFRA-282 (Phase 109) — item (3) resolved:** …` note to the
    `CER-095` Finding cell and amend the trailing "items (3) and (4) … remain
    open" sentence to name only item (4) / INFRA-283. Copy the exact format of
    the INFRA-280 / INFRA-281 notes already in that cell. Escape literal pipes
    as `\|`. Do not reword the original finding, do not move the row, do not
    change the phase cell.

### Notes

17. **Accepted limitation — the read-modify-write window.** Two `write_attempt_count`
    calls that interleave between their read and their `os.replace` can still
    lose one update. Atomic replacement (assertion 7) guarantees no reader ever
    sees a truncated file and no *corrupt* state is written; it does not
    serialise concurrent RMW. This is deliberate and deferred: file-level
    serialisation of `.companion/` writers is INFRA-285's advisory state lock
    (CER-097), and pre-empting it here would create a second, competing locking
    scheme. State the limitation in the architecture paragraph from
    assertion 19 — do not leave it implicit.

18. **Ideology note (Step 4a, resolved inline).** Three entries in
    `docs/ideology.md` shaped this spec. *"Never silently pass contradictions"*
    is the constraint the whole story serves: a counter that silently reports
    `0` for a story that has failed twice is precisely a contradiction passing
    unnoticed, and its "silent bypass is never permitted" rationale is why
    instruction 17 requires the residual RMW window to be **written down**
    rather than quietly accepted. *"We prefer rationale-bearing decisions over
    bare rules"* is why assertions 10, 11, 19 and the docstring rewrites in
    instructions 3, 5 and 10 all require the *reason* next to the rule —
    especially assertion 11, where a bare "discard does not clear" reads like an
    omission to the next agent and would be "fixed" into a ladder-resetting bug.
    *"Sidebar owns all state writes"* is respected: this story adds no writer;
    it changes the shape written by helpers that already own the file, and the
    E9 guard stays pure-read on the hook side (assertion 17), so the
    hook-as-thin-relay constraint is untouched. No conflict required routing
    around.

19. **Do not** change `next_action.py` (assertion 12) or
    `resolver_fixtures.py` (assertion 14). If a resolver test appears to need a
    source change, the keyed read is wrong — fix the helper, not the caller.

## Tests

Targeted, then full:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_flex_build_attempt_counter.py \
  tests/pairmode/test_flex_build.py \
  tests/pairmode/test_subagent_transcript.py \
  tests/pairmode/test_next_action.py -q 2>&1 | tail -30
```

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Run the full suite **without `-x`**, so a known pre-existing failure cannot mask
a real one.

**Acceptance:**

- The targeted run is fully green.
- The full-suite result is unchanged from clean `HEAD`: green except any known
  pre-existing failure (e.g.
  `test_observability_ui.py::test_ui_build_emits_dist_index_html`), which must
  be shown to reproduce on clean `HEAD` if it appears.
- `git diff main -- skills/pairmode/scripts/next_action.py tests/pairmode/resolver_fixtures.py`
  is empty (assertions 12 and 14).

Also exercise the CLI directly, as a live check of the scoped clear:

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/flex_build.py \
  clear-attempt-count --help ; echo "exit=$?"
```

`--story-id` must appear in the help output and the command must exit 0.

## Out of scope

- **Phase-keyed checkpoint state** (CER-095 item 4) — that is INFRA-283. This
  story touches neither `checkpoint_step` nor `checkpoint_phase`.
- **effort.db concurrency** — WAL, `busy_timeout`, atomic attempt-number
  derivation and sweep ownership are INFRA-284 (CER-096). The attempt counter is
  deliberately *independent* of `effort_tracking` (see `bump_attempt_count`'s
  docstring: core build-loop control state, not observability), and this story
  must not couple them.
- **A lock or advisory-lease protocol for `.companion/` writers** — INFRA-285
  (CER-097). See instruction 17: this story delivers atomic *replacement*, not
  serialised read-modify-write.
- **Merge robustness / return-code checks** on `merge-story-worktree` —
  INFRA-286 (CER-098). This story changes exactly one call inside that command.
- **Migrating existing `attempt_counter.json` files.** There is no migration
  command and no bootstrap change: legacy files are read as-is and upgraded on
  the next write. A one-shot migration would be a state write from a code path
  that has no business writing.
- **Changing `next_action.py`'s escalation rows, model-selection ladder, or
  `SCHEMA_VERSION`.** Per-key escalation is a consequence of keyed storage, not
  a resolver change.
- **Recording the counter in observability** (`flex_observability.py`, the SPA,
  `pairmode_effort.py`) — the counter is control state, and surfacing it is an
  OBS-rail concern.
- **`resolver_fixtures.py` migration to the keyed shape.** Leaving it on the
  legacy shape is deliberate: it is the suite's standing regression test for
  read compatibility.
