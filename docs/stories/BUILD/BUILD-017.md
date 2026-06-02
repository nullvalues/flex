---
id: BUILD-017
rail: BUILD
title: Formal era transition command
status: planned
phase: "52"
story_class: code
primary_files:
  - skills/pairmode/scripts/era_transition.py
touches:
  - skills/pairmode/scripts/flex_build.py
  - tests/pairmode/test_era_transition.py
---

# BUILD-017 — Formal era transition command

## Background

`era_new.py` can create a new era file, but there is no command to formally
close the current era. A project that has outgrown its initial era has no
sanctioned path: it either manually edits the old era's status field or
silently starts a second `active` era alongside the first. Both produce
confusing state — `pairmode_status.py` warns on multiple active eras but
cannot resolve it, and the spec workflow (BUILD-015) would stop with "No
active era found" or pick the wrong one.

A formal transition command closes the current era (status → `complete`,
records `closed_at`), creates the next era with a name and strategic intent,
and reports the result. New phases scaffolded after the transition automatically
inherit the new era (via `phase_new.py`'s active-era detection).

## Ensures

- `era_transition.py` exists at `skills/pairmode/scripts/era_transition.py`
  with CLI: `uv run era_transition.py --project-dir DIR [--name NAME]
  [--intent INTENT] [--yes]`.
- Invocation:
  1. Detects the current active era (scans `docs/eras/*.md` for
     `status: active`). If none found: exits 1 with
     `"No active era to close. Use era_new.py to create one."`.
     If multiple active: exits 1 with
     `"Multiple active eras found: [list]. Resolve manually before transitioning."`.
  2. Prompts (interactive) or accepts flags:
     - `--name`: new era name (required; prompted if absent)
     - `--intent`: new era strategic intent (optional; prompted if absent,
       Enter to skip)
  3. Closes the current active era:
     - Sets `status: complete` in its frontmatter
     - Adds `closed_at: YYYY-MM-DD` (today's date) to its frontmatter
  4. Creates the new era via `era_new.py` logic (next sequential ID, name,
     intent).
  5. Reports:
     ```
     Era NNN closed: [old name]
     Era NNN+1 opened: [new name]
     New phases will be assigned to Era NNN+1.
     ```
- `flex_build.py` gains a `transition-era` subcommand that delegates to
  `era_transition.py`'s main function (same pattern as other subcommands).
- `--yes` mode: skips prompts; `--name` is required in this mode; `--intent`
  defaults to empty (placeholder written to new era file).
- Path traversal guard on `--project-dir` (same depth check as other CLIs).
- The command is idempotent for the "new era" side: if the new era file already
  exists with the same ID, exits 1 with a clear message rather than
  overwriting.

## Out of scope

- Migrating existing phase frontmatter to the new era (phases keep their
  original era assignment; only new phases pick up the new era).
- Updating the phase index to show era boundary markers (cosmetic; can be
  done manually or in a follow-on).
- Bulk-reopening a closed era (manual frontmatter edit if needed).

## Instructions

### 1. Create `era_transition.py`

Follow the structure of `era_new.py`: click CLI, path traversal guard,
frontmatter read/write via the existing `_parse_frontmatter` / string
manipulation pattern used elsewhere in the scripts.

Closing the current era:
```python
# Read era file, update frontmatter: status → complete, add closed_at
import datetime
today = datetime.date.today().isoformat()
# Parse frontmatter block (lines between --- markers), update status and
# insert closed_at, rewrite file.
```

Creating the new era: import and call the `era_new` logic from `era_new.py`
(or duplicate the minimal creation logic — whichever avoids circular imports).

### 2. Wire into `flex_build.py`

Add to the argument parser / subcommand dispatch:

```python
elif args.command == "transition-era":
    from era_transition import era_transition_cli
    sys.exit(era_transition_cli(
        project_dir=args.project_dir,
        name=getattr(args, "name", None),
        intent=getattr(args, "intent", ""),
        yes=getattr(args, "yes", False),
    ))
```

Add the subparser with `--name`, `--intent`, `--project-dir`, `--yes` options.

### 3. Frontmatter write pattern

The existing scripts use regex-based frontmatter parsing. For the close
operation, update the frontmatter block in place:

```python
def _close_era_frontmatter(content: str, today: str) -> str:
    """Set status: complete and add closed_at: DATE in the frontmatter block."""
    # Replace `status: active` with `status: complete`
    # Insert `closed_at: YYYY-MM-DD` after the status line
    ...
```

## Tests

`tests/pairmode/test_era_transition.py` (new):

1. `test_transition_closes_active_era` — create a tmp project with one active
   era file; run transition with `--name "Next era" --yes`; assert old era has
   `status: complete` and `closed_at` set.
2. `test_transition_creates_new_era` — same setup; assert new era file exists
   with `status: active` and sequential ID.
3. `test_transition_no_active_era_exits_1` — no active era; assert exit code 1
   and error message.
4. `test_transition_multiple_active_eras_exits_1` — two active era files;
   assert exit code 1.
5. `test_transition_project_dir_depth_guard` — path traversal attempt; assert
   rejected.
6. `test_flex_build_transition_era_subcommand` — verify `flex_build.py
   transition-era --help` exits 0 (subcommand wired).
