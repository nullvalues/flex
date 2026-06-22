---
id: INFRA-183
rail: INFRA
title: "Phase 74 security remediation — bound JSONL scan, session_id containment, CLAUDE.md exception doc"
status: complete
phase: "75"
story_class: code
primary_files:
  - skills/pairmode/scripts/context_budget.py
  - CLAUDE.md
touches:
  - docs/cer/backlog.md
  - tests/pairmode/test_context_budget.py
---

# INFRA-183 — Phase 74 security remediation

**Phase:** 75
**Rail:** INFRA

## Background

Phase 74 security audit returned FAIL. Three findings to fix:

1. **CRITICAL**: `compute_context_tokens` does a full unbounded reverse scan of the JSONL
   file — blocking I/O inside a 5-second hook timeout. Fix: bound to last 500 lines.
2. **HIGH**: `_derive_transcript_path` builds a path from `session_id` (hook input) with
   no containment check — a crafted session_id could escape `~/.claude/`. Fix: add
   `is_relative_to` guard.
3. **CRITICAL/LOW**: `CLAUDE.md` still documents the old `decide(story_id=...)` interface
   and has no exception block for `post_tool_use.py`. Fix: update the HOOK PERFORMANCE
   carve-out.

## Protected-file modification statement

- `CLAUDE.md`: updating the HOOK PERFORMANCE check (item 1) to document the new
  `post_tool_use.py` thin-delegation exception and correct the stale `decide()` interface
  description. `CLAUDE.md` is not in the project's protected-files list and requires no
  deny-list override.

## Acceptance criteria

### `skills/pairmode/scripts/context_budget.py`

**`compute_context_tokens`** — bound to last 500 lines:
```python
lines = transcript_path.read_text(encoding="utf-8").splitlines()
tail = lines[-500:] if len(lines) > 500 else lines
for line in reversed(tail):
    ...
```

**`_derive_transcript_path`** — add containment check after constructing `candidate`:
```python
resolved = candidate.resolve()
if not resolved.is_relative_to((home / ".claude").resolve()):
    return None
```
Wrap in try/except; return None on any exception.

### `CLAUDE.md`

Replace the `hooks/pre_tool_use.py` carve-out section under HOOK PERFORMANCE with:

```
`hooks/pre_tool_use.py` is a thin dispatcher for two tool types:

- `Task` / `Agent` → `skills/pairmode/scripts/context_budget.py`
  (CER-027 context-budget enforcement; both tool names accepted — CER-049)
- `Edit` / `Write` → `skills/pairmode/scripts/scope_guard.py`
  (Phase 55 story file-scope enforcement)

For the `Task`/`Agent` dispatch: one tool-name check, one delegated module call
(`decide(project_dir)` for the block decision — reads `context_current_tokens`
scalar from state.json, written by `post_tool_use.py` after each completed
Task/Agent spawn), one stdout emit. All domain logic lives in the named module,
NOT in the hook. The Task branch has one state-write path:
`context_budget_acknowledged_at` when blocking (single `write_text()` call).
`post_tool_use.py` (PostToolUse Task/Agent branch, INFRA-182) is the sole live
writer of `context_current_tokens`.

For the `Edit`/`Write` dispatch: one tool-name check, one delegated module call,
one stdout emit. The Edit/Write branch is read-only.

`hooks/post_tool_use.py` is a thin dispatcher for two tool types:

- `Write` / `Edit` / `MultiEdit` → companion sidebar pipe relay (file-change events)
- `Task` / `Agent` → `skills/pairmode/scripts/context_budget.py`
  (INFRA-182 PostToolUse context-token writer)

For the `Task`/`Agent` dispatch: one tool-name check, one delegated module call
(`read_current_tokens(project_dir, session_id)` — reads the JSONL transcript,
bounded to last 500 lines), one state.json write (`context_current_tokens` +
`context_current_tokens_recorded_at` when a live count is obtained). Never emits
a block decision. All JSONL parsing logic lives in `context_budget.py`, NOT in
the hook. The Task/Agent branch is write-only.

`hooks/session_start.py` (CER-047 / Phase 68 INFRA-175) is a thin
dispatcher for the SessionStart `source` field:

- `source` ∈ {`clear`, `startup`} → `skills/pairmode/scripts/session_reset.py`
  (dead-reckoning counter reset)

For this dispatch: one stdin read, one delegated `decide_reset` call,
one hook-owned state write (`context_current_tokens` +
`context_current_tokens_recorded_at` + `context_session_reset_at` —
three keys returned by `decide_reset()` as a dict — see INFRA-180),
one emit. All decision logic lives in `session_reset.py`, NOT in the hook.

Any logic added inside `pre_tool_use.py`, `post_tool_use.py`, or
`session_start.py` beyond tool-name / source dispatch + module delegation
+ emit remains CRITICAL. Any *other* hook that emits a decision-block
response remains CRITICAL.
```

### `docs/cer/backlog.md`

File CER-052 in the resolved section:

```
| CER-052 | `_derive_transcript_path` in `context_budget.py` constructs a JSONL path from `session_id` (hook event input) without a `Path.resolve().is_relative_to()` containment check. A crafted `session_id` with `..` segments could escape `~/.claude/`. Fix: add containment guard after `candidate.resolve()`. HIGH severity. `skills/pairmode/scripts/context_budget.py` `_derive_transcript_path`. | Phase 74 security audit | 2026-06-22 | 75 | **RESOLVED Phase 75 INFRA-183** |
```

### `tests/pairmode/test_context_budget.py`

Add tests:
1. `_derive_transcript_path` returns `None` for session_id containing `../` traversal
2. `compute_context_tokens` finds assistant entry at line 450 (bounded scan regression guard)
3. `compute_context_tokens` does NOT find assistant entry placed only at line 600 (500-line bound guard)

## Implementation notes

- The 500-line bound is explicit: `lines[-500:]` — not configurable for now.
- `is_relative_to` is available in Python 3.9+; project requires 3.11+ so no compat shim needed.
- Do not change the `compute_context_tokens` return semantics — only the line scan bound changes.
- Do not change `CLAUDE.build.md` or `architecture.md` in this story (already updated in Phase 74 doc pass).
