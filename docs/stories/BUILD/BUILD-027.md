---
id: BUILD-027
rail: BUILD
title: "`CLAUDE.build.md` — accumulated context gate + bump-context-tokens in Step 6"
status: planned
phase: "65"
story_class: methodology
primary_files:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - /mnt/work/forqsite/CLAUDE.build.md
---

# BUILD-027 — CLAUDE.build.md: accumulated context gate + bump-context-tokens in Step 6

## Context

Part C of the Phase 65 fix. The Context gate currently says "call `/context` and
read the current token count, then call `set-context-tokens --tokens [N]`." Since
Claude cannot invoke `/context` programmatically, the orchestrator always estimates
(and estimates wrong). This story redesigns the gate to read the ACCUMULATED value
from state.json instead, and adds `bump-context-tokens` to Step 6 to maintain it.

Depends on INFRA-169 (`bump-context-tokens` command) and INFRA-170 (token count
persists across `story_context.py --clear`).

## Acceptance criteria

### Context gate section redesign

1. The gate no longer instructs the orchestrator to call `/context` as the primary
   action. Instead:

   **If `context_current_tokens` is present and non-stale in state.json:**
   - Output: `CONTEXT: [N] / [threshold] tokens — proceeding`
     (where N is read from state.json, not from /context)
   - Call `story-cost-estimate` and display verbatim
   - Check remaining headroom against estimate; append advisory if needed
   - Proceed to pre-story schema gate

   **If `context_current_tokens` is absent or stale:**
   - The `pre_tool_use.py` hook will emit CONTEXT CHECK REQUIRED on the first
     Task spawn, but the orchestrator should surface this proactively:
   - Output: `CONTEXT CHECK REQUIRED — no token count on record`
   - Instruct: "Run /context, then call: `flex_build.py set-context-tokens --tokens N`"
   - Do not spawn any agent until set-context-tokens has been called.

2. The `set-context-tokens` call is REMOVED from the normal (non-REQUIRED) gate body.
   It is only described in the CONTEXT CHECK REQUIRED path.

3. The gate note ("pre_tool_use.py hook provides a secondary check") is updated to
   reflect that the hook and the gate now both read the same accumulated value —
   they are no longer primary/secondary but co-equal checks of the same source.

4. The threshold check still works: if N ≥ threshold, output THRESHOLD REACHED and
   stop (unchanged behavior).

### Step 6 addition

5. Immediately after the `record_attempt.py` bash block and the "no-ops silently"
   prose, and BEFORE the guardrail call, insert:

   ```
   Advance the per-session context estimate by this story's actual cost (CER-045):

   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
     bump-context-tokens --cost [total_tokens] --project-dir .
   ```

   Where `[total_tokens]` is the value extracted from the builder's `<usage>` block.
   `bump-context-tokens` no-ops silently when state.json is absent.
   ```

6. The same bump call is NOT added for the reviewer's `record_attempt.py` block —
   only the builder's per-story cost is bumped. (The reviewer cost is part of the
   total story spend and is captured in the builder's `total_tokens` read during
   this session's context growth, which the hook accounts for via the accumulated total.)

   Actually: reviewer IS a separate Task spawn and its cost also grows orchestrator
   context. ADD the bump call to the reviewer block too, using the reviewer's
   `total_tokens`. Document: each Task's cost is bumped individually; the accumulated
   total reflects both builder + reviewer costs per story.

### Sync

7. The same gate redesign and Step 6 addition are applied to `forqsite/CLAUDE.build.md`
   at the equivalent locations.

8. `skills/pairmode/templates/CLAUDE.build.md.j2` receives the same edits.

## Implementation guidance

### Locating the targets

In `CLAUDE.build.md`:
- Context gate: lines ~339–384 (from "### Context gate" to "### Pre-story schema gate")
- Step 6 builder record_attempt section: after the "no-ops silently" prose at ~line 567,
  before "After recording the attempt, run the real-time effort guardrail" at ~line 569
- Step 6 reviewer record_attempt section: after the parallel "no-ops silently" prose
  for the reviewer's record_attempt call

### New Context gate prose (replace the existing block)

```
### Context gate

Before any other action for this story, check the accumulated context estimate.

Read `context_current_tokens` from `.companion/state.json`.

**If the key is present and non-stale:**
  Output: `CONTEXT: [N] / [threshold] tokens — proceeding`
  (N is the value from state.json. Threshold default: 120,000.)

  Then call:
    PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
      story-cost-estimate --story-id RAIL-NNN --project-dir .

  Display its output verbatim. If the estimate is numeric and `threshold - N` is less
  than the estimate, append:
    Estimated story cost exceeds remaining headroom; consider /clear before proceeding.
  The estimate is informational — it does not block.

  If N is **at or above** threshold:
    Output:
      CONTEXT: [N] / [threshold] tokens — THRESHOLD REACHED
      Build paused. Please /clear then resume:
        "Continue building from story [RAIL-NNN]"
    Stop. Do not spawn any agent.

**If the key is absent or stale (CONTEXT CHECK REQUIRED):**
  Output:
    CONTEXT CHECK REQUIRED — no accumulated token count on record.
    Run /context, read the current token count, then call:
      PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
        set-context-tokens --tokens N --project-dir .
    Replace N with the integer count from /context. Then re-run this story's Context gate.
  Stop. Do not spawn any agent until set-context-tokens has been called.

Note: `pre_tool_use.py` hook also reads `context_current_tokens` from state.json on
every Task spawn — same source, same result. The hook and this gate are co-equal checks
of the accumulated value.
```
