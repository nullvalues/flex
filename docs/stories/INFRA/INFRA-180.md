---
id: INFRA-180
rail: INFRA
title: "Replace context_current_tokens scalar with per-story-ID dict; add session-boundary staleness gate"
status: complete
phase: "73"
story_class: code
primary_files:
  - skills/pairmode/scripts/context_budget.py
  - skills/pairmode/scripts/flex_build.py
  - tests/pairmode/test_context_budget.py
  - tests/pairmode/test_flex_build_set_context_tokens.py
touches:
  - hooks/pre_tool_use.py
  - hooks/session_start.py
  - skills/pairmode/scripts/session_reset.py
---

# INFRA-180 — Replace `context_current_tokens` scalar with per-story-ID dict

**Phase:** 73
**Rail:** INFRA

## Background

`state["context_current_tokens"]` is a single mutable scalar overwritten on every
`set-context-tokens` call. It has two reliability gaps:

1. **No story binding.** The hook has no way to detect whether the recorded value was
   for the current story or a previous one. If the orchestrator drifts (skips the
   `/context` call, reads a cached value, or advances the story ID without re-recording),
   the hook enforces against the wrong number.

2. **SessionStart reset is lossy.** The scalar is overwritten to 25k on every
   `clear`/`startup` event, erasing the pre-clear value and removing the ability to
   distinguish a reset from a fresh recording.

**Design:** Replace the scalar with `state["context_story_tokens"]`, a dict keyed by
story ID. Each entry stores the token count and the timestamp it was recorded. The hook
validates both: the key must exist for the current story AND the entry must post-date
the most recent session reset (`context_session_reset_at`). Missing or stale → block
with CONTEXT CHECK REQUIRED. The history of all stories within the session remains
visible in state.json.

## Protected-file modification statements

- `hooks/pre_tool_use.py`: remove the `read_current_tokens` call and `live_tokens`
  path (JSONL, from Phase 72); simplify the Task/Agent branch back to a single
  `context_budget.decide()` call. The state.json write of
  `context_current_tokens` / `context_current_tokens_recorded_at` is removed from the
  hook — that write now belongs solely to `flex_build.py set-context-tokens`.
  The `context_budget_acknowledged_at` write on block remains. The merged
  `write_text()` call reduces to writing only `context_budget_acknowledged_at` when
  blocking.
- `hooks/session_start.py`: on `clear` or `startup`, write
  `context_session_reset_at` to state.json (UTC ISO-8601) in addition to the existing
  `context_current_tokens` + `context_current_tokens_recorded_at` writes.
  (`context_current_tokens` writes are kept for now as a backwards-compatible display
  value; INFRA-181 removes them when the Context gate is restored to `/context`-based.)

## Acceptance criteria

### `state.json` schema additions

| Key | Type | Writer | Purpose |
|-----|------|--------|---------|
| `context_story_tokens` | `dict[str, {"tokens": int, "recorded_at": str}]` | `set-context-tokens` | Per-story token count history |
| `context_session_reset_at` | `str` (UTC ISO-8601) | `session_start.py` | Boundary timestamp; entries older than this are stale |

### `skills/pairmode/scripts/context_budget.py`

#### 1. New private function: `read_story_token_entry`

```python
def _read_story_token_entry(
    state: dict,
    story_id: str,
) -> dict | None:
```

- Returns `state["context_story_tokens"][story_id]` if present and correctly shaped
  (`{"tokens": int, "recorded_at": str}`).
- Returns `None` if: `context_story_tokens` absent, `story_id` absent in dict,
  entry malformed, or any exception. Never raises.

#### 2. New private function: `_is_entry_fresh`

```python
def _is_entry_fresh(
    entry: dict,
    state: dict,
    _now: datetime | None = None,
) -> bool:
```

- Returns `False` if `context_session_reset_at` is present in state AND
  `entry["recorded_at"]` (parsed as UTC ISO-8601) is **not after**
  `context_session_reset_at`.
- Returns `True` if `context_session_reset_at` is absent (no reset recorded yet) OR
  `entry["recorded_at"]` is after the reset timestamp.
- Returns `True` if either timestamp is unparseable (fail-open for backwards compat).
- `_now` is unused but accepted for signature symmetry with other helpers.

#### 3. Modified function: `read_context_tokens_from_state`

Add a new primary read path **before** the existing scalar read:

```python
def read_context_tokens_from_state(state: dict, story_id: str = "") -> int | None:
```

Logic:
1. If `story_id` is non-empty:
   a. Call `_read_story_token_entry(state, story_id)`.
   b. If entry found and `_is_entry_fresh(entry, state)` is True: return `entry["tokens"]`.
   c. If entry found but stale: return `None` (stale = treat as absent).
   d. If entry not found: return `None`.
2. Fall back to existing scalar read (`state.get("context_current_tokens")` with TTL
   check) when `story_id` is empty. This path is used by tests that do not yet pass a
   story ID and by callers in non-pairmode projects.

#### 4. Modified function: `decide`

Signature change — replace `session_id` parameter (added in Phase 72, removed here)
with `story_id`:

```python
def decide(
    project_dir: Path,
    story_id: str = "",
    flex_factor: float = 1.0,
) -> dict | None:
```

Internal change: pass `story_id` to `read_context_tokens_from_state`. The JSONL
waterfall added in Phase 72 is removed entirely — `read_context_tokens_from_state`
is the sole token source.

**Return contract (unchanged):**

| Condition | Return |
|-----------|--------|
| `state.json` absent (non-pairmode) | `None` |
| Under budget OR within reprompt margin | `None` |
| Over budget | `{"block": True, "reason": ..., "tokens": N, "acknowledged_at": N}` |
| No count from story dict or scalar fallback | `{"block": True, "reason": CONTEXT_CHECK_REQUIRED, ...}` |

#### 5. Updated `_CONTEXT_CHECK_REQUIRED_MSG`

```python
_CONTEXT_CHECK_REQUIRED_MSG = (
    "CONTEXT CHECK REQUIRED\n"
    "No token count has been recorded for the current story in this session.\n"
    "Call /context and run:\n"
    f"  PATH=$HOME/.local/bin:$PATH uv run python {_FLEX_BUILD_PATH} \\\n"
    "    set-context-tokens --tokens N --project-dir .\n"
    "Replace N with the integer token count from /context.\n"
)
```

---

### `skills/pairmode/scripts/flex_build.py` — `cmd_set_context_tokens`

In addition to writing `context_current_tokens` and
`context_current_tokens_recorded_at` (kept for backwards compat / display):

1. Read `state.get("current_story", {}).get("id", "")` to get the active story ID.
2. If story ID is non-empty, write to `context_story_tokens`:
   ```python
   state.setdefault("context_story_tokens", {})[story_id] = {
       "tokens": tokens,
       "recorded_at": datetime.now(timezone.utc).isoformat(),
   }
   ```
3. If story ID is empty, skip the dict write (no active story — standalone invocation
   or non-pairmode context). Emit a note to stderr: `"no active story; dict entry not written"`.
4. Write state.json atomically (use `write_text` as before; atomic write is CER-050
   and out of scope here).

---

### `hooks/pre_tool_use.py`

**Stated reason for modification:** remove Phase 72 JSONL additions; pass `story_id`
instead of `session_id`; simplify state write to acknowledged_at only.

The Task/Agent branch becomes:

```python
if tool_name in ("Task", "Agent"):
    try:
        import context_budget

        project_dir = Path(data.get("cwd") or ".")
        story_id = (
            json.loads((project_dir / ".companion" / "state.json").read_text())
            .get("current_story", {})
            .get("id", "")
            if (project_dir / ".companion" / "state.json").exists()
            else ""
        )

        result = context_budget.decide(
            project_dir=project_dir,
            story_id=story_id,
        )
    except Exception:
        sys.exit(0)

    if result and result.get("block"):
        try:
            state_path = project_dir / ".companion" / "state.json"
            if state_path.exists():
                state = json.loads(state_path.read_text())
                state["context_budget_acknowledged_at"] = result["acknowledged_at"]
                state_path.write_text(json.dumps(state, indent=2))
        except Exception:
            pass
        print(json.dumps({"decision": "block", "reason": result["reason"]}))
    sys.exit(0)
```

The docstring must be updated: single delegated call (`decide` for the block decision,
passing `story_id` for dict lookup); state write is `context_budget_acknowledged_at`
only (on block). No live-count write; `set-context-tokens` is the sole writer of
`context_story_tokens`.

---

### `hooks/session_start.py` and `skills/pairmode/scripts/session_reset.py`

**Stated reason for modification:** write `context_session_reset_at` on
`clear`/`startup` so `decide()` can detect pre-clear entries.

`session_reset.decide_reset()` must return `context_session_reset_at` alongside the
existing fields. On `clear` or `startup`:

```python
return {
    "should_reset": True,
    "context_current_tokens": baseline,
    "context_current_tokens_recorded_at": now_iso,
    "context_session_reset_at": now_iso,
}
```

On `resume`/`compact` (no reset): `context_session_reset_at` absent from return dict
(existing behaviour preserved).

`session_start.py` writes all returned keys to state.json in its existing write call.

---

### `tests/pairmode/test_context_budget.py`

Remove all tests added in Phase 72 for `_derive_transcript_path`,
`compute_context_tokens`, and `read_current_tokens`.

Add new test sections:

#### `# _read_story_token_entry`

| Test | Behaviour |
|------|-----------|
| present and well-formed → entry | returns dict with tokens and recorded_at |
| story_id absent from dict → None | key not in context_story_tokens |
| context_story_tokens absent → None | key not in state |
| malformed entry (missing tokens) → None | entry exists but wrong shape |

#### `# _is_entry_fresh`

| Test | Behaviour |
|------|-----------|
| recorded_at after reset → True | entry is fresh |
| recorded_at before reset → False | entry is stale |
| recorded_at equal to reset → False | equal = not after → stale |
| no context_session_reset_at → True | no reset recorded, fail-open |
| unparseable recorded_at → True | fail-open |
| unparseable reset_at → True | fail-open |

#### `# read_context_tokens_from_state` (additions to existing tests)

| Test | Behaviour |
|------|-----------|
| story_id + fresh dict entry → returns dict tokens | dict path takes priority |
| story_id + stale dict entry → None | stale = treat as absent |
| story_id + no dict entry → None | falls through to None |
| story_id="" + scalar present → returns scalar | backwards compat path |

#### `# decide` (additions)

| Test | Behaviour |
|------|-----------|
| fresh dict entry under budget → None (pass) | nominal path |
| fresh dict entry over budget → block | threshold exceeded |
| stale dict entry → CONTEXT CHECK REQUIRED | reset boundary respected |
| no dict entry for story → CONTEXT CHECK REQUIRED | story not yet recorded |

#### Update existing test

`test_decide_returns_check_required_when_tokens_absent`: assert that
`"current story"` appears in `result["reason"]` (locking in the updated message).

### `tests/pairmode/test_flex_build_set_context_tokens.py`

Add tests for the dict write:

| Test | Behaviour |
|------|-----------|
| active story + tokens → dict entry written | `context_story_tokens[story_id]` present |
| no active story → dict entry not written, stderr note | graceful skip |
| multiple stories accumulate → all entries present | dict grows, older entries preserved |
| overwrite same story → entry updated | post-clear scenario |
| recorded_at is UTC ISO-8601 | format validated |

### `tests/pairmode/test_session_reset.py` (additions)

| Test | Behaviour |
|------|-----------|
| clear → context_session_reset_at present in return | key written on reset |
| startup → context_session_reset_at present in return | same as clear |
| resume → context_session_reset_at absent from return | no reset on resume |
| compact → context_session_reset_at absent from return | no reset on compact |

## Implementation notes

- The dict is append-only within a session (previous story entries are preserved).
  After a `/clear`, `context_session_reset_at` is updated so old entries are detected
  as stale; when the orchestrator re-records for the same story, the entry is
  overwritten with a fresh `recorded_at` that post-dates the reset.
- `context_current_tokens` and `context_current_tokens_recorded_at` are kept in the
  state.json write in `set-context-tokens` for backwards compatibility with any
  existing sibling-project CLAUDE.build.md files that read those keys for display.
  INFRA-181 (next story) restores the `/context`-based Context gate which reads the
  dict instead. The scalar keys become display-only; the hook uses the dict exclusively.
- `session_id` parameter added to `decide()` in Phase 72 is removed; the new parameter
  is `story_id`. No in-tree callers pass `session_id` by keyword (only the hook called
  it, and the hook is updated here), so this is a safe rename.
