# flex — Phase 30: Hook security fix and sync tooling gaps

← [Phase 29: Project drift detection and promotion workflow](phase-29.md)

## Goal

Three targeted improvements: close the one remaining open security finding (CER-020,
the `exit_plan_mode.py` pipe-path containment gap left behind when INFRA-062 fixed the
other three hooks), and fill two operability gaps identified during Phase 25 and Phase 29
development — propagating `CLAUDE.build.md` template changes to existing projects, and
managing the `registered_projects` list in `state.json` without manual JSON editing.

These are small, independent stories with no cross-dependencies. They can be built in
any order.

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-068 | CER-020: `exit_plan_mode.py` pipe-path containment guard | complete |
| INFRA-069 | `pairmode sync-build` — propagate CLAUDE.build.md template changes | complete |
| INFRA-070 | `pairmode register/unregister` — manage registered_projects in state.json | complete |

---

### Story INFRA-068 — CER-020: `exit_plan_mode.py` pipe-path containment guard

**Rail:** INFRA | **story_class:** code

**Acceptance criterion:** `hooks/exit_plan_mode.py` applies the same
`_resolve_pipe_path` containment guard as `hooks/post_tool_use.py` (INFRA-062). Line
16-17 (`if _state.get("pipe_path"): PIPE_PATH = _state["pipe_path"]`) is replaced with
the validated pattern: `_resolve_pipe_path()` checks that the resolved path is
`relative_to(Path(tempfile.gettempdir()).resolve())`; if the check fails, the hook
keeps the legacy fallback. CER-020 is marked RESOLVED in `docs/cer/backlog.md`.

**Note:** `exit_plan_mode.py` is a protected file. The builder must use Opus for this
story.

**Instructions:**

1. Read `hooks/post_tool_use.py` lines 21-43 to understand the `_resolve_pipe_path`
   helper and the validated-assignment pattern introduced by INFRA-062.

2. In `hooks/exit_plan_mode.py`:
   - After the `import tempfile` line (line 10), import `Path` from `pathlib`.
   - Add the `_resolve_pipe_path(raw_path: str) -> str | None` helper verbatim from
     `post_tool_use.py` (same function body, same docstring).
   - Replace lines 16-17:
     ```python
     if _state.get("pipe_path"):
         PIPE_PATH = _state["pipe_path"]
     ```
     with:
     ```python
     if _state.get("pipe_path"):
         _validated = _resolve_pipe_path(_state["pipe_path"])
         if _validated:
             PIPE_PATH = _validated
     ```

3. In `docs/cer/backlog.md`, append `**RESOLVED** Phase 30 INFRA-068` to the CER-020
   row.

**Primary files:** `hooks/exit_plan_mode.py`
**Touches:** `docs/cer/backlog.md`

**Tests:** `tests/pairmode/test_hooks.py` — assert that a crafted `state.json` with
`pipe_path` pointing outside `tempfile.gettempdir()` does not override `PIPE_PATH`; assert
that a valid `pipe_path` inside `tempfile.gettempdir()` is accepted; assert that the module
still imports and executes `main()` successfully when state.json is absent.

---

### Story INFRA-069 — `pairmode sync-build` — propagate CLAUDE.build.md template changes

**Rail:** INFRA | **story_class:** code

**Acceptance criterion:** `pairmode sync-build --project-dir <path>` compares the target
project's `CLAUDE.build.md` against the canonical `CLAUDE.build.md.j2` template rendered
with the project's `state.json`. It prints a unified diff. With `--apply`, it writes the
rendered template to the project's `CLAUDE.build.md` after explicit confirmation (or
immediately with `--yes`). With `--dry-run`, it prints the diff and exits without writing.
The subcommand is accessible via `pairmode sync-build` in the same entry-point as
`sync-agents`.

**Background:** Phase 25 added `pairmode sync-agents` to propagate agent-template changes
to existing projects. `CLAUDE.build.md` was intentionally excluded from `sync-agents`
because it is a build-loop document that projects customise. `sync-build` fills this gap
with an explicit opt-in apply step rather than silent propagation.

**Instructions:**

1. In `skills/pairmode/scripts/pairmode_sync.py`, add a new Click subcommand
   `sync-build`:
   - Options: `--project-dir PATH` (required), `--dry-run` (flag), `--apply` (flag),
     `--yes` (flag, skip confirmation on `--apply`).
   - Read `state.json` from `<project-dir>/.companion/state.json` to get template vars
     (project_name, tech_stack, modules, etc.). Fall back gracefully when keys are absent.
   - Render `skills/pairmode/templates/CLAUDE.build.md.j2` with those vars using Jinja2.
   - Diff the rendered output against `<project-dir>/CLAUDE.build.md`.
   - With `--dry-run` or no `--apply`: print the diff and exit 0.
   - With `--apply` and no `--yes`: print the diff and prompt "Apply? [y/N]". Proceed only
     on `y`.
   - Apply: write the rendered template to `<project-dir>/CLAUDE.build.md`.
   - Apply `resolve().relative_to()` containment guard on `--project-dir`, consistent with
     all other pairmode entry points.

2. Register `sync_build` in the `pairmode` CLI group at the bottom of `pairmode_sync.py`
   alongside the existing `sync_agents` registration.

3. Add a one-line entry for `pairmode sync-build` in the `## pairmode_sync.py` section
   of `docs/architecture.md` alongside `pairmode sync-agents`.

**Primary files:** `skills/pairmode/scripts/pairmode_sync.py`
**Touches:** `docs/architecture.md`

**Tests:** `tests/pairmode/test_sync.py` — fixture project with a stale `CLAUDE.build.md`
(missing a section present in the template). Assert `sync-build --dry-run` prints a diff
containing the missing section and does not modify the file. Assert `sync-build --apply
--yes` writes the rendered template. Assert containment guard rejects a `--project-dir`
that resolves outside a safe base path.

---

### Story INFRA-070 — `pairmode register/unregister` — manage registered_projects

**Rail:** INFRA | **story_class:** code

**Acceptance criterion:** Three new subcommands in the `pairmode` CLI:

- `pairmode register --project-dir <path>` — adds the resolved absolute path to
  `registered_projects` in flex's `.companion/state.json`. If the path is already
  registered, prints "already registered" and exits 0.
- `pairmode unregister --project-dir <path>` — removes the resolved absolute path from
  `registered_projects`. If not found, prints "not registered" and exits 0.
- `pairmode list-projects` — prints the current `registered_projects` list (one entry per
  line), or "No projects registered." when empty.

All three commands read and write flex's own `.companion/state.json` (the file in the
current working directory, not the target project's). The `registered_projects` key is a
list of strings; it is created when the first project is registered if absent.

**Background:** Phase 29 INFRA-066 added `drift promotion` which reads
`state.json["registered_projects"]`. There was no CLI to manage that list — users had to
hand-edit state.json. This story closes that gap.

**Instructions:**

1. Create `skills/pairmode/scripts/pairmode_register.py` with three Click commands:
   `register`, `unregister`, `list-projects`. All three load and save
   `.companion/state.json` atomically (write to a temp file and rename).
   - `register`: resolve `--project-dir`, apply `_depth_guard`, add to
     `registered_projects` list if not present, save.
   - `unregister`: resolve `--project-dir`, remove from list if present, save.
   - `list-projects`: read and print `registered_projects`.

2. Wire all three commands into the top-level `pairmode` CLI group. The simplest approach
   is to import and register them in `pairmode_sync.py` (which already owns the CLI group)
   or add them to a shared `pairmode_cli.py` entry point if one exists. Follow the existing
   pattern.

3. Document `registered_projects` key format in `docs/architecture.md` alongside the
   existing INFRA-066 note about drift promotion reading it. Note that `pairmode register`/
   `unregister`/`list-projects` are the canonical management path.

**Primary files:** `skills/pairmode/scripts/pairmode_register.py`
**Touches:** `skills/pairmode/scripts/pairmode_sync.py`, `docs/architecture.md`

**Tests:** `tests/pairmode/test_register.py` — assert `register` adds a path and
idempotent; `unregister` removes a path and is a no-op when not found; `list-projects`
returns empty message when no entries; state.json atomic write (file is valid JSON after
each operation); `_depth_guard` rejects shallow paths.

---

Tag: `cp30-hook-fix-and-sync-tooling`
