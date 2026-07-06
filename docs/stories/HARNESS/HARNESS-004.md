---
id: HARNESS-004
rail: HARNESS
title: "`CLAUDE.md` + `CLAUDE.build.md` token surgery"
status: planned
phase: "HARNESS010-main"
story_class: documentation
auth_gated: false
schema_introduces: false
primary_files:
  - CLAUDE.md
  - CLAUDE.build.md
  - hooks/pre_tool_use.py
  - hooks/post_tool_use.py
  - hooks/session_start.py
touches:
  - skills/pairmode/templates/CLAUDE.md.j2
  - skills/pairmode/templates/CLAUDE.build.md.j2
---

## Context

`CLAUDE.md` is loaded unconditionally into every session (reviewer and build). It currently
carries the full 10-item reviewer checklist (~1,100 tokens) with multi-paragraph hook exception
footnotes (~600 tokens) — dead weight in every build session. The "Session modes" section is an
Era 001/002 vestige now that build mode is an explicit `CLAUDE.build.md` session. `CLAUDE.build.md`
carries a "Spec mode" paragraph that duplicates what the resolver action already provides, plus
explanatory prose in the "Checkpoint" paragraph that is similarly redundant.

Agreement HARNESS010-main DP1/DP2/DP4 (settled 2026-07-04).

## Ensures

### CLAUDE.md

1. **Session modes removed.** The `## Session modes` section (lines 17–30 in current file) is
   deleted. Replaced with one sentence immediately after `## Project context`:
   `"Build sessions are governed by \`CLAUDE.build.md\`; all other input applies the reviewer role."`

2. **Review checklist replaced by reference.** The entire `## Review checklist` section (lines
   31–146, all 10 items plus hook exception footnotes) is removed. Replaced with:
   ```
   ## Review checklist

   Apply the checklist in the reviewer procedure skill.
   See `skills/pairmode/skills/reviewer/procedure.md`.
   ```

3. **Hook exception footnotes gone from CLAUDE.md.** The multi-paragraph prose explaining
   `pre_tool_use.py`, `post_tool_use.py`, and `session_start.py` dispatch logic (currently
   embedded in checklist items 1–3) is deleted — it lives in the hook scripts now (see below).

4. **Review output format, Story test verification, Loop-breaker mode sections are retained**
   in `CLAUDE.md` unchanged.

### hooks/pre_tool_use.py, post_tool_use.py, session_start.py

5. **Each hook script gains a one-line thin-dispatcher comment** at the top of the file
   (after the shebang/imports, before the main logic), explaining what it delegates to:
   - `pre_tool_use.py`: `# thin dispatcher — Edit/Write → scope_guard.py; Task/Agent → context_budget.py`
   - `post_tool_use.py`: `# thin dispatcher — Write/Edit/MultiEdit → sidebar pipe relay; Task/Agent → context_budget.py`
   - `session_start.py`: `# thin dispatcher — clear/startup → session_reset.py`

### CLAUDE.build.md

6. **Spec mode paragraph removed.** The `## Spec mode` section is deleted entirely.

7. **Checkpoint paragraph trimmed.** The `## Checkpoint` section is reduced to:
   ```
   ## Checkpoint

   Execute each checkpoint leaf worker as dispatched. After each returns, call:
     flex_build.py record-checkpoint-step <action> --project-dir .
   Then re-run next-action. checkpoint-tag: `git tag cp-<phase-key> && git push origin harness --tags`.
   ```
   (The existing text is already close to this; confirm it matches exactly and remove any
   additional prose if present.)

8. **All other input section retained** unchanged.

### Templates

9. **`skills/pairmode/templates/CLAUDE.md.j2`** is updated with the same changes as `CLAUDE.md`
   (Session modes removed, checklist replaced by reference).

10. **`skills/pairmode/templates/CLAUDE.build.md.j2`** is updated with the same changes as
    `CLAUDE.build.md` (Spec mode paragraph removed, Checkpoint paragraph trimmed to match).

11. `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

**Documentation story — no test file required.** Acceptance gate is checklist completeness:
the reviewer procedure must still hold the full 10-item checklist after this change (it already
does — confirm by reading `skills/pairmode/skills/reviewer/procedure.md`).

1. Edit `CLAUDE.md`:
   - Delete the `## Session modes` block (lines 17–30). Add the one-sentence routing note
     at the end of `## Project context` or as a standalone sentence before the next section.
   - Replace the `## Review checklist` block (lines 31–146) with the two-line reference.
   - The sections after (Review output format, Story test verification, Loop-breaker mode)
     are unchanged.

2. Add the thin-dispatcher comment line to each of the three hook scripts. Do not change any
   logic — comment only.

3. Edit `CLAUDE.build.md`:
   - Delete the `## Spec mode` section (lines 23–27 in current file).
   - Verify the `## Checkpoint` section matches the trimmed form specified above.

4. Apply the same CLAUDE.md edits to `skills/pairmode/templates/CLAUDE.md.j2`.

5. Apply the same CLAUDE.build.md edits to `skills/pairmode/templates/CLAUDE.build.md.j2`.

6. Confirm `skills/pairmode/skills/reviewer/procedure.md` still contains all 10 checklist
   items (items 1–10, `### 1.` through `### 10.`). Do not modify this file.

7. Run tests:
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
   ```

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: Session modes section gone from `CLAUDE.md`; Review checklist replaced by reference;
hook scripts have thin-dispatcher comment; Spec mode paragraph gone from `CLAUDE.build.md`;
Checkpoint paragraph trimmed; both `.j2` templates updated; reviewer procedure holds all 10 items;
suite green.
