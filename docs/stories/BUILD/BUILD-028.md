---
id: BUILD-028
rail: BUILD
title: "`CLAUDE.build.md` checkpoint step 7 — call `mark-phase-complete`; retroactive index fix"
status: complete
phase: "65"
story_class: methodology
primary_files:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - docs/phases/index.md
  - /mnt/work/forqsite/docs/phases/index.md
  - /mnt/work/forqsite/CLAUDE.build.md
---

# BUILD-028 — CLAUDE.build.md: call mark-phase-complete at checkpoint + retroactive fix

## Context

INFRA-172 adds the `mark-phase-complete` command. This story wires it into the
checkpoint sequence (step 7 in CLAUDE.build.md) and fixes the retroactive drift in
both repos.

Confirmed drift:
- flex `docs/phases/index.md`: statuses were maintained manually and are currently
  correct; no retroactive fix needed.
- forqsite `docs/phases/index.md`: phases that are checkpointed but still show
  `planned` need to be identified and corrected.

## Acceptance criteria

### CLAUDE.build.md: checkpoint step 7 addition

1. In the checkpoint step 7 ("Tag the checkpoint"), BEFORE running the tag command,
   a new step calls:

   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
     mark-phase-complete --phase [phase-id] --project-dir .
   ```

   The call is placed after the phase completion check (step 5) and before the
   `git tag` / tag command. The commit that carries the checkpoint tag also carries
   the index update.

2. The prose explains: "This records the phase as complete in `docs/phases/index.md`.
   The index update is staged and included in the checkpoint commit."

3. The same addition is applied to `forqsite/CLAUDE.build.md` and
   `skills/pairmode/templates/CLAUDE.build.md.j2`.

### Retroactive forqsite fix

4. Identify every phase in `forqsite/docs/phases/index.md` that has a git tag
   (i.e., has been checkpointed) but still shows a non-`complete` status. For each:
   - Run `mark-phase-complete --phase [key] --project-dir /mnt/work/forqsite`

5. The retroactive fix is committed to forqsite as a standalone "chore" commit:
   `chore: retroactive mark-phase-complete for all checkpointed phases`

### Verification

6. After the retroactive fix, `_parse_index_phases` on forqsite's index returns no row
   where the status is `planned` for a phase that has a git tag.

## Implementation guidance

### Finding checkpointed phases in forqsite

```bash
# List all checkpoint tags (cp-prefixed or cp\d+ pattern)
git -C /mnt/work/forqsite tag | grep -E '^cp'
```

Cross-reference with the index to find rows still showing `planned`. Typical pattern:
a phase is checkpointed when its tag exists in git. Run `mark-phase-complete` for each.

### Checkpoint step 7 insertion point (CLAUDE.build.md)

Insert immediately before "Run the tag command from /docs/checkpoints.md":

```
Before tagging, mark the phase as complete in the index:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
  mark-phase-complete --phase [phase-id] --project-dir .
```

Stage the updated index alongside any doc updates from step 3. All staged changes
(index update + doc updates) are included in the checkpoint commit.

Then run the tag command from `/docs/checkpoints.md` for this phase.
```
