---
id: INFRA-138
rail: INFRA
title: "`scope_guard.py` — story file-scope enforcement module"
status: planned
phase: "55"
story_class: code
primary_files:
  - skills/pairmode/scripts/scope_guard.py
touches:
  - tests/pairmode/test_scope_guard.py
---

# INFRA-138 — `scope_guard.py` — story file-scope enforcement module

## Background

INFRA-137 generates `docs/phases/permissions/<STORY_ID>.json` for each story.
INFRA-139 extends `pre_tool_use.py` to intercept Edit/Write tool calls.
This story implements the module that sits between them: given a file path and a
project directory, `scope_guard.check_path` determines whether the current story
permits writes to that path.

The module is designed to fail open: when there is no active story, no permissions
file, or any unexpected error, it returns `(True, reason)` and allows the write.
Fail-closed would block all writes during non-story orchestrator work (spec mode,
checkpointing, etc.), which would break the workflow entirely.

The active story ID is read from `.companion/state.json` under the key
`current_story` — the same key `context_budget.py` already uses.

## Ensures

### `check_path` function

- Module: `skills/pairmode/scripts/scope_guard.py`
- Public API: `check_path(file_path: str | Path, project_dir: str | Path) -> tuple[bool, str]`
  - Returns `(True, reason)` when the write is allowed.
  - Returns `(False, reason)` when the write is outside declared story scope.
- The function is side-effect-free (read-only).

### Decision logic

1. Resolve `project_dir` to an absolute Path.
2. Read `<project_dir>/.companion/state.json`. On any error (missing, malformed),
   return `(True, "no state.json — allowing")`.
3. Extract `current_story` from state. If absent or empty,
   return `(True, "no active story — allowing")`.
4. Construct permissions file path:
   `<project_dir>/docs/phases/permissions/<current_story>.json`.
5. If the file does not exist, return `(True, "no permissions file for {story_id} — allowing")`.
6. Parse the JSON file. On decode error, return `(True, "malformed permissions file — allowing")`.
7. Extract `allowed_paths` list from the JSON. If absent or empty,
   return `(True, "empty allowed_paths — allowing")`.
8. Normalise `file_path`:
   - If absolute: compute relative path from `project_dir`; if it escapes the
     project directory, return `(False, "path escapes project root")`.
   - If relative: strip leading `./` and normalise separators.
9. Check if the normalised path is an exact string match against any entry in
   `allowed_paths`.
10. Return `(True, "allowed")` or
    `(False, "not in story scope for {story_id}: {normalised_path}")`.

### Allowed-path normalisation rules

- All paths in `allowed_paths` and the incoming `file_path` are normalised to
  POSIX-style relative strings (forward slashes, no leading `./`).
- Case-sensitive comparison (POSIX semantics).
- No glob expansion — exact string match only.

### Module structure

- No public state; no imports beyond stdlib and `pathlib`.
- `check_path` is the only public symbol.
- A `_read_state`, `_read_permissions`, and `_normalise_path` private helper
  pattern keeps the function readable; all helpers are internal.

## Out of scope

- Glob pattern matching in `allowed_paths`.
- Caching permissions files across calls.
- Windows path normalisation beyond what `pathlib` provides.

## Instructions

### 1. Create `skills/pairmode/scripts/scope_guard.py`

```python
"""
scope_guard.py — Story file-scope enforcement for the pre_tool_use hook.

check_path(file_path, project_dir) -> (allowed: bool, reason: str)

Fails open: when state, permissions file, or any read fails, returns (True, reason).
"""
from __future__ import annotations

import json
from pathlib import Path


def check_path(
    file_path: str | Path,
    project_dir: str | Path,
) -> tuple[bool, str]:
    project = Path(project_dir).resolve()

    story_id = _read_current_story(project)
    if not story_id:
        return True, "no active story — allowing"

    allowed_paths = _read_allowed_paths(project, story_id)
    if allowed_paths is None:
        return True, f"no permissions file for {story_id} — allowing"
    if not allowed_paths:
        return True, f"empty allowed_paths for {story_id} — allowing"

    normalised = _normalise(file_path, project)
    if normalised is None:
        return False, "path escapes project root"

    if normalised in allowed_paths:
        return True, "allowed"
    return False, f"not in story scope for {story_id}: {normalised}"


def _read_current_story(project: Path) -> str | None:
    try:
        state = json.loads((project / ".companion" / "state.json").read_text())
        val = state.get("current_story")
        return str(val).strip() if val else None
    except Exception:
        return None


def _read_allowed_paths(project: Path, story_id: str) -> list[str] | None:
    perm_path = project / "docs" / "phases" / "permissions" / f"{story_id}.json"
    if not perm_path.exists():
        return None
    try:
        data = json.loads(perm_path.read_text())
        paths = data.get("allowed_paths")
        return [_norm_str(p) for p in paths] if isinstance(paths, list) else []
    except Exception:
        return None  # malformed — fail open


def _normalise(file_path: str | Path, project: Path) -> str | None:
    p = Path(file_path)
    if p.is_absolute():
        try:
            return _norm_str(p.resolve().relative_to(project))
        except ValueError:
            return None
    return _norm_str(p)


def _norm_str(p: str | Path) -> str:
    s = Path(p).as_posix()
    return s.lstrip("./") if s.startswith("./") else s
```

### 2. No additional wiring required

`scope_guard.py` is a pure function module. INFRA-139 wires it into the hook.

## Tests

File: `tests/pairmode/test_scope_guard.py`

Use `tmp_path` to create a fake project tree with `.companion/state.json` and
`docs/phases/permissions/<STORY_ID>.json` as needed.

1. `test_scope_guard_allows_when_no_state_json`
   — no `.companion/state.json`; assert `(True, ...)`.

2. `test_scope_guard_allows_when_no_current_story_in_state`
   — state.json exists but has no `current_story` key; assert `(True, ...)`.

3. `test_scope_guard_allows_when_no_permissions_file`
   — state.json has `current_story: "INFRA-999"`; no permissions file;
   assert `(True, ...)` and reason contains "no permissions file".

4. `test_scope_guard_allows_declared_primary_file`
   — permissions file has `allowed_paths: ["skills/foo.py"]`;
   `check_path("skills/foo.py", ...)` → `(True, "allowed")`.

5. `test_scope_guard_blocks_undeclared_file`
   — permissions file does not include `"README.md"`;
   `check_path("README.md", ...)` → `(False, ...)` and reason contains "not in story scope".

6. `test_scope_guard_normalizes_absolute_path`
   — pass absolute path to a file that IS in `allowed_paths`;
   assert `(True, "allowed")`.

7. `test_scope_guard_normalizes_dotslash_prefix`
   — pass `"./skills/foo.py"` when `"skills/foo.py"` is in `allowed_paths`;
   assert `(True, "allowed")`.

8. `test_scope_guard_blocks_path_escaping_project_root`
   — pass `"/etc/passwd"` (or `"../../etc/passwd"`);
   assert `(False, ...)` and reason contains "escapes project root".

9. `test_scope_guard_allows_on_malformed_permissions_file`
   — permissions file contains invalid JSON; assert `(True, ...)` (fail open).

10. `test_scope_guard_empty_allowed_paths_allows`
    — permissions file has `"allowed_paths": []`; assert `(True, ...)`.
