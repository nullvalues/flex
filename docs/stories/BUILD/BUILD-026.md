---
id: BUILD-026
rail: BUILD
title: "context gate: prior authorization does not survive a threshold-crossing /context read"
status: complete
phase: "62"
story_class: methodology
primary_files:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - tests/pairmode/test_templates.py
---

# BUILD-026 — context gate: prior authorization does not survive a threshold-crossing /context read

## Context

The Context gate in CLAUDE.build.md (line ~370) stops the build loop when `/context`
reports at-or-above threshold and tells the model to pause and ask for `/clear`. The
gate works correctly in the nominal case.

The observed failure mode: the user typed "continue building" *before* running
`/context`. When `/context` then showed 159.2k > 120k, the model produced
`CONTEXT: 159.2k / 120k — proceeding`, treating the prior "continue building" as
authorization that survived the threshold check. The reasoning is: "the user already
said to proceed, so I'll proceed." That reasoning is wrong — the command was issued
under uncertainty, and the real token count invalidates it.

The current gate text does not say that prior instructions are invalidated by a
threshold-crossing read. Without that explicit rule, the model can rationalize past
the gate. The fix is one sentence added to the "at or above" branch.

The same change applies to `skills/pairmode/templates/CLAUDE.build.md.j2` so the
rule propagates to all bootstrapped projects via `sync-build`.

## Acceptance criteria

### Fix — `CLAUDE.build.md` (and identical change in the template)

In the `### Context gate` section, the existing "at or above" branch reads:

```
If the token count is **at or above** the threshold:
  Output:
    CONTEXT: [N] / [threshold] tokens — THRESHOLD REACHED
    Build paused. Please /clear then resume:
      "Continue building from story [RAIL-NNN]"
  Stop. Do not spawn any agent.
```

After `Stop. Do not spawn any agent.` add one sentence as a new paragraph:

```
A "continue building" (or equivalent) instruction issued before this `/context`
call was made does not authorize proceeding. The token count is authoritative —
re-evaluate against it regardless of any prior instruction.
```

The full updated block:

```
If the token count is **at or above** the threshold:
  Output:
    CONTEXT: [N] / [threshold] tokens — THRESHOLD REACHED
    Build paused. Please /clear then resume:
      "Continue building from story [RAIL-NNN]"
  Stop. Do not spawn any agent.

A "continue building" (or equivalent) instruction issued before this `/context`
call was made does not authorize proceeding. The token count is authoritative —
re-evaluate against it regardless of any prior instruction.
```

### Template — `skills/pairmode/templates/CLAUDE.build.md.j2`

Apply the identical change in the template. The template uses
`{{ pairmode_scripts_dir }}/flex_build.py` for script paths but the prose being
added contains no hardcoded paths, so no substitution is needed.

### Tests — `tests/pairmode/test_templates.py`

Add assertions to the existing `test_templates.py` (same pattern as
`TestBuild025PreStoryScopeCheck`) verifying:

1. The sentence `"does not authorize proceeding"` is present in both the rendered
   template output and the live `CLAUDE.build.md`.
2. The sentence `"re-evaluate against it regardless of any prior instruction"` is
   present in both.
3. Both sentences appear within the same section that contains
   `"THRESHOLD REACHED"` (section ordering check: new text is near the gate, not
   floating elsewhere).

No new test file needed — extend `test_templates.py`.

### Verification

```bash
grep -c "does not authorize proceeding" CLAUDE.build.md                         # >= 1
grep -c "re-evaluate against it" CLAUDE.build.md                               # >= 1
grep -c "does not authorize proceeding" skills/pairmode/templates/CLAUDE.build.md.j2  # >= 1
```

### Manual propagation (orchestrator post-commit)

After the reviewer commits, sync forqsite:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/pairmode_sync.py \
  sync-build --project-dir /mnt/work/forqsite --apply --yes
```

Verify `CLAUDE.build.md` in forqsite contains `"does not authorize proceeding"`.

## Out of scope

- Changing the hook (`pre_tool_use.py`, `context_budget.py`) — mechanical
  enforcement already exists at that layer; this story closes the prose gap only.
- Adding a new CLI subcommand.
- Changing the threshold value or overrun policy.
- Updating `docs/architecture.md` (no architectural change — the gate structure
  is unchanged; only the prose clarification is new).
