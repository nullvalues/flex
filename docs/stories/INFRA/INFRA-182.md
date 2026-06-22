---
id: INFRA-182
rail: INFRA
title: "PostToolUse JSONL writer + PreToolUse state.json reader — deterministic context gate"
status: complete
phase: "74"
story_class: code
primary_files:
  - hooks/hooks.json
  - hooks/post_tool_use.py
  - hooks/pre_tool_use.py
  - skills/pairmode/scripts/context_budget.py
touches:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - tests/pairmode/test_context_budget.py
  - tests/pairmode/test_templates.py
  - tests/pairmode/test_flex_build_set_context_tokens.py
  - skills/pairmode/scripts/flex_build.py
  - docs/phases/index.md
  - docs/phases/phase-74.md
---

# INFRA-182 — PostToolUse JSONL writer + PreToolUse state.json reader — deterministic context gate

**Phase:** 74
**Rail:** INFRA

## Background

The context gate has oscillated between two broken designs:

- **LLM-cooperation** (`/context` + `set-context-tokens`): unreliable — the orchestrator
  skips the step, the hook blocks with CONTEXT CHECK REQUIRED, builds stall.
- **JSONL in PreToolUse** (INFRA-179): reads the *previous* turn's token count, not the
  current one — PreToolUse fires before the current turn's JSONL entry is written, so the
  count is always one turn stale and underestimates the true context.

The root fix: **PostToolUse is the writer, PreToolUse is the reader**.

PostToolUse fires after a Task/Agent completes. At that point the orchestrator's JSONL
has a fresh assistant entry from the current turn. PostToolUse reads it (full reverse
scan — no fixed-line tail), writes `context_current_tokens` +
`context_current_tokens_recorded_at` to state.json.

PreToolUse reads `context_current_tokens` from state.json (kept fresh by PostToolUse or
the SessionStart baseline). If absent or stale: block hard. If fresh and under threshold:
proceed.

No JSONL reading in PreToolUse. No LLM cooperation. No per-story dict. No stale fallback.

## Protected-file modification statements

- `hooks/hooks.json`: add `Task|Agent` PostToolUse matcher pointing to `post_tool_use.py`.
  Justified: required to wire the PostToolUse JSONL writer for agent spawns.
- `hooks/post_tool_use.py`: add Task/Agent branch for JSONL read + state.json write.
  Justified: PostToolUse is the sole writer of `context_current_tokens` under this design.
- `hooks/pre_tool_use.py`: simplify Task/Agent branch — remove `story_id` lookup, pass
  only `project_dir` to `decide()`. Justified: cleaning up the now-removed per-story dict.

## Acceptance criteria

### `hooks/hooks.json`

Add a second PostToolUse entry with matcher `Task|Agent`:

```json
{
  "matcher": "Task|Agent",
  "hooks": [
    {
      "type": "command",
      "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.py",
      "timeout": 5
    }
  ]
}
```

### `hooks/post_tool_use.py`

Add a Task/Agent branch before the existing `WATCHED_TOOLS` check:

```python
if tool_name in ("Task", "Agent"):
    # Read JSONL, write fresh count to state.json. Never blocks.
    try:
        import context_budget
        project_dir = Path(data.get("cwd") or ".")
        session_id = data.get("session_id", "")
        live_tokens = context_budget.read_current_tokens(
            project_dir=project_dir,
            session_id=session_id,
        )
        if live_tokens is not None:
            from datetime import datetime, timezone
            state_path = project_dir / ".companion" / "state.json"
            if state_path.exists():
                state = json.loads(state_path.read_text())
                state["context_current_tokens"] = live_tokens
                state["context_current_tokens_recorded_at"] = (
                    datetime.now(timezone.utc).isoformat()
                )
                state_path.write_text(json.dumps(state, indent=2))
    except Exception:
        pass
    sys.exit(0)
```

The `sys.path.insert` for `skills/pairmode/scripts` is already present in
`post_tool_use.py` — confirm it is (add if not).

### `hooks/pre_tool_use.py`

Simplify the Task/Agent branch:

- Remove the `story_id` inline state.json lookup
- Call `context_budget.decide(project_dir=project_dir)` — no `story_id`, no `session_id`
- Remove the merged state.json write for `live_tokens` (that now lives in PostToolUse)
- Keep the `context_budget_acknowledged_at` write on block

### `skills/pairmode/scripts/context_budget.py`

#### Restore JSONL reading functions (removed in INFRA-181)

Restore with one fix — `compute_context_tokens` scans the full file in reverse (no
fixed-line tail):

```python
def _derive_transcript_path(cwd, session_id, home=None):
    """Derive the Claude Code session JSONL transcript path. Returns None on failure."""
    ...  # same logic as INFRA-179

def compute_context_tokens(transcript_path):
    """Full reverse scan — no tail limit. Returns int or None."""
    try:
        lines = transcript_path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):  # full scan, no slice
            ...  # same parse logic as INFRA-179
        return None
    except Exception:
        return None

def read_current_tokens(project_dir, session_id="", home=None):
    """JSONL-only read. No state.json fallback."""
    ...  # same as INFRA-179
```

#### Update `decide()` signature and logic

```python
def decide(project_dir: Path, flex_factor: float = 1.0) -> dict | None:
```

- Remove `story_id` and `session_id` parameters
- Remove all per-story dict logic (`context_story_tokens`, `_is_entry_fresh`)
- Read `context_current_tokens` from state.json only (via `read_context_tokens_from_state`)
- If absent: return CONTEXT CHECK REQUIRED block
- If stale (`context_current_tokens_recorded_at` < `context_session_reset_at`): return
  CONTEXT CHECK REQUIRED block
- If fresh and under threshold: return None (proceed)
- If fresh and over threshold: return block dict

CONTEXT CHECK REQUIRED message: `"Context token count is missing or stale. It will
update automatically after the next tool call completes."`

#### Remove per-story dict helpers

Remove `_is_entry_fresh`, `_lookup_story_tokens`, and any other functions introduced
solely to support the `context_story_tokens` dict gate (INFRA-180).

#### Update module docstring

Describe the new write/read split: PostToolUse writes `context_current_tokens` via
`read_current_tokens()` + hook state write; `decide()` reads it. `set-context-tokens`
remains as a manual override/debugging escape hatch only.

### `CLAUDE.build.md`

Replace the `### Context gate` section:

```markdown
### Context gate

Before any other action for this story, call `/context` and read the current token count
for display.

The threshold is the value of `context_budget_threshold` in `.companion/state.json`
(default: 120,000 if the key is absent or the file does not exist).

Output: `CONTEXT: [N] / [threshold] tokens — proceeding` (or `THRESHOLD REACHED`).

Then call:
    PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
      story-cost-estimate --story-id RAIL-NNN --project-dir .

Display its output verbatim. If the estimate is numeric and `threshold - N` is less
than the estimate, append:
    Estimated story cost exceeds remaining headroom; consider /clear before proceeding.
The estimate is informational — it does not block.

Note: `pre_tool_use.py` enforces the budget automatically on every Task/Agent spawn by
reading `context_current_tokens` from state.json (written by `post_tool_use.py` after
each completed spawn, or by the SessionStart baseline on `/clear`). No manual
`set-context-tokens` call is required.
```

Remove the `set-context-tokens` instruction and all references to `context_story_tokens`.

Update `## Context budget check (between stories)` to describe the PostToolUse writer /
PreToolUse reader architecture.

### `skills/pairmode/templates/CLAUDE.build.md.j2`

Mirror all `CLAUDE.build.md` changes, replacing hardcoded paths with
`{{ pairmode_scripts_dir }}`.

### `tests/pairmode/test_context_budget.py`

- Restore tests for `_derive_transcript_path`, `compute_context_tokens`,
  `read_current_tokens` (removed in INFRA-181)
- Add test: `compute_context_tokens` finds entry beyond 100 lines (full reverse scan)
- Add test: `decide()` hard-blocks when `context_current_tokens_recorded_at` predates
  `context_session_reset_at` (stale)
- Add test: `decide()` hard-blocks when `context_current_tokens` is absent from state
- Update / remove tests for per-story dict logic (no longer exists in `decide()`)

### `tests/pairmode/test_templates.py`

Update assertions to match new Context gate wording (display-only; no
`set-context-tokens` step).

## Implementation notes

- `post_tool_use.py` currently does not have `sys.path.insert` for pairmode scripts.
  The builder must add it (same pattern as `pre_tool_use.py`).
- PostToolUse **never** emits `decision: block`. It is a best-effort writer — failure
  exits silently via `sys.exit(0)`.
- The SessionStart baseline (`context_current_tokens: 25000`,
  `context_current_tokens_recorded_at: <reset_time>`, `context_session_reset_at: <same>`)
  means `recorded_at == reset_at` on a fresh session. The staleness check must use
  strict less-than (`<`), not less-than-or-equal, so the baseline is treated as fresh.
- `set-context-tokens` CLI in `flex_build.py` — leave in place as a manual override.
  It should write `context_current_tokens` (scalar) only, not `context_story_tokens`.
- The JSONL path key: `str(Path(cwd).resolve()).replace("/", "-")` — verified correct
  for this project (`/mnt/work/flex` → `-mnt-work-flex`).
