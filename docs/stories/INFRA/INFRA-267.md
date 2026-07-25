---
id: INFRA-267
rail: INFRA
title: Stage docs/eras in commit paths, era-ledger status updates, backfill phases 96-103 (CER-082)
status: draft
phase: "104"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/scripts/phase_new.py
  - docs/eras/003-flex-orchestrator-as-harness.md
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - docs/architecture.md
  - docs/cer/backlog.md
  - tests/pairmode/test_phase_new.py
  - tests/pairmode/test_flex_build_mark_phase_complete.py
  - tests/pairmode/test_record_checkpoint_step.py
  - tests/pairmode/test_template_reduction.py
  - tests/pairmode/test_flip_dogfood.py
  - docs/stories/INFRA/INFRA-267.md
---

## Context

The era doc is supposed to be the era's phase ledger — the one place a cold
reader learns which phases the era contains and where each one stands. On this
repo it is neither. CER-082 recorded two halves of the failure; verifying it for
this spec turned up a third, worse than either.

**Half 1 — nothing commits the ledger.** `phase_new.py::_update_era_phases_table`
appends `| <phase> | <title> | planned |` to the active era doc on every
scaffold. No commit path stages `docs/eras/`. CER-082 cites `CLAUDE.build.md`
step 5c (spec-mode commit) and Step 1.5 (pre-reviewer methodology commit) —
**both of those sections no longer exist**: HARNESS006-main flipped
`CLAUDE.build.md` and its `.j2` to the ~20-line dispatch loop and neither
retains any staging-path list. So the current harness does not omit
`docs/eras/` from a list; it has no list, which is the same drift with fewer
places to fix it. Observed live in forqsite (2026-07-22): three uncommitted
ledger rows spanning PM064-main, PM064-post1, PM065-main, two from prior
sessions, discovered as an "unexplained" modified era doc.

**Half 2 — the status column is write-once.** `flex_build.py`'s
`_mark_phase_complete_in_index` flips `docs/phases/index.md` only. Nothing ever
advances the ledger's third cell, so every checkpointed phase reads `planned`
in the era doc forever. Both forqsite PM064 rows were complete-and-tagged while
still reading `planned`.

**Half 3 (found while verifying this story) — on *this* repo the appender has
never fired at all.** `_update_era_phases_table` matches its target section with
`stripped == "## Phases"`. Era 003's heading is
`## Phases (proposed — \`HARNESS\` predicate, suffix scheme)`. The equality
fails, `inserted` stays `False`, `in_phases_table` stays `False`, and the
function returns having written nothing — silently, with no error path.
Confirmed by running `_update_era_phases_table(d, '003', '109', ...)` against a
copy of the live era doc: no row appears. That is why `docs/eras/003-flex-orchestrator-as-harness.md`
lists only the 8 originally-designed HARNESS phases and none of 96-108,
including 104-108, scaffolded 2026-07-25, which the orchestrator's prompt
correctly suspected were never appended. A ledger that no tool writes and no
commit stages is not drifting — it is dead.

**Why this is worth code and not just a doc fix.** `flex_build.py check-index`
already has the enforcement (check 2c, `index_integrity.py`
`_parse_era_phase_table`): it compares every era-doc row that carries a
`Status` column against `docs/phases/index.md` and reports a `cross-link`
violation on mismatch. Era 003's narrative table has no `Status` column, so
check 2c skips it entirely — the checker is live and silent because there is
nothing for it to read. Give the era doc a real ledger and the existing checker
starts guarding it for free; era 001 is the proof, contributing all 5 of the
current era-doc cross-link violations from exactly this drift.

## Requires

- **INFRA-265 is complete and merged.** It rewrites the phase-key resolution
  inside `_record_checkpoint_step` (precedence: `--phase-key` →
  `state.json["checkpoint_phase"]` → unambiguous re-derivation → exit 2) and
  edits the same two files this story edits (`flex_build.py`,
  `CLAUDE.build.md` + its `.j2`, and `tests/pairmode/test_record_checkpoint_step.py`).
  Every line number quoted below is a **pre-INFRA-265 anchor**: locate the
  named function or string, never the line. Rebase on the current branch tip
  before starting; a `flex_build.py` conflict is expected and resolvable — 265
  changes how the phase key is *chosen*, this story changes what is *written*
  once it is chosen.
- Phase-104 ordering (`docs/phases/phase-104.md` § Ordering) puts this story
  last of the `flex_build.py` group: build order 263, 264, 265, 266, **267**, 268.
- `skills/pairmode/scripts/flex_build.py` exposes, at spec-time line numbers:
  `_mark_phase_complete_in_index` (716), `cmd_mark_phase_complete` (801),
  `_record_checkpoint_step` (~2072, whose terminal branch calls
  `_mark_phase_complete_in_index` at 2138), and imports
  `_parse_frontmatter` from `schema_validator` at line 39.
- `skills/pairmode/scripts/phase_new.py` exposes `_detect_active_era` (88) and
  `_update_era_phases_table` (124), whose section match is
  `if stripped == "## Phases":` (163).
- `skills/pairmode/scripts/index_integrity.py` exposes `_parse_era_phase_table`
  (90) — matches any pipe table having both a `Phase`/`Phase key`/`Phase ref`
  column and a `Status` column — and check 2c consumes it (~281).
- `docs/eras/003-flex-orchestrator-as-harness.md` has `status: active`, a
  `## Phases (proposed — ...)` section holding a 4-column
  `| Phase key | Title | Rail | Intent |` narrative table (spec-time lines
  ~115-125), and an `## Era summary` section whose first sentence reads
  `All 8 planned phases complete as of 2026-07-03:`.
- `docs/phases/index.md` has rows 96-108 with statuses: 96 `complete`,
  97 `deferred`, 98-103 `complete`, 104-108 `planned`.
- Line-count gates, both currently at their ceiling: `tests/pairmode/test_template_reduction.py::test_non_blank_line_count`
  (rendered `CLAUDE.build.md.j2` ≤ 40 non-blank lines; renders at **exactly 40**
  today) and `tests/pairmode/test_flip_dogfood.py::test_live_build_md_non_blank_line_count`
  (live `CLAUDE.build.md` ≤ 40 non-blank; at **39** today). Both files must be
  edited by **extending existing lines**, adding no new non-blank line.
- `docs/cer/backlog.md` contains a `CER-082` row whose `Phase` cell reads `—`.
- Baseline `flex_build.py check-index --project-dir .` output: **48** violation
  lines, of which **5** are `docs/eras/001-initial.md` cross-link rows and
  **0** reference `docs/eras/002-*` or `docs/eras/003-*`. Record this before
  changing anything.
- Known environmental failure inside fresh story worktrees:
  `tests/pairmode/test_observability_ui.py::test_ui_build_emits_dist_index_html`
  (CER-090). Not caused by this story.

## Ensures

**A. Appender — the section match no longer fails on a qualified heading.**

1. `phase_new.py::_update_era_phases_table` treats a line as the ledger heading
   when it is exactly `## Phases` **or** begins with `## Phases` followed by
   whitespace; the first such heading in document order wins. Headings at other
   depths (`### Phase G scope`) never match.
2. Calling `_update_era_phases_table(project_dir, era_id, "109", "T")` against
   an era doc whose only ledger heading is `## Phases (proposed — x)` appends
   `| 109 | T | planned |` as the last row of that section's first pipe table.
   (Today it appends nothing and returns silently — the regression this pins.)
3. The exact-`## Phases` behaviour is unchanged: the same call against an
   `era_new.py`-shaped doc (`## Phases` + `| Phase | Title | Status |`) still
   appends exactly one row at the end of that table.
4. `_update_era_phases_table` still writes nothing and raises nothing when
   `docs/eras/` is absent, no file matches `era_id`, or no ledger heading
   exists.

**B. Ledger status advances with the index, from the same phase key.**

5. `flex_build.py` defines `_mark_phase_complete_in_era_ledger(phase_key: str, project_dir: Path) -> bool`
   which sets the third cell of the `## Phases` ledger row whose first cell
   equals `phase_key` to `complete` in the **active** era doc (frontmatter
   `status: active`), writing via `NamedTemporaryFile` + `os.replace` in the
   target's own directory — the same atomic pattern as
   `_mark_phase_complete_in_index`.
6. It returns `False` and writes nothing, raising no exception and printing no
   traceback, in every one of these states: `docs/eras/` missing; no era doc
   with `status: active`; active era doc has no ledger heading; ledger table
   has no row whose first cell equals `phase_key`; that row's status cell
   already reads `complete`. **Legacy eras with no ledger row must not crash
   the checkpoint.**
7. It never edits an era doc whose frontmatter `status` is not `active`.
8. `flex_build.py mark-phase-complete --phase <K> --project-dir <d>` flips both
   `docs/phases/index.md`'s row for `K` **and** the active era ledger's row for
   `K` to `complete`, in one invocation, exiting 0.
9. `record-checkpoint-step checkpoint-tag` flips the era-ledger row for
   **exactly the phase key INFRA-265's precedence chain resolved** — the key
   already passed to `_mark_phase_complete_in_index` in that branch, re-used,
   never re-derived by a second lookup.
10. A failure or no-op inside the era-ledger write never changes the exit
    status or the `state.json` writes of `mark-phase-complete` or
    `record-checkpoint-step`: an era doc that is absent, unparseable, or
    read-only leaves both commands' index/`state.json` behaviour byte-for-byte
    what it is today.

**C. Commit paths stage `docs/eras/`.**

11. Both `CLAUDE.build.md` and `skills/pairmode/templates/CLAUDE.build.md.j2`
    contain the literal string `docs/eras/` (neither does today), stating both
    occasions: scaffolded planning docs are committed with `docs/eras/`
    alongside `docs/phases/` and `docs/stories/`; and the checkpoint-tag step's
    ledger flip is committed with `docs/phases/index.md` **before** `git tag`.
12. The rendered `.j2` is still ≤ 40 non-blank lines and the live
    `CLAUDE.build.md` still ≤ 40 non-blank lines — i.e. every edit in C extends
    an existing line and adds no new non-blank line to either file.
13. The mandated checkpoint-tag order from CER-083 (record-checkpoint-step →
    `git tag` + push → promote) is unchanged in both files; the commit clause is
    inserted **inside** step 1's text, not as a new step that reorders anything.

**D. Backfill — era 003's ledger tells the truth.**

14. `docs/eras/003-flex-orchestrator-as-harness.md` contains a section whose
    heading is **exactly** `## Phases`, holding a table headed
    `| Phase | Title | Status |` with one row per phase 96 through 108
    inclusive (13 rows, ascending), each row's title matching
    `docs/phases/index.md`'s title cell for that phase and each row's status
    matching that phase's index status exactly: 96 `complete`, 97 `deferred`,
    98 `complete`, 99 `complete`, 100 `complete`, 101 `complete`,
    102 `complete`, 103 `complete`, 104 `planned`, 105 `planned`,
    106 `planned`, 107 `planned`, 108 `planned`.
15. The pre-existing 4-column narrative table and every line of prose around it
    (`### Phase G scope`, `### Open design threads`) survive verbatim; only its
    `##` heading is renamed so that it no longer begins with `## Phases` —
    otherwise A1's prefix match would resolve to the narrative table, which has
    no `Status` column and is not machine-maintained.
16. `flex_build.py check-index --project-dir .` reports **zero** violation
    lines whose path is `docs/eras/003-flex-orchestrator-as-harness.md`, and
    the total violation count is **≤ 48** (the Requires baseline). Any mismatch
    between a backfilled row and the index shows up here — this is the
    acceptance instrument for D14, not a manual read.
17. `## Era summary` no longer contains the string
    `All 8 planned phases complete as of 2026-07-03`. Its replacement states
    that the 8 designed HARNESS phases plus the HARNESS009-016 follow-ons
    completed by 2026-07-21, that the era then entered a post-fold remediation
    arc running as numeric phases 96 onward, and that formal close is gated on
    phase 108 — with the 9 existing per-phase bullets left intact.
18. `docs/eras/001-initial.md` and `docs/eras/002-*.md` are not modified: the
    5 baseline era-001 violations are still exactly 5 after this story.

**E. Documentation and backlog.**

19. `docs/architecture.md` § *Era files* (spec-time line 770) documents the
    ledger contract: canonical heading `## Phases` (exact, or `## Phases` plus a
    qualifier), columns `| Phase | Title | Status |`, `phase_new.py` appends
    `planned` at scaffold time, `mark-phase-complete` /
    `record-checkpoint-step checkpoint-tag` flip it to `complete`, and
    `check-index` check 2c enforces parity with `docs/phases/index.md`.
20. `docs/architecture.md`'s state-ownership table (spec-time ~line 1484, the
    single-writer table that already has a `docs/phases/index.md` phase status
    cell row) gains a row for the active era doc's ledger status cell, naming
    `flex_build.py mark-phase-complete` / `record-checkpoint-step checkpoint-tag`
    (INFRA-267) as sole writer and the resolver as read-only.
21. `docs/cer/backlog.md`'s `CER-082` row ends with a bolded
    `**RESOLVED phase 104 (INFRA-267) — ...**` note naming all three fixes
    (staging clause in both harness files, `_mark_phase_complete_in_era_ledger`,
    era-003 backfill) **and** recording that the cited `CLAUDE.build.md` step 5c
    / Step 1.5 anchors no longer exist post-flip, plus half 3 (the
    exact-equality heading match that made the appender a silent no-op on this
    repo). The row's `Phase` cell is `104` instead of `—`.

## Instructions

Build in the order below: A and B are independent code halves, C depends on
nothing, D depends on A (the renamed heading is what makes A1's prefix match
safe), E is bookkeeping.

**Ideology note (Step 4a, `docs/ideology.md`):** no conflict, resolved nothing
inline. This story is a direct application of *"codifying policy over implicit
convention"* and *"decision fidelity over convenience"* — a status column that
no writer maintains is exactly the silently-dropped context the value hierarchy
forbids. The *"sidebar owns all state writes"* constraint is respected: the era
doc is written by `flex_build.py`, a skill script, never by a hook.

### A — `phase_new.py::_update_era_phases_table`

1. Replace the section match at line 163:

   ```python
   if stripped == "## Phases":
   ```

   with a helper or inline predicate that is true for `## Phases` and for
   `## Phases` followed by whitespace-plus-anything, and false for `### ...`.
   `stripped == "## Phases" or stripped.startswith("## Phases ")` is sufficient
   and is what the tests should pin; do not use a bare `startswith("## Phases")`
   without the trailing space, which would also match a hypothetical
   `## Phaseset`.
2. Change nothing else in the function — the "insert before the first non-`|`
   line after the table" logic and the end-of-file fallback are both correct as
   written and are what A2/A3 assert.
3. Leave `_detect_active_era` alone. It already resolves era 003 correctly
   (verified: returns `003`); the appender's bug was never in era detection.

### B — `flex_build.py` era-ledger status write

4. Add `_mark_phase_complete_in_era_ledger(phase_key: str, project_dir: Path) -> bool`
   directly beneath `_mark_phase_complete_in_index` (line 716), mirroring its
   docstring style and its idempotency contract. Implementation:
   - `eras_dir = project_dir / "docs" / "eras"`; return `False` if not a dir.
   - Iterate `sorted(eras_dir.glob("*.md"))`, parse each with the already-imported
     `_parse_frontmatter` (the canonical parser rule, `docs/architecture.md`
     § *`schema_validator.py` is the canonical frontmatter parser* — do not
     re-implement, do not import `phase_new`), collect those whose `status`
     is `active`. Return `False` when none. When more than one, use the **last**
     in sorted order, matching `phase_new._detect_active_era`'s documented
     "highest ID wins" rule — but print no warning: this is a write helper on a
     CLI whose stdout other tooling reads.
   - Walk the text line by line. Find the first ledger heading using the *same*
     predicate as A1 (duplicate the two-line predicate locally rather than
     importing `phase_new` into `flex_build`, which would add a new module
     dependency for four tokens; note the duplication in a comment naming
     `phase_new._update_era_phases_table` as the twin).
   - After that heading, find the first pipe table; within it, find the first
     row whose cells (split on `|`, dropping the leading/trailing empties, as
     `_mark_phase_complete_in_index` does) satisfy `len(cells) >= 3` and
     `cells[0] == phase_key`. Skip the header and `|---|` separator rows
     naturally by the `cells[0] == phase_key` test.
   - Return `False` when that row's `cells[2]` already equals `complete`
     (idempotent no-op, no write). Otherwise set `cells[2] = "complete"`,
     re-join as `"| " + " | ".join(cells) + " |\n"`, rewrite that one line, and
     atomically write with `NamedTemporaryFile(dir=<era file's parent>)` +
     `os.replace`. Return `True`.
   - Flip **any** non-`complete` status, including `deferred` — symmetric with
     `_mark_phase_complete_in_index`, and required for D16 parity, since the
     same call flips the index row too.
5. Call it from both write sites, immediately after the existing
   `_mark_phase_complete_in_index` call, passing **the identical key variable**:
   - `cmd_mark_phase_complete` (line 821);
   - `_record_checkpoint_step`'s terminal `checkpoint-tag` branch (line 2138
     pre-265; post-265 this is wherever the resolved phase key reaches
     `_mark_phase_complete_in_index`). Do not add a second phase-key lookup
     here — re-deriving the key is the CER-077 failure mode INFRA-265 just
     removed.
6. Do not guard the new call in a `try/except` that swallows everything: the
   helper's own contract (Ensures 6) is to return `False` rather than raise for
   every *expected* absence. Reserve `except OSError` for the read/write calls,
   consistent with how `phase_new` handles unreadable era files.
7. Do not change `mark-phase-complete`'s or `record-checkpoint-step`'s CLI
   signature: era 003's additive-until-flip contract binds every downstream
   project's bootstrapped loop (`docs/eras/003…` § *Versioning & compatibility*),
   and `tests/pairmode/fixtures/cli_surface_0_2.json` pins the surface. No new
   options, no new subcommand.

### C — staging clauses in the two harness files

8. In **both** `CLAUDE.build.md` and `skills/pairmode/templates/CLAUDE.build.md.j2`,
   extend the `## Build loop` preamble paragraph (the single long line ending
   `...they stay on the main worktree, unwrapped.`) with a sentence to this
   effect — same text in both files, since the live file is the rendered twin:

   > Planning-doc writes are not worktree-scoped: `phase_new.py` appends a
   > `| <phase> | <title> | planned |` row to the active era doc's `## Phases`
   > ledger on every scaffold, so any commit of scaffolded planning docs stages
   > `docs/eras/` alongside `docs/phases/` and `docs/stories/` — an unstaged
   > ledger row is silent working-tree drift (CER-082).

9. In both files, extend step 1 of the `## Checkpoint` section's mandated
   checkpoint-tag order — currently
   `1) \`record-checkpoint-step checkpoint-tag --project-dir .\` (resets checkpoint_step, marks phase complete);`
   — so it reads to this effect, leaving steps 2 and 3 (tag/push, promote) and
   the CER-083 rationale sentence untouched:

   > 1) `record-checkpoint-step checkpoint-tag --project-dir .` (resets
   > checkpoint_step; marks the phase complete in `docs/phases/index.md` **and**
   > flips its `## Phases` row in the active `docs/eras/` doc, INFRA-267), then
   > commit both paths — `git add docs/phases/index.md docs/eras/` — before
   > tagging;

10. **Add no new lines to either file.** Both edits are extensions of existing
    lines. Verify before committing:
    `grep -c . CLAUDE.build.md` must still print `39`, and the rendered
    template must still be 40 non-blank lines (Tests, below, has the command).
    If a clause will not fit readably, shorten the prose — do not spend the
    live file's one spare line, which would leave the template with none.
11. INFRA-265 also edits the `## Checkpoint` line in both files. If a conflict
    surfaces there, keep 265's phase-key text and add this story's clause to
    it; the two are additive.

### D — era-003 backfill

12. Rename the narrative section's heading from
    `## Phases (proposed — \`HARNESS\` predicate, suffix scheme)` to
    `## Planned phase design (HARNESS predicate, suffix scheme)`. Nothing else
    in that section changes — not the 4-column table, not the paragraph about
    the suffix convention, not `### Phase G scope`, not
    `### Open design threads to resolve in the agreements docs`.
13. Insert a new section immediately **before** `## Versioning & compatibility`
    (i.e. after the narrative section and all its subsections), headed exactly
    `## Phases`, with a short scope note then the ledger table:

    ```markdown
    ## Phases

    Machine-maintained ledger: `phase_new.py` appends a row on every scaffold,
    `flex_build.py mark-phase-complete` / `record-checkpoint-step checkpoint-tag`
    flips its status, and `check-index` (check 2c) enforces parity with
    `docs/phases/index.md`. Backfilled in INFRA-267 (CER-082) — until then the
    appender's heading match never fired on this doc. Coverage starts at the
    post-fold numeric phases; the era's earlier HARNESS phases are recorded in
    § Planned phase design and § Era summary above.

    | Phase | Title | Status |
    |-------|-------|--------|
    | 96 | ... | complete |
    ```

    Copy each title verbatim from `docs/phases/index.md`'s title cell (do not
    re-word, do not carry the link cell) and each status verbatim from its
    status cell, for phases 96-108 ascending. Ensures 14 lists the expected
    statuses; if the index disagrees with that list when you read it, the index
    wins and `check-index` (D16) is the arbiter.
14. Update `## Era summary`'s opening sentence per Ensures 17. Keep the
    parenthetical "(era active — not yet closed...)" note above it and all 9
    per-phase bullets below it unchanged; this is a one-sentence replacement,
    not a rewrite of the summary.
15. Do not touch `docs/eras/001-initial.md` or
    `docs/eras/002-flex-build-loop-and-observability.md`. Era 001's 5
    cross-link violations are pre-existing and out of scope (see § Out of scope).

### E — docs and backlog

16. Make the two `docs/architecture.md` edits (Ensures 19, 20). Optionally
    extend the `flex_build.py` subcommand inventory line (spec-time line 56)
    where it describes `mark-phase-complete` / INFRA-239, with a clause that
    the same write path now also flips the active era ledger — keep it to a
    clause; that line is already enormous.
17. Append the `CER-082` RESOLVED note and set its `Phase` cell to `104`
    (Ensures 21). Match the in-file convention, e.g. CER-066's
    `**RESOLVED HARNESS015-main (RESOLVER-017) — ...**`. Do not delete or
    re-word the original finding text — the backlog is append-only history.

## Tests

Run from the story worktree root with `PATH=$HOME/.local/bin:$PATH`.

**1. New/extended unit tests.** Add to the existing files — no new test module:

- `tests/pairmode/test_phase_new.py`
  - `test_era_ledger_heading_with_trailing_qualifier_appends_row` — era doc
    with `## Phases (proposed — x)` + a `| Phase | Title | Status |` table;
    assert the appended row is present and is the table's last row (A2).
  - `test_era_ledger_exact_heading_still_appends_row` — `era_new.py`-shaped doc
    (A3).
  - `test_era_ledger_h3_phase_heading_does_not_match` — a doc whose only
    `Phase`-ish heading is `### Phase G scope` gets no row and no exception (A1/A4).
- `tests/pairmode/test_flex_build_mark_phase_complete.py`
  - `test_mark_phase_complete_flips_active_era_ledger_row` — fixture project
    with index row + active era ledger row both `planned`; after
    `mark-phase-complete`, both read `complete`, exit 0 (Ensures 8).
  - `test_mark_phase_complete_era_ledger_row_absent_is_tolerated` — active era
    doc with a ledger table that has no row for the phase; exit 0, index
    flipped, era doc byte-identical (Ensures 6, the legacy-era case).
  - `test_mark_phase_complete_no_eras_dir_is_tolerated` — exit 0, index flipped
    (Ensures 6).
  - `test_mark_phase_complete_era_ledger_is_idempotent` — row already
    `complete`; era doc byte-identical after the call (Ensures 6).
  - `test_mark_phase_complete_ignores_inactive_era_doc` — two era docs, one
    `status: complete` holding a matching row, one `status: active` without
    one; the complete era's file is byte-identical afterwards (Ensures 7).
- `tests/pairmode/test_record_checkpoint_step.py`
  - `test_checkpoint_tag_flips_era_ledger_row` — asserts the flip happens on
    the checkpoint-tag path for the same phase key the step resolved
    (Ensures 9), and that `state.json`'s `checkpoint_step` reset is unaffected
    (Ensures 10).
- `tests/pairmode/test_template_reduction.py`
  - `test_rendered_template_stages_eras` — `"docs/eras/" in rendered`
    (Ensures 11). The existing `test_non_blank_line_count` covers Ensures 12
    for the template; do not raise its 40 limit.
- `tests/pairmode/test_flip_dogfood.py`
  - `test_live_build_md_stages_eras` — `"docs/eras/" in` the live
    `CLAUDE.build.md` (Ensures 11). The existing
    `test_live_build_md_non_blank_line_count` covers Ensures 12 for the live
    file; do not raise its limit.

**2. Targeted run** — all six touched test files green:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_phase_new.py \
  tests/pairmode/test_flex_build_mark_phase_complete.py \
  tests/pairmode/test_record_checkpoint_step.py \
  tests/pairmode/test_template_reduction.py \
  tests/pairmode/test_flip_dogfood.py \
  tests/pairmode/test_templates.py -q 2>&1 | tail -20
```

**3. Full suite, without `-x`** (a known pre-existing failure must not mask a
real one — run to completion and compare the failure set against the CER-090
baseline):

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Acceptance: green except, inside a worktree only,
`test_observability_ui.py::test_ui_build_emits_dist_index_html` (CER-090). Any
other failure blocks the story.

**4. Backfill acceptance — `check-index` is the arbiter (Ensures 16, 18):**

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/flex_build.py \
  check-index --project-dir . 2>&1 | grep "docs/eras" | awk '{print $3}' | sort | uniq -c
```

Acceptance: output is exactly `5 docs/eras/001-initial.md` — five era-001 rows,
**zero** era-003 rows. A single era-003 line means a backfilled title or status
disagrees with `docs/phases/index.md`; fix the ledger, not the index. Also
confirm the total has not grown:

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/flex_build.py \
  check-index --project-dir . 2>&1 | grep -c .
```

Acceptance: ≤ 48.

**5. Line-count gates (Ensures 12), belt-and-braces alongside the pytest
assertions:**

```bash
grep -c . CLAUDE.build.md   # must print 39
PATH=$HOME/.local/bin:$PATH uv run python -c "
import jinja2, pathlib
p = pathlib.Path('skills/pairmode/templates/CLAUDE.build.md.j2')
env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(p.parent)))
r = env.get_template(p.name).render(project_name='t', pairmode_scripts_dir='/x', test_command='y')
print(len([l for l in r.splitlines() if l.strip()]))"   # must print 40
```

**6. End-to-end proof that the appender now fires on the live era doc** (a
throwaway copy — do **not** run `phase_new.py` against the repo):

```bash
PATH=$HOME/.local/bin:$PATH uv run python -c "
import sys, shutil, pathlib
sys.path.insert(0, 'skills/pairmode/scripts')
d = pathlib.Path('/tmp/era-check'); shutil.rmtree(d, ignore_errors=True)
(d / 'docs' / 'eras').mkdir(parents=True)
shutil.copy('docs/eras/003-flex-orchestrator-as-harness.md', d / 'docs/eras/003.md')
import phase_new
phase_new._update_era_phases_table(d, '003', '109', 'Probe')
t = (d / 'docs/eras/003.md').read_text()
assert '| 109 | Probe | planned |' in t, 'appender still a no-op'
print('OK: row appended')"
```

Acceptance: prints `OK: row appended`. The identical command against
pre-story `HEAD` prints the assertion failure — that contrast is the story's
headline evidence and belongs in the BUILD-RESULT notes.

## Out of scope

- **Era 001's 5 cross-link violations** (`phase-23`, `phase-53`, `phase-54`, …
  showing statuses that disagree with the index). Same root cause, closed era,
  a separate hand-reconciliation with its own risk of rewriting history.
  Leave them; they are the Requires baseline and Ensures 18 pins them at 5.
  Filing them as a CER row for the phase-107 backlog drain is the operator's
  call, not this builder's.
- **Backfilling era 003's pre-96 phases** — phases 82-95 and HARNESS001-016 are
  also era 003 (44 era-003 index rows in total) and equally absent from the
  ledger. The ledger's scope note says so explicitly rather than implying
  completeness. Widening the backfill to all 44 is a mechanical follow-on, not
  this story.
- **`docs/phases/phase-100.md` has no YAML frontmatter at all** (hence no
  `era:` key) — found while enumerating era-003 phases. Out of scope: phase
  docs are append-only history and it is not this story's file.
- **Dropping the status column instead of maintaining it** — CER-082's
  alternative fix direction (b). Rejected: `check-index` check 2c already
  exists to guard that column, so maintaining it costs one write and buys
  live enforcement, while deleting it discards a working checker.
- **Retro-committing forqsite's three drifted ledger rows.** Cross-repo; this
  story fixes the mechanism, not other projects' working trees.
- **Teaching `era_new.py` / `bootstrap.py` a richer ledger template** (they
  already emit the canonical `## Phases` + `| Phase | Title | Status |` shape;
  no change needed) and **teaching `check-index` to flag an era doc that has
  *no* ledger table at all** — the gap that hid this bug for 44 phases. The
  latter is a genuine follow-on for the housekeeper rail; do not build it here.
- **Any status other than `complete`.** Nothing in this story teaches the
  ledger to record `deferred`, `backlog`, or `active`; those cells stay
  hand-maintained, as `docs/phases/index.md`'s are.
- **Changing `mark-phase-complete`'s or `record-checkpoint-step`'s CLI
  surface**, or any part of INFRA-265's phase-key precedence chain.
