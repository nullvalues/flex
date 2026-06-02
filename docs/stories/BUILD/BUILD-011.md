---
id: BUILD-011
rail: BUILD
title: Upfront context elimination
status: planned
phase: "52"
story_class: methodology
primary_files:
  - CLAUDE.md
  - CLAUDE.build.md
  - CLAUDE.build.md.j2
  - skills/pairmode/scripts/flex_build.py
touches:
  - docs/phases/index.md
---

# BUILD-011 — Upfront context elimination

## Background

Two instructions currently front-load context on every session and every build:

1. `CLAUDE.md` contains `Read /docs/brief.md then /docs/architecture.md before
   any task.` This fires on every session load regardless of mode — including
   general troubleshooting sessions where neither file is relevant.

2. `CLAUDE.build.md` "Before the first build loop" steps 1–3 read `brief.md`,
   `architecture.md`, and the phase file in full before the orchestrator knows
   what story it is building. By story 4 of a phase, the orchestrator context
   carries tens of thousands of tokens from files that provide no routing value.

The orchestrator's orientation for routing purposes is: what project is this,
and which story is next. The first is answered by the project description already
in `CLAUDE.md`. The second is answered by two CLI calls. Everything else belongs
inside the cold-start context of the builder and reviewer agents.

## Ensures

- `CLAUDE.md` no longer contains a blanket instruction to read `brief.md` or
  `architecture.md`. The existing project context paragraph (first section of
  `CLAUDE.md`) is sufficient orchestrator orientation.
- `CLAUDE.build.md` "Before the first build loop" section is replaced with:
  1. Call `flex_build.py current-phase --project-dir .` → receive path to the
     active phase file (most recent phase with at least one unbuilt story).
  2. Call `next_story.py <phase-file> --project-dir .` → receive the next story
     ID and story file path.
  3. Proceed to the build loop with that story.
- `flex_build.py current-phase --project-dir DIR` is implemented and exits 0
  with the phase file path on stdout, or exits 1 with a message if all stories
  in all phases are complete.
- `CLAUDE.build.md.j2` template is updated to match.

## Out of scope

- Changes to what the builder or reviewer reads (BUILD-012).
- Changes to what agents return to the orchestrator (BUILD-013).
- Auth check relocation (can be a follow-on if needed; for now the auth check
  step in the build loop reads architecture.md only when an auth-gated story
  is encountered — that targeted read is acceptable).

## Instructions

### 1. Add `current-phase` subcommand to `flex_build.py`

Add `cmd_current_phase(project_dir: str)` that:
- Reads `docs/phases/index.md` from `project_dir`
- Parses the `| Phase | ... | Status |` table
- Finds the last phase whose status is not `complete` (i.e. `anchor` or
  `planned` or absent)
- Falls back to scanning phase files directly if the index is absent:
  iterates `docs/phases/phase-N.md` in descending order, calls
  `find_next_story` from `next_story.py`, returns the first phase file
  where a next story exists
- Prints the phase file path (e.g. `docs/phases/phase-52.md`) and exits 0
- Exits 1 with `"No active phase found — all stories complete."` if none found

Wire into `flex_build.py` CLI as `current-phase` alongside existing subcommands.

### 2. Update `CLAUDE.md`

Remove the line:
```
Read `/docs/brief.md` then `/docs/architecture.md` before any task.
```

The project context paragraph that already opens `CLAUDE.md` is sufficient.
Builders and reviewers read architecture context themselves.

### 3. Update `CLAUDE.build.md` "Before the first build loop"

Replace steps 1–3 with:

```
1. Identify the active phase and next story:

   PATH=$HOME/.local/bin:$PATH uv run python /path/to/flex_build.py \
     current-phase --project-dir .

   This prints the path to the active phase file (e.g. docs/phases/phase-52.md).
   If exit code 1: all stories complete — report to user and stop.

2. Find the next unbuilt story:

   PATH=$HOME/.local/bin:$PATH uv run python /path/to/next_story.py \
     <phase-file> --project-dir .

   This prints the story ID and file path.
   Exit 1 means the phase is complete — run the checkpoint sequence.
   Exit 2 means an error — report and stop.

3. Proceed to the build loop with the story ID from step 2.
```

Steps 4–7 of the old "Before the first build loop" (git log, stories table
read, story file read, developer action gate check) are absorbed into the
loop itself or handled by the CLI.

### 4. Update `CLAUDE.build.md.j2`

Mirror all changes to `CLAUDE.build.md` in the Jinja2 template.

## Tests

`tests/pairmode/test_flex_build_current_phase.py` (new):

1. `test_current_phase_from_index` — mock phase index with one active phase;
   assert CLI returns its path and exits 0.
2. `test_current_phase_all_complete` — mock phase index with all complete;
   assert exits 1.
3. `test_current_phase_fallback_no_index` — no index file; mock phase files
   with one having an unbuilt story; assert correct path returned.
4. `test_current_phase_project_dir_depth_guard` — path traversal attempt via
   `--project-dir`; assert rejected.
