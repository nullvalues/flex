# Phase 75 — Phase 74 security remediation

**Era:** era-002
**Status:** planned
**Parent phase:** Phase 74 (INFRA-182 PostToolUse context gate)

## Problem

Phase 74's security audit (checkpoint cp-74) returned FAIL with two CRITICAL findings and two HIGH findings in the INFRA-182 implementation:

- **CRITICAL**: Full JSONL reverse scan is unbounded blocking I/O inside a 5-second hook timeout
- **CRITICAL**: `post_tool_use.py` not documented as a thin-delegation exception in `CLAUDE.md` or `architecture.md` (architecture.md was fixed in the intent-review doc pass; `CLAUDE.md` still needs updating)
- **HIGH**: No path containment guard on `session_id` in `_derive_transcript_path` — a crafted session_id could escape `~/.claude/`
- **HIGH**: `architecture.md` and `CLAUDE.md` describe the stale `decide(story_id=...)` interface (architecture.md fixed in intent-review pass; `CLAUDE.md` still needs updating)

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-183 | Phase 74 security remediation — bound JSONL scan, session_id containment, CLAUDE.md exception doc | planned |

---

## Story INFRA-183

**Title:** Phase 74 security remediation — bound JSONL scan, session_id containment, CLAUDE.md exception doc

**Rail:** INFRA
**Phase:** 75
**Status:** planned

### Acceptance criteria

#### 1. Bound the JSONL scan in `compute_context_tokens` (CRITICAL 2)

Replace the full-file read with a bounded tail read. Read the last 500 lines:

```python
lines = transcript_path.read_text(encoding="utf-8").splitlines()
tail = lines[-500:] if len(lines) > 500 else lines
for line in reversed(tail):
    ...
```

500 lines is ~5× the original 100-line limit; based on observed session density (~78 assistant entries per 200 lines), this reliably captures the last assistant entry while bounding synchronous I/O to a predictable size.

Add a test: `compute_context_tokens` finds the last assistant entry when it is positioned beyond line 100 but within line 500 of the file (regression guard for the original 100-line defect), AND does not read past line 500 (bounded scan guard).

#### 2. Path containment guard on `session_id` (HIGH 1)

In `_derive_transcript_path`, after constructing `candidate`, add a containment check before calling `candidate.exists()`:

```python
try:
    resolved = candidate.resolve()
    if not resolved.is_relative_to((home / ".claude").resolve()):
        return None
except Exception:
    return None
```

This prevents a crafted `session_id` (e.g. `"../../../attack"`) from escaping `~/.claude/`.

Add a test: `_derive_transcript_path` returns `None` for a session_id containing `..` path traversal components.

File a new CER for this finding: CER-052 in `docs/cer/backlog.md` (RESOLVED by this story).

#### 3. Update `CLAUDE.md` thin-delegation exception block (CRITICAL 1 / LOW)

In `CLAUDE.md`, update the `hooks/pre_tool_use.py` carve-out under HOOK PERFORMANCE (check item 1) to:

a. Update the Task/Agent dispatch description to reflect the new `decide(project_dir)` signature (no `story_id`, reads `context_current_tokens` scalar written by PostToolUse).

b. Add a documented exception block for `hooks/post_tool_use.py` immediately after the `pre_tool_use.py` block:

```
`hooks/post_tool_use.py` is a thin dispatcher for two tool types:

- `Write` / `Edit` / `MultiEdit` → companion sidebar pipe relay (existing role)
- `Task` / `Agent` → `skills/pairmode/scripts/context_budget.py`
  (INFRA-182 PostToolUse context-token writer)

For the `Task`/`Agent` dispatch: one tool-name check, one delegated module call
(`read_current_tokens(project_dir, session_id)` — reads the JSONL transcript,
bounded to last 500 lines), one state.json write
(`context_current_tokens` + `context_current_tokens_recorded_at` when a live count
is obtained). Never emits a block decision. All JSONL parsing logic lives in
`context_budget.py`, NOT in the hook. The Task/Agent branch is write-only.
```

c. Update the `session_start.py` exception reference from INFRA-180 to include INFRA-182 where relevant.

#### 4. Tests

- `test_context_budget.py`: add path traversal test for `_derive_transcript_path`; add bounded-scan test for `compute_context_tokens` (entry at line 450 found, entry at line 600 not found)
- `test_templates.py`: update assertions if CLAUDE.build.md template wording changed (it should not be in this story)
- All existing tests must continue to pass

### Primary files

- `skills/pairmode/scripts/context_budget.py`
- `CLAUDE.md`

### Touches

- `docs/cer/backlog.md`
- `tests/pairmode/test_context_budget.py`

### Notes

- `architecture.md` was already updated in the Phase 74 intent-review doc pass. Do not re-edit it unless a specific stale claim is found.
- `CLAUDE.md` is NOT in the project's protected-files list and does not require a deny-list override.
- The MEDIUM finding (unvalidated `cwd` in `post_tool_use.py`) is consistent with the existing `pre_tool_use.py` documented exception pattern. Now that `post_tool_use.py` is documented, this finding is resolved by documentation. No code change needed.
