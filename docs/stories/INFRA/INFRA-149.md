---
id: INFRA-149
rail: INFRA
title: "`CLAUDE.build.md` — record `/context` result to state.json in Context gate"
status: complete
phase: "58"
story_class: methodology
primary_files:
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - CLAUDE.build.md
touches: []
---

# INFRA-149 — `CLAUDE.build.md`: record `/context` result to state.json in Context gate

## Context

INFRA-148 introduces `flex_build.py set-context-tokens --tokens N` and redesigns
`context_budget.py` to read `state.json["context_current_tokens"]` instead of the broken
transcript-path approach. The hook now blocks any Task spawn when that key is absent.

This story closes the loop on the orchestrator side: the existing Context gate in CLAUDE.build.md
already calls `/context`; it now also writes the result to `state.json` so the secondary hook
gate has a valid token count on every subsequent Task spawn.

**Depends on INFRA-148** (the `set-context-tokens` CLI must exist before this story ships).

## Acceptance criteria

### `CLAUDE.build.md.j2` and `CLAUDE.build.md` — `### Context gate` section

1. Immediately after the line `Output: \`CONTEXT: [N] / [threshold] tokens — proceeding\``,
   add the following instruction and bash block:

   ```
   Then record the count for the secondary hook gate:
     PATH=$HOME/.local/bin:$PATH uv run python {{ flex_build_script }} \
       set-context-tokens --tokens [N] --project-dir .
   Replace [N] with the integer token count read from /context.
   ```

   In `CLAUDE.build.md.j2`, `{{ flex_build_script }}` is the Jinja2 variable for the
   flex_build.py path (check the template for the existing variable name; it is used elsewhere
   in the template). In `CLAUDE.build.md` (flex's own live file), use the hardcoded path
   `/mnt/work/flex/skills/pairmode/scripts/flex_build.py` consistent with adjacent bash blocks.

2. Update the closing note in `### Context gate` from:
   ```
   Note: the `pre_tool_use.py` hook provides a secondary transcript-based check
   as a fallback. The inline `/context` call above is the primary gate and should
   be treated as authoritative.
   ```
   to:
   ```
   Note: the `pre_tool_use.py` hook provides a secondary state.json-based check
   as a fallback. The hook reads `context_current_tokens` from `.companion/state.json`,
   written by the `set-context-tokens` step above. The inline `/context` call above
   is the primary gate and should be treated as authoritative.
   ```

3. No changes to the "threshold reached" branch, the `story-cost-estimate` call, or any
   other section of the gate.

### `CLAUDE.build.md.j2` and `CLAUDE.build.md` — `## Context budget check (between stories)` section

4. In the secondary-fallback description, update the phrase "transcript-based check" (or
   "transcript JSONL") to "state.json-based check" wherever it appears. No other prose changes.

### Manual propagation (orchestrator post-commit step — not builder acceptance)

5. The builder cannot reach `/mnt/work/forqsite` due to cross-project scope restrictions.
   After the story commits, the orchestrator runs the forqsite sync directly. The builder
   does NOT attempt AC5; the reviewer does NOT block on it.

   Orchestrator step (run after reviewer PASS):
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/pairmode_sync.py \
     sync-build --project-dir /mnt/work/forqsite --apply --yes
   ```
   Verify `CLAUDE.build.md` in forqsite contains the `set-context-tokens` step.

## Out of scope

- Syncing all registered projects (only forqsite required at acceptance; others can sync on
  their next scheduled sync)
- Changes to any script or hook (INFRA-148)
- Changes to the reviewer or builder agent templates
