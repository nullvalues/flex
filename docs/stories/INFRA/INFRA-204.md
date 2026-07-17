---
id: INFRA-204
rail: INFRA
title: "Scope update_phase_story_status to the story's declared phase: frontmatter (suffix-aware), fall back to whole-glob only for legacy phase-less stories, with cross-phase-leakage regression tests"
status: planned
phase: "92"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/story_update.py
  - tests/pairmode/test_story_update.py
touches:
  - docs/architecture.md
---

# INFRA-204 — Scope `update_phase_story_status` to the story's declared `phase:` frontmatter, falling back to the whole-glob scan only for legacy phase-less stories

## Context

`update_phase_story_status(story_id, project_dir, status)` in
`skills/pairmode/scripts/story_update.py` (lines 109-130) globs **every** file
under `docs/phases/*.md` via `for phase_path in sorted(phases_dir.glob("*.md"))`
and updates the status column of **any** `## Stories`-table row whose bare first
column equals `story_id`, with zero phase or rail disambiguation. The matching
logic in `_update_story_row_in_phase` (lines 145-235) keys only on the stripped
first-column value (`first_col == story_id`).

This is a live, reproduced data-corruption bug (CER-064, "Do Now"):

- Reproduced directly with two fixture phase files each carrying an independent
  `REF-106` row — one representing the story's real phase, one an unrelated
  collision. A single `--status complete` call flipped **both** rows.
- Real collision precedent in this repo (CER-063): `INFRA-203` collides between
  `main`'s phase 91 and the unmerged `fold-prep` branch's `HARNESS011-main`.
- Reported externally by the `ud` migration repo, whose Phase 24 and Phase 29
  both carried an unrelated `REF-106` row; a status update on one leaked into
  the other. That repo cannot fix shared pairmode tooling directly.

The fix must scope the update to only the phase(s) actually named in the target
story file's own `phase:` frontmatter field. That value is already accessible in
the same CLI call chain: the `story_update` command (lines 259-275) first calls
`update_story_status`, which opens `docs/stories/<rail>/<story_id>.md`, and then
calls `update_phase_story_status` against the same `project_dir`. Reading the
story's `phase:` value is the same lookup `record_attempt.py` already performs
(it fills `--phase` from frontmatter via `schema_validator._parse_frontmatter`,
lines 233-254).

The `phase:` value is a bare key (e.g. `"91"`, `"92"`, or `"HARNESS011"`), while
the on-disk phase manifest filename may take either the exact form
`phase-<key>.md` or a suffixed form `phase-<key>-<suffix>.md` (the
`ante`/`main`/`post`/`sec` suffixes documented in CLAUDE.build.md's "Phase naming
suffixes" section, which preserve disk sort order). `story_new.py`'s
`_append_to_phase` (lines 127-145) already resolves exactly this family of
filename shapes — `{phase}-*.md`, exact `phase-{phase}.md`, and suffixed
`phase-{phase}-*.md` (the last added under CER-062 / INFRA-197). This story must
mirror that resolution so `story_update.py` and `story_new.py` agree on which
manifest(s) a phase key names. There is no pure resolver helper to import:
`_append_to_phase` couples resolution with mutation (it appends a row and writes
the file), so the glob logic is mirrored locally in `story_update.py` rather than
imported — no cross-module dependency or circular-import risk is introduced.

Legacy stories predating the `phase:` field convention have no `phase:` value.
For those, and only those, the current whole-glob scan-and-match-every-file
behavior must be preserved unchanged so nothing regresses.

## Ensures

1. **Story `phase:` is read before any manifest is scanned.**
   `update_phase_story_status` reads the target story's `phase:` frontmatter
   value (from `docs/stories/<rail>/<story_id>.md`, resolved with the same
   path-containment guard `update_story_status` uses) before it scans or updates
   any phase manifest. Frontmatter parsing reuses the existing
   `schema_validator._parse_frontmatter` helper rather than a bespoke parser.

2. **When `phase:` is present, only matching manifest(s) are scanned/updated.**
   Given a non-empty `phase:` key, only phase manifests whose filename is the
   exact `phase-<key>.md` or the suffixed `phase-<key>-<suffix>.md` (resolved by
   mirroring `story_new.py._append_to_phase`'s glob shapes) are opened and
   updated. Any other phase file's `## Stories`-table row carrying the same bare
   `story_id` is left byte-for-byte unchanged. The exact CER-064 two-phase
   collision (one matching phase, one unrelated colliding phase) updates only the
   correctly-scoped row.

3. **When `phase:` is absent, behavior is unchanged (no legacy regression).**
   If the story frontmatter has no `phase:` field at all (or the story file
   cannot be found/read), `update_phase_story_status` falls back to the current
   whole-glob scan across every `docs/phases/*.md`, matching every Stories-table
   row with the bare `story_id` — identical to today's behavior. An empty-string
   `phase:` value is treated as absent (fall back to whole-glob).

4. **Return contract preserved.** `update_phase_story_status` still returns a
   `list[Path]` of the phase files it actually modified (empty list when none
   matched or `docs/phases/` is absent). The CLI's "Phase manifest updated" /
   "no phase manifest found" output (lines 269-275) is unchanged.

5. **New regression test reproduces the exact cross-phase leak.** A test creates
   a story whose `phase:` frontmatter names one phase, plus two phase manifests
   each containing a `## Stories` row for the same bare `story_id` (only one of
   which matches the declared `phase:`). After a single status update it asserts
   the matching phase's row is updated **and** the non-matching phase file is
   byte-identical to before the call (captured pre-image compared with a full
   `read_text()`, not just a substring check).

6. **Legacy fall-back is covered.** A test with a story whose frontmatter has no
   `phase:` field asserts the whole-glob behavior still updates the row in every
   phase that carries it (preserving `test_two_phase_manifests_both_updated`'s
   intent for the phase-less case).

7. **Suffixed-manifest resolution is covered.** A test with `phase: "PM025"` and
   a manifest named `phase-PM025-main.md` asserts that manifest's row is updated
   while an unrelated `phase-PM025-post1.md` carrying a colliding bare ID (for a
   different story) is untouched — exercising the suffixed glob shape.

8. **Existing tests stay green.** `PATH=$HOME/.local/bin:$PATH uv run pytest
   tests/pairmode/test_story_update.py -x -q` passes. Existing single-phase-file
   scenarios continue to pass; any fixture that must exercise the intended-match
   path is given a `phase:` value consistent with its phase filename (the shared
   `_make_story` helper already writes `phase: "1"`, and `_make_phase` names
   files like `phase-001.md` — see Instructions for the one alignment needed so
   the `phase:` key "1" resolves to `phase-001.md`).

## Instructions

- Edit `update_phase_story_status` in `skills/pairmode/scripts/story_update.py`
  (lines 109-130). Do **not** change `_update_story_row_in_phase`'s row-matching
  internals (lines 145-235) or the CLI command body (lines 259-275) beyond what
  Ensures #4 allows — the scoping decision belongs in
  `update_phase_story_status`, which selects *which* manifests to hand to
  `_update_story_row_in_phase`.

- **Read the story's `phase:` value.** At the top of
  `update_phase_story_status`, resolve the story path the same way
  `update_story_status` does (`_parse_story_id` for the rail, then
  `resolved / "docs" / "stories" / rail / f"{story_id}.md"` with the
  `resolve().relative_to(resolved)` containment guard). If the story file exists,
  read it and extract `phase` via `from schema_validator import
  _parse_frontmatter` (already importable — `story_update.py` inserts the repo
  root on `sys.path` at line 23, and `record_attempt.py` imports
  `_parse_frontmatter` the same way). Treat a missing file, missing `phase` key,
  or empty/whitespace `phase` value as "no declared phase" → legacy fall-back.
  Do not raise if the story file is missing here — `update_phase_story_status`
  must remain callable independently and degrade to the whole-glob scan.

- **Add a local manifest-resolution helper** mirroring
  `story_new.py._append_to_phase`'s glob shapes (do not import `_append_to_phase`
  — it mutates files). Given `phases_dir` and the bare `phase` key, return the
  sorted list of matching `Path`s by trying, in order:
  1. `sorted(phases_dir.glob(f"{phase}-*.md"))`
  2. exact `phases_dir / f"phase-{phase}.md"` (if it exists)
  3. `sorted(phases_dir.glob(f"phase-{phase}-*.md"))` (suffixed form)
  Collect matches consistently with `_append_to_phase`'s precedence. Keep a
  short comment cross-referencing CER-062 / INFRA-197 and CER-064 so the shared
  filename-matching contract survives future edits.

- **Branch the scan.** When a non-empty `phase` was read, iterate only the
  resolved manifest list; when it was absent, keep the existing
  `sorted(phases_dir.glob("*.md"))` scan verbatim. Both branches feed each
  matched path through `_update_story_row_in_phase` and append modified files to
  `updated` exactly as today.

- **Update `docs/architecture.md`.** The `story_update.py` paragraph (around
  line 452, "finds all phase manifests containing the story's ID in their
  `## Stories` table and updates the status column") must be revised to state
  that, since INFRA-204, the scan is scoped to the phase manifest(s) named by the
  target story's own `phase:` frontmatter (resolving exact and suffixed filename
  forms, mirroring `story_new.py`'s `_append_to_phase`), and only falls back to
  the whole-glob scan when the story declares no `phase:` (legacy). Note that
  this closes CER-064's cross-phase status-leakage bug.

- Do **not** change `_update_story_row_in_phase`, `_strip_link`, `_parse_story_id`,
  the CLI option surface, or `story_new.py`.

## Tests

`story_class: code` — a real new branch in the manifest-selection path. Run the
gate:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Add these cases to `tests/pairmode/test_story_update.py`, reusing the existing
`_make_project`, `_make_story`, and `_make_phase` fixtures (extend `_make_story`
or add a variant so the story's `phase:` value can be set/omitted per test):

- `test_phase_scope_does_not_leak_across_phases` — the core CER-064 regression.
  Create a story with `phase: "24"`; create `phase-24.md` and `phase-29.md`,
  each with a `REF-106` Stories row (the story under test is `REF-106`).
  Capture `phase-29.md`'s full text pre-image. Run
  `update_phase_story_status("REF-106", project, "complete")`. Assert
  `phase-24.md`'s `REF-106` row is now `complete`, `phase-29.md`'s text is
  byte-identical to the pre-image, and the returned list contains only the
  `phase-24.md` path.

- `test_phase_scope_absent_frontmatter_falls_back_to_whole_glob` — create a
  story whose frontmatter omits `phase:` entirely; create two phase manifests
  each carrying its row. Assert both are updated (legacy whole-glob behavior
  preserved) — the phase-less analogue of `test_two_phase_manifests_both_updated`.

- `test_phase_scope_resolves_suffixed_manifest` — story with `phase: "PM025"`;
  create `phase-PM025-main.md` (carrying the story's row) and
  `phase-PM025-post1.md` (carrying a colliding bare ID for a *different* story).
  Assert only `phase-PM025-main.md`'s row is updated and `phase-PM025-post1.md`
  is unchanged.

- `test_phase_scope_missing_story_file_falls_back` — call
  `update_phase_story_status` for a `story_id` whose story file does not exist,
  with one phase manifest carrying its row. Assert the row is still updated
  (fall-back path; no exception raised).

- Reconcile the existing `update_phase_story_status` tests so their `phase:`
  values resolve to their phase filenames on the scoped path
  (`_make_story` writes `phase: "1"`; `_make_phase` files are `phase-001.md` —
  confirm `"1"` resolves to `phase-001.md` via the `phase-{phase}.md`/`{phase}-*.md`
  globs, adjusting the fixture phase filename to `phase-1.md` **or** the story
  `phase:` value to `"001"` so the intended-match tests still pass on the scoped
  branch). Do not weaken `test_only_matching_row_updated_multiple_rows`,
  `test_phase_manifest_with_link_syntax_in_id_cell`, or the CLI integration
  tests — they must remain green.

### Out of scope

- Changing `story_new.py._append_to_phase` or extracting a shared resolver
  module. INFRA-204 mirrors its glob shapes locally; a later refactor may
  unify them, but that is not this story.
- Modifying `_update_story_row_in_phase`'s row-matching (first-column equality,
  link stripping, spacing preservation).
- Adding rail-level disambiguation beyond phase scoping. The `phase:` field is
  sufficient to resolve CER-064; per-rail scoping is not required.
- The `fold-prep`/`HARNESS011-main` merge-time renumbering of the colliding
  `INFRA-203` (CER-063) — a separate merge-time concern.
- Any change to the CLI option surface, valid-status choices, or the
  `update_story_status` frontmatter writer.
