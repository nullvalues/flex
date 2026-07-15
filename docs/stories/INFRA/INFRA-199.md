---
id: INFRA-199
rail: INFRA
title: "Scope context-budget PreToolUse gate to pairmode build-cycle agent spawns via tool_input.subagent_type allowlist"
status: planned
phase: "88"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - hooks/pre_tool_use.py
  - tests/pairmode/test_pre_tool_use_hook.py
touches:
  - CLAUDE.md
  - docs/architecture.md
---

# INFRA-199 — Scope context-budget PreToolUse gate to pairmode build-cycle agent spawns

## Context

`hooks/pre_tool_use.py`'s Task/Agent branch calls `context_budget.decide()` for
*every* agent spawn, with no discrimination on the spawned subagent's type. Once
`context_current_tokens` accumulates past the overrun ceiling, that means a
general-purpose spawn — a Plan step, an Explore, a `general-purpose` helper
subagent — gets blocked with the CONTEXT BUDGET prompt exactly as a builder
spawn would. Worse, the block's turn-tracking acknowledgment (INFRA-192/193)
only clears on a genuine new `UserPromptSubmit`, so a same-turn retry of a
non-build-cycle spawn can never satisfy the gate: it is wedged until a human
takes a turn, even though the context-budget discipline was never meant to
govern these spawns.

The gate is only meaningful for the pairmode build cycle — the sequence of
builder/reviewer/loop-breaker/security-auditor/intent-reviewer spawns whose
context growth the budget model tracks. The fix keys the dispatch on the spawn
payload's `tool_input.subagent_type` field, gating only when that value is one
of the five build-cycle agent names and passing everything else through
untouched.

`tool_input.subagent_type` is the field the Task/Agent PreToolUse payload
carries to identify the *spawned* subagent's type (confirmed
`docs/architecture.md:530`: `Agent({..., subagent_type: "reviewer", ...})`).
This is a distinct mechanism from the top-level `agent_type` field the Read
branch's `cold_read_guard.py` consumes — that field identifies the *acting*
subagent context a Read is happening inside of. The two must not be conflated:
this story touches only the Task/Agent branch's new `subagent_type` condition
and leaves the Read branch and `cold_read_guard.py` entirely alone.

`context_budget.py`'s internal `decide()` / `should_block()` / turn-tracking
logic is unchanged — only the hook's dispatch condition narrows. CER-049's
dual-acceptance of both `Task` and `Agent` tool names is preserved: the new
`subagent_type` check is an additional AND condition, not a replacement of the
tool-name check.

The allowlist is added as a module-level constant so that when Era 003's
HARNESS-track leaf-worker agent types arrive (WORKER rail — gate, builder,
reviewer, security-auditor, intent-reviewer, loop-breaker, spec-writer as
agent-shell + skill), they can be enrolled in the gate by editing one line in
one place. No HARNESS-track names are added now — only the five agents that
exist in `.claude/agents/*.md` today.

## Ensures

1. **Allowlist gate on `subagent_type`.** `hooks/pre_tool_use.py`'s Task/Agent
   branch calls `context_budget.decide()` — and performs the resulting
   `context_budget_acknowledged_at` / `context_budget_acknowledged_user_turn_seq`
   state write — *only* when
   `data.get("tool_input", {}).get("subagent_type")` is one of the five
   build-cycle agent names. When `subagent_type` is absent, or is any value not
   in the allowlist, the branch passes through with **no** `context_budget`
   import/call, **no** block emission, and **no** state write — it reaches
   `sys.exit(0)` after the tool-name-plus-subagent_type check exactly as a
   non-matching tool name does today.

2. **CER-049 dual-acceptance preserved.** Both `"Task"` and `"Agent"` tool
   names still route into this branch. The `subagent_type` allowlist check is an
   additional AND condition on top of the existing `tool_name in ("Task",
   "Agent")` check — not a replacement of it. An allowlisted `subagent_type`
   gates identically under either tool name.

3. **Allowlist as a module-level constant.** The five build-cycle agent names
   live in a single module-level constant in `hooks/pre_tool_use.py` (e.g. a
   `frozenset` named `BUILD_CYCLE_SUBAGENTS`), not inlined in the branch
   condition, so a future WORKER-rail leaf-worker agent type (per Era 003
   HARNESS phases) can be enrolled by editing one line in one place. The
   constant contains exactly `builder`, `reviewer`, `loop-breaker`,
   `security-auditor`, `intent-reviewer` — **no** HARNESS-track agent names are
   added by this story.

4. **CLAUDE.md updated.** The Hook Performance checklist item 1
   ("Documented thin-delegation exceptions") Task/Agent → `context_budget.py`
   bullet states that the dispatch is additionally scoped to `subagent_type` ∈
   {`builder`, `reviewer`, `loop-breaker`, `security-auditor`,
   `intent-reviewer`}, and that general-purpose / Plan / Explore / other spawns
   are never gated.

5. **docs/architecture.md updated.** Wherever the Task/Agent PreToolUse
   `context_budget` dispatch is documented (the § Hook architecture bullet at
   `docs/architecture.md:997-1009`, and the one-line dispatcher summary at
   `docs/architecture.md:26`), the prose reflects the same `subagent_type`
   scoping: the gate fires only for the five build-cycle subagent types; other
   spawns pass through ungated.

6. **Tests.** `tests/pairmode/test_pre_tool_use_hook.py` gains cases covering:
   - (a) `subagent_type=builder` with context over threshold still emits the
     block decision (existing behavior preserved).
   - (b) `subagent_type=general-purpose` (and a Plan-type value, and
     `subagent_type` absent entirely) with context over threshold does **not**
     block, does **not** call `context_budget.decide` (verified via a spy /
     mock module on `PYTHONPATH`), and does **not** write
     `context_budget_acknowledged_at` / `context_budget_acknowledged_user_turn_seq`
     to `state.json`.
   - (c) each of `reviewer`, `loop-breaker`, `security-auditor`,
     `intent-reviewer` still gates (block emitted) — parametrized or individual
     cases.
   - (d) both `"Task"` and `"Agent"` tool_name values still gate correctly for
     an allowlisted `subagent_type`.

7. `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- In `hooks/pre_tool_use.py`, add a module-level constant near `PLUGIN_ROOT`
  (top of the file, before `main()`):

  ```python
  # Build-cycle subagent types the context-budget gate governs (INFRA-199).
  # The gate models context growth across the pairmode build loop only; a
  # general-purpose / Plan / Explore spawn must never be blocked. Future
  # Era-003 WORKER-rail leaf-worker types are enrolled by adding one line here.
  BUILD_CYCLE_SUBAGENTS = frozenset({
      "builder",
      "reviewer",
      "loop-breaker",
      "security-auditor",
      "intent-reviewer",
  })
  ```

- Narrow the Task/Agent branch guard. The branch must still be entered on
  `tool_name in ("Task", "Agent")` (CER-049 unchanged), but the
  `context_budget` import/call and the acknowledgment state write must be gated
  on `subagent_type` membership. Concretely, read
  `subagent_type = data.get("tool_input", {}).get("subagent_type")` inside the
  branch and, when `subagent_type not in BUILD_CYCLE_SUBAGENTS`, fall straight
  through to `sys.exit(0)` without importing `context_budget`, without calling
  `decide()`, without emitting a block, and without touching `state.json`. Keep
  the existing block/state-write path unchanged for the
  allowlisted case, including the single `write_text()` covering both
  `context_budget_acknowledged_at` and `context_budget_acknowledged_user_turn_seq`.
  Do not restructure the Edit/Write or Read branches.

- Update the module docstring's Task/Agent bullet to note the additional
  `subagent_type` allowlist gate (one line), consistent with the CLAUDE.md and
  architecture.md prose.

- In `CLAUDE.md`, under Review checklist item 1 "HOOK PERFORMANCE" →
  "Documented thin-delegation exceptions", amend the
  `Task` / `Agent` → `context_budget.py` bullet and the
  Task/Agent dispatch paragraph to state that the gate
  is additionally scoped to `subagent_type` ∈ {`builder`, `reviewer`,
  `loop-breaker`, `security-auditor`, `intent-reviewer`}, and that
  general-purpose / Plan / Explore / other spawns are never gated. Do not
  change the `Edit`/`Write`, `Read`, `post_tool_use.py`, `session_start.py`, or
  `user_prompt_submit.py` descriptions.

- In `docs/architecture.md`, update the § Hook architecture Task/Agent bullet
  and the top-of-file one-line dispatcher summary (line 26) to
  document the `subagent_type` allowlist scoping. Keep the existing INFRA-182 /
  CER-049 framing intact; add the scoping as an additional qualifier, not
  a rewrite.

- In `tests/pairmode/test_pre_tool_use_hook.py`, add the cases enumerated in
  Ensures item 6. For the "does not call decide" assertion (case b), reuse the
  existing spy pattern already present in the test file for degrade-safely
  cases: put a stub `context_budget.py` on
  `PYTHONPATH` whose `decide()` records that it was called (e.g. writes a
  sentinel the test can inspect, or raises) and assert the hook produced empty
  stdout and left `state.json` free of the two acknowledgment keys — proving the
  branch short-circuited before importing/calling `context_budget`. Existing
  Task/Agent block/pass tests should be updated to pass an
  allowlisted `subagent_type` (e.g. `builder`) in their `tool_input`, since
  those assert the gate fires.

- Do not touch `context_budget.py`, `cold_read_guard.py`, `scope_guard.py`,
  `post_tool_use.py`, or the Read/Edit/Write branches. Do not add any
  HARNESS-track agent names to `BUILD_CYCLE_SUBAGENTS`.

## Tests

`story_class: code` — new logic in the hook's dispatch condition, covered by new
cases in `tests/pairmode/test_pre_tool_use_hook.py` (Ensures item 6). Run the
full gate:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

### Out of scope

- Changing `context_budget.py`'s internal `decide()` / `should_block()` /
  turn-tracking logic (INFRA-193). The gate's *decision* is unchanged; only
  *whether the hook consults it* narrows.
- Any change to the Read branch or `cold_read_guard.py`, or to the top-level
  `agent_type` field it consumes. `agent_type` (acting-context identity) and
  `tool_input.subagent_type` (spawned-agent identity) are distinct fields and
  distinct mechanisms.
- Adding HARNESS-track / WORKER-rail agent names (gate, spec-writer, or the
  leaf-worker conversions of the existing five) to the allowlist. The constant
  is structured so those can be added later in one line, but this story adds
  only the five agents that exist today.
- Changing CER-049's dual-acceptance of the `Task` / `Agent` tool names.
