---
id: INFRA-152
rail: INFRA
title: "`flex_build.py next-phase --after [phase-id]` — index-based next-phase lookup"
status: planned
phase: "60"
story_class: code
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - tests/pairmode/test_flex_build_next_phase.py
touches: []
---

# INFRA-152 — `flex_build.py next-phase`: index-based next-phase lookup

## Context

The checkpoint report template uses `[N+1]` arithmetic to generate the closing
prompt (`"Build Phase [N+1]"`). This breaks for suffix-keyed phases (e.g.
`RD077-main`) where integer arithmetic doesn't apply, and silently produces an
unhelpful `[next]` literal when no next phase is specced.

This story adds a `flex_build.py next-phase --after [phase-id]` subcommand that
reads `docs/phases/index.md`, locates the row for `[phase-id]`, and returns the
key of the immediately following row. This gives the orchestrator a deterministic,
index-authoritative answer without arithmetic — works for any phase key shape.

**Depends on nothing.** INFRA-153 depends on this command existing.

## Acceptance criteria

### `skills/pairmode/scripts/flex_build.py`

1. Add a `next-phase` subcommand:

   ```
   flex_build.py next-phase --after PHASE_ID [--project-dir DIR]
   ```

   - `--after` (required, `type=str`) — the current phase key (e.g. `59`,
     `RD077-main`).
   - `--project-dir` — standard depth-guarded project-dir argument (same pattern
     as siblings; default `.`).

2. Implementation:
   - Read `docs/phases/index.md`. If the file does not exist: exit 1 silently.
   - Parse the phase table using `_parse_index_phases()` (already present in
     `flex_build.py`) to get an ordered list of `(phase_ref, status)` tuples.
   - Find the row whose `phase_ref` equals `--after`. If not found: exit 1
     silently.
   - Return the `phase_ref` of the next row in the list (the one immediately
     after the match). If the matched row is last: exit 1 silently.
   - On success: print the next phase key (one line, no trailing whitespace)
     and exit 0.
   - Never print anything on exit 1 (stderr is acceptable for debug use but
     stdout must be empty so callers can test `if output:` cleanly).

3. The command is read-only. No writes to any file.

### Tests — `tests/pairmode/test_flex_build_next_phase.py`

4. Create a new test file with these cases (use `tmp_path` + `CliRunner` pattern
   consistent with sibling test files):

   - **`test_next_phase_integer_key`** — index has rows `58 planned`, `59 planned`,
     `60 planned`; `--after 59` → prints `60`, exit 0.

   - **`test_next_phase_suffix_key`** — index has rows `RD077-ante1 planned`,
     `RD077-main planned`, `RD077-post1 planned`; `--after RD077-main` → prints
     `RD077-post1`, exit 0.

   - **`test_next_phase_last_row`** — index has rows `58 planned`, `59 planned`;
     `--after 59` → stdout empty, exit 1.

   - **`test_next_phase_not_in_index`** — index has rows `58 planned`, `59 planned`;
     `--after 99` → stdout empty, exit 1.

   - **`test_next_phase_no_index_file`** — no `docs/phases/index.md` exists →
     stdout empty, exit 1.

   - **`test_next_phase_skips_complete_rows`** — index has rows `58 complete`,
     `59 complete`, `60 planned`; `--after 59` → prints `60`, exit 0.
     *(The command returns the next row regardless of its status — status
     filtering is the caller's responsibility.)*

## Out of scope

- Filtering by status (caller decides what to do with the returned key)
- Updating the index row to `complete` (not part of this story)
- Changes to `CLAUDE.build.md` or the template (INFRA-153)
