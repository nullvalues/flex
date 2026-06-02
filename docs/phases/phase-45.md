---
era: "001"
---

# flex — Phase 45: Deterministic orchestrator offload

← [Phase 44: Fix `sync-agents` silent rendering failure](phase-44.md)

## Goal

The build loop orchestrator spends significant context on work that is purely
deterministic: finding the next unbuilt story, selecting models, parsing token
counts out of the `<usage>` block, and invoking guardrail checks. Each of these
tasks is re-derived by the LLM on every loop iteration, burning tokens and
growing the orchestrator's per-story context footprint.

This phase wraps the existing deterministic functions behind thin CLI entry
points so the orchestrator can call a script and read a result instead of
re-deriving logic from scratch each time. No existing logic is replaced or
rewritten — only CLI doors are added in front of what already works.

**Four stories:**

| ID | Title | Status |
|----|-------|--------|
| INFRA-116 | `next_story.py` — find next unbuilt story from phase file | complete |
| INFRA-117 | `model_selector.py --story-file` CLI mode | complete |
| INFRA-118 | Guardrail + context-health CLI subcommands | complete |
| INFRA-119 | `record_attempt.py --usage-block` parsing | complete |

**Story dependencies:** All four stories are independent and can be built in
any order. INFRA-117 and INFRA-118 both touch test files that already exist;
INFRA-116 and INFRA-119 create new test files.

---

## Stories

### Story INFRA-116 — `next_story.py`: find next unbuilt story from phase file

**Rail:** INFRA | **story_class:** code

#### Requires

- `skills/pairmode/scripts/story_resolver.py` exists with `_parse_stories_table`
  (returns list of story IDs from a Stories table) and `list_phase_stories`.
- The orchestrator currently resolves the next planned story by manually reading
  the phase `## Stories` table and scanning `git log` for `story-<ID>` commits.
- No `next_story.py` script exists.

#### Ensures

**`skills/pairmode/scripts/next_story.py`** (new file)

1. Executable as `uv run next_story.py <phase-file> [--json] [--project-dir DIR]`.

2. Reads the `## Stories` table from the given phase file using `_parse_stories_table`
   from `story_resolver.py`. Iterates stories in table order.

3. For each story, determines completion by checking whether a git commit
   matching the pattern `story-<STORY_ID>` (case-insensitive) exists in
   `git log --oneline` of the project directory. A commit match is authoritative
   over the table's status column (same rule the orchestrator uses today).

4. Returns the **first** story that: (a) has no matching git commit, AND (b) whose
   table status is not `deferred` or `skipped`. If the table says `complete` but no
   commit exists, the story is returned with `git_verified: true` — git's absence of
   a commit overrides the table's `complete` status.

5. Default (non-`--json`) output: prints two whitespace-separated tokens to
   stdout:
   ```
   <story_id> <resolved_story_file>
   ```
   where `<resolved_story_file>` is the path returned by `story_resolver.resolve_story`.
   If the story file cannot be resolved, prints `<story_id> UNRESOLVED`.

6. `--json` output: prints a single JSON object:
   ```json
   {"story_id": "RAIL-NNN", "story_file": "...", "git_verified": false}
   ```
   `git_verified` is `true` when the table status is `complete` but no matching
   commit exists (git's absence overrides the table's stated complete status).

7. Exit codes:
   - `0` — a next story was found and printed.
   - `1` — all stories in the phase are complete; prints `all stories complete`
     to stdout.
   - `2` — error (phase file not found, parse failure, etc.); prints message to
     stderr.

**`tests/pairmode/test_next_story.py`** (new file)

8. `test_finds_first_planned_story` — write a minimal phase file with two
   stories, both `planned` in the table; mock `git log` to return no matching
   commits; assert script outputs the first story's ID and file.

9. `test_skips_complete_story` — write a phase file with one `complete` story
   and one `planned` story; mock `git log` to return no commits; assert script
   outputs the second story.

10. `test_git_commit_overrides_table_status` — write a phase file with two
    stories: first is `planned` with a matching git commit (skip it); second is
    `complete` with no commit (return it with `git_verified: true`). Assert the
    second story is returned with exit 0 and `git_verified: true` in JSON mode.

11. `test_all_done_exits_1` — all stories complete; assert exit 1 and output
    `all stories complete`.

12. `test_missing_phase_file_exits_2` — pass a non-existent path; assert exit 2.

#### Instructions

1. Create `skills/pairmode/scripts/next_story.py`.
2. Import `_parse_stories_table` and `resolve_story` from `story_resolver`.
3. Use `subprocess.run(["git", "log", "--oneline"], capture_output=True, cwd=project_dir)`
   to get commit history; search each story ID with a case-insensitive substring
   match.
4. Add a `__main__` block with `click` (consistent with the rest of the pairmode script
   family): positional `phase_file`, optional `--json` flag, optional `--project-dir`
   (defaults to `Path(phase_file).parent.parent.parent` — the repo root relative to
   `docs/phases/`).
5. Create `tests/pairmode/test_next_story.py` with the tests above. Use
   `unittest.mock.patch` on `subprocess.run` to control `git log` output.

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_story.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

All new tests must pass. Full suite must pass.

---

### Story INFRA-117 — `model_selector.py --story-file` CLI mode

**Rail:** INFRA | **story_class:** code

#### Requires

- `skills/pairmode/scripts/model_selector.py` exists with `select_builder_model`,
  `select_reviewer_model`, `select_intent_reviewer_model`, `select_security_auditor_model`.
  Note: there is no `select_checkpoint_model` — the `checkpoint` role is omitted from
  the CLI (the two checkpoint-agent selectors cover intent-reviewer and security-auditor).
- The orchestrator currently invokes model selection via an inline `python -c`
  heredoc that hand-copies `story_class`, `primary_files`, `phase_id`, attempt
  number, and a hardcoded protected-files list into the script body each time.
- `model_selector.py` has no `__main__` / CLI entry point.

#### Ensures

**`skills/pairmode/scripts/model_selector.py`**

1. Gains a `__main__` block with an `argparse` CLI:
   ```
   model_selector.py --story-file PATH
                      --role {builder,reviewer,intent-reviewer,security-auditor}
                      [--attempt N]
                      [--project-dir DIR]
   ```
   `--role` defaults to `builder`. `--attempt` defaults to `1`.

2. Reads YAML frontmatter from the story file to extract:
   - `story_class` — passed to the relevant selection function.
   - `primary_files` — used by `select_builder_model` when checking for
     protected-file overlap.
   - `phase` — passed as `phase_id` to functions that accept it.

3. Calls the appropriate selection function:
   | `--role` | Function |
   |---|---|
   | `builder` | `select_builder_model` |
   | `reviewer` | `select_reviewer_model` |
   | `intent-reviewer` | `select_intent_reviewer_model` |
   | `security-auditor` | `select_security_auditor_model` |

4. Prints `model` on the first line of stdout. Prints `reason` on the second
   line. (Two-line output so the orchestrator can capture either with `head -1`
   or `tail -1`.)

5. Exit code `0` on success; `1` on missing story file or unparseable frontmatter.

6. No changes to any existing selection functions.

**`tests/pairmode/test_model_selector.py`** (must already exist — extend it)

7. `test_cli_builder_defaults` — write a minimal story file with
   `story_class: code`, `phase: "45"`, `primary_files: []`; invoke the CLI
   via `subprocess` or `argparse`; assert stdout first line is a valid model
   identifier string.

8. `test_cli_reviewer_role` — same story file, `--role reviewer`; assert
   output is a valid model string.

9. `test_cli_missing_story_file_exits_1` — pass a non-existent path; assert
   exit code 1.

#### Instructions

1. At the bottom of `model_selector.py`, add a `if __name__ == "__main__":` block.
2. Use `argparse` (not click — avoid adding a new dependency to this module).
3. For frontmatter parsing, use a simple regex or `yaml.safe_load` on the block
   between `---` delimiters; `pyyaml` is already available in the environment.
4. Add the three tests to the existing `tests/pairmode/test_model_selector.py`.

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_model_selector.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

All new tests must pass. Full suite must pass.

---

### Story INFRA-118 — Guardrail + context-health CLI subcommands

**Rail:** INFRA | **story_class:** code

#### Requires

- `skills/pairmode/scripts/effort_db.py` has `check_guardrail(db_path, *, story_id, rail, latest_tokens, ...)` at line ~315.
  The first parameter is `db_path: Path`; remaining parameters are keyword-only (after `*`).
- `skills/pairmode/scripts/context_health.py` has `check_context_health(...)`.
- The orchestrator currently invokes both via inline `python -c` heredocs that
  hand-copy `story_id`, `rail`, and token counts into the script body each time.
- Neither module has a `__main__` / CLI entry point.

#### Ensures

**`skills/pairmode/scripts/effort_db.py`**

1. Gains a `__main__` block with a multi-command CLI (use `argparse` subparsers):
   ```
   effort_db.py guardrail-check
       --story-id RAIL-NNN
       --rail RAIL
       --tokens N
       [--project-dir DIR]
   ```
   Resolves the effort DB path using `resolve_effort_db_path(project_dir)`.
   Calls `check_guardrail(db_path, story_id=..., rail=..., latest_tokens=...)`
   using keyword arguments (all params after `db_path` are keyword-only).
   Prints the `result["message"]` field to stdout when `result["fired"]` is True;
   otherwise prints nothing. Exits `0` in all cases (guardrail is informational only).

**`skills/pairmode/scripts/context_health.py`**

2. Gains a `__main__` block:
   ```
   context_health.py check
       --phase PHASE_ID
       [--project-dir DIR]
   ```
   Calls `resolve_effort_db_path(project_dir)` from `effort_db` to get the DB path,
   then calls `check_context_health(db_path=db_path, current_phase=phase_id)`.
   Actual signature: `check_context_health(db_path: Path, current_phase: str, lookback_phases: int = 10) -> dict`.
   Prints the `result["message"]` field to stdout.
   Exits `0` when `result["recommendation"]` is `"normal"` or `"insufficient_data"`;
   exits `1` when `result["recommendation"]` is `"elevated"` or `"high"`.

3. The exit-code semantics for `context_health.py check` must be documented
   in a one-line comment above the `__main__` block: `# exit 0 = healthy, 1 = unhealthy`.

**`tests/pairmode/test_effort_db.py`** (extend) and **`tests/pairmode/test_context_health.py`** (extend or create)

4. `test_guardrail_check_cli_no_warning` — mock `check_guardrail` to return
   `{"fired": False, "message": ""}`; invoke the CLI; assert exit 0 and empty stdout.

5. `test_guardrail_check_cli_with_warning` — mock `check_guardrail` to return
   `{"fired": True, "message": "effort guardrail: story exceeded 3x median"}`; invoke
   the CLI; assert exit 0 and stdout contains the warning message.

6. `test_context_health_cli_healthy` — mock `check_context_health` to return
   `{"recommendation": "normal", "message": "context health: normal"}`; invoke CLI;
   assert exit 0 and stdout contains the message.

7. `test_context_health_cli_unhealthy` — mock `check_context_health` to return
   `{"recommendation": "elevated", "message": "context health: elevated retry burden"}`; invoke CLI;
   assert exit 1 and stdout contains the message.

#### Instructions

1. Add `if __name__ == "__main__":` blocks to `effort_db.py` and `context_health.py`.
2. Use `argparse` with subparsers for `effort_db.py`; a single positional subcommand
   `check` for `context_health.py`.
3. In `context_health.py`'s `__main__`, import `resolve_effort_db_path` from `effort_db`
   (same `sys.path` pattern used by other sibling scripts) to obtain the DB path.
4. Add the tests to the relevant existing test files (create
   `tests/pairmode/test_context_health.py` if it does not exist).

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_effort_db.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_context_health.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

All new tests must pass. Full suite must pass.

---

### Story INFRA-119 — `record_attempt.py --usage-block` parsing

**Rail:** INFRA | **story_class:** code

#### Requires

- `skills/pairmode/scripts/record_attempt.py` already accepts: `--tokens-total`,
  `--tokens-in`, `--tokens-out`, `--cache-read-tokens`, `--cache-write-tokens`,
  `--tool-uses`, `--duration-ms`.
- The orchestrator currently hand-transcribes all seven values from the runtime
  `<usage>` XML block into individual CLI flags on every builder and reviewer
  spawn.
- `record_attempt.py` has no `--usage-block` option.

#### Ensures

**`skills/pairmode/scripts/record_attempt.py`**

1. Gains a `--usage-block` click option accepting a file path or `-` for stdin:
   ```
   --usage-block PATH   Parse <usage>…</usage> block from file or stdin (- for stdin).
   ```

2. When `--usage-block` is present, the script reads the source, extracts the
   content between `<usage>` and `</usage>` tags, and parses the following
   fields with simple line-by-line regex:
   - `total_tokens` → `--tokens-total`
   - `input_tokens` → `--tokens-in`
   - `output_tokens` → `--tokens-out`
   - `cache_read_tokens` → `--cache-read-tokens`
   - `cache_write_tokens` → `--cache-write-tokens`
   - `tool_uses` → `--tool-uses`
   - `duration_ms` → `--duration-ms`

3. An explicitly supplied numeric flag takes precedence over the parsed value.
   (Orchestrator can override a single field without re-parsing.)

4. When `--usage-block` is present, all seven numeric flags become optional.
   When `--usage-block` is absent, the existing validation behaviour is
   unchanged.

5. If the `<usage>` block is missing or malformed, the script prints a warning
   to stderr (`"warning: could not parse usage block: {reason}"`) and continues
   with whatever numeric flags were supplied explicitly.

**`tests/pairmode/test_record_attempt.py`** (extend)

6. `test_usage_block_from_string` — write a temp file containing a synthetic
   `<usage>` block with known values; invoke `record_attempt` via `CliRunner`
   with `--usage-block <tmpfile>`; assert the attempt row written to the DB
   has the correct token counts.

7. `test_explicit_flag_overrides_usage_block` — same setup, but also pass
   `--tokens-total 999`; assert the stored value is `999` not the value from
   the block.

8. `test_usage_block_missing_graceful` — pass `--usage-block` pointing to a
   file with no `<usage>` tags; assert exit 0 (warning only, not failure).

#### Instructions

1. Add a `--usage-block` option to the `@click.command()` in `record_attempt.py`
   before the existing `record_attempt` function signature.
2. At the top of the function body, if `usage_block` is set, open and parse it;
   populate local variables that are then used wherever the explicit flags would
   have been — do not mutate click's parameter objects, just use local fallback
   variables.
3. Use `re.search(r"<(\w+?)>\s*(\d+)\s*</\1>", line)` or equivalent to parse
   each field by tag name.
4. Add the three tests to `tests/pairmode/test_record_attempt.py`.

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_record_attempt.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

All new tests must pass. Full suite must pass.

---

Tag: `cp45-deterministic-orchestrator-offload`
