---
id: BUILD-029
rail: BUILD
title: "Restore per-story `/context` call in Context gate; remove `bump-context-tokens`"
status: planned
phase: "70"
story_class: methodology
primary_files:
  - CLAUDE.build.md
touches:
  - docs/architecture.md
  - README.md
---

# BUILD-029 — Restore per-story `/context` call in Context gate; remove `bump-context-tokens`

## Context

BUILD-027 (Phase 65, CER-045) replaced the Context gate's direct `/context` call with
reading `context_current_tokens` from state.json, and introduced `bump-context-tokens`
to keep that stored value current by adding subagent `total_tokens` after each builder
and reviewer spawn.

This design has two flaws:

**Flaw 1 — Wrong input to bump.** Subagents (builder, reviewer) start fresh with only
the story ID. Their `total_tokens` is their own internal context cost — not the growth
of the orchestrator's context window. Bumping by 50–90k per spawn inflates
`context_current_tokens` to 300k+ when the real orchestrator context is ~60–80k.
False budget blocks result.

**Flaw 2 — Wrong gate design.** The pre-story Context gate is a synchronous, real-time
decision: "we're about to build — do we have room?" It doesn't need a stored value or
a TTL. It needs the live count right now. BUILD-027 introduced TTL-based staleness
logic into what should be a direct snapshot check.

The correct design (pre-BUILD-027):
- **Context gate** (before each story): call `/context`, read N, compare to threshold.
  If room: record N via `set-context-tokens` for the hook to use during spawns, then proceed.
  If at threshold: stop.
- **Hook** (PreToolUse, before each Agent spawn): reads `context_current_tokens` from
  state.json — the value the Context gate just wrote. TTL is appropriate here because the
  hook fires many times within a story and you don't want a live `/context` call on every
  spawn. The TTL guards against the hook seeing a value from a previous session.
- **bump-context-tokens**: not called anywhere in the build loop. The build loop has
  no good proxy for the orchestrator's per-spawn context growth. Don't guess.

## Acceptance criteria

### `CLAUDE.build.md` — Context gate

1. The `### Context gate` section opens with a `/context` call, not a state.json read.
   The gate reads the live token count and compares it to the threshold.

2. The **below-threshold** path records the live count via `set-context-tokens` before
   proceeding, so the hook has an accurate value for the builder and reviewer spawns:

   ```
   Then record the count for the hook gate:
     PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
       set-context-tokens --tokens [N] --project-dir .
   Replace [N] with the integer count from /context.
   ```

3. The **at/above-threshold** path blocks and outputs `THRESHOLD REACHED` — unchanged
   from the current text.

4. The CONTEXT CHECK REQUIRED block is **removed** from the Context gate. It is no longer
   needed here: the gate calls `/context` directly and always has a live value. (The hook
   still emits CONTEXT CHECK REQUIRED when its stored value is absent or stale — that
   path remains correct for the hook's role.)

5. The closing note on the hook's role is updated to reflect:
   "The `pre_tool_use.py` hook provides a secondary state.json-based check during the
   builder and reviewer spawns. The hook reads `context_current_tokens` written by the
   `set-context-tokens` step above. The `/context` call above is the primary gate and
   is authoritative."

### `CLAUDE.build.md` — Steps 1 and 2

6. The `bump-context-tokens --cost [total_tokens]` call and its surrounding comment are
   **removed** from Step 1 (after builder). The `record_attempt.py` call is untouched.

7. The same removal applies to Step 2 (after reviewer).

### `CLAUDE.build.md` — Context budget check (between stories)

8. The "Primary gate" paragraph no longer says the value is "maintained by
   `bump-context-tokens`." It accurately describes the gate as a per-story live
   `/context` call, with the hook as the secondary check during spawns.

9. The "Secondary fallback" paragraph's matcher reference is updated from `Task` to
   `Task|Agent` (CER-049 correction).

### `docs/architecture.md`

10. § 9 "Context budget check": the sentence describing `context_current_tokens` as
    "accumulated by `flex_build.py bump-context-tokens` after each builder and reviewer
    spawn" is replaced with: "written by `flex_build.py set-context-tokens` from the
    per-story Context gate's live `/context` read (primary) and by the SessionStart hook
    reset on `clear`/`startup` (session boundary)."

11. The state.json `context_current_tokens` key description (≈ line 798): remove
    "`flex_build.py bump-context-tokens --cost N` after each builder and reviewer spawn
    (primary writer)." Update to: the Context gate's `set-context-tokens` call (per
    story, primary write) and the SessionStart hook reset (session boundary).

12. The `context_current_tokens_recorded_at` description (≈ line 817): remove
    `bump-context-tokens` from the writers list. Writers: `set-context-tokens`
    (from the Context gate) and `session_start.py` (SessionStart reset).

### `README.md`

13. Any description of `bump-context-tokens` as a writer of `context_current_tokens`
    is corrected to reflect the Context gate's per-story `set-context-tokens` call.

### Out of scope

14. `flex_build.py bump-context-tokens` command and its tests are NOT removed.
    Only the build loop invocations are removed.

15. The hook's CONTEXT CHECK REQUIRED path is NOT removed. It remains correct for
    the hook's role (fires when `context_current_tokens` is absent or stale, e.g.
    after a cold session start without a SessionStart event or a very long session
    that outlasts the TTL). The Context gate's per-story `/context` call prevents
    this path from being the common case.

## Implementation guidance

### Context gate replacement

The current Context gate (CLAUDE.build.md `### Context gate`) reads from state.json
and has a CONTEXT CHECK REQUIRED branch. Replace the entire section with the
pre-BUILD-027 design:

```
### Context gate

Before any other action for this story, call `/context` and read the current token count.

The threshold is the value of `context_budget_threshold` in `.companion/state.json`
(default: 120,000 if the key is absent or the file does not exist).

If the token count is **below** the threshold:
  Output: `CONTEXT: [N] / [threshold] tokens — proceeding`

  Then record the count for the hook gate:
    PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
      set-context-tokens --tokens [N] --project-dir .
  Replace [N] with the integer count from /context.

  Then call:
    PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
      story-cost-estimate --story-id RAIL-NNN --project-dir .

  Display its output verbatim. If the estimate is numeric and `threshold - N` is
  less than the estimate, append:
    Estimated story cost exceeds remaining headroom; consider /clear before proceeding.
  The estimate is informational — it does not block.

  Continue to the pre-story schema gate.

If the token count is **at or above** the threshold:
  Output:
    CONTEXT: [N] / [threshold] tokens — THRESHOLD REACHED
    Build paused. Please /clear then resume:
      "Continue building from story [RAIL-NNN]"
  Stop. Do not spawn any agent.

A "continue building" (or equivalent) instruction issued before this `/context`
call was made does not authorize proceeding. The token count is authoritative —
re-evaluate against it regardless of any prior instruction.

Note: `pre_tool_use.py` hook provides a secondary state.json-based check during
builder and reviewer spawns. The hook reads `context_current_tokens` written by
the `set-context-tokens` step above. The `/context` call above is the primary
gate and is authoritative.
```

### Step 1 and Step 2 — bump removal

Find and remove each block matching:

```
Advance the per-session context estimate by this story's actual builder cost (CER-045):

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
  bump-context-tokens --cost [total_tokens] --project-dir .
```

Where `[total_tokens]` is the value extracted from the builder's `<usage>` block.
`bump-context-tokens` no-ops silently when state.json is absent.
```

And the equivalent reviewer block in Step 2. Remove only these blocks; leave
all surrounding `record_attempt.py` text intact.

## Tests

Methodology story — changes to CLAUDE.build.md, docs/architecture.md, README.md only.

Verification:
```bash
# No bump invocations remain in the build loop
grep -n "bump-context-tokens" CLAUDE.build.md
# Should show zero results (or only within the "Context budget check" section
# where the command is described, not invoked)

# Test suite passes unchanged
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```
