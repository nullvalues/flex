---
id: BUILD-030
rail: BUILD
title: "Propagate BUILD-029 Context gate fix into `CLAUDE.build.md.j2` template"
status: complete
phase: "71"
story_class: methodology
primary_files:
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
---

# BUILD-030 — Propagate BUILD-029 Context gate fix into `CLAUDE.build.md.j2` template

## Context

BUILD-029 (Phase 70) fixed the Context gate design in this project's own
orchestrator file `CLAUDE.build.md`: it restored the per-story live `/context`
call as the primary gate, removed the `CONTEXT CHECK REQUIRED` branch from the
gate (the hook still keeps its own copy), removed `bump-context-tokens --cost`
invocations from Step 1 and Step 2 of the build loop, and corrected the
"Context budget check" Primary gate paragraph and the Secondary fallback
matcher reference (`Task` → `Task|Agent`).

BUILD-029 did **not** update the Jinja2 template
`skills/pairmode/templates/CLAUDE.build.md.j2` that pairmode uses to generate
`CLAUDE.build.md` for sibling projects. The template still encodes the
pre-BUILD-029 design:

- `### Context gate` (≈ line 338) opens with `Read context_current_tokens from
  .companion/state.json` instead of a live `/context` call.
- The `CONTEXT CHECK REQUIRED` branch (≈ lines 369–376) is still present inside
  the Context gate section.
- `bump-context-tokens --cost [total_tokens]` is invoked after the builder
  spawn in Step 1 (≈ line 565) and after the reviewer spawn in Step 2
  (≈ line 696).
- The "Primary gate" paragraph in the "Context budget check" section
  (≈ lines 788–790) still says `context_current_tokens` is "maintained by
  `bump-context-tokens` after each builder and reviewer spawn."
- The "Secondary fallback" paragraph (same section) still describes the
  hook matcher as `Task` (not `Task|Agent`).

Consequence: any sibling project that runs
`pairmode_sync.py sync-build --apply` will see the template diff against its
locally-fixed `CLAUDE.build.md` and silently revert the file back to the broken
BUILD-027 design. The template must be updated to match the BUILD-029 outcome
so that `sync-build` is a no-op for an up-to-date sibling and an upgrade for a
stale one.

This story is methodology-only: no Python logic changes, no hook changes.
`flex_build.py bump-context-tokens` stays where it is and its tests are
untouched. Only the template's invocations of that command (and the surrounding
gate prose) are corrected.

## Acceptance criteria

1. `CLAUDE.build.md.j2` `### Context gate` section opens with a `/context` call
   — the live token read — not a `Read context_current_tokens from state.json`
   instruction. The gate design mirrors the post-BUILD-029 `CLAUDE.build.md`
   Context gate verbatim: live `/context` read → record via
   `set-context-tokens` → below-threshold proceed (with `story-cost-estimate`
   informational call) / at-or-above-threshold block.

2. The `CONTEXT CHECK REQUIRED` branch is removed from the `### Context gate`
   section in the template. (The hook's own `CONTEXT CHECK REQUIRED` path in
   `context_budget.py` is untouched — it remains correct for the hook's role.)

3. The below-threshold path in the template gate records the live count via
   `set-context-tokens` before proceeding, so the hook has an accurate value
   during the builder and reviewer spawns that follow.

4. The `bump-context-tokens --cost [total_tokens]` block and its surrounding
   "Advance the per-session context estimate…" comment are removed from
   Step 1 (after builder) in the template. The `record_attempt.py` block in
   Step 1 is untouched.

5. The same removal applies to Step 2 (after reviewer): the
   `bump-context-tokens --cost [total_tokens]` block and surrounding comment
   are removed; the `record_attempt.py` block is untouched.

6. The "Primary gate" paragraph in the "Context budget check" section no
   longer says the value is "maintained by `bump-context-tokens` after each
   builder and reviewer spawn." It instead reads:
   "The per-story live `/context` call (see `### Context gate` above) is the
   authoritative check."

7. The "Secondary fallback" paragraph in "Context budget check" uses matcher
   `Task|Agent` (not `Task` alone) — matching CER-049 / BUILD-029 criterion 9.

8. `grep -n "bump-context-tokens" skills/pairmode/templates/CLAUDE.build.md.j2`
   returns zero matches inside the `### Context gate` section, Step 1, and
   Step 2. (The command name may still appear in the "Context budget check"
   description if it describes prior behavior — but it must not appear as an
   invoked command in those three sections.)

9. `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes
   unchanged. No Python logic was modified.

10. Running
    `PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/pairmode_sync.py sync-build --project-dir . --dry-run`
    in this flex project produces an empty diff (no changes). The template and
    the post-BUILD-029 live `CLAUDE.build.md` now agree on the Context gate,
    Step 1 / Step 2 bump removals, and the "Context budget check" Primary gate
    and Secondary fallback paragraphs.

### Out of scope

- `flex_build.py bump-context-tokens` command and its tests are NOT removed.
  Only the template invocations of that command are removed.
- No changes to `docs/architecture.md` or `README.md`. Those were updated by
  BUILD-029 and already describe the runtime behavior correctly.
- No changes to any hook (`pre_tool_use.py`, `context_budget.py`,
  `session_start.py`) or any Python script.
- No changes to `CLAUDE.build.md` (this project's own orchestrator file —
  already correct after BUILD-029).

## Implementation guidance

### Context gate replacement (≈ lines 338–388 of the template)

Replace the entire `### Context gate` section in
`skills/pairmode/templates/CLAUDE.build.md.j2` — from the `### Context gate`
heading up to (but not including) the next section heading — with the verbatim
BUILD-029 Context gate text:

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

If the template uses Jinja2 variables (e.g. `{{ flex_repo_root }}`) for the
`/mnt/work/flex` path, preserve the existing variable form rather than
hardcoding the absolute path. Otherwise leave the path literal as-is to match
BUILD-029's `CLAUDE.build.md`.

### Step 1 — bump removal (≈ line 565)

Locate the block in Step 1 that reads (approximately):

```
Advance the per-session context estimate by this story's actual builder cost (CER-045):

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
  bump-context-tokens --cost [total_tokens] --project-dir .
```

Where `[total_tokens]` is the value extracted from the builder's `<usage>` block.
`bump-context-tokens` no-ops silently when state.json is absent.
```

Remove the entire block — heading sentence, fenced code, and trailing
explanation — leaving the `record_attempt.py` block and any surrounding
prose intact.

### Step 2 — bump removal (≈ line 696)

Apply the same removal to the equivalent block in Step 2 (after reviewer).
Leave the reviewer's `record_attempt.py` block untouched.

### Context budget check — Primary gate and Secondary fallback (≈ lines 788–793)

Update the "Primary gate" paragraph to match the post-BUILD-029 wording:

```
**Primary gate:** The per-story live `/context` call (see `### Context gate`
above) is the authoritative check.
```

Update the "Secondary fallback" paragraph's matcher reference from `Task` to
`Task|Agent`:

```
**Secondary fallback:** Enforced mechanically by `hooks/pre_tool_use.py`
(matcher `Task|Agent`) …
```

Preserve any other content of the Secondary fallback paragraph not related to
the matcher name.

### Verifying parity with the live file

After the edits, run `pairmode_sync.py sync-build --dry-run --project-dir .`
from `/mnt/work/flex`. The expected outcome is an empty diff — confirming the
template renders to exactly the post-BUILD-029 `CLAUDE.build.md` in this
project, so applying sync to any sibling will not regress the gate.

## As-built note

The builder also updated the following template sections that were carrying
stale pre-BUILD-029 values, aligned to current architecture.md:

- Builder model decision table: `attempt` column added; threshold updated from
  `< 3` to `< 5` primary_files; `retry-upgrade` row added.
- Step 1 and Step 2 `record_attempt.py` examples: extended token flag set added
  (`--tokens-in`, `--tokens-out`, `--cache-read-tokens`, `--cache-write-tokens`).
- Retry path: instruction to re-call `select_builder_model` with `attempt_number=2`
  added before retry builder spawn.
- `build_command` and `test_command` blocks: `or` fallback for absent context keys.

None of these changes affect Python logic or hook behavior.

## Tests

Methodology story — only `skills/pairmode/templates/CLAUDE.build.md.j2`
changes. No Python tests are affected.

```bash
# Confirm no bump-context-tokens invocations remain in the template's build loop steps
# (Acceptance criterion 8.)
grep -n "bump-context-tokens" skills/pairmode/templates/CLAUDE.build.md.j2

# Confirm sync-build sees no diff (template matches live file)
# (Acceptance criterion 10.)
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/pairmode_sync.py \
  sync-build --project-dir . --dry-run

# Test suite passes unchanged
# (Acceptance criterion 9.)
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```
