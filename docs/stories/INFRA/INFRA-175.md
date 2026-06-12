---
id: INFRA-175
rail: INFRA
title: "Reset `context_current_tokens` on SessionStart `clear`/`startup` via thin-delegation hook"
status: planned
phase: "68"
story_class: code
primary_files:
  - hooks/session_start.py
  - skills/pairmode/scripts/session_reset.py
touches:
  - tests/pairmode/test_session_reset.py
  - tests/pairmode/test_templates.py
  - CLAUDE.md
  - docs/architecture.md
---

# INFRA-175 — Reset `context_current_tokens` on SessionStart `clear`/`startup` via thin-delegation hook

**Phase:** 68
**Rail:** INFRA
**Status:** planned

## Problem (CER-047)

`context_current_tokens` is a dead-reckoning counter: anchored once from a real
`/context` reading, then advanced by each builder/reviewer's measured cost
(Phase 65 design, CER-045). Dead-reckoning has no signal for "the window was
just wiped." After `/clear`, `state.json` retains the previous session's
accumulated total; the context gate then blocks the next builder spawn on a
phantom number. Confirmed in production (coherra, 2026-06-12): a clear at
212,492 tokens left the counter intact and blocked the next story.

Existing mitigations don't cover this:

- **CER-041 TTL (Phase 59 INFRA-151):** only fires when the recorded value is
  older than 60 minutes. A clear within the TTL window is trusted as-is. And
  when the TTL *does* fire, `read_context_tokens_from_state` returns `None`,
  which produces the CONTEXT CHECK REQUIRED block — the same manual step.
- **Phase 67 INFRA-174 seed:** only runs on `is_new_state` (fresh bootstrap),
  never on an established `state.json`.

Claude Code fires the SessionStart hook with a stdin JSON payload containing
`source`: `"startup"` (new process), `"resume"` (`--resume`/`--continue`),
`"clear"` (`/clear`), or `"compact"` (auto-compaction). `hooks/session_start.py`
already runs at every session start but never reads stdin, so the signal is
discarded.

## Fix

### 1. New pure module: `skills/pairmode/scripts/session_reset.py`

Mirrors the `context_budget.py` D11 boundary — pure decision logic, no I/O:

```python
RESET_SOURCES = frozenset({"clear", "startup"})
DEFAULT_BASELINE_TOKENS = 25_000

def decide_reset(source: str | None, state: dict) -> int | None:
    """Return the baseline token value to write, or None for no reset."""
```

Rules:

- Returns `None` unless `source in RESET_SOURCES`.
- Returns `None` unless `state` is a dict containing a truthy
  `pairmode_version` (non-pairmode repos are untouched, matching the
  existing early-exit in `session_start.py`).
- Otherwise returns `int(state.get("context_baseline_tokens"))` when that key
  holds a valid positive integer, else `DEFAULT_BASELINE_TOKENS`.

Rationale for the baseline (vs. the Phase 67 seed of `1`): after a mid-build
clear there is **no** orchestrator `set-context-tokens` call coming to replace
the value — the whole point is removing that step — so the reset value is the
permanent dead-reckoning anchor for the new session. A fresh window genuinely
contains ~15–25k tokens (system prompt, CLAUDE.md, memory, hook output).
`25_000` is deliberately on the high side: overstating fails safe (gate blocks
slightly early); understating erodes the overflow margin. Operators can tune
per-project via `state["context_baseline_tokens"]`.

`resume` never resets (the same window is restored — the counter is still
correct). `compact` never resets (post-compact window size is unknown; the
stale counter overstates, which over-blocks — fail-safe; deferred per CER-047).

### 2. `hooks/session_start.py` — thin dispatch + one hook-owned write

Following the `pre_tool_use.py` pattern exactly (`sys.path` insert from
`PLUGIN_ROOT`, broad try/except so the hook can never break session start):

- Read stdin JSON at the top of `main()`; on any parse failure treat
  `source = None` (hook behaves exactly as today — backwards compatible with
  direct invocation and older harnesses).
- After loading state (existing code path), call
  `session_reset.decide_reset(source, state)`.
- When it returns a value N, perform the single hook-owned state write:
  `state["context_current_tokens"] = N` and
  `state["context_current_tokens_recorded_at"] = <UTC ISO-8601 now>`,
  written back with `json.dumps(state, indent=2)`.
- Append to the emitted `additionalContext`:
  `Context counter reset to N (session source: clear).`
- Any exception in the reset path is swallowed; the status block still emits.

No other logic moves into the hook: one stdin read, one delegated decide
call, one state write, one emit.

### 3. Contract amendments (same story, not follow-ups)

- **CLAUDE.md** review checklist item 1 (HOOK PERFORMANCE): add
  `hooks/session_start.py` to the documented thin-delegation exceptions —
  one source check delegated to `session_reset.decide_reset`, one hook-owned
  state write (`context_current_tokens` + `_recorded_at`), one emit. Logic
  beyond that remains CRITICAL.
- **docs/architecture.md** `context_current_tokens` field docs: amend
  "Never written by the companion sidebar or hook" to name the SessionStart
  reset as the second documented hook write (alongside `pre_tool_use.py`'s
  `acknowledged_at`), with source-gating (`clear`/`startup` only) and the
  Phase 68 reference.

## Acceptance criteria

1. `decide_reset("clear", state_with_pairmode)` returns `25_000` when no
   `context_baseline_tokens` override is present.
2. `decide_reset("startup", ...)` behaves identically to `"clear"`.
3. `decide_reset(source, ...)` returns `None` for `"resume"`, `"compact"`,
   `None`, and `""`.
4. `decide_reset("clear", {})` and `decide_reset("clear", {"foo": 1})` return
   `None` (no `pairmode_version` → non-pairmode repo, no write).
5. `state["context_baseline_tokens"] = 30000` makes `decide_reset` return
   `30000`; invalid values (`0`, `-5`, `"abc"`) fall back to `25_000`.
6. Invoking `hooks/session_start.py` with stdin `{"source": "clear"}` against
   a state.json carrying `context_current_tokens: 212492` rewrites the value
   to the baseline and writes a fresh `context_current_tokens_recorded_at`;
   the emitted `additionalContext` includes the reset notice.
7. Invoking the hook with stdin `{"source": "resume"}` (or empty/garbage
   stdin) leaves both keys byte-identical and emits the status block as today.
8. `context_budget.read_context_tokens_from_state` on the post-reset state
   returns the baseline (gate unblocked, no CONTEXT CHECK REQUIRED).
9. CLAUDE.md checklist item 1 and architecture.md writer contract updated as
   described.
10. Full suite passes: `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`.

## Primary files

- `hooks/session_start.py` — protected file; modification reason: CER-047
  fix requires the hook to consume the `source` field it already receives.
- `skills/pairmode/scripts/session_reset.py` (new)

## Touches

- `tests/pairmode/test_session_reset.py` (new — criteria 1–8; hook-level
  criteria via subprocess invocation with temp project dir, matching existing
  hook test patterns)
- `CLAUDE.md` (checklist item 1 exception)
- `docs/architecture.md` (writer contract amendment)
