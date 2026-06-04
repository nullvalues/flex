---
id: INFRA-155
rail: INFRA
title: "`flex_build.py check-story-scope RAIL-NNN` — co-dependency heuristic warnings"
status: complete
phase: "61"
story_class: code
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - tests/pairmode/test_flex_build_check_story_scope.py
touches: []
---

# INFRA-155 — `flex_build.py check-story-scope`: co-dependency heuristic warnings

## Context

The Plan subagent (spec writer) consistently misses co-located files when
declaring a story's `primary_files` and `touches` frontmatter. The companion
sidebar's scope_miss capture (INFRA-154) records this after the fact; this
story prevents it at gate time.

Two heuristic patterns dominate scope misses in this codebase:

1. **Test co-location.** When a story declares
   `skills/pairmode/scripts/X.py`, the test file `tests/pairmode/test_X.py`
   is almost always also edited. Every code-class story under
   `skills/pairmode/scripts/` lists its sibling test in primary_files.

2. **Template / live-rendered pair.** When a story declares
   `skills/pairmode/templates/CLAUDE.build.md.j2`, the bootstrap-rendered
   counterpart `CLAUDE.build.md` at the project root is almost always also
   edited (see BUILD-024 primary_files for prior art).

INFRA-155 adds a `flex_build.py check-story-scope STORY_ID` subcommand that
applies these heuristics to a story's declared primary_files and touches and
prints informational warnings. The command is purely advisory: it always
exits 0 and prints nothing when no warnings are found. The build loop
(BUILD-025) calls it; the developer decides whether to update the spec.

**Depends on nothing.** BUILD-025 depends on this command existing.

## Acceptance criteria

### `skills/pairmode/scripts/flex_build.py`

1. Add a `check-story-scope` subcommand following sibling conventions:

   ```
   flex_build.py check-story-scope STORY_ID [--project-dir DIR]
   ```

   - `STORY_ID` — required positional argument (matches `cmd_permissions_create`
     argument style).
   - `--project-dir` — standard option (`default="."`,
     `type=click.Path(file_okay=False, dir_okay=True)`).

2. Validation:

   - `STORY_ID` must match `_STORY_ID_RE` (line 57). On mismatch: emit
     `check-story-scope: invalid story_id format: {story_id!r}` to stderr,
     exit 1.

   - Resolve `project_dir`, locate story spec via `_story_path`. If missing:
     emit `check-story-scope: story spec not found: {story_path}` to stderr,
     exit 1.

   - Parse frontmatter via `_read_story_frontmatter`. On failure: emit
     exception to stderr, exit 1.

3. Build the declared scope set: union of `primary_files` and `touches`
   (treat missing keys as empty lists; deduplicate; normalise each path via
   `lambda s: s.replace("\\", "/").lstrip("./")`).

4. **Rule 1 — Test co-location.** For each path `p` in the declared scope:

   - If `p` matches `skills/pairmode/scripts/*.py` AND basename does not
     start with `test_` AND basename is not `__init__.py`:
     - Expected test path: `tests/pairmode/test_{stem}.py`
       where `stem = Path(p).stem`.
     - If the test file exists on disk under `project_dir` AND its
       normalised path is NOT in the declared scope set:
       - Print to stdout:
         ```
         SCOPE WARNING: {story_id}: scripts/{basename} declared but tests/pairmode/test_{stem}.py not in primary_files/touches
         ```

5. **Rule 2 — Template / live-rendered pair.** For each path `p` in the
   declared scope:

   - If `p` matches `skills/pairmode/templates/**/*.j2`:
     - Compute `bare = Path(p).name[:-3]` (strip `.j2`).
     - Check candidate live locations in order:
       1. `bare` (project root)
       2. `skills/pairmode/{bare}` (skill root)
     - For the first candidate that exists on disk AND is NOT in the declared
       scope set:
       - Print to stdout:
         ```
         SCOPE WARNING: {story_id}: {p} declared but {live_path} not in primary_files/touches
         ```
       - `{live_path}` is the project-relative POSIX path. Only the first
         matching candidate emits (do not emit two warnings per template).

6. Always exits 0 once validation passes. Read-only — no file writes.

7. Path comparison normalised on both sides:
   `lambda s: s.replace("\\", "/").lstrip("./")`

### Tests — `tests/pairmode/test_flex_build_check_story_scope.py`

8. New test file using the `subprocess` pattern from
   `tests/pairmode/test_flex_build_next_phase.py` (lines 29–39).
   `_SCRIPT` points to `skills/pairmode/scripts/flex_build.py`.

9. Helper `_make_story(tmp_path, story_id, primary_files, touches)` —
   writes a minimal frontmatter-only story file under
   `docs/stories/<RAIL>/<STORY_ID>.md`.

10. Helper `_touch(tmp_path, rel_path)` — creates an empty file ensuring
    parent directories exist.

11. Required test cases:

    - **`test_rule1_fires_when_script_declared_without_test`** — Story declares
      `["skills/pairmode/scripts/foo.py"]`; test file exists on disk; test
      absent from scope. Assert stdout contains `SCOPE WARNING:` with sibling-
      test phrase; exit 0.

    - **`test_rule1_silent_when_test_declared`** — Both script and test
      declared; test file on disk. Assert stdout empty; exit 0.

    - **`test_rule1_silent_when_test_not_on_disk`** — Script declared but
      expected test path does not exist. Assert stdout empty; exit 0.

    - **`test_rule1_silent_for_script_in_touches`** — Script in `touches`,
      test in `primary_files`. Assert no warning (scope = union).

    - **`test_rule1_skips_test_files_and_init`** — Story declares
      `skills/pairmode/scripts/test_foo.py` and
      `skills/pairmode/scripts/__init__.py`. Assert stdout empty; exit 0.

    - **`test_rule2_fires_when_template_declared_without_live`** — Story
      declares `["skills/pairmode/templates/CLAUDE.build.md.j2"]`;
      `CLAUDE.build.md` exists at `tmp_path`; live file absent from scope.
      Assert stdout contains `SCOPE WARNING:` naming both template and live
      path; exit 0.

    - **`test_rule2_silent_when_live_declared`** — Both template and live
      declared. Assert stdout empty.

    - **`test_rule2_silent_when_no_live_counterpart_exists`** — Template
      declared; no live counterpart at any candidate location. Assert stdout
      empty.

    - **`test_no_warnings_on_empty_primary_files`** — Empty `primary_files`
      and `touches`. Assert stdout empty; exit 0.

    - **`test_exit_zero_when_warnings_present`** — Story producing warnings
      still exits 0.

    - **`test_invalid_story_id_exits_one`** — Pass `not-a-story-id`. Assert
      exit 1; stderr contains `invalid story_id format`.

    - **`test_missing_story_spec_exits_one`** — Valid `STORY_ID` but no story
      file. Assert exit 1; stderr contains `story spec not found`.

    - **`test_multiple_warnings_for_multiple_scripts`** — Story declares three
      scripts, none with test siblings declared; all three test files on disk.
      Assert stdout has exactly three `SCOPE WARNING:` lines.

12. Tests must not depend on the host repo's actual `skills/pairmode/`
    contents — every test sets up its own `tmp_path` skeleton.

## Out of scope

- Wiring the call site into `CLAUDE.build.md` or the Jinja2 template (BUILD-025).
- Persisting warnings to `lessons.json` (stdout-only; INFRA-154 is the
  persistence layer).
- Heuristics for other rails (e.g. `skills/companion/scripts/` paired with
  `tests/companion/`) — kept to the two highest-signal patterns.
- LLM-driven scope inference.
- Blocking the build loop on warnings (informational only).
