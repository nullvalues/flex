---
id: BUILD-022
rail: BUILD
title: "Durable per-story attempt counter via `flex_build.py` + orchestrator instructions"
status: complete
phase: "53"
story_class: code
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - tests/pairmode/test_flex_build_attempt_counter.py
---

# BUILD-022 — Durable per-story attempt counter via `flex_build.py` + orchestrator instructions

## Background

`CLAUDE.build.md` Step 1 instructs the orchestrator to maintain a per-story
attempt counter:

> `--attempt-number` is `1` on the first attempt and incremented on each
> retry — the orchestrator must remember the per-story attempt counter across
> builder spawns.

Phase 52's lean-orchestrator change made `/clear` part of the normal build
loop: the inline `/context` gate (BUILD-014) tells the user to `/clear` then
resume mid-phase. When this happens the orchestrator's in-context attempt
counter is lost. After a `/clear`, attempt 2 of a story is recorded as
attempt 1 in `effort.db`, polluting the model-selection signal
(`select_reviewer_model` and `select_builder_model` both read
`attempt_number`) and breaking the FAIL-loop's retry-vs-loop-breaker branch.

Cold-eyes finding **H4**: the durable counter needs a tiny JSON file the
orchestrator reads at loop-iteration start and writes after each builder
return. The shape is one story-id + count; the file lives in `.companion/`
which is already gitignored.

`flex_build.py` is the natural home for these helpers — three subcommands
that read, write, and clear the counter file. The orchestrator template
instructs when to call each.

## Ensures

- `flex_build.py` gains a `write-attempt-count` subcommand with options
  `--story-id RAIL-NNN`, `--count N` (int), and `--project-dir DIR`. It
  writes `{"story_id": "RAIL-NNN", "attempt_count": N}` to
  `<project-dir>/.companion/attempt_counter.json`, creating `.companion/` if
  absent. Prints nothing on success.
- `flex_build.py` gains a `read-attempt-count` subcommand with options
  `--story-id RAIL-NNN` and `--project-dir DIR`. It reads
  `.companion/attempt_counter.json` and prints `N` (the integer
  `attempt_count`) on stdout when the file exists and `story_id` matches.
  When the file is absent, malformed, or `story_id` does not match, it
  prints `0` and exits 0.
- `flex_build.py` gains a `clear-attempt-count` subcommand with option
  `--project-dir DIR`. It deletes `.companion/attempt_counter.json` if
  present; silently no-ops if absent. Exits 0.
- All three subcommands apply the same `_depth_guard` pattern already used
  by existing commands.
- `.companion/attempt_counter.json` is covered by the existing `.companion/`
  rule in `.gitignore`; no `.gitignore` edit needed.
- `CLAUDE.build.md` Step 1 — at the start of "Spawn the builder", before the
  pre-authorize block — adds a "Restore attempt counter" step that calls
  `read-attempt-count` and uses the result as the starting `attempt_number`
  (treat `0` as attempt `1` — fresh story).
- `CLAUDE.build.md` Step 1 — after `record_attempt.py` and before Step 1.5 —
  adds a "Persist attempt counter" call to `write-attempt-count` with the
  current attempt number.
- `CLAUDE.build.md` Step 3 — under "If reviewer reports PASS (committed)",
  after `story_update.py --status complete` — adds a `clear-attempt-count`
  call.
- `CLAUDE.build.md` Step 3 — under "Attempt 1 FAIL — auto-retry" and
  "Attempt 2 FAIL — auto loop-breaker" — adds a `write-attempt-count` call
  after incrementing the counter.
- `skills/pairmode/templates/CLAUDE.build.md.j2` mirrors all
  `CLAUDE.build.md` edits, using `{{ pairmode_scripts_dir }}/flex_build.py`
  for the script path.

## Out of scope

- Migrating the counter to `state.json` (dedicated file decouples lifecycle).
- Reading the counter inside `record_attempt.py`.
- Adding a CLI to inspect or edit the counter beyond read/write/clear.
- Effort-cost estimation surfaces (INFRA-135).

## Instructions

### 1. Add three `flex_build.py` subcommands

In `skills/pairmode/scripts/flex_build.py`, add after the existing commands:

```python
# ---------------------------------------------------------------------------
# Per-story attempt counter (BUILD-022)
# ---------------------------------------------------------------------------


def _attempt_counter_path(project_dir: Path) -> Path:
    return project_dir / ".companion" / "attempt_counter.json"


@flex_build.command("write-attempt-count")
@click.option("--story-id", required=True, help="Story ID (e.g. BUILD-022).")
@click.option("--count", required=True, type=int, help="Attempt count (>=1).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_write_attempt_count(story_id: str, count: int, project_dir: str) -> None:
    """Persist the per-story attempt counter to .companion/attempt_counter.json."""
    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    path = _attempt_counter_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"story_id": story_id, "attempt_count": count}),
        encoding="utf-8",
    )


@flex_build.command("read-attempt-count")
@click.option("--story-id", required=True, help="Story ID (e.g. BUILD-022).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_read_attempt_count(story_id: str, project_dir: str) -> None:
    """Print the persisted attempt count for *story_id* (0 if absent/mismatched)."""
    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    path = _attempt_counter_path(project_path)
    if not path.exists():
        click.echo("0")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        click.echo("0")
        return
    if data.get("story_id") != story_id:
        click.echo("0")
        return
    try:
        click.echo(str(int(data.get("attempt_count", 0))))
    except (TypeError, ValueError):
        click.echo("0")


@flex_build.command("clear-attempt-count")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_clear_attempt_count(project_dir: str) -> None:
    """Delete .companion/attempt_counter.json if present."""
    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    path = _attempt_counter_path(project_path)
    if path.exists():
        path.unlink()
```

Note: `json` is already imported in `flex_build.py` — confirm before adding
an extra import statement.

### 2. Wire the counter into the build loop in `CLAUDE.build.md`

In Step 1 ("Spawn the builder"), before the "pre-authorize edits" block, add:

> **Restore attempt counter.** Read any persisted attempt count before
> spawning the builder:
>
> ```bash
> PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
>   read-attempt-count --story-id RAIL-NNN --project-dir .
> ```
>
> Use the printed integer as the starting attempt number. If it prints `0`,
> this is a fresh story and the attempt number is `1`.

After the `record_attempt.py` call and before Step 1.5, add:

> **Persist attempt counter.** Write the current attempt number to disk so
> a `/clear` mid-phase preserves it:
>
> ```bash
> PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
>   write-attempt-count --story-id RAIL-NNN --count [current attempt] --project-dir .
> ```

In Step 3, under "**If reviewer reports PASS (committed)**", after
`story_update.py --status complete`, add:

> ```bash
> PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
>   clear-attempt-count --project-dir .
> ```

In Step 3, under "**Attempt 1 FAIL — auto-retry:**", after "Increment the
per-story attempt counter to 2.", add a `write-attempt-count --count 2` call.

In Step 3, under "**Attempt 2 FAIL — auto loop-breaker:**", before spawning
the loop-breaker, add a `write-attempt-count --count 3` call.

### 3. Mirror in `CLAUDE.build.md.j2`

Apply the same step-2 edits to `skills/pairmode/templates/CLAUDE.build.md.j2`,
replacing the absolute script path with `{{ pairmode_scripts_dir }}/flex_build.py`.

### 4. Confirm gitignore coverage

Confirm `.companion/` is already listed in `.gitignore`. No edit needed.

## Tests

`tests/pairmode/test_flex_build_attempt_counter.py` (new):

1. `test_write_attempt_count_creates_file_with_expected_shape` — write
   count=2 for story BUILD-022; assert file exists and parses to
   `{"story_id": "BUILD-022", "attempt_count": 2}`.
2. `test_write_attempt_count_creates_companion_dir` — invoke against tmp
   dir with no `.companion/`; assert parent created and file written.
3. `test_write_attempt_count_overwrites_existing_file` — write count=1
   then count=3; assert file reads `attempt_count: 3`.
4. `test_read_attempt_count_returns_persisted_value` — write count=2,
   read for same story; assert stdout is `2` and exit 0.
5. `test_read_attempt_count_missing_file_returns_zero` — no counter file;
   assert stdout is `0` and exit 0.
6. `test_read_attempt_count_mismatched_story_returns_zero` — write for
   BUILD-022, read for INFRA-135; assert stdout is `0` and exit 0.
7. `test_read_attempt_count_malformed_file_returns_zero` — write non-JSON
   garbage to counter file; assert stdout is `0` and exit 0.
8. `test_clear_attempt_count_removes_file` — write counter, then clear;
   assert file no longer exists and exit 0.
9. `test_clear_attempt_count_missing_file_noop` — no counter file; assert
   exit 0 (silent no-op).
10. `test_attempt_counter_path_is_gitignored` — write counter file, invoke
    `git check-ignore -q .companion/attempt_counter.json`; assert exit 0.
11. `test_write_attempt_count_depth_guard` — shallow `--project-dir`; assert
    non-zero exit.

Follow the pattern in `tests/pairmode/test_flex_build_current_phase.py` for
subprocess invocation, `PYTHONPATH` setup, and tmp-project scaffolding.
