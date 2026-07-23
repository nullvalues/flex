---
id: INFRA-241
rail: INFRA
title: Reconcile builder/reviewer spawn subagent_type contract with the context-budget gate allowlist
status: planned
phase: "98"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - hooks/pre_tool_use.py
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - .claude/agents/
touches:
  - CLAUDE.build.md
  - skills/pairmode/scripts/context_budget.py
  - tests/pairmode/test_pre_tool_use_scope_guard.py
  - tests/pairmode/test_context_budget.py
  - docs/architecture.md
---

## Context

`hooks/pre_tool_use.py:113-115` gates the context-budget check (INFRA-199) with an
exact-string match:

```python
subagent_type = data.get("tool_input", {}).get("subagent_type")
if subagent_type not in BUILD_CYCLE_SUBAGENTS:
    sys.exit(0)
```

`BUILD_CYCLE_SUBAGENTS` (`:53-60`) = `{"builder", "reviewer", "loop-breaker",
"security-auditor", "intent-reviewer"}`. This is intentional design, not an oversight
— the header comment (`:8-11,55-56`) explicitly names `general-purpose` as a type that
"must never be blocked."

But no custom agent type named `builder`, `reviewer`, `loop-breaker`,
`security-auditor`, or `intent-reviewer` is registered anywhere in this repo —
`.claude/agents/` contains only `reconstruction-agent.md` and `gate-worker.md`, since
HARNESS-002 deliberately retired the rendered per-role agent files in favor of shared
procedure skills loaded by generic thin shells. `CLAUDE.build.md`'s own
`spawn leaf-worker-for(a.action)` line (`:28,32`) defines no explicit `subagent_type`
mapping — confirmed this session: the two builder-equivalent spawns for INFRA-235 used
`subagent_type: "general-purpose"` (the Task/Agent tool's `subagent_type` must resolve
to something real, and nothing named `builder` exists to resolve to).

Result, confirmed by direct trace this session: `subagent_type not in
BUILD_CYCLE_SUBAGENTS` is true for every spawn following the currently-documented
process, the gate hits `sys.exit(0)` before `context_budget.decide()` ever runs, and
the context-budget PreToolUse gate — built specifically to govern build-cycle spawns —
has been fully decorative for every real build spawn since HARNESS-002. Not a partial
gap: total.

## Requires

- A decision on which side changes: register real custom agent types
  (`.claude/agents/builder.md`, etc.) that resolve `subagent_type` to those literal
  strings while still loading the shared procedure skill as their instruction body
  (preserves HARNESS-002's shared-procedure design, restores a matchable type string),
  versus changing `BUILD_CYCLE_SUBAGENTS`'s matching to key off something else the
  `general-purpose` spawn actually carries (the loaded procedure-skill path, a marker
  in the prompt). Prefer the former — it requires no change to the gate's already-tested
  matching logic and is a smaller diff — unless registering five thin agent files is
  judged to reintroduce the per-role-file duplication HARNESS-002 was trying to
  eliminate, in which case document that tradeoff explicitly before choosing the
  latter.

## Ensures

- After the fix, spawning a builder-equivalent worker for a real story cycle produces
  an observable `context_budget.decide()` invocation — verified either via a state.json
  side effect (e.g. `context_budget_acknowledged_at` updates on a block) or a test that
  stubs `decide()` and asserts it's called — for a spawn using whatever
  `subagent_type` value the fixed contract specifies.
- The gate remains a no-op for `general-purpose`, `Plan`, `Explore`, and any other
  non-build-cycle spawn — the existing allowlist behavior for those types is
  unchanged.
- `CLAUDE.build.md.j2`'s `spawn leaf-worker-for(a.action)` line is no longer ambiguous
  — it names the exact `subagent_type` to use per action (`spawn-builder` →
  `"builder"`, `spawn-reviewer` → `"reviewer"`, etc.), removing the interpretation gap
  that led to this session's `general-purpose` choice.
- `docs/architecture.md` updated to describe the resolved spawn contract.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` passes (run without
  `-x`; confirm only the known CER-070 environmental failure remains).

## Instructions

1. Make the explicit choice from Requires and document the reasoning in the commit
   message or a short architecture.md note.
2. If registering agent types: create thin `.claude/agents/{builder,reviewer,
   loop-breaker,security-auditor,intent-reviewer}.md` files whose entire body is the
   "Shell instruction" already documented in each corresponding `procedure.md` (load
   the procedure skill, execute for the given story ID) — no role logic duplicated
   into the agent file itself, preserving HARNESS-002's single-source-of-truth intent.
3. If changing the gate's matcher instead: update `context_budget.py`'s matching logic
   and add equivalent test coverage for the new signal.
4. Update `CLAUDE.build.md.j2`'s pseudocode to name the exact `subagent_type` per
   action.
5. Add the observable-invocation test described in Ensures.
6. Update `docs/architecture.md`.
7. Run the full test suite without `-x`; confirm only the known CER-070 failure
   remains.

## Out of scope

- Changing what `context_budget.decide()` actually does once invoked — this story only
  restores the invocation, not the budget logic itself.
- INFRA-236/237/238/239 — adjacent dead-wiring gaps, separate root causes.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental failure; new
coverage proves `context_budget.decide()` is actually invoked for a build-cycle spawn
under the fixed contract, and remains skipped for non-build-cycle spawn types.
