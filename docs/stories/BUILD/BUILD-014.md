---
id: BUILD-014
rail: BUILD
title: /context inline gate
status: planned
phase: "52"
story_class: methodology
primary_files:
  - CLAUDE.build.md
  - CLAUDE.build.md.j2
touches: []
---

# BUILD-014 — /context inline gate

## Background

The existing context budget gate (`pre_tool_use.py` → `context_budget.py`)
reads token counts from the transcript JSONL file. In practice this approach
has proven unreliable: the 50-line tail read misses the relevant assistant
message in busy sessions (returning `None` → silent pass-through), and the
transcript value is always at least one turn stale. A confirmed failure mode
produced an 80k-token overshoot past the intended 150k degradation threshold.

The correct source of truth is `/context`, which reads directly from the
Claude Code runtime. The orchestrator can call `/context` itself — it is not
a tool call that routes through the hook system, it is a slash command whose
output is visible inline. An orchestrator instructed to call it before each
story spawn reads an authoritative value and can make a reliable stop/proceed
decision.

The transcript-based `pre_tool_use.py` hook is retained as a belt-and-suspenders
fallback. The inline `/context` check is the primary gate.

## Ensures

- `CLAUDE.build.md` per-story loop opens with a `/context` gate step before
  any other action (before `write-permissions`, before spawning the builder).
- The gate step specifies: call `/context`, read the token count, compare
  against `context_budget_threshold` from `.companion/state.json`
  (default 120,000 if absent).
- If below threshold, the orchestrator outputs:
  ```
  CONTEXT: [N] / [limit] tokens — proceeding
  ```
  and continues.
- If at or above threshold, the orchestrator outputs:
  ```
  CONTEXT: [N] / [limit] tokens — THRESHOLD REACHED
  Build paused. Please /clear then resume:
    "Continue building from story [RAIL-NNN]"
  ```
  and stops. It does not spawn any agent.
- `CLAUDE.build.md.j2` is updated to match.
- The `pre_tool_use.py` hook is explicitly noted in `CLAUDE.build.md` as a
  secondary fallback, not the primary gate.

## Out of scope

- Removing or modifying `pre_tool_use.py` or `context_budget.py`.
- Any automated `/clear` trigger (requires external orchestration outside
  Claude Code's session model).
- Changes to the checkpoint context health check (step 7.5).

## Instructions

### 1. Add context gate to `CLAUDE.build.md` per-story loop

Insert as the first step in "Build loop (repeat for each story)", before
"Pre-story schema gate":

```markdown
### Context gate

Before any other action for this story, call `/context` and read the
current token count.

Read `context_budget_threshold` from `.companion/state.json`
(default: 120,000 if the key is absent or the file does not exist).

If the token count is **below** the threshold:
  Output: `CONTEXT: [N] / [threshold] tokens — proceeding`
  Continue to the pre-story schema gate.

If the token count is **at or above** the threshold:
  Output:
    CONTEXT: [N] / [threshold] tokens — THRESHOLD REACHED
    Build paused. Please /clear then resume:
      "Continue building from story [RAIL-NNN]"
  Stop. Do not spawn any agent.

Note: the `pre_tool_use.py` hook provides a secondary transcript-based check
as a fallback. The inline `/context` call above is the primary gate and should
be treated as authoritative.
```

### 2. Update `CLAUDE.build.md.j2`

Mirror the context gate section in the Jinja2 template.

## Tests

`TEST RUN: methodology story — no logic module.`

Acceptance verified by: the `CONTEXT:` gate line appearing as the first output
of each story loop iteration in orchestrator output, and the build stopping with
the correct resume instruction when context exceeds threshold.
