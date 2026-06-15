---
id: BUILD-029
rail: BUILD
title: "Remove `bump-context-tokens` from orchestrator build loop"
status: planned
phase: "70"
story_class: methodology
primary_files:
  - CLAUDE.build.md
touches:
  - docs/architecture.md
  - README.md
---

# BUILD-029 — Remove `bump-context-tokens` from orchestrator build loop

## Context

The build loop contains two `bump-context-tokens --cost [total_tokens]` calls:
one after the builder returns (Step 1) and one after the reviewer returns (Step 2).
These were added in Phase 65 (BUILD-027 / CER-045) to keep `context_current_tokens`
current between stories so the context gate has a non-stale value to evaluate.

The cost input is `total_tokens` from the subagent's `<usage>` block. This is wrong:
subagents (builder, reviewer) start fresh with only the story ID. Their `total_tokens`
reflects the subagent's own internal context (50–90k each), not what gets added to the
orchestrator's context window (which grows only by the compact SUMMARY + BUILD-RESULT
the subagent returns). Bumping by subagent totals inflates `context_current_tokens`
by ~50–90k per spawn, producing values of 300k+ when the real orchestrator context
is ~60k. This causes false budget blocks.

There are two distinct token-tracking processes:
1. **Metric collection** — `record_attempt.py` feeds `effort.db` with per-story token
   costs for cost estimation and the effort guardrail. `total_tokens` feeds this correctly.
2. **Orchestrator context management** — `context_current_tokens` in `state.json`, read
   by the hook before every agent spawn. Should reflect the orchestrator's actual context.

The bump calls conflate these two by writing metric data into the context management key.

The correct sources for `context_current_tokens` are:
- **SessionStart hook** — resets to baseline on `clear`/`startup` (Phase 68 INFRA-175)
- **`set-context-tokens`** — user runs `/context`, reads the integer, calls
  `flex_build.py set-context-tokens --tokens N`. This is the authoritative write.

When `context_current_tokens` is absent or stale (TTL: 60 minutes), `context_budget.py`
already fires `CONTEXT CHECK REQUIRED`, which prompts the user to run `/context` and
call `set-context-tokens`. That path is correct and sufficient.

## Acceptance criteria

1. `CLAUDE.build.md` Step 1 (after builder): the `bump-context-tokens --cost [total_tokens]`
   call and its surrounding comment are removed. `record_attempt.py` call is untouched.

2. `CLAUDE.build.md` Step 2 (after reviewer): same — the `bump-context-tokens` call and
   its comment are removed. `record_attempt.py` call is untouched.

3. `CLAUDE.build.md` "Context budget check (between stories)" section: the claim that
   `bump-context-tokens` is the primary writer of `context_current_tokens` is removed.
   The section accurately describes the two authoritative sources: SessionStart hook reset
   and user-driven `set-context-tokens`.

4. `docs/architecture.md` § 9 "Context budget check": the phrase
   "accumulated by `flex_build.py bump-context-tokens` after each builder and reviewer spawn"
   is removed. The description correctly attributes `context_current_tokens` to the
   SessionStart hook reset and `set-context-tokens`.

5. `docs/architecture.md` `context_current_tokens` state.json key description (≈ line 798):
   `bump-context-tokens` is no longer listed as the "primary writer". The description
   reflects: SessionStart hook reset (primary), `set-context-tokens` (user-driven recovery),
   bootstrap seed of `1` (fallback only).

6. `docs/architecture.md` `context_current_tokens_recorded_at` description (≈ line 817):
   `bump-context-tokens` is removed from the list of writers; only `set-context-tokens`
   and `session_start.py` remain.

7. `README.md` line ≈ 181: any reference to `bump-context-tokens` as a writer of
   `context_current_tokens` is corrected to reflect SessionStart + `set-context-tokens`.

8. `flex_build.py bump-context-tokens` command and its tests are NOT removed —
   the command may have standalone uses. Only the orchestrator protocol calls are removed.

## Implementation guidance

### CLAUDE.build.md — Step 1 removal

Find the block after `record_attempt.py` in Step 1 that reads:

```
Advance the per-session context estimate by this story's actual builder cost (CER-045):

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
  bump-context-tokens --cost [total_tokens] --project-dir .
```

Where `[total_tokens]` is the value extracted from the builder's `<usage>` block.
`bump-context-tokens` no-ops silently when state.json is absent.
```

Remove this entire block (paragraph + code fence + trailing sentence).

### CLAUDE.build.md — Step 2 removal

Find the block after `record_attempt.py` in Step 2 that reads:

```
Advance the per-session context estimate by the reviewer's cost (CER-045):

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
  bump-context-tokens --cost [total_tokens] --project-dir .
```

Where `[total_tokens]` is the value extracted from the reviewer's `<usage>` block.
Each Task's cost is bumped individually; the accumulated total reflects both builder
and reviewer costs per story.
```

Remove this entire block.

### CLAUDE.build.md — Context budget check section

The section currently opens with:

> **Primary gate:** The accumulated `context_current_tokens` value in state.json
> (see `### Context gate` above) is the authoritative check. It is maintained by
> `bump-context-tokens` after each builder and reviewer spawn and is evaluated
> before any agent spawns.

Replace with:

> **Primary gate:** The accumulated `context_current_tokens` value in state.json
> (see `### Context gate` above) is the authoritative check. It is written by the
> SessionStart hook on `clear`/`startup` (baseline reset) and by `set-context-tokens`
> when the user runs `/context` and records the current count. The hook enforces
> `CONTEXT CHECK REQUIRED` when the value is absent or stale (TTL: 60 minutes).

Also update the secondary fallback paragraph: the matcher reference should say
`Task|Agent` (not `Task`) to reflect the CER-049 fix.

### docs/architecture.md

Three targeted edits:

**Edit 1** — § 9 sentence starting "The module reads `state["context_current_tokens"]`
(accumulated by `flex_build.py bump-context-tokens` after each builder and reviewer
spawn; anchored at session start or after `/clear` via `flex_build.py set-context-tokens`)":

Replace parenthetical with:
"(written by the SessionStart hook reset on `clear`/`startup` and by `flex_build.py
set-context-tokens` when the operator runs `/context` and records the current count)"

**Edit 2** — state.json `context_current_tokens` key description. Remove:
"Written by `flex_build.py bump-context-tokens --cost N` after each builder and
reviewer spawn (primary writer);"

Update to lead with:
"Written by the SessionStart hook (`session_start.py`) on `clear`/`startup` (primary
reset) and by `flex_build.py set-context-tokens --tokens N` for manual recovery after
`/clear` or when `CONTEXT CHECK REQUIRED` fires;"

**Edit 3** — `context_current_tokens_recorded_at` description. Remove `bump-context-tokens`
from the list of writers. Only `set-context-tokens` and `session_start.py` remain.

### README.md

Locate any sentence that describes `bump-context-tokens` as the primary writer of
`context_current_tokens`. Replace with a description of SessionStart + `set-context-tokens`.

## Tests

This is a methodology story — changes are to CLAUDE.build.md, docs/architecture.md, and
README.md only. No Python logic is modified.

Verification:
- `grep -n "bump-context-tokens" CLAUDE.build.md` should show only the command
  description in the "Context budget check" section (if any reference remains there
  for documentation), but no `--cost [total_tokens]` invocations.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` must pass
  (no code changes, but confirm nothing broke).
