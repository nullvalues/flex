# flex — Phase 38: Data quality and portability cleanup

← [Phase 37: Builder model-selection tuning + token-direction recording](phase-37.md)

## Goal

Three small cleanup items surfaced from the Phase 37 era: two from the CER backlog
(CER-022, CER-023) and one from the effort-DB analysis (outcome case normalisation).

1. **CER-022 — sync-agents depth guard gap.** `pairmode_sync.py` `sync_agents` handler
   calls `Path(project_dir).resolve()` but has no depth check, unlike `sync_build` which
   calls `_depth_guard_sync_build`. A caller passing `--project-dir /` is silently accepted.
   Fix: call `_depth_guard_sync_build(project_path)` at the top of the `sync_agents` handler.

2. **CER-023 — PostToolUse hook hardcoded absolute path.** `.claude/settings.json` PostToolUse
   hook contains `cd /mnt/work/flex`, making it non-portable across developer machines.
   The hook already reads `INPUT=$(cat)` and the payload includes a `cwd` field (confirmed
   in `hooks/post_tool_use.py:69`). Fix: replace the hardcoded `cd` with a `cwd`-derived
   path: `PROJECT_DIR=$(echo "$INPUT" | jq -re '.cwd // "."``) && cd "$PROJECT_DIR"`.

3. **Outcome case normalisation.** `record_attempt.py` stores the `--outcome` value verbatim.
   Two rows in cora were recorded as `pass` (lowercase) instead of `PASS`, excluding them
   from pass-rate aggregations that filter `outcome = 'PASS'`. Fix: normalise to uppercase
   before inserting.

**Story dependencies:** All three are independent.

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-100 | Fix `sync_agents` depth guard gap (CER-022) | planned |
| INFRA-101 | Fix PostToolUse hook hardcoded path (CER-023) | planned |
| INFRA-102 | Normalise outcome case in `record_attempt.py` | planned |

---

### Story INFRA-100 — Fix `sync_agents` depth guard gap

**Rail:** INFRA | **story_class:** code

#### Requires

- `pairmode_sync.py` `sync_agents` starts at line 430 and calls `Path(project_dir).resolve()`
  at line 441 but does not call `_depth_guard_sync_build` before proceeding.
- `_depth_guard_sync_build(project_dir: Path)` exists at line 306 and raises `SystemExit(1)`
  when `len(project_dir.parts) < 3`.
- `sync_build` handler calls `_depth_guard_sync_build` (line 515 of pairmode_sync.py).

#### Ensures

`sync_agents` calls `_depth_guard_sync_build(project_path)` immediately after resolving
`project_path` (before `_load_state`), matching the guard discipline of `sync_build`.

`tests/pairmode/test_pairmode_sync.py` gains a test that calls `sync_agents` with
`--project-dir /tmp` (two components) and asserts it exits with code 1.

#### Instructions

**`skills/pairmode/scripts/pairmode_sync.py`**

In `sync_agents`, after line 441 (`project_path = Path(project_dir).resolve()`), add:

```python
    _depth_guard_sync_build(project_path)
```

This is the only code change.

**`tests/pairmode/test_pairmode_sync.py`**

Add a test in the `sync-agents` test class (or create one):

```python
def test_sync_agents_rejects_shallow_path(tmp_path):
    from click.testing import CliRunner
    runner = CliRunner()
    # /tmp has only 1 component — should be rejected
    result = runner.invoke(sync_agents, ["--project-dir", "/tmp"])
    assert result.exit_code == 1
```

Import `sync_agents` from `pairmode_sync` at the top of the test file if not already imported.

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_pairmode_sync.py -x -q -k "shallow"
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

---

### Story INFRA-101 — Fix PostToolUse hook hardcoded path

**Rail:** INFRA | **story_class:** code

#### Requires

- `.claude/settings.json` PostToolUse hook command contains `cd /mnt/work/flex`.
- The PostToolUse JSON payload includes a `cwd` field (confirmed in `hooks/post_tool_use.py:69`).
- `jq` is available in the hook execution environment (already used in the same command via
  `jq -re '.tool_input.file_path // ""'`).

#### Ensures

`.claude/settings.json` PostToolUse hook command no longer contains any hardcoded absolute path.
The `cd` target is derived from the hook payload's `cwd` field:

```
INPUT=$(cat); echo "$INPUT" | jq -re '.tool_input.file_path // ""' | grep -q '\.py$' && PROJECT_DIR=$(echo "$INPUT" | jq -re '.cwd // "."``) && cd "$PROJECT_DIR" && PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q 2>&1 | tail -20 || true
```

The functional behaviour (run tests when a .py file is edited) is unchanged.

#### Instructions

**`.claude/settings.json`**

Replace the `command` value in the PostToolUse hook (the `Edit|Write` matcher) with:

```
INPUT=$(cat); echo \"$INPUT\" | jq -re '.tool_input.file_path // \"\"' | grep -q '\\.py$' && PROJECT_DIR=$(echo \"$INPUT\" | jq -re '.cwd // \".\"') && cd \"$PROJECT_DIR\" && PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q 2>&1 | tail -20 || true
```

Note: JSON requires `\"` for embedded double quotes. The resulting JSON string value must be
valid JSON — double-check with `python3 -m json.tool .claude/settings.json` after editing.

#### Tests

This story modifies only `.claude/settings.json`. No Python test file is expected.

The reviewer verifies:
1. `.claude/settings.json` is valid JSON (`python3 -m json.tool .claude/settings.json` exits 0).
2. The PostToolUse hook command string does NOT contain `/mnt/work/flex`.
3. The command string DOES contain `.cwd`.

`TEST RUN: configuration story — no test file expected`

---

### Story INFRA-102 — Normalise outcome case in `record_attempt.py`

**Rail:** INFRA | **story_class:** code

#### Requires

- `record_attempt.py` passes `outcome=outcome` verbatim to `_effort_db.insert_attempt`
  at line 237.
- Two historical rows in cora have `outcome = 'pass'` (lowercase), excluded from
  `outcome = 'PASS'` pass-rate queries.

#### Ensures

`record_attempt.py` normalises `outcome` to uppercase before the DB insert:
`outcome = outcome.upper() if outcome is not None else None`

This change is applied once, before `insert_attempt` is called.

`tests/pairmode/test_record_attempt.py` (create if absent) gains tests asserting:
- `outcome = 'pass'` is stored as `'PASS'`
- `outcome = 'FAIL'` remains `'FAIL'`
- `outcome = None` remains `None` (no-op guard)

#### Instructions

**`skills/pairmode/scripts/record_attempt.py`**

In `record_attempt`, before the `_effort_db.insert_attempt(...)` call (line ~222),
add the normalisation:

```python
    # Normalise outcome to uppercase (prevents 'pass'/'fail' case drift).
    if outcome is not None:
        outcome = outcome.upper()
```

No other changes to `record_attempt.py`.

**`tests/pairmode/test_record_attempt.py`**

If this file does not exist, create it. Add:

```python
import pytest
from click.testing import CliRunner
from pathlib import Path
import json
import sqlite3

from record_attempt import record_attempt as _cmd


def _make_project(tmp_path: Path) -> Path:
    """Scaffold a minimal project dir with effort tracking enabled."""
    companion = tmp_path / ".companion"
    companion.mkdir()
    state = {
        "effort_tracking": True,
        "effort_db_path": ".companion/effort.db",
    }
    (companion / "state.json").write_text(json.dumps(state))
    return tmp_path


def _make_story(tmp_path: Path, story_id: str = "INFRA-001") -> Path:
    story_dir = tmp_path / "docs" / "stories" / "INFRA"
    story_dir.mkdir(parents=True)
    story_file = story_dir / f"{story_id}.md"
    story_file.write_text(
        f"---\nid: {story_id}\nphase: '38'\nrail: INFRA\nstory_class: code\n---\n\n# Story\n"
    )
    return story_file


class TestOutcomeNormalisation:
    def test_lowercase_pass_stored_as_uppercase(self, tmp_path):
        project = _make_project(tmp_path)
        story = _make_story(project)
        runner = CliRunner()
        result = runner.invoke(
            _cmd,
            [
                "--story-file", str(story),
                "--agent-role", "builder",
                "--outcome", "pass",
                "--project-dir", str(project),
            ],
        )
        assert result.exit_code == 0, result.output
        db = project / ".companion" / "effort.db"
        conn = sqlite3.connect(db)
        row = conn.execute("SELECT outcome FROM attempts WHERE story_id = 'INFRA-001'").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "PASS"

    def test_uppercase_fail_unchanged(self, tmp_path):
        project = _make_project(tmp_path)
        story = _make_story(project, "INFRA-002")
        runner = CliRunner()
        result = runner.invoke(
            _cmd,
            [
                "--story-file", str(story),
                "--agent-role", "reviewer",
                "--outcome", "FAIL",
                "--project-dir", str(project),
            ],
        )
        assert result.exit_code == 0
        db = project / ".companion" / "effort.db"
        conn = sqlite3.connect(db)
        row = conn.execute("SELECT outcome FROM attempts WHERE story_id = 'INFRA-002'").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "FAIL"

    def test_none_outcome_no_crash(self, tmp_path):
        project = _make_project(tmp_path)
        story = _make_story(project, "INFRA-003")
        runner = CliRunner()
        result = runner.invoke(
            _cmd,
            [
                "--story-file", str(story),
                "--agent-role", "builder",
                "--project-dir", str(project),
            ],
        )
        assert result.exit_code == 0
```

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_record_attempt.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

---

Tag: `cp38-data-quality-portability`
