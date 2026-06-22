# Phase 74 — PostToolUse JSONL context gate (deterministic, no LLM cooperation)

**Era:** era-002
**Status:** complete
**Parent phase:** Phase 73 (per-story dict gate) — superseded by this design

## Problem

The context gate has oscillated between two broken designs:
- **LLM-cooperation** (`/context` + `set-context-tokens`): unreliable — I skip the step
- **JSONL in PreToolUse** (INFRA-179): reads the *previous* turn's token count, not the current one

The root issue: PreToolUse fires mid-turn, before the current turn's JSONL entry is written. Reading JSONL there gives a stale (under-estimated) count.

## Design

**PostToolUse** is the writer. It fires after a Task/Agent completes, at which point the orchestrator's JSONL has a fresh assistant entry from the current turn. PostToolUse reads the JSONL (full reverse scan, no fixed tail), writes `context_current_tokens` + `context_current_tokens_recorded_at` to state.json.

**PreToolUse** is the reader. It reads `context_current_tokens` from state.json (written by PostToolUse or the SessionStart baseline). If the value is absent or stale (older than `context_session_reset_at`): block hard. If present and fresh: check threshold and block if exceeded.

No JSONL reading in PreToolUse. No LLM cooperation. No per-story dict. No fallback to stale state.

The SessionStart baseline (25,000) covers the first spawn of a session before any PostToolUse write has occurred.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-182 | PostToolUse JSONL writer + PreToolUse state.json reader — deterministic context gate | complete |

---

## Story INFRA-182

**Title:** PostToolUse JSONL writer + PreToolUse state.json reader — deterministic context gate

**Rail:** INFRA
**Phase:** 74
**Status:** complete

### Problem

The per-story dict gate (INFRA-180/181) requires the orchestrator to call `set-context-tokens` before each story. I skip this. The gate fails silently or blocks with CONTEXT CHECK REQUIRED, stalling builds.

### Acceptance criteria

1. `hooks/hooks.json` — PostToolUse has a `Task|Agent` matcher pointing to `post_tool_use.py`
2. `hooks/post_tool_use.py` — Task/Agent branch: reads JSONL via `context_budget.read_current_tokens()`, writes `context_current_tokens` + `context_current_tokens_recorded_at` to state.json. Exits silently on any failure (never blocks).
3. `hooks/pre_tool_use.py` — Task/Agent branch: calls `decide(project_dir)` with no `story_id` or `session_id`. Blocks hard if result is CONTEXT CHECK REQUIRED.
4. `skills/pairmode/scripts/context_budget.py`:
   - Restores `_derive_transcript_path`, `compute_context_tokens`, `read_current_tokens` (removed in INFRA-181) with one fix: `compute_context_tokens` scans the full file in reverse (no fixed-line tail)
   - `decide()` signature: `(project_dir, flex_factor=1.0)` — no `story_id`, no `session_id`
   - `decide()` reads `context_current_tokens` from state.json only (no JSONL, no per-story dict)
   - Hard block (CONTEXT CHECK REQUIRED) when `context_current_tokens` is absent or stale (`recorded_at < context_session_reset_at`)
   - Removes all per-story dict logic (`context_story_tokens`, `story_id`)
5. `CLAUDE.build.md` — Context gate step: call `/context` for display only; remove `set-context-tokens` instruction; note that the hook manages enforcement automatically
6. `skills/pairmode/templates/CLAUDE.build.md.j2` — same as above
7. `tests/pairmode/test_context_budget.py` — updated to cover: fresh count proceeds, stale count hard-blocks, absent count hard-blocks, full reverse scan finds entry beyond 100 lines
8. `tests/pairmode/test_templates.py` — updated assertions to match new Context gate wording

### Primary files

- `hooks/hooks.json`
- `hooks/post_tool_use.py`
- `hooks/pre_tool_use.py`
- `skills/pairmode/scripts/context_budget.py`

### Touches

- `CLAUDE.build.md`
- `skills/pairmode/templates/CLAUDE.build.md.j2`
- `tests/pairmode/test_context_budget.py`
- `tests/pairmode/test_templates.py`

### Out of scope

- `set-context-tokens` CLI command — leave in place as a manual override/debugging escape hatch
- `context_story_tokens` key in state.json — leave existing entries untouched; just stop reading/writing them
- SessionStart hook — unchanged; it remains the sole writer of `context_session_reset_at` and the baseline `context_current_tokens`

### Notes

- The 100-line tail limit in INFRA-179's `compute_context_tokens` was a known defect. The fix is a full reverse scan using `reversed(lines)` over the entire file — no slice.
- PostToolUse must never block (no `decision: block` output). It is a best-effort writer only.
- The JSONL `session_id` field is available in PostToolUse hook data (`data.get("session_id", "")`).
- Protected file changes in `hooks/` are justified: this is a targeted architectural fix to a documented gate defect.
