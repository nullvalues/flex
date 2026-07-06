---
id: WORKER-015
rail: WORKER
title: Builder + reviewer procedure Non-negotiables removal
status: complete
phase: "HARNESS010-main"
story_class: documentation
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/builder/procedure.md
  - skills/pairmode/skills/reviewer/procedure.md
touches: []
---

## Context

Both builder and reviewer procedures end with a `## Non-negotiables` section (~5 items each)
that restates rules already stated in the body of the same file (return format, commit protocol,
no autonomous push). The repetition adds ~200 tokens per procedure with no enforcement benefit.

Depends on HARNESS-004 landing first — that story establishes the reviewer procedure as the
canonical checklist owner and removes the `## Session modes` section from `CLAUDE.md`. This
story then removes the Non-negotiables redundancy from both procedures.

Agreement HARNESS010-main DP3/DP4 (settled 2026-07-04).

## Ensures

### Builder procedure (`skills/pairmode/skills/builder/procedure.md`)

1. **`## Non-negotiables` section removed.** The section at line 166 and its 5 bullet items
   are deleted entirely.

2. **One-sentence contract note added** to the `## Return format` section. Append after the
   closing paragraph of the return-format description (before the triple-dash separator if
   present, or at the end of the section):
   `"Deviating from this format invalidates the result."`

### Reviewer procedure (`skills/pairmode/skills/reviewer/procedure.md`)

3. **`## Non-negotiables` section removed.** The section at line 336 and its 5 bullet items
   are deleted entirely.

4. **One-sentence contract note added** to the `## Return format` section. Append after the
   closing paragraph of the return-format description:
   `"Deviating from this format invalidates the result."`

5. **Full 10-item checklist confirmed present** in the reviewer procedure (inherited from
   HARNESS-004; this story does not modify the checklist — confirm it is intact at `## Review
   checklist`, items `### 1.` through `### 10.`).

### Verification

6. `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

**Documentation story — no test file required.** Acceptance gate: confirm the reviewer
procedure's checklist is complete (all 10 items present) before marking done.

1. Edit `skills/pairmode/skills/builder/procedure.md`:
   - Delete `## Non-negotiables` and its 5 bullet items (currently at line 166 to end of file).
   - In `## Return format`, append `"Deviating from this format invalidates the result."` after
     the existing closing paragraph.

2. Edit `skills/pairmode/skills/reviewer/procedure.md`:
   - Delete `## Non-negotiables` and its 5 bullet items (currently at line 336 to end of file).
   - In `## Return format`, append `"Deviating from this format invalidates the result."` after
     the existing closing paragraph.

3. Verify `skills/pairmode/skills/reviewer/procedure.md` contains all 10 review checklist items
   (`### 1.` through `### 10.`). If any are missing, this is a blocker — do not mark the story
   done.

4. Run tests:
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
   ```

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: Non-negotiables section gone from both procedures; one-sentence contract note
present in each return-format section; reviewer procedure holds all 10 checklist items;
suite green.
