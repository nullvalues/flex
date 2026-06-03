---
id: BUILD-024
rail: BUILD
title: "Replace `write-permissions`/`clear-permissions` with `permissions-create` in build loop"
status: planned
phase: "55"
story_class: code
primary_files:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - docs/phases/phase-55.md
---

# BUILD-024 — Replace `write-permissions`/`clear-permissions` with `permissions-create` in build loop

## Background

The current build loop in `CLAUDE.build.md` calls two Bash commands that write to
`.claude/settings.local.json`:

1. **Before the builder spawns** (Step 2):
   ```bash
   flex_build.py write-permissions --story-id RAIL-NNN --project-dir .
   ```
2. **After the reviewer completes** (Step 3):
   ```bash
   flex_build.py clear-permissions --project-dir .
   ```

Both commands touch `.claude/settings.local.json`, which is in the `.claude/`
directory. The Claude Code auto-mode classifier unconditionally hard-blocks writes
to `.claude/**`, so these commands trigger a user-approval prompt on every story.
Over a multi-story phase, this accumulates to N×2 mandatory user interactions purely
for permissions housekeeping.

Phase 55 provides a replacement: `flex_build.py permissions-create STORY-ID`
writes `docs/phases/permissions/STORY-ID.json` (in `docs/phases/`, not `.claude/`),
which the `scope_guard` hook reads automatically. No corresponding cleanup command
is needed — the permissions file is idempotent and persists across stories safely
(the hook only consults the file for the story listed in `state.json`'s
`current_story` field).

This story updates `CLAUDE.build.md` and its Jinja2 template to use the new
mechanism: replace `write-permissions` with `permissions-create` before the builder,
and remove the `clear-permissions` call entirely.

## Ensures

### `CLAUDE.build.md` — Step 2 (before builder)

The block:
```
Before spawning the builder, pre-authorize edits within the story's declared scope:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py write-permissions \
  --story-id RAIL-NNN --project-dir .
```

Replace RAIL/RAIL-NNN with the current story's ID. After this runs, the builder
session will not prompt for edits to any file declared in primary_files or touches.
```

Is replaced with:
```
Before spawning the builder, generate the story's scope-enforcement permissions file:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py permissions-create \
  RAIL-NNN --project-dir .
```

Replace RAIL-NNN with the current story's ID. This writes
`docs/phases/permissions/RAIL-NNN.json` from the story spec's `primary_files` and
`touches` frontmatter. The `scope_guard` hook reads this file automatically on
every Edit/Write tool call during the build and blocks writes to undeclared paths.
No cleanup step is needed after the build — the permissions file is idempotent.
```

### `CLAUDE.build.md` — Step 3 (after reviewer)

The block:
```
1. Clean up story-scoped allow rules:
```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py clear-permissions --project-dir .
```
```

Is removed entirely. Step 3's numbering is updated accordingly (what was item 2
becomes item 1, etc.).

### Spec-mode workflow — Step 5 (commit spec)

After step 5b (story files written by Plan subagent), before 5c (git commit), add:

```
   b2. Generate permissions files for each story in the phase:
       For each story ID in the Stories table, run:
       ```bash
       PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
         permissions-create STORY-ID --project-dir .
       ```
```

And update the git commit in step 5c to include `docs/phases/permissions/`:
```bash
git add docs/phases/phase-N.md docs/stories/ docs/phases/permissions/
git commit -m "spec(phase-N): scaffold phase and story specs [spec-mode]"
```

### `skills/pairmode/templates/CLAUDE.build.md.j2`

Apply the identical three changes to the template, using `{{ pairmode_scripts_dir }}`
in place of the hardcoded absolute path:
- Replace `write-permissions --story-id RAIL-NNN` with `permissions-create RAIL-NNN`
- Remove the `clear-permissions` cleanup block from Step 3
- Add the `permissions-create` loop to the spec-mode Step 5 and update the git add

### `docs/phases/phase-55.md`

Update the phase-55.md Stories table entry for BUILD-024 from `planned` to
`complete` after this story ships.

## Out of scope

- Removing `write-permissions` / `clear-permissions` commands from `flex_build.py`
  (kept for backwards compatibility and manual use; deprecation is a Phase 56 story).
- Updating SKILL.md or architecture.md (intent review will surface any gaps).
- Adding `permissions-create` to SKILL.md `/flex:pairmode` command reference
  (separate story if needed).

## Instructions

### 1. Edit `CLAUDE.build.md`

**Find** (Step 2 block — before builder spawn):
```
Before spawning the builder, pre-authorize edits within the story's declared scope:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py write-permissions \
  --story-id RAIL-NNN --project-dir .
```

Replace RAIL/RAIL-NNN with the current story's ID. After this runs, the builder
session will not prompt for edits to any file declared in primary_files or touches.
```

**Replace with:**
```
Before spawning the builder, generate the story's scope-enforcement permissions file:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py permissions-create \
  RAIL-NNN --project-dir .
```

Replace RAIL-NNN with the current story's ID. This writes
`docs/phases/permissions/RAIL-NNN.json` from the story spec's `primary_files` and
`touches` frontmatter. The `scope_guard` hook enforces this scope automatically on
every Edit/Write call during the build. No cleanup step is needed after the build.
```

**Find** (Step 3 item 1 — clear-permissions):
```
1. Clean up story-scoped allow rules:
```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py clear-permissions --project-dir .
```
```

**Delete** this item and renumber the remaining Step 3 items starting from 1.

**Find** (spec-mode Step 5b — story files commit):
```
   c. Commit:
      ```bash
      git add docs/phases/phase-N.md docs/stories/
      git commit -m "spec(phase-N): scaffold phase and story specs [spec-mode]"
      ```
```

**Replace with:**
```
   b2. Generate permissions files for each story in the phase:
       For each story ID in the confirmed Stories table, run:
       ```bash
       PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
         permissions-create STORY-ID --project-dir .
       ```

   c. Commit:
      ```bash
      git add docs/phases/phase-N.md docs/stories/ docs/phases/permissions/
      git commit -m "spec(phase-N): scaffold phase and story specs [spec-mode]"
      ```
```

### 2. Edit `skills/pairmode/templates/CLAUDE.build.md.j2`

Apply the same three changes, using `{{ pairmode_scripts_dir }}` instead of the
hardcoded path. The `write-permissions --story-id` form becomes
`permissions-create` (positional argument, no `--story-id` flag). The
`clear-permissions` block is deleted. The spec-mode step is updated with the
`permissions-create` loop and the expanded `git add`.

## Tests

This is a documentation/template story — the acceptance criteria are structural
(correct text present / incorrect text absent) rather than runtime behaviour.

Verify with `grep`:

```bash
grep -c "write-permissions" CLAUDE.build.md       # must be 0
grep -c "clear-permissions" CLAUDE.build.md       # must be 0
grep -c "permissions-create" CLAUDE.build.md      # must be >= 2 (Step 2 + spec Step 5)
grep -c "docs/phases/permissions/" CLAUDE.build.md # must be >= 1
grep -c "write-permissions" skills/pairmode/templates/CLAUDE.build.md.j2  # must be 0
grep -c "clear-permissions" skills/pairmode/templates/CLAUDE.build.md.j2  # must be 0
grep -c "permissions-create" skills/pairmode/templates/CLAUDE.build.md.j2 # must be >= 2
```

If `tests/pairmode/test_templates.py` already asserts on `CLAUDE.build.md.j2`
content, add assertions there rather than creating a new test file.
