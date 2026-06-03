---
id: INFRA-142
rail: INFRA
title: "`docs/architecture.md` — document Edit/Write → scope_guard dispatch"
status: planned
phase: "55"
story_class: doc
primary_files:
  - docs/architecture.md
touches:
---

# INFRA-142 — `docs/architecture.md` — document Edit/Write → scope_guard dispatch

## Background

CER-037 (Phase 55 security audit): `docs/architecture.md` still describes
`hooks/pre_tool_use.py` as handling only context budget enforcement (CER-027,
context_budget.py). Phase 55 INFRA-139 added a second dispatch branch
(`Edit`/`Write` → `scope_guard.py`) but did not update architecture.md.
The "Documented exception" block at line 785 names only CER-027. Future reviewers
reading architecture.md see no authority for the scope_guard dispatch.

## Ensures

### Module structure list (line ~26)

Replace:
```
pre_tool_use.py               ← context budget enforcement (CER-027); thin delegate to skills/pairmode/scripts/context_budget.py
```
With:
```
pre_tool_use.py               ← thin dispatcher: Task → context_budget.py (CER-027 budget enforcement); Edit/Write → scope_guard.py (Phase 55 file-scope enforcement)
```

### Step 9 narrative (lines ~169–178)

The paragraph describing the context budget check step currently ends without
mentioning scope enforcement. Append a new step 9.5 (or extend step 9):

```
**9.5 Story file-scope enforcement** — `hooks/pre_tool_use.py` also intercepts
`Edit` and `Write` tool calls. It delegates to
`skills/pairmode/scripts/scope_guard.py`, which reads
`<project_dir>/.companion/state.json["current_story"]["id"]` and then reads
`<project_dir>/docs/phases/permissions/<story_id>.json` to verify the target
path is declared in the active story's `primary_files` or `touches`. If the
path is not declared, the hook emits `{"decision": "block", "reason": "..."}`.
The check fails open on any error (missing state, missing permissions file,
malformed JSON) so non-story orchestrator work (checkpointing, spec mode) is
never blocked. Introduced in Phase 55 (INFRA-138, INFRA-139).
```

### Documented exception block (line ~785)

Extend the "Documented exception" block to cover scope_guard alongside context_budget:

Replace the current block (starting "**Documented exception — `hooks/pre_tool_use.py` (CER-027 enforcement):**")
with:

```
**Documented exception — `hooks/pre_tool_use.py` (dual thin-delegate):**
`pre_tool_use.py` dispatches to two modules:

- **`Task` → `context_budget.py` (CER-027):** decides whether to block a new
  subagent spawn based on transcript token count. Writes
  `context_budget_acknowledged_at` to `.companion/state.json`. Does not write
  to the pipe.
- **`Edit`/`Write` → `scope_guard.py` (Phase 55):** decides whether to block
  a file write based on the active story's declared `primary_files`/`touches`.
  Read-only; no state writes. Fails open when state or permissions file absent.

All decision logic lives in the named modules; the hook is a thin dispatcher.
```

## Out of scope

- Updating SKILL.md (separate story if needed).
- Updating CLAUDE.build.md.j2 (already done in BUILD-024).

## Instructions

Read `docs/architecture.md` in full to locate the three sections described above,
then apply the replacements exactly as specified in Ensures.

## Tests

`TEST RUN: documentation story — no test file expected`
