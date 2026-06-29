# Phase 79 — era-002 index-tooling maintenance

**Era:** era-002
**Status:** planned

## Goal

Three era-002 maintenance fixes for index/checkpoint tooling that upstream fleet
projects still on era-002 depend on (until the era-003 harness line lands and
cuts over). These are **not** part of the HARNESS001 refactor and do **not**
block harness work — they are standalone corrections to `current-phase`,
`mark-phase-complete`, and the reviewer agent's FAIL-revert. Discovered while
driving an upstream era-002 build loop (RK002-main) where `current-phase`
mis-reported phase status and `mark-phase-complete` corrupted a seeded 5-column
index.

Story-level detail (acceptance criteria, file paths, repro, tests) lives in
`docs/stories/BUILD/BUILD-03{6,7,8}.md` — not here.

## Problem

Three independent defects, all confirmed by reproduction against this repo's own
`docs/phases/index.md` and the seeded `index.md.j2` template:

1. **`current-phase` selects the wrong phase** (`flex_build.py:437–453`).
   - "Last-non-complete wins": the loop keeps the *last* row with status ≠
     `complete`. When the index lists a future **planned** phase whose
     `phase-*.md` file does not exist yet, that row wins, `candidate.exists()`
     is False, and the command falsely prints *"all stories complete"* — the
     observed upstream symptom. The correct selection is the **first**
     incomplete phase in build order.
   - Exact-match status: `status != "complete"` misclassifies terminal/parked
     states. `complete (partial)` is treated as active (it is terminal →
     should count as complete); `deferred` is treated as active (it has been
     moved elsewhere → should be skipped). Against this repo's index the loop
     currently picks `64` (deferred) as "active".

   This is **not** a 5-column parse failure: `_parse_index_phases` reads status
   at `parts[3]`, correct for both the native 4-column and seeded 5-column
   layouts. The "doesn't parse the seeded index" symptom is the last-wins bug
   firing on a planned-but-fileless row.

2. **`mark-phase-complete` corrupts a 5-column index** (`flex_build.py:580–590`).
   The row rewrite is hardcoded to emit **4 columns** regardless of input
   width. On the seeded 5-column index (`| Phase | Title | Status | Deferred
   from | Link |`) it drops the **Link** cell and collapses the row to 4
   columns, leaving it narrower than the header. Every checkpoint on such an
   index re-corrupts the active row.

3. **Reviewer FAIL-revert is broader than documented**
   (`.claude/agents/reviewer.md:174–175`). The revert runs `git checkout .`
   followed by `git clean -fd`, which deletes **all** untracked files and
   directories — including legitimate ones unrelated to the story (this repo
   has an untracked `flex_eph/` right now). The intended revert restores
   tracked files only.

## Stories

| ID | Title | Status |
|----|-------|--------|
| BUILD-036 | current-phase: first-incomplete selection + status classification | complete |
| BUILD-037 | mark-phase-complete: column-count-preserving status rewrite | complete |
| BUILD-038 | reviewer FAIL-revert: drop `git clean -fd` | planned |

## Schema delivery

No new persistent schema objects introduced in this phase.

---

### CP-79 Cold-eyes checklist

— developer fills in after phase completion —
