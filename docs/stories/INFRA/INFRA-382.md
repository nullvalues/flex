---
id: INFRA-382
rail: INFRA
title: Correct stale story statuses in docs/phases/phase-64.md's Stories table (CER-125)
status: draft
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - docs/phases/phase-64.md
touches: []
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-125 (LOW): `docs/phases/phase-64.md`'s Stories table lists INFRA-164..168 as `backlog` even
though all five completed under `HARNESS007-main` (Phase G resume) — a stale manifest that
`story_update.py` cannot reach by design, since legacy phase docs are outside its write scope. Fix
is a hand edit of the five status cells with a pointer note to `HARNESS007-main`. Gate was the
next hand edit to `phase-64.md` for any reason, or any `story_update.py` change adding
legacy-phase-doc handling — either has now arrived given this phase's scope. File:
`docs/phases/phase-64.md` (Stories table, INFRA-164 through INFRA-168 rows). From the 2026-07-29
cold-eyes review (F12).

Picked up now as part of era 004's Phase 119 goal of draining the CER backlog to zero unresolved
operational findings.

## Requires

- No Phase 119 story is a prerequisite; INFRA-382 is independent of the other 17 stories and
  touches no file they touch.
- `docs/phases/phase-64.md` exists and its Stories table still carries `backlog` in the Status
  cells of the INFRA-164 through INFRA-168 rows.
- `docs/stories/INFRA/INFRA-164.md` through `INFRA-168.md` exist; their own frontmatter `status:`
  values are the authority for the corrected cell values.

## Ensures

1. Each of the INFRA-164, -165, -166, -167, -168 rows in `docs/phases/phase-64.md`'s Stories table
   carries a Status cell whose value equals that story's own frontmatter `status:` in
   `docs/stories/INFRA/<ID>.md`. **Forbidden proxy:** adding a prose note that the rows are stale
   while the cells still read `backlog` — the assertion is on the cell values themselves.
2. `docs/phases/phase-64.md` contains a pointer note (adjacent to the Stories table) naming
   `HARNESS007-main` as the checkout where those five stories completed (Phase G resume), and
   stating why the correction was made by hand rather than by `story_update.py` (legacy phase docs
   are outside its write scope).
3. No other row of that Stories table has its Status cell changed, and `git diff --name-only`
   after the edit lists exactly `docs/phases/phase-64.md` and this story file — no change to
   `story_update.py`, to the five story files, or to any other phase doc.
4. Full `tests/pairmode/` suite green.

## Instructions

1. Read the frontmatter `status:` of each of `docs/stories/INFRA/INFRA-164.md` ..
   `INFRA-168.md`. Those five values — not an assumption that all five are `complete` — are what
   the phase-64 cells must be set to.
2. Edit only the Status cells of those five rows in `docs/phases/phase-64.md`'s Stories table.
   Leave every other row, and the rest of the file's content, untouched.
3. Add a one-line pointer note immediately below the Stories table (or below its heading),
   e.g.: `> INFRA-164..168 completed under the HARNESS007-main checkout (Phase G resume); statuses`
   `> corrected by hand in INFRA-382 (CER-125) because story_update.py's write scope does not reach`
   `> legacy phase docs.` The note carries the reason, not just the fact — a bare corrected cell
   loses why the manifest drifted (ideology: rationale-bearing decisions over bare rules).
4. Do **not** extend `story_update.py` to write legacy phase docs. That was one of CER-125's two
   gates, not the remedy this story delivers.
5. No new test file: this is a doc-content correction with no logic. Run the full suite anyway —
   index/manifest-integrity tests read phase docs and are the regression signal here.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
grep -nE 'INFRA-16[4-8]' docs/phases/phase-64.md
git diff --name-only
```

Acceptance: suite green; the `grep` output shows no `backlog` on the five rows and the corrected
values match the story files' own frontmatter; `git diff --name-only` lists only
`docs/phases/phase-64.md` and `docs/stories/INFRA/INFRA-382.md`.

## Out of scope

- Auditing the other legacy phase docs for the same class of stale Status cell. If one is spotted
  while working here, file a CER rather than fixing it inline.
- Teaching `story_update.py` (or any other tool) to write legacy phase docs — explicitly deferred.
- Editing the INFRA-164..168 story files themselves; they are read-only inputs here.

Preflight note: `spec-preflight` reports `docs/stories/INFRA/INFRA-164.md` as named-but-not-in-scope.
That is intentional — the five story files are read to source the correct status values and are
never written, so they are deliberately absent from `touches:`.
