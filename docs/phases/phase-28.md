# anchor — Phase 28: CER backlog remediation (LOW items)

← [Phase 27: Auth check per-story placement fix](phase-27.md)

## Goal

Close all six open Do Later CER items. All are LOW severity with bounded, single-file
fixes. CER-009 (hooks) touches protected files and uses opus for the builder.

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-057 | CER-019: sanitize project_name in pairmode_sync.py | complete |
| INFRA-058 | CER-016: effort_db.py resolve_effort_db_path containment guard | complete |
| INFRA-059 | CER-018: lesson.py CLI — add value_framing and validation_phase flags | complete |
| INFRA-060 | CER-004: lesson_review.py — Path.relative_to() containment | planned |
| INFRA-061 | CER-017: bootstrap.py — surface effort_tracking to user | planned |
| INFRA-062 | CER-009: hooks PIPE_PATH validation against tempdir | planned |

---

### Story INFRA-057 — CER-019: sanitize project_name in pairmode_sync.py

**Rail:** INFRA | **story_class:** code

**Acceptance criterion:** `_get_project_name` in `pairmode_sync.py` strips embedded
newline and carriage-return characters from the returned value before it is used in
template rendering, closing the YAML injection vector described in CER-019.

**Instructions:**

1. In `pairmode_sync.py`, `_get_project_name` currently returns `name.strip()` (line 62)
   or `project_dir.name` as fallback. `.strip()` removes leading/trailing whitespace
   but leaves embedded `\n`/`\r` in the middle of the string intact.

   Change the return path to strip embedded newlines:
   ```python
   # Before
   return name.strip()
   # After
   return name.strip().replace("\n", "").replace("\r", "")
   ```
   Apply the same sanitization to the `project_dir.name` fallback path if any
   newline characters could theoretically appear there (use the same pattern for
   consistency even though directory names cannot contain `/n` on Linux).

2. Mark CER-019 resolved in `docs/cer/backlog.md`.

**Tests:** `tests/pairmode/test_sync_agents.py` — add a test that `_get_project_name`
strips embedded newlines from `project_name` values in state (e.g., `"foo\nmodel: opus"`
→ `"foomodel: opus"`, not two lines).

---

### Story INFRA-058 — CER-016: effort_db.py resolve_effort_db_path containment guard

**Rail:** INFRA | **story_class:** code

**Acceptance criterion:** `resolve_effort_db_path` in `effort_db.py` applies a
`resolve().relative_to()` containment check on any `effort_db_path` value read from
`state.json`, consistent with the guard discipline applied in `permission_scope.py`.
A path that resolves outside `project_dir` falls back to the default
`<project_dir>/.companion/effort.db`.

**Instructions:**

1. In `effort_db.py`, `resolve_effort_db_path` (line 127), after resolving
   `configured_path` and applying `_depth_guard`, add a containment check:
   ```python
   try:
       configured_path.resolve().relative_to(project_dir.resolve())
   except ValueError:
       # Path escapes project_dir — use default
       return project_dir / ".companion" / "effort.db"
   ```
   The `_depth_guard` call already rejects shallow paths; this adds the stronger
   `relative_to` check that matches `permission_scope.py`'s discipline.

2. Mark CER-016 resolved in `docs/cer/backlog.md`.

**Tests:** `tests/pairmode/test_effort_db.py` — add tests:
- A configured path within `project_dir` is accepted and returned.
- A configured path that escapes `project_dir` (e.g. `../../etc/passwd`) falls back
  to the default `.companion/effort.db`.

---

### Story INFRA-059 — CER-018: lesson.py CLI value_framing and validation_phase flags

**Rail:** INFRA | **story_class:** code

**Acceptance criterion:** The `capture_lesson` function and its argparse/CLI entry
point in `lesson.py` accept `--value-framing TEXT` and `--validation-phase TEXT`
optional flags. When provided, these fields are included in the appended lesson entry.
When absent, the fields are omitted from the entry (consistent with how L001–L010
omit them). Closes CER-018.

**Instructions:**

1. Read `lesson.py` to understand the current `capture_lesson` signature and the
   argparse setup. The function builds a lesson dict and appends it to
   `lessons/lessons.json`.

2. Add `value_framing: str | None = None` and `validation_phase: str | None = None`
   parameters to `capture_lesson`. When non-None, include them in the lesson dict
   being appended.

3. Add `--value-framing` and `--validation-phase` optional arguments to the argparse
   definition, feeding into `capture_lesson`.

4. Mark CER-018 resolved in `docs/cer/backlog.md`.

**Tests:** `tests/pairmode/` — find or create a test file for `lesson.py`. Add tests:
- `--value-framing` and `--validation-phase` are written to the lesson entry when provided.
- When omitted, the fields are absent from the lesson entry (not written as null).

---

### Story INFRA-060 — CER-004: lesson_review.py Path.relative_to() containment

**Rail:** INFRA | **story_class:** code

**Acceptance criterion:** The path containment check in `lesson_review.py:149`
is replaced with a formal `Path.resolve().relative_to()` check, eliminating the
`str.startswith()` prefix-collision risk described in CER-004.

**Instructions:**

1. In `lesson_review.py:149`, the current check is:
   ```python
   if not str(template_path).startswith(str(templates_boundary)):
   ```
   Replace with:
   ```python
   try:
       template_path.resolve().relative_to(templates_boundary.resolve())
   except ValueError:
       raise ValueError(
           f"Template path {template_path} is outside templates directory"
       )
   ```
   Remove the old `if not str(...)` block and the raise inside it.

2. Mark CER-004 resolved in `docs/cer/backlog.md`.

**Tests:** `tests/pairmode/test_lesson_review.py` — add a test that a template path
outside the templates boundary raises `ValueError` (path traversal attempt).
Verify a valid template path within the boundary does not raise.

---

### Story INFRA-061 — CER-017: bootstrap.py surface effort_tracking to user

**Rail:** INFRA | **story_class:** code

**Acceptance criterion:** When `bootstrap.py`'s `_record_state` enables
`effort_tracking: true` in `state.json`, the bootstrap summary output includes a
one-line note informing the user. Closes CER-017.

**Instructions:**

1. In `bootstrap.py`, find where `_record_state` is called (line ~912) and where
   the bootstrap summary is printed to the user. After the summary, or within it,
   add a line:
   ```
   Effort tracking: enabled (records build token costs to .companion/effort.db)
   ```
   The note should only appear when `effort_tracking` was actually set (i.e., when
   it was absent from state.json before and was added). If `effort_tracking` was
   already present (user had set it manually), the note is suppressed.

2. The mechanism: `_record_state` sets the key only when absent. You can detect this
   by checking the return value of `_record_state` if it's convenient, or by reading
   the state before and after, or by having `_record_state` return a bool indicating
   whether it newly enabled tracking. Choose the least invasive approach.

3. Mark CER-017 resolved in `docs/cer/backlog.md`.

**Tests:** `tests/pairmode/test_bootstrap.py` — add tests:
- When state.json has no `effort_tracking` key, bootstrap output contains the
  transparency note.
- When state.json already has `effort_tracking: true`, the note is suppressed.

---

### Story INFRA-062 — CER-009: hooks PIPE_PATH validation against tempdir

**Rail:** INFRA | **story_class:** code
**Note:** Touches protected hook files — builder uses opus.

**Acceptance criterion:** `hooks/stop.py`, `hooks/post_tool_use.py`, and
`hooks/session_end.py` validate that a `pipe_path` value read from `state.json`
resolves under `tempfile.gettempdir()` before accepting it. An out-of-bounds path
falls back to the legacy default. Closes CER-009.

**Background:** `exit_plan_mode.py` already uses `tempfile.gettempdir()` correctly.
The three listed hooks use a hardcoded `"/tmp/companion.pipe"` fallback and accept
any string from state.json without validation.

**Instructions:**

1. In each of `hooks/stop.py`, `hooks/post_tool_use.py`, `hooks/session_end.py`,
   the current pattern is:
   ```python
   PIPE_PATH = "/tmp/companion.pipe"  # legacy fallback
   if _state.get("pipe_path"):
       PIPE_PATH = _state["pipe_path"]
   ```
   Replace with:
   ```python
   import tempfile
   PIPE_PATH = "/tmp/companion.pipe"  # legacy fallback
   if _state.get("pipe_path"):
       try:
           candidate = Path(_state["pipe_path"]).resolve()
           if candidate.is_relative_to(Path(tempfile.gettempdir()).resolve()):
               PIPE_PATH = str(candidate)
       except Exception:
           pass  # malformed path — keep legacy fallback
   ```
   `Path` is already imported in each hook. Add `import tempfile` where needed
   (check existing imports first).

2. Mark CER-009 resolved in `docs/cer/backlog.md`.

**Tests:** The hook scripts themselves are thin relays that write to a named pipe —
hard to unit-test directly. If `tests/pairmode/` already has hook tests, extend them.
If not, add `tests/pairmode/test_hooks.py` with tests that mock `_state` and verify:
- A valid path under `tempfile.gettempdir()` is accepted.
- A path outside `tempfile.gettempdir()` (e.g. `/etc/passwd`) falls back to the default.
- A malformed path string falls back to the default.
The test can call the path-validation logic directly (extract it to a helper function
in the hook if needed to make it testable without mocking os.open).

---

Tag: `cp28-cer-backlog-remediation`
