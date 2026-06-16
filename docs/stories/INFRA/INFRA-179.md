---
id: INFRA-179
rail: INFRA
title: "Restore JSONL transcript parsing in context_budget.py; make hook the sole enforcer"
status: planned
phase: "72"
story_class: code
primary_files:
  - skills/pairmode/scripts/context_budget.py
  - tests/pairmode/test_context_budget.py
touches:
  - hooks/pre_tool_use.py
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - CLAUDE.md
---

# INFRA-179 — Restore JSONL transcript parsing in `context_budget.py`; make hook the sole enforcer

**Phase:** 72
**Rail:** INFRA

## Context

INFRA-128 (Phase 47) introduced the `pre_tool_use.py` hook gate, which read the
session JSONL transcript to get the live context token count. It got the transcript
path from `data.get("transcript_path")` in the hook event payload.

INFRA-148 (Phase 58) replaced JSONL parsing with a state.json contract after observing
that the gate had never fired in production. The diagnosis was that `transcript_path`
was "absent or incorrect" in PreToolUse events. The replacement requires the
orchestrator to call `/context` and run `set-context-tokens` to record the count —
but `/context` is a user-facing slash command the LLM cannot invoke. The gate has
silently operated on a stale 25,000-token SessionStart baseline ever since.

**Confirmed in Phase 72 investigation:**
- The JSONL format is correct — tail-parsing finds `type: "assistant"` entries with
  `message.usage` blocks containing `input_tokens`, `cache_read_input_tokens`, and
  `cache_creation_input_tokens`.
- Both `session_id` and `cwd` are reliably present in PreToolUse events.
- The transcript path can be constructed as:
  `Path.home() / ".claude" / "projects" / str(Path(cwd).resolve()).replace("/", "-") / f"{session_id}.jsonl"`
- Verified against the live `~/.claude/projects/-mnt-work-flex/` directory on this
  project. The formula correctly matches Claude Code's directory naming convention.

## Protected-file modification statements

- `hooks/pre_tool_use.py`: pass `session_id` from the hook event to
  `context_budget.read_current_tokens()` and `context_budget.decide()`; write the
  JSONL-derived token count to state.json when JSONL parsing succeeds (not on
  state.json fallback, to avoid re-arming the CER-041 staleness TTL with stale data).
  This expands the hook's state.json write scope: the Task branch now has two write
  paths merged into one `write_text()` call — `context_current_tokens` +
  `context_current_tokens_recorded_at` when JSONL succeeds, and
  `context_budget_acknowledged_at` when blocking.
- `CLAUDE.build.md`: remove the `/context` call instruction and `set-context-tokens`
  step from the Context gate; convert to a display-only step. Remove the
  hard-stop-at-threshold branch. The hook is now the sole enforcer. Update
  `## Context budget check (between stories)` to reflect the new architecture.
- `skills/pairmode/templates/CLAUDE.build.md.j2`: mirror all `CLAUDE.build.md`
  changes (replacing hardcoded paths with `{{ pairmode_scripts_dir }}` as
  appropriate).
- `CLAUDE.md`: update the `hooks/pre_tool_use.py` carve-out in the HOOK PERFORMANCE
  check to document the expanded Task-branch write scope and the two delegated module
  calls.

## Acceptance criteria

### `skills/pairmode/scripts/context_budget.py`

#### 1. New private helper: `_derive_transcript_path`

```python
def _derive_transcript_path(
    cwd: Path,
    session_id: str,
    home: Path | None = None,
) -> Path | None:
```

- Returns `None` if `session_id` is empty, None, or not a non-empty string.
- `home` defaults to `Path.home()` when `None`; callers (including tests) can
  inject an alternative root to avoid touching the real `~/.claude/` tree.
- Constructs:
  `home / ".claude" / "projects" / str(Path(cwd).resolve()).replace("/", "-") / f"{session_id}.jsonl"`
- Returns `None` if the constructed path does not exist (fail-open).
- Pure function; no side effects; all exceptions caught and returned as `None`.

#### 2. Restored function: `compute_context_tokens`

```python
def compute_context_tokens(transcript_path: Path) -> int | None:
```

- Tail-reads the last **100 lines** of `transcript_path` (increased from the original
  50 to handle busy sessions with many interleaved metadata entries).
- Walks in reverse to find the first (last chronological) entry where
  `entry.get("type") == "assistant"`.
- From that entry: reads `entry["message"]["usage"]` and returns
  `int(input_tokens + cache_read_input_tokens + cache_creation_input_tokens)`.
- Returns `None` if: file is missing, unreadable (OSError), no valid assistant entry
  with a `usage` dict is found in the tail, or any value is non-numeric. All
  exceptions must be caught; this function must never raise.
- **No TTL on the JSONL count.** The last assistant entry in the tail reflects the
  context state at the most recent completed response. This is always closer to the
  live window size than the SessionStart baseline in state.json.

#### 3. New public function: `read_current_tokens`

```python
def read_current_tokens(
    project_dir: Path,
    session_id: str = "",
    home: Path | None = None,
) -> int | None:
```

**JSONL only** — no state.json fallback. This function is the hook's source for the
live count it writes back to state.json. Keeping it JSONL-only avoids re-arming the
CER-041 staleness TTL with a stale state.json value.

Logic:
1. If `session_id` is non-empty: call `_derive_transcript_path(project_dir, session_id, home)`.
   If the path resolves and `compute_context_tokens()` returns a positive int, return it.
2. Return `None` in all other cases.

`home` is passed through to `_derive_transcript_path` for testability.

#### 4. Modified function: `decide`

Signature change — add `session_id` **after** `project_dir` and **before** `flex_factor`
to keep `flex_factor` as a keyword-only parameter and avoid breaking existing callers:

```python
def decide(
    project_dir: Path,
    session_id: str = "",
    flex_factor: float = 1.0,
) -> dict | None:
```

Internal change: replace the standalone `read_context_tokens_from_state(state)` call
with a two-tier waterfall:

1. Try `read_current_tokens(project_dir, session_id)` (JSONL).
2. If `None`, fall back to `read_context_tokens_from_state(state)`.
3. If both return `None`, return the CONTEXT CHECK REQUIRED block (same as before).

**Return contract (unchanged from INFRA-148):**

| Condition | Return |
|-----------|--------|
| `state.json` absent (non-pairmode) | `None` |
| Under budget OR within reprompt margin | `None` |
| Over budget | `{"block": True, "reason": ..., "tokens": N, "acknowledged_at": N}` |
| No count from JSONL or state.json | `{"block": True, "reason": CONTEXT_CHECK_REQUIRED, "tokens": 0, "acknowledged_at": 0}` |

No callers in-tree pass `flex_factor` positionally; all use keyword syntax. The
new `session_id` kwarg is inserted between `project_dir` and `flex_factor` so the
positional call `decide(project_dir)` continues to work unchanged.

#### 5. Updated `_CONTEXT_CHECK_REQUIRED_MSG`

```python
_CONTEXT_CHECK_REQUIRED_MSG = (
    "CONTEXT CHECK REQUIRED\n"
    "No token count could be read from the session transcript or from state.json.\n"
    "This should resolve automatically on the next spawn if session_id is available.\n"
    "To record manually, run:\n"
    f"  PATH=$HOME/.local/bin:$PATH uv run python {_FLEX_BUILD_PATH} \\\n"
    "    set-context-tokens --tokens N --project-dir .\n"
    "Replace N with the integer token count from /context.\n"
)
```

Note: `_FLEX_BUILD_PATH` is the existing module-level constant; the f-string
interpolation must use the constant, not a literal path placeholder.

#### 6. D11 docstring update

Update the module-level docstring to reflect:
- `decide()` now accepts `session_id` and tries JSONL before state.json.
- `read_current_tokens()` is the new JSONL-only public function used by the hook.
- The hook (not `decide()`) owns the state.json write of `context_current_tokens`.

---

### `hooks/pre_tool_use.py`

**Stated reason for modification:** pass `session_id`; write live JSONL-derived count
to state.json on every spawn where JSONL succeeds; merge all state writes into one
`write_text()` call.

The Task/Agent branch becomes:

```python
if tool_name in ("Task", "Agent"):
    try:
        import context_budget
        from datetime import datetime, timezone

        project_dir = Path(data.get("cwd") or ".")
        session_id = data.get("session_id", "")

        # JSONL-only read — for state.json display update.
        live_tokens = context_budget.read_current_tokens(
            project_dir=project_dir,
            session_id=session_id,
        )

        # Block decision (JSONL-first, state.json fallback internally).
        result = context_budget.decide(
            project_dir=project_dir,
            session_id=session_id,
        )
    except Exception:
        sys.exit(0)

    # Merge state.json writes (live count + optional acknowledged_at).
    needs_write = live_tokens is not None or (result and result.get("block"))
    if needs_write:
        try:
            state_path = project_dir / ".companion" / "state.json"
            if state_path.exists():
                state = json.loads(state_path.read_text())
                if live_tokens is not None:
                    state["context_current_tokens"] = live_tokens
                    state["context_current_tokens_recorded_at"] = (
                        datetime.now(timezone.utc).isoformat()
                    )
                if result and result.get("block"):
                    state["context_budget_acknowledged_at"] = result["acknowledged_at"]
                state_path.write_text(json.dumps(state, indent=2))
        except Exception:
            pass

    if result and result.get("block"):
        print(json.dumps({"decision": "block", "reason": result["reason"]}))
    sys.exit(0)
```

The docstring must be updated to describe both delegated module calls
(`read_current_tokens` for the live JSONL count; `decide` for the block decision)
and both state-write paths, consistent with the CLAUDE.md carve-out update below.

---

### `CLAUDE.md`

**Stated reason for modification:** update the `hooks/pre_tool_use.py` carve-out in
the HOOK PERFORMANCE check to reflect the expanded Task-branch write scope and the two
delegated module calls.

Replace the existing `pre_tool_use.py` carve-out block (starting at
"`hooks/pre_tool_use.py` is a thin dispatcher") with:

```
`hooks/pre_tool_use.py` is a thin dispatcher for two tool types:

- `Task` / `Agent` → `skills/pairmode/scripts/context_budget.py`
  (CER-027 context-budget enforcement; both tool names accepted — CER-049)
- `Edit` / `Write` → `skills/pairmode/scripts/scope_guard.py`
  (Phase 55 story file-scope enforcement)

For the `Task`/`Agent` dispatch: one tool-name check, two delegated module
calls (`read_current_tokens` for the live JSONL count, `decide` for the block
decision), one combined state.json write, one stdout emit. All domain logic lives
in the named modules, NOT in the hook. The Task branch has two state-write paths,
merged into a single `write_text()` call: `context_current_tokens` +
`context_current_tokens_recorded_at` when a live JSONL count is obtained (every
spawn where JSONL parsing succeeds), and `context_budget_acknowledged_at` when
blocking.

For the `Edit`/`Write` dispatch: one tool-name check, one delegated module call,
one stdout emit. The Edit/Write branch is read-only.
```

---

### `CLAUDE.build.md` and `skills/pairmode/templates/CLAUDE.build.md.j2`

**Stated reason for modification:** convert the Context gate from a broken
LLM-cooperation step to a display-only step; remove hard-stop; update the budget
check description.

#### Replace `### Context gate`

```markdown
### Context gate

Before any other action for this story, read `context_current_tokens` from
`.companion/state.json` (written by the `pre_tool_use.py` hook on the previous
spawn, or the SessionStart baseline of 25,000 if no spawn has occurred yet in
this session).

The threshold is the value of `context_budget_threshold` in `.companion/state.json`
(default: 120,000 if the key is absent or the file does not exist).

Output: `CONTEXT: [N] / [threshold] tokens`

Then call:
    PATH=$HOME/.local/bin:$PATH uv run python <pairmode_scripts_dir>/flex_build.py \
      story-cost-estimate --story-id RAIL-NNN --project-dir .

Display its output verbatim. If the estimate is numeric and `threshold - N` is less
than the estimate, append:
    Estimated story cost exceeds remaining headroom; consider /clear before proceeding.
The estimate is informational — it does not block.

Continue to the pre-story schema gate.

Note: the `pre_tool_use.py` hook reads the live token count from the session JSONL
transcript before every Task/Agent spawn and writes it back to state.json.  The
hook is the sole budget enforcer — it will block the spawn and offer options
(Proceed or /clear) if `current + estimated_next_step` exceeds the overrun ceiling
(`threshold × (1 + overrun_pct)`, default 132,000). Tokens in the range
[threshold, ceiling) are not hard-stopped; the hook determines whether the next
step's cost would push over the ceiling.
```

(In the `.j2` template, replace `<pairmode_scripts_dir>` with
`{{ pairmode_scripts_dir }}`.)

#### Replace `## Context budget check (between stories)` 

```markdown
## Context budget check (between stories)

**Enforcer:** `hooks/pre_tool_use.py` (matcher `Task|Agent`) delegates to
`skills/pairmode/scripts/context_budget.py`. On every subagent spawn, the hook:

1. Reads the live token count from the session JSONL transcript
   (`~/.claude/projects/{cwd-key}/{session_id}.jsonl`, last 100 lines,
   last `type: "assistant"` entry's `usage` sum). No LLM cooperation required.
2. Writes the count to `state["context_current_tokens"]` so the Context gate
   (above) can display it on the next story.
3. Falls back to `state["context_current_tokens"]` if JSONL parsing fails
   (missing session, no assistant entry yet). Does **not** re-write state.json
   on the fallback path (avoids re-arming the staleness TTL with stale data).
4. Checks whether `current + estimated_next_step > threshold × (1 + overrun_pct)`
   (defaults: 120,000 × 1.10 = 132,000). When it would, blocks the spawn.

`set-context-tokens` (in `flex_build.py`) remains as a manual override / debugging
escape hatch. The SessionStart hook seeds `context_current_tokens` to the
configurable baseline (default 25,000) on every `/clear` or fresh `startup`.

Canonical prompt body (source of truth:
`tests/pairmode/fixtures/context_budget_prompt.txt`, reproduced
here for in-doc readability):

````
CONTEXT BUDGET — [story RAIL-NNN] just completed.
Context is at approximately [N] tokens (threshold: [T], overrun: [O]).
Estimated next step: ~[E] tokens — [R] tokens remaining before ceiling.

Continuing risks context compaction mid-story. Options:

1. **Proceed** — continue building in this session; budget acknowledged.
   Say: "Continue building"

2. **Clear and resume** — run /clear, then in the fresh session:
   Say: "Continue building Phase X from story RAIL-NNN"
````

Response handling:
- "Continue building" → `context_budget.decide()` has already
  written `state["context_budget_acknowledged_at"]`. Re-prompt is
  suppressed until tokens cross
  `acknowledged_at + state["context_budget_reprompt_margin"]`
  (default 10,000).
- "Clear and resume" → user types `/clear`; the fresh session
  starts with a SessionStart-reset counter and the hook reads a fresh
  JSONL file.

Tunables (all in `.companion/state.json`):
`context_budget_threshold`, `context_budget_overrun_pct`,
`expected_step_tokens` (seeded prior; replaced by the per-phase
effort.db median once ≥5 attempts accumulate),
`context_budget_reprompt_margin`.
```

---

### `tests/pairmode/test_context_budget.py`

Add new test sections after the existing `# render_alert_prompt` tests.

#### `# _derive_transcript_path`

| Test | Behaviour |
|------|-----------|
| empty session_id → None | `_derive_transcript_path(tmp_path, "")` returns `None` |
| None session_id → None | `_derive_transcript_path(tmp_path, None)` returns `None` |
| non-existent file → None | valid session_id, file not on disk → `None` |
| existing file → correct Path | create `home / ".claude" / "projects" / key / f"{sid}.jsonl"` in tmp; assert returned path equals exactly that path |
| formula pins key transform | `cwd=Path("/a/b/c")`, `session_id="abc"`, `home=tmp_path` → returned path ends in `-a-b-c/abc.jsonl` |
| relative cwd resolved | `cwd=Path(".")` resolves; returned path uses the absolute form (no literal `.` in key) |

All tests pass `home=tmp_path` to avoid touching `~/.claude/`.

#### `# compute_context_tokens`

| Test | Behaviour |
|------|-----------|
| valid JSONL last-assistant-with-usage → sum | writes JSONL with one assistant entry; returns `input + cache_read + cache_create` |
| no assistant entry in 100-line tail → None | only user/tool_result entries → `None` |
| assistant entry missing usage key → None | entry has no `usage` key → `None` |
| missing file → None | path does not exist → `None` |
| malformed JSON lines skipped | lines before valid entry are unparseable; still finds the valid entry |
| entry beyond 50-line window found | assistant entry at line 60 from end is found (tail is 100, not 50) |
| all exceptions caught | OSError on open → `None` (no raise) |

Write minimal JSONL fixture files in `tmp_path`; no real transcript touched.

#### `# read_current_tokens`

| Test | Behaviour |
|------|-----------|
| JSONL succeeds → returns JSONL count | creates JSONL fixture; result matches JSONL sum |
| no session_id → None | `session_id=""` → returns `None` |
| JSONL file missing → None | valid session_id but no file → `None` |

All tests inject `home=tmp_path`.

#### Updates to existing tests

- `test_decide_returns_check_required_when_tokens_absent`: add assertion that
  `"session transcript or from state.json"` is in `result["reason"]` to lock in the
  updated message text.
- All existing `decide()` tests omit `session_id` (default `""`), so the JSONL path
  is skipped and state.json fallback proceeds as before. No other existing tests
  require changes.

## Implementation notes

- In `_derive_transcript_path`, the path construction must use
  `str(Path(cwd).resolve()).replace("/", "-")` — resolve first to handle `cwd="."`,
  relative paths, and trailing slashes consistently.
- `compute_context_tokens` must catch all exceptions (OSError, JSONDecodeError,
  KeyError, TypeError, ValueError) and return `None`. Never raise.
- In `pre_tool_use.py`, `live_tokens` and `result` are computed independently.
  `read_current_tokens` is JSONL-only; `decide()` handles its own JSONL-then-state
  waterfall. The double JSONL read is acceptable — tail-reading 100 lines of a local
  file is sub-millisecond.
- `set-context-tokens` in `flex_build.py` is **not** removed — it remains as a manual
  override / debugging escape hatch.
- `bump-context-tokens` in `flex_build.py` is also **not** removed — it is already
  unused in the build loop (removed in BUILD-029) but may still be referenced in
  older sibling-project CLAUDE.build.md files; removal is out of scope.
