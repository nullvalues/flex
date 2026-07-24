---
id: RELEASE-009
rail: RELEASE
title: Fix thin CLAUDE.build.md.j2 binding and dispatch defects
status: complete
phase: "HARNESS012-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - skills/pairmode/scripts/pairmode_sync.py
touches:
  - CLAUDE.build.md
  - tests/pairmode/test_pairmode_sync.py
---

## Ensures

- **Defect 1 — `pairmode_scripts_dir` missing**: The rendered `CLAUDE.build.md`
  contains an explicit `pairmode_scripts_dir = <abs-path>` key-value line
  matching the pattern `fleet_discovery._SCRIPTS_DIR_PATTERN` (e.g.
  `pairmode_scripts_dir = /mnt/work/flex/skills/pairmode/scripts`). Signal-1
  detection in `fleet_discovery.py` fires `present` for the flex repo itself
  after self-sync.
- **Defect 2 — pathless script invocations**: All `flex_build.py` and
  `record_attempt.py` invocations in the template use
  `{{ pairmode_scripts_dir }}/flex_build.py` (absolute path), not bare
  `flex_build.py`.
- **Defect 3 — hardcoded branch**: The tag-push line uses the project's default
  branch variable (`{{ default_branch | default('main') }}`) rather than the
  hardcoded string `harness`. The self-sync render of flex's own CLAUDE.build.md
  uses `main`.
- **Defect 4 — nonexistent `record-attempt` subcommand**: The dispatch loop
  references a valid mechanism for recording attempt results. Either a new
  `flex_build.py record-attempt` alias is added (delegating to
  `record_attempt.py`), or the template references `record_attempt.py` directly
  by absolute path. The referenced subcommand/script exists and runs.
- `pairmode_sync.py` already passes `pairmode_scripts_dir` in its template
  context (verify at line ~296); if absent, add it.
- After self-sync, running `fleet_discovery.py discover --project-dir .`
  against the flex repo returns `binding: scripts` (Signal-1 present).
- A rendered-template test asserts all four properties.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

### Defect 1 + 2 — pairmode_scripts_dir

In `CLAUDE.build.md.j2`:
1. Add at the top of the orchestrator block:
   ```
   pairmode_scripts_dir = {{ pairmode_scripts_dir }}
   ```
2. Replace all bare `flex_build.py` invocations with
   `{{ pairmode_scripts_dir }}/flex_build.py`.

In `pairmode_sync.py`, confirm the template context dict includes
`pairmode_scripts_dir`. If not, compute it as
`str(Path(__file__).parent.resolve())` and add it.

### Defect 3 — hardcoded branch

In the template, replace `git push origin harness --tags` with
`git push origin {{ default_branch | default('main') }} --tags`.

Add `default_branch` to the `pairmode_sync.py` context (read from
`state.json["default_branch"]` if present, else `"main"`).

### Defect 4 — record-attempt

Option A (preferred): Add a `record-attempt` Click command to `flex_build.py`
that delegates to `record_attempt.py`'s `cmd_record()` with the same
arguments. Update the template to call it.

Option B: Update the template to call
`{{ pairmode_scripts_dir }}/record_attempt.py` directly.

Pick one option and apply consistently in template and tests.

### Self-sync verification

After fixing the template, re-render flex's own `CLAUDE.build.md`:
```bash
PYTHONPATH=... uv run python skills/pairmode/scripts/pairmode_sync.py \
  sync-build --project-dir . --apply --yes
```
Then run:
```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/fleet_discovery.py \
  discover --project-dir .
```
Confirm output contains `binding: scripts` or `Signal 1: present`.

## Tests

Add to `tests/pairmode/test_pairmode_sync.py` (or `test_claude_build.py`):
- Rendered CLAUDE.build.md contains `pairmode_scripts_dir =` line.
- Rendered CLAUDE.build.md has no bare `flex_build.py` reference (all
  invocations use absolute path).
- Rendered CLAUDE.build.md does not contain the literal string `harness` as a
  branch name.
- `record-attempt` alias exists and delegates correctly (or
  `record_attempt.py` path is absolute in the render).
