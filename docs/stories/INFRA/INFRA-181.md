---
id: INFRA-181
rail: INFRA
title: "Revert Phase 72 JSONL additions; restore /context + set-context-tokens Context gate"
status: complete
phase: "73"
story_class: code
primary_files:
  - skills/pairmode/scripts/context_budget.py
  - tests/pairmode/test_context_budget.py
  - tests/pairmode/test_templates.py
touches:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - CLAUDE.md
  - docs/architecture.md
  - README.md
---

# INFRA-181 — Revert Phase 72 JSONL additions; restore `/context` + `set-context-tokens` Context gate

**Phase:** 73
**Rail:** INFRA

## Background

Phase 72 (INFRA-179) added three functions to `context_budget.py`
(`_derive_transcript_path`, `compute_context_tokens`, `read_current_tokens`) and wired
a JSONL-first enforcement path into `decide()`. The premise — that JSONL is a reliable
live token source — was incorrect: the last assistant entry in the transcript lags the
current context window and can silently produce a stale count without triggering
CONTEXT CHECK REQUIRED.

INFRA-180 replaced the JSONL path with the per-story dict gate. The three JSONL
functions are now dead code. This story removes them and restores the documentation
surface (CLAUDE.build.md, template, CLAUDE.md, architecture.md, README.md) to
accurately reflect the architecture after INFRA-180.

The Context gate in CLAUDE.build.md is also restored to the Phase 70/71 design: the
orchestrator calls `/context` before each story, records via `set-context-tokens`, and
the hook enforces the gate using the dict entry. The hook failing closed when the dict
entry is absent (INFRA-180) is what makes the system systematic — the orchestrator's
lapses become hard stops, not silent passes.

## Protected-file modification statements

- `CLAUDE.md`: update the `hooks/pre_tool_use.py` carve-out in HOOK PERFORMANCE check
  to remove references to `read_current_tokens` and `session_id`; describe the single
  `decide(story_id=...)` call and the `context_budget_acknowledged_at`-only state write.
- `CLAUDE.build.md`: restore the Context gate section to call `/context` and run
  `set-context-tokens`; update the `## Context budget check (between stories)` section
  to describe the dict-based enforcement (INFRA-180 architecture).
- `skills/pairmode/templates/CLAUDE.build.md.j2`: mirror all CLAUDE.build.md changes,
  replacing hardcoded paths with `{{ pairmode_scripts_dir }}`.

## Acceptance criteria

### `skills/pairmode/scripts/context_budget.py`

Remove the following entirely (introduced in Phase 72 / INFRA-179):
- `_derive_transcript_path(cwd, session_id, home)`
- `compute_context_tokens(transcript_path)`
- `read_current_tokens(project_dir, session_id, home)`

The `decide()` signature after INFRA-180 is:
```python
def decide(project_dir: Path, story_id: str = "", flex_factor: float = 1.0) -> dict | None:
```
No further changes to `decide()` in this story — INFRA-180 already removed the JSONL
waterfall.

Update the module-level docstring to reflect:
- `decide()` accepts `story_id` and reads from `context_story_tokens` dict first,
  then falls back to the scalar for backwards compat.
- `read_context_tokens_from_state()` is the sole token source for `decide()`.
- The hook (`pre_tool_use.py`) passes `story_id` from `state["current_story"]["id"]`.
- `set-context-tokens` is the sole writer of `context_story_tokens` entries.

---

### `CLAUDE.build.md`

#### Replace `### Context gate`

```markdown
### Context gate

Before any other action for this story, call `/context` and read the current token count.

The threshold is the value of `context_budget_threshold` in `.companion/state.json`
(default: 120,000 if the key is absent or the file does not exist).

Output: `CONTEXT: [N] / [threshold] tokens`

Then record the count for this story:
    PATH=$HOME/.local/bin:$PATH uv run python <pairmode_scripts_dir>/flex_build.py \
      set-context-tokens --tokens N --project-dir .
Replace N with the integer token count from /context. This writes the count into
`state["context_story_tokens"][story_id]` so the hook can enforce the gate on the
next spawn.

Then call:
    PATH=$HOME/.local/bin:$PATH uv run python <pairmode_scripts_dir>/flex_build.py \
      story-cost-estimate --story-id RAIL-NNN --project-dir .

Display its output verbatim. If the estimate is numeric and `threshold - N` is less
than the estimate, append:
    Estimated story cost exceeds remaining headroom; consider /clear before proceeding.
The estimate is informational — it does not block.

Continue to the pre-story schema gate.

Note: the `pre_tool_use.py` hook reads `state["context_story_tokens"][story_id]`
before every Task/Agent spawn. If the entry is absent (orchestrator skipped
`set-context-tokens`) or was recorded before the last `/clear`
(`context_session_reset_at`), the hook blocks with CONTEXT CHECK REQUIRED.
The hook is the sole budget enforcer.
```

(In the `.j2` template, replace `<pairmode_scripts_dir>` with
`{{ pairmode_scripts_dir }}`.)

#### Replace `## Context budget check (between stories)`

```markdown
## Context budget check (between stories)

**Enforcer:** `hooks/pre_tool_use.py` (matcher `Task|Agent`) delegates to
`skills/pairmode/scripts/context_budget.py`. On every subagent spawn, the hook:

1. Reads `state["current_story"]["id"]` to get the active story ID.
2. Looks up `state["context_story_tokens"][story_id]` — the count the orchestrator
   recorded via `set-context-tokens` at the Context gate step above.
3. Validates the entry is fresh: `entry["recorded_at"]` must post-date
   `state["context_session_reset_at"]` (written by the SessionStart hook on
   `clear`/`startup`). An entry older than the last session reset is stale.
4. If the entry is missing or stale: blocks with CONTEXT CHECK REQUIRED.
   The orchestrator must call `/context` and run `set-context-tokens` for the
   current story before the spawn can proceed.
5. If entry is fresh: checks whether `tokens + estimated_next_step > threshold ×
   (1 + overrun_pct)` (defaults: 120,000 × 1.10 = 132,000). Blocks when exceeded.

The per-story dict preserves the full session history of token counts — visible in
`.companion/state.json["context_story_tokens"]`. A /clear is visible as a lower count
for the same story ID on the subsequent run (the entry is overwritten when the
orchestrator re-records after the clear).

`set-context-tokens` is the sole writer of `context_story_tokens` entries.
The SessionStart hook writes `context_session_reset_at` on `clear`/`startup`.

Canonical prompt body (source of truth:
`tests/pairmode/fixtures/context_budget_prompt.txt`, reproduced
here for in-doc readability):

````
CONTEXT BUDGET — [story RAIL-NNN] just completed.
Context is at approximately [N] tokens (threshold: [T], overrun: [O]).
Estimated next step: ~[E] tokens — [R] tokens remaining before ceiling.

Continuing risks context compaction mid-story. Options:

1. **Proceed** — continue building in this session; budget acknowledged.
   Say: "Continue building"

2. **Clear and resume** — run /clear, then in the fresh session:
   Say: "Continue building Phase X from story RAIL-NNN"
````

Response handling:
- "Continue building" → `context_budget.decide()` has already
  written `state["context_budget_acknowledged_at"]`. Re-prompt is
  suppressed until tokens cross
  `acknowledged_at + state["context_budget_reprompt_margin"]`
  (default 10,000).
- "Clear and resume" → user types `/clear`; the SessionStart hook writes a fresh
  `context_session_reset_at`, invalidating pre-clear dict entries. The orchestrator
  calls `/context` and `set-context-tokens` in the resumed session to record a
  fresh entry for the story.

Tunables (all in `.companion/state.json`):
`context_budget_threshold`, `context_budget_overrun_pct`,
`expected_step_tokens` (seeded prior; replaced by the per-phase
effort.db median once ≥5 attempts accumulate),
`context_budget_reprompt_margin`.
```

---

### `CLAUDE.md`

Replace the `hooks/pre_tool_use.py` carve-out in the HOOK PERFORMANCE check (the
block starting "`hooks/pre_tool_use.py` is a thin dispatcher") with:

```
`hooks/pre_tool_use.py` is a thin dispatcher for two tool types:

- `Task` / `Agent` → `skills/pairmode/scripts/context_budget.py`
  (CER-027 context-budget enforcement; both tool names accepted — CER-049)
- `Edit` / `Write` → `skills/pairmode/scripts/scope_guard.py`
  (Phase 55 story file-scope enforcement)

For the `Task`/`Agent` dispatch: one tool-name check, one delegated module call
(`decide(story_id=...)` for the block decision — reads `context_story_tokens[story_id]`
from state.json), one stdout emit. All domain logic lives in the named module, NOT
in the hook. The Task branch has one state-write path: `context_budget_acknowledged_at`
when blocking (single `write_text()` call). `set-context-tokens` (not the hook) is
the sole writer of `context_story_tokens` entries.

For the `Edit`/`Write` dispatch: one tool-name check, one delegated module call,
one stdout emit. The Edit/Write branch is read-only.
```

---

### `docs/architecture.md`

Update the following sections to reflect the INFRA-180/181 architecture:

**Section 9 "Context budget check":** The module reads the token count from
`state["context_story_tokens"][story_id]` (written by `set-context-tokens` from the
orchestrator's per-story `/context` call). Falls back to the scalar
`context_current_tokens` when `story_id` is empty. If the dict entry is absent or
predates `context_session_reset_at`, blocks with CONTEXT CHECK REQUIRED. Remove all
references to JSONL reading and `read_current_tokens`. Remove references to
`session_id` parameter. Update the reference list to include INFRA-180.

**Section "Hook architecture" — `Task`/`Agent` bullet:** single `decide(story_id=...)`
call; state write is `context_budget_acknowledged_at` only (on block). Remove
`read_current_tokens`, `session_id`, and JSONL references. Add INFRA-180 to reference
list.

**Section "Companion data files":**
- `context_story_tokens`: new entry — dict keyed by story ID;
  written by `flex_build.py set-context-tokens`; read by `context_budget.decide()`;
  entries validated against `context_session_reset_at`.
- `context_session_reset_at`: new entry — written by `session_start.py` on
  `clear`/`startup` via `session_reset.decide_reset()`; used by `_is_entry_fresh()`
  to detect pre-clear dict entries.
- `context_current_tokens`: update description — now a display-only scalar kept for
  backwards compat with sibling-project CLAUDE.build.md files; `set-context-tokens`
  still writes it alongside the dict entry; not read by the hook or `decide()`.
- `context_current_tokens_recorded_at`: update description similarly.
- Remove all references to JSONL, `read_current_tokens`, `session_id` from the
  context-budget subsections.

---

### `README.md`

Update the Context gate paragraph (step 2 of the pairmode build loop) to describe
the `/context` + `set-context-tokens` + dict-based hook enforcement:

```
2. **Context gate.** Before the next builder spawns, the orchestrator calls `/context`
   to read the live token count and records it for the current story via
   `flex_build.py set-context-tokens`, which writes to
   `state["context_story_tokens"][story_id]`. On session start after a `/clear`
   (or a fresh `startup`), the SessionStart hook writes `context_session_reset_at` so
   pre-clear dict entries are detected as stale.
   The hook is the sole budget enforcer: `hooks/pre_tool_use.py` intercepts every
   Agent spawn, looks up the current story's dict entry, validates it post-dates the
   last session reset, and blocks if the entry is absent, stale, or the projected token
   total exceeds the overrun ceiling (`threshold × 1.10`, default 132k). If the
   orchestrator skipped `set-context-tokens`, the hook blocks with
   CONTEXT CHECK REQUIRED — the orchestrator's lapse becomes a hard stop.
```

---

### `tests/pairmode/test_context_budget.py`

Remove all tests added in Phase 72 for `_derive_transcript_path`,
`compute_context_tokens`, and `read_current_tokens` (these functions no longer exist).

Update `test_templates.py` to check for the restored Context gate text (the
`/context` call and `set-context-tokens` step) rather than the Phase 72
display-only text.

## Implementation notes

- INFRA-180 must be committed before this story is built. This story only removes
  dead JSONL code and updates documentation — it does not touch enforcement logic.
- The `test_templates.py` test update is the most likely source of builder error:
  ensure the template text assertions match the exact wording in the `.j2` file after
  INFRA-180's hook-description changes are applied.
- `docs/architecture.md` has three separate subsections to update (§9, Hook
  architecture, Companion data files); the builder should update all three in a single
  pass to avoid partial-update failures at review.
