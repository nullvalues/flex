# flex — Phase 36: `/flex:pairmode migrate-from-anchor`

← [Phase 35: Project rename to flex](phase-35.md)

## Goal

Phase 35 renamed this repo from `anchor` to `flex`. But every sibling project that
was bootstrapped by anchor (cora, radar, aab, forqsite, ud, and any future
discoveries) still carries anchor references in its bootstrap-generated
methodology surface — `CLAUDE.build.md`, agent file bodies, hooks, launcher
scripts, the companion sidebar, identifier names, environment-variable names,
`/tmp/` runtime paths, and `.companion/state.json` version metadata.

Existing flex tooling closes part of the gap (`sync-build` regenerates
`CLAUDE.build.md`; `sync-agents` regenerates agent frontmatter) but does not
touch agent file bodies, hook scripts, launcher scripts, or sidebar branding.
Without a one-shot tool, every sibling-project owner has to discover and
manually rewrite the same dozen-or-so substitution patterns that this repo
already worked out in phase 35.

This phase adds **`/flex:pairmode migrate-from-anchor`** — a single CLI command
that, when run inside an anchor-bootstrapped project, applies the phase-35
substitution matrix to that project's methodology surface, composes the existing
sync-build / sync-agents flows, bumps `pairmode_version`, and runs the same
verification gates phase 35 used to confirm a clean migration.

**Design principles:**

1. **Idempotent.** Running the command twice on the same project must produce
   identical state on both runs. Re-running on a fully-migrated project reports
   "already migrated" and exits cleanly.
2. **Methodology-surface-only.** The tool touches files known to be
   bootstrap-generated (the same surface the spec for phase 35 enumerated for
   this repo). It does NOT touch project-authored content — `README.md`,
   `CHANGELOG.md`, `docs/brief.md`, `docs/architecture.md`, project phase docs,
   CER backlog, lessons. Migrating those is the project owner's call.
3. **Safe by default.** Default mode is `--dry-run`. The user must pass
   `--apply` to write. With `--apply`, each touched file is backed up to
   `<path>.pre-flex-migration` before modification. `--yes` skips the apply
   confirmation prompt.
4. **Verifiable.** After applying, the same seven grep gates from INFRA-091 run
   against the target project. Any residual anchor reference in scope is
   reported.

**Out of scope:**

- Lessons file content rewrite. Each project's `lessons/lessons.json` is its own
  record; the migration tool may optionally offer to rewrite `source_project:
  "anchor"` → `"flex"` (with a `--migrate-lessons` flag) but that's the only
  lessons-touching mode. Default leaves lessons untouched.
- Plugin uninstall/reinstall in Claude Code itself (that's a user action — the
  migration tool can't do it from inside a script).
- Repository-level git operations (renaming the project's git remote, etc.).

**Story dependencies:**

```
INFRA-092 (core migration engine) ── independent
INFRA-093 (tests + fixture)        ── depends on INFRA-092
INFRA-094 (CLI wiring + SKILL.md)  ── depends on INFRA-092
```

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-092 | `pairmode_migrate.py` — substitution engine + per-file rule table + safety flags | complete |
| INFRA-093 | Tests — fixture-based anchor-bootstrapped project + migration assertions | complete |
| INFRA-094 | CLI wiring — pairmode dispatcher + SKILL.md documentation | complete |
| INFRA-095 | Security hardening: backup-suffix path validation + sentinel-file check | planned |

---

### Story INFRA-092 — `pairmode_migrate.py` substitution engine + per-file rule table + safety flags

**Rail:** INFRA | **story_class:** code

## Requires

- Existing `pairmode_sync.py` `sync-build` and `sync-agents` subcommands (invoked via subprocess).
- `_depth_guard_sync_build()` in `pairmode_sync.py` as the model for the 3-component path depth check.
- Existing canonical-template paths under `skills/pairmode/templates/`.

## Ensures

A new module `skills/pairmode/scripts/pairmode_migrate.py` exposing:

**CLI:**
```
pairmode_migrate.py --project-dir PATH [--apply] [--yes] [--migrate-lessons] [--backup-suffix SUFFIX]
```

Default mode is dry-run (no `--apply`). The output of a dry-run is the same
human-readable summary that an apply run produces, except no files are written
and no backups are created.

**Substitution rule table** (the heart of the story; declared as a module-level
constant `MIGRATION_RULES` for testability):

| # | File or pattern | Strategy | Notes |
|---|------|------|------|
| 1 | `CLAUDE.build.md` | Subprocess: `uv run python <FLEX_ROOT>/skills/pairmode/scripts/pairmode_sync.py sync-build --project-dir <project_dir> --apply --yes` | `sync_build` is a Click command handler; invoke via subprocess, not direct import |
| 2 | `.claude/agents/*.md` (frontmatter) | Subprocess: `uv run python <FLEX_ROOT>/skills/pairmode/scripts/pairmode_sync.py sync-agents --project-dir <project_dir> --apply --yes` | Same — Click handler, invoke via subprocess |
| 3 | `.claude/agents/*.md` (body) | Regex substitution | `"anchor project"` → `"flex project"`; `$HOME/\.anchor/` → `$HOME/.flex/`; `/anchor:` → `/flex:` |
| 4 | `hooks/*.py` | Regex substitution | `ANCHOR_PROJECT_DIR` → `FLEX_PROJECT_DIR`; `ANCHOR_PROJECT_HASH` → `FLEX_PROJECT_HASH`; `/tmp/anchor_project_dir` → `/tmp/flex_project_dir`; local var `anchor_root` → `repo_root` |
| 5 | `skills/companion/scripts/launch_sidebar.sh` and `.command` | Regex substitution | Same as hooks/, plus `$HOME/\.anchor/` → `$HOME/.flex/` |
| 6 | `skills/companion/scripts/start_sidebar.sh` | Regex substitution | Same as launch_sidebar |
| 7 | `skills/companion/scripts/sidebar.py` | Regex substitution | `_ANCHOR_ROOT` → `_REPO_ROOT`; `[bold]anchor[/bold]` → `[bold]flex[/bold]`; `[bold #d75f00]Anchor[/bold #d75f00]` → `[bold #d75f00]Flex[/bold #d75f00]`; `/anchor:companion` → `/flex:companion` |
| 8 | `skills/seed/SKILL.md` | Regex substitution | `name: anchor:seed` → `name: flex:seed`; `/anchor:seed` → `/flex:seed` |
| 9 | `skills/pairmode/SKILL.md` | Regex substitution | `/anchor:pairmode` → `/flex:pairmode` |
| 10 | `skills/companion/SKILL.md` | Regex substitution | `/anchor:companion` → `/flex:companion` |
| 11 | `skills/pairmode/scripts/*.py` (if present — some projects copy) | Regex substitution | `_ANCHOR_ROOT` → `_REPO_ROOT`; comment "anchor repo root" → "repo root" |
| 12 | `.claude/settings.deny-rationale.json` | Regex substitution | `"generated_by": "anchor:pairmode"` → `"flex:pairmode"`; `"anchor intercepts"` → `"flex intercepts"` |
| 13 | `.companion/state.json` | Conditional key-update | If `pairmode_version` starts with `"anchor-"` or is unset, set to current flex version (`"0.2.0"` at spec time); if `project_name` exactly equals `"anchor"`, set to `"flex"` (otherwise leave alone — the project may legitimately have its own name) |
| 14 | `lessons/lessons.json` (gated on `--migrate-lessons`) | One-time bypass | Same pattern as phase 35 INFRA-091: load with `json.load`, rewrite `source_project: "anchor"` → `"flex"`, rewrite free-text anchor refs, dump with `json.dump`. Bypasses `save_lessons()`. NOT default. |
| 15 | `lessons/LESSONS.md` (gated on `--migrate-lessons`) | Regenerate | Call `lesson_utils.generate_lessons_md(data)` after step 14, write result. |

**Rule application order:** 1, 2, then 3 through 15 (sync delegates run first so
their re-rendered output is what subsequent regex passes see; this matters
because the templates themselves no longer carry anchor strings, but the
template rendering might overwrite manual fixes the user made — the migration
tool deliberately favors the canonical template state).

**Engine behavior:**

```python
def migrate(project_dir: Path, *, apply: bool, yes: bool,
            migrate_lessons: bool, backup_suffix: str = ".pre-flex-migration"
           ) -> MigrationReport:
    """
    Apply the MIGRATION_RULES table to project_dir.

    Returns a MigrationReport with:
      - changed: list[Path]      — files modified
      - skipped: list[Path]      — files that exist but had no anchor refs (no-op)
      - missing: list[Path]      — files in MIGRATION_RULES that don't exist in the project
      - backups: list[Path]      — paths of backup files written
      - gate_results: dict       — outcome of each of the 7 final-gate checks
      - already_migrated: bool   — True if the project was already clean (no-op run)
    """
```

**Safety guards:**

- `--project-dir` must resolve to a path with at least 3 path components
  (same check as `_depth_guard_sync_build` in `pairmode_sync.py`: `len(path.parts) < 3`).
  Implement inline in `pairmode_migrate.py` — `permission_scope.py` does not
  export a depth guard. Raise `SystemExit(1)` with an error message if too shallow.
- `apply=False` (dry-run) is the default. The script prints the proposed diff
  for each file but writes nothing.
- `apply=True` requires interactive `[y/N]` confirmation unless `--yes`.
- Backups: for each file the engine intends to modify, write
  `<path><backup_suffix>` *before* the modification. The backup is the
  pre-migration content. If the migration fails partway through, the user can
  manually restore from backups.

**Idempotency:**

- The engine first runs the 7 final-state grep gates on the project (the same
  gates from INFRA-091, but project-scoped — exclude spec docs for THIS
  project, not phase-35.md from the flex repo).
- If all 7 gates return zero matches, set `already_migrated = True` and skip
  all writes. Print: `Project already migrated. No changes.`
- Otherwise, apply rules 1–13 (and 14–15 if `--migrate-lessons`), then re-run
  the gates. Report gate results in the summary.

**Final report format** (printed to stdout at end of run):

```
MIGRATION REPORT — <project_dir>
  Mode:                <dry-run | apply>
  Files changed:       <N>
  Files skipped:       <N>  (existed but had no anchor refs)
  Files missing:       <N>  (in rule table but not present in project)
  Backups created:     <N>  (with suffix <backup_suffix>)
  pairmode_version:    <old> → <new>
  Final gate results:
    /anchor: slash refs        ✓ clean
    _ANCHOR_ROOT identifiers   ✓ clean
    /mnt/work/anchor paths     ✓ clean
    ~/.anchor/ refs            ✓ clean
    ANCHOR_PROJECT_* env vars  ✓ clean
    emitted "anchor:pairmode"  ✓ clean
    project-name anchor prose  ✗ 2 residual matches (listed below)
  Residuals:
    <file:line>     <matched text>
    <file:line>     <matched text>
```

**Primary files:**
- `skills/pairmode/scripts/pairmode_migrate.py`

**Touches:** (none)

**Tests:** Logic module — test file required (covered in INFRA-093).

---

### Story INFRA-093 — Tests — fixture-based anchor-bootstrapped project + migration assertions

**Rail:** INFRA | **story_class:** code

## Requires

- INFRA-092 complete: `pairmode_migrate.py` with `migrate()` and the
  MIGRATION_RULES table importable.

## Ensures

A new test file `tests/pairmode/test_pairmode_migrate.py` exercising the
migration engine against a synthetic anchor-bootstrapped project.

**Fixture:** a helper `_build_anchor_project(tmp_path) -> Path` that creates a
minimal but representative anchor-bootstrapped project tree under `tmp_path`,
populated with anchor references at every substitution site the rule table
covers:

```
tmp_path/
  CLAUDE.build.md                       # contains /mnt/work/anchor/skills/pairmode/scripts/...
  .claude/
    agents/
      builder.md                        # body says "You are the builder for the anchor project."
      reviewer.md                       # same pattern
      security-auditor.md               # has $HOME/.anchor/auth.json
    settings.deny-rationale.json        # has "generated_by": "anchor:pairmode"
  hooks/
    session_start.py                    # uses ANCHOR_PROJECT_DIR, /tmp/anchor_project_dir_
    session_end.py                      # prints "Anchor companion terminal."
  skills/
    companion/
      SKILL.md                          # /anchor:companion
      scripts/
        launch_sidebar.sh               # ~/.anchor/auth.json, ANCHOR_PROJECT_*
        start_sidebar.sh                # ANCHOR_PROJECT_*
        sidebar.py                      # title="[bold]anchor[/bold]"
    seed/
      SKILL.md                          # name: anchor:seed
    pairmode/
      SKILL.md                          # /anchor:pairmode references
  .companion/
    state.json                          # {"pairmode_version": "anchor-0.1.0", "project_name": "anchor"}
  lessons/
    lessons.json                        # one lesson with source_project: "anchor" and anchor in body
    LESSONS.md                          # "# Anchor Methodology Lessons" heading
  docs/
    phases/
      phase-1.md                        # NOT touched by migration — project's history
    architecture.md                     # NOT touched — project-authored content
```

**Tests:**

1. **`test_migrate_dry_run_does_not_write`** — Run `migrate(project, apply=False)`.
   Capture report. Assert: report.changed list is populated, but all original
   file contents are byte-identical after run. No backups created. No
   `pre-flex-migration` files exist.

2. **`test_migrate_apply_writes_changes_and_backups`** — Run with `apply=True,
   yes=True`. Assert: each file in `report.changed` has new content (no anchor
   refs in scope); each has a corresponding `.pre-flex-migration` backup with
   pre-migration content.

3. **`test_migrate_state_json_version_bumped`** — After apply, read
   `.companion/state.json` and assert `pairmode_version` no longer starts with
   `"anchor-"`, and `project_name` is `"flex"` if it was `"anchor"`.

4. **`test_migrate_state_json_custom_project_name_preserved`** — If
   `project_name` is set to `"cora"` (or anything not `"anchor"`), the
   migration does NOT change it.

5. **`test_migrate_does_not_touch_authored_content`** — After migration, the
   fixture's `docs/phases/phase-1.md` and `docs/architecture.md` (which contain
   anchor references in test content) are byte-identical to pre-migration
   state.

6. **`test_migrate_lessons_default_skip`** — Without `--migrate-lessons`,
   `lessons/lessons.json` is unchanged after run.

7. **`test_migrate_lessons_with_flag`** — With `migrate_lessons=True`, lessons
   are rewritten: `source_project` → `"flex"`, free-text anchor refs replaced,
   `LESSONS.md` regenerated with `"# Flex Methodology Lessons"` heading.

8. **`test_migrate_idempotent`** — Run twice. Second run reports
   `already_migrated=True`. File mtimes (or content hashes) are identical
   between first-run end-state and second-run end-state. No new backups
   created on the second run.

9. **`test_migrate_partial_project_missing_files`** — Build a fixture without
   `skills/seed/`. Run migration. Assert: `report.missing` includes the missing
   files; engine completes successfully on the rest.

10. **`test_migrate_gate_residuals_reported`** — Build a fixture with an
    additional, deliberately uncovered anchor reference (e.g., a `docs/foo.md`
    file with `/anchor:pairmode` in it). Run migration. Assert: the project-name
    gate reports 1 residual match at `docs/foo.md`.

11. **`test_migrate_depth_guard_rejects_shallow_path`** — Call `migrate(Path("/tmp"))`
    (2 path components). Engine raises or returns an error.

12. **`test_migrate_dry_run_then_apply`** — Run dry-run first, capture proposed
    changes; then run apply; assert applied changes match dry-run's projection.

**Primary files:**
- `tests/pairmode/test_pairmode_migrate.py`

**Touches:** (none)

**Tests:** This story IS the test addition. Verify by:
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_pairmode_migrate.py -x -v` passes all 12 tests.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes the full suite with no regressions.

---

### Story INFRA-094 — CLI wiring — pairmode dispatcher + SKILL.md documentation

**Rail:** INFRA | **story_class:** methodology

## Requires

- INFRA-092 complete: `pairmode_migrate.py` exists and is invocable.
- INFRA-093 complete: tests pass.

## Ensures

**`skills/pairmode/SKILL.md`** gains a new section documenting the command,
following the conventions of the existing subcommand sections (e.g.
`sync-agents`, `drift-report`, `register`). The section includes:

- "When to use" — for migrating an anchor-bootstrapped sibling project to flex.
- "Inputs expected" — `--project-dir`, optional `--migrate-lessons`,
  `--apply`/`--yes`/`--backup-suffix`.
- "What it does" — high-level summary of the 13-rule substitution table plus
  conditional rules 14–15 for lessons.
- "Outputs" — the migration report format.
- "Flags" reference table — full list of CLI flags.
- "Workflow" — recommended invocation pattern: dry-run first, review output,
  then apply.
- A note that this is a one-time-per-project operation, not a recurring sync.

**`skills/pairmode/SKILL.md`** also updates the top-level "Commands" listing to
include `migrate-from-anchor`.

**CLI invocation (documented in SKILL.md):**
```bash
PYTHONPATH="/mnt/work/flex" uv run python /mnt/work/flex/skills/pairmode/scripts/pairmode_migrate.py \
  --project-dir /path/to/sibling-project
# Dry-run by default. Review output, then:
PYTHONPATH="/mnt/work/flex" uv run python /mnt/work/flex/skills/pairmode/scripts/pairmode_migrate.py \
  --project-dir /path/to/sibling-project --apply --yes
```

**Primary files:**
- `skills/pairmode/SKILL.md`

**Touches:** (none — `pairmode_migrate.py` is a standalone CLI like
`phase_new.py` and `cer.py`, invoked directly per existing convention; no
central dispatcher edit needed.)

**Tests:** Documentation story — no new test file expected. Verify by:
- `skills/pairmode/SKILL.md` contains a section heading
  `### /flex:pairmode migrate-from-anchor` (or equivalent).
- The Commands listing at the top of SKILL.md mentions
  `migrate-from-anchor`.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` still
  passes (including `test_skill_md.py` if it has assertions on SKILL.md
  structure).

---

### Story INFRA-095 — Security hardening: backup-suffix path validation + sentinel-file check

**Rail:** INFRA | **story_class:** code

## Requires

- INFRA-092 complete: `pairmode_migrate.py` exists.
- Security audit finding: Phase 36 checkpoint audit flagged two HIGH issues.

## Ensures

**Fix 1 — backup-suffix path validation** (`pairmode_migrate.py`)

Add a `_validate_backup_suffix(suffix: str) -> None` function that rejects any
suffix containing a `/` or `..` component. Raise `SystemExit(1)` with a clear
error message. Call it at CLI entry point before any work begins.

Acceptable suffix: `.pre-flex-migration`, `.bak`, `-backup`  
Rejected: `/tmp/x`, `../etc/cron.d/x`, `../../foo`

Implementation — call in the CLI entry point after argument parsing:

```python
def _validate_backup_suffix(suffix: str) -> None:
    if "/" in suffix or ".." in suffix:
        click.echo(
            f"error: --backup-suffix must be a leaf string (no '/' or '..'): {suffix!r}",
            err=True,
        )
        sys.exit(1)
```

**Fix 2 — sentinel-file check before apply** (`pairmode_migrate.py`)

Before writing any files (i.e., when `apply=True`), verify that the target
project is plausibly a methodology-managed project by checking that at least
one sentinel exists:
- `CLAUDE.build.md`
- `.companion/` directory
- `.claude/agents/` directory

If none are present, abort with:

```
error: --project-dir does not look like a flex/anchor-bootstrapped project
       (expected at least one of: CLAUDE.build.md, .companion/, .claude/agents/)
       Re-run without --apply to preview what would change, or verify the path.
```

Dry-run mode (`apply=False`) does NOT enforce this check — the user may want
to preview against an arbitrary directory to understand what would be touched.

Add a test `test_migrate_apply_rejects_non_project_dir` to
`tests/pairmode/test_pairmode_migrate.py` that:
- Creates a tmp directory with no sentinel files
- Calls `migrate(..., apply=True, yes=True)` 
- Asserts `SystemExit` is raised (or appropriate error return)

Also add a test `test_migrate_backup_suffix_validation` that:
- Calls the CLI (or `migrate()` directly if the validation is called there) with
  `backup_suffix="/tmp/evil"`
- Asserts `SystemExit` is raised

**Primary files:**
- `skills/pairmode/scripts/pairmode_migrate.py`

**Touches:**
- `tests/pairmode/test_pairmode_migrate.py`

**Tests:**
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.
- Both new tests pass.

---

## Stories

Update the stories table to include INFRA-095:

---

Tag: `cp36-migrate-from-anchor`
