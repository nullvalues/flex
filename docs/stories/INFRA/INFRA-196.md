---
id: INFRA-196
rail: INFRA
title: scope_guard fail-closed protected-path list
status: draft
phase: "HARNESS011-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/scope_guard.py
touches:
  - hooks/pre_tool_use.py
---

## Ensures

- **CER-048 (partial)** — `scope_guard.py` has a `PROTECTED_GLOBS` constant containing
  the same glob patterns as the static deny entries in `.claude/settings.json`
  (`hooks/**`, `.claude-plugin/**`, `skills/seed/**`, `skills/companion/**`, `lessons/**`,
  `.claude/settings.json`).
- When `scope_guard.check()` is called with no active story (the fail-open path), it now
  checks whether the write target matches any glob in `PROTECTED_GLOBS`. If it matches,
  the write is blocked with a clear message explaining the path is protected and requires
  an active story that explicitly declares it in `primary_files`.
- When an active story IS present and the write target matches `PROTECTED_GLOBS`, the
  existing `primary_files` lookup proceeds unchanged — if the story declares the file, the
  write is allowed.
- The static deny entries in `.claude/settings.json` are NOT removed in this story
  (retirement is a post-fold story per DP1).
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

In `scope_guard.py`:

```python
import fnmatch

PROTECTED_GLOBS = [
    "hooks/**",
    ".claude-plugin/**",
    "skills/seed/**",
    "skills/companion/**",
    "lessons/**",
    ".claude/settings.json",
    ".claude/settings.local.json",
]

def _is_protected(path_str: str) -> bool:
    return any(fnmatch.fnmatch(path_str, g) for g in PROTECTED_GLOBS)
```

In the no-active-story branch of `check()` (the current fail-open path):
```python
if _is_protected(relative_path):
    return ScopeResult(allowed=False, reason=f"{relative_path} is a protected path — requires an active story with this file in primary_files")
```

The `relative_path` must be relative to `project_dir` for the glob match to work
correctly. Verify this is already the case in the existing function signature.

## Tests

No new test file required — add cases to the existing scope_guard test coverage:
- Write to `hooks/pre_tool_use.py` with no active story → blocked.
- Write to `hooks/pre_tool_use.py` with an active story that declares it → allowed.
- Write to `src/app.py` with no active story → allowed (not protected).
