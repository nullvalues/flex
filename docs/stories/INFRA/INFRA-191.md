---
id: INFRA-191
rail: INFRA
title: "Orchestrator integration of spec_preflight via flex_build.py spec-preflight subcommand"
status: planned
phase: "84"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - tests/pairmode/test_flex_build.py
  - docs/architecture.md
---

## Requires

- INFRA-190 has landed: `skills/pairmode/scripts/spec_preflight.py` exists and exports `run_preflight(story_path: Path, project_dir: Path) -> list[str]`.
- `flex_build.py` follows the click group pattern with all subcommands registered on the `flex_build` group.
- `skills/pairmode/templates/CLAUDE.build.md.j2` has a pre-story gate sequence including `check-schema-gate`, `check-stub`, and `check-story-scope` sections.

## Ensures

- `grep -n "spec.preflight\|spec_preflight" skills/pairmode/scripts/flex_build.py` returns at least one match for a subcommand registration and at least one match for a `run_preflight` or `spec_preflight` import/call.
- `PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/flex_build.py spec-preflight --help` exits 0 and output contains `"--story-id"` and `"--project-dir"`.
- `PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/flex_build.py spec-preflight --story-id INFRA-191 --project-dir .` exits 0.
- `grep -n "spec.preflight\|SPEC PREFLIGHT" skills/pairmode/templates/CLAUDE.build.md.j2` returns at least one match.
- In `CLAUDE.build.md.j2`, the spec-preflight block appears after `check-stub` and before `check-story-scope` by line number order.
- The template instructs: if preflight output is non-empty, display a `SPEC PREFLIGHT — Story RAIL-NNN` header, the warnings verbatim, and `"These are informational. Review before proceeding."`; if empty, print nothing.
- `grep -n "spec_preflight" docs/architecture.md` returns at least one match.
- At least two tests for `spec-preflight` exist in `tests/pairmode/test_flex_build.py`.

## Instructions

**1. Add `spec-preflight` subcommand to `flex_build.py`.**

Import `spec_preflight` lazily inside the command function to avoid circular imports at module load:

```python
@flex_build.command("spec-preflight")
@click.option("--story-id", required=True, help="Story ID (e.g. INFRA-190).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_spec_preflight(story_id: str, project_dir: str) -> None:
    """Scan a story's body sections for unverifiable routes and constants.

    Always exits 0. Non-empty output = informational warnings.
    """
    import spec_preflight as _sp  # noqa: PLC0415

    project_path = Path(project_dir).resolve()
    story_path = _story_path(story_id, project_path)

    if not story_path.exists():
        click.echo(f"spec-preflight: story file not found: {story_path}", err=True)
        sys.exit(0)

    for w in _sp.run_preflight(story_path, project_path):
        click.echo(w)
```

Place this command after the existing `check-story-scope` command (around line 1090) and before `transition-era`.

**2. Update `skills/pairmode/templates/CLAUDE.build.md.j2` — insert spec-preflight step.**

Locate the pre-story gate sequence. Current order: schema gate → auth gate → stub gate → scope check. Insert the spec-preflight step between the stub gate and the scope check:

```markdown
### Spec preflight

Run once per story, after the stub gate, before the scope check.

  preflight_output=$(PATH=$HOME/.local/bin:$PATH uv run python {{ pairmode_scripts_dir }}/flex_build.py \
    spec-preflight --story-id RAIL-NNN --project-dir .)

Replace `RAIL-NNN` with the current story ID.

If `preflight_output` is non-empty, surface it to the developer:

  SPEC PREFLIGHT — Story RAIL-NNN

  [preflight_output verbatim]

  These are informational. Review before proceeding.

If `preflight_output` is empty, print nothing and continue silently.

The check does not block. Continue to the Pre-story scope check regardless of output.
```

**3. Update `docs/architecture.md`.**

In the Module structure scripts table (under `skills/pairmode/scripts/`), add a line for `spec_preflight.py`:

```
        spec_preflight.py         ← INFRA-190/191 — scans story body sections for unverifiable route and constant references; informational only (always exits 0)
```

Insert alphabetically near `scope_guard.py` and `session_reset.py`.

## Tests

Add to `tests/pairmode/test_flex_build.py`:

- `test_spec_preflight_subcommand_exits_0_with_clean_story(tmp_path)` — create a minimal story file with no route/constant references; run `spec-preflight` via CliRunner; assert exit code 0 and empty stdout.
- `test_spec_preflight_subcommand_missing_story_exits_0(tmp_path)` — run `spec-preflight --story-id INFRA-999` where no story exists; assert exit code 0.
- `test_spec_preflight_subcommand_help_shows_story_id_flag()` — run `spec-preflight --help`; assert `"--story-id"` in output.
- `test_build_template_contains_spec_preflight_step()` — read `skills/pairmode/templates/CLAUDE.build.md.j2`; assert `"spec-preflight"` present; assert `"SPEC PREFLIGHT"` present; assert line number of `"spec-preflight"` is between line numbers of `"check-stub"` and `"check-story-scope"`.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_build.py -x -q -k "spec_preflight"
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```
