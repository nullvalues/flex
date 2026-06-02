---
id: BUILD-021
rail: BUILD
title: "Pre-reviewer commit scope: stop pre-staging `docs/stories/`"
status: complete
phase: "53"
story_class: methodology
primary_files:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches: []
---

# BUILD-021 — Pre-reviewer commit scope: stop pre-staging `docs/stories/`

## Background

Phase 52 Step 1.5 of the build loop tells the orchestrator to pre-commit
methodology-file edits before spawning the reviewer, so a reviewer revert
(`git checkout .` / `git reset --hard HEAD`) does not erase
orchestrator-side notes. The current block stages three directories:

```bash
git add docs/stories/ docs/phases/ docs/cer/ 2>/dev/null
git diff --cached --quiet || git commit -m "chore(orchestrator): pre-reviewer methodology file commit"
```

Cold-eyes finding **C4**: pre-staging `docs/stories/` collides with the
builder's edits to story-status frontmatter and any notes the builder may
have written into the story body. The reviewer's checklist explicitly diffs
`HEAD` to inspect what the builder changed — by pre-committing builder-touched
story files, the orchestrator hides exactly the changes the reviewer is
supposed to verify.

`docs/phases/` and `docs/cer/` are different — the builder does not write
there; only the orchestrator does, and only as session-housekeeping (phase
doc Status-column flips, CER triage notes). They remain safe to pre-stage.

The fix removes `docs/stories/` from the glob. If the orchestrator
legitimately edited a single story file during session setup, it can stage
that file with a targeted `git add docs/stories/<RAIL>/<ID>.md` — never
the blanket `docs/stories/` glob.

## Ensures

- `CLAUDE.build.md` Step 1.5's `git add` line stages only `docs/phases/`
  and `docs/cer/` — not `docs/stories/`.
- The Step 1.5 explanatory prose explicitly notes that `docs/stories/` is
  intentionally excluded so the reviewer can see builder-edited story files
  in `git diff HEAD`.
- The Step 1.5 prose includes a note: if the orchestrator must commit an
  individual story-file change it made during session setup, it stages that
  file with a targeted `git add docs/stories/<RAIL>/<ID>.md` for only the
  file it touched — never `docs/stories/` as a glob.
- The lesson-file revert (`git checkout -- lessons/lessons.json
  lessons/LESSONS.md`) is unchanged.
- `skills/pairmode/templates/CLAUDE.build.md.j2` is updated to match
  byte-for-byte.
- A grep for `git add docs/stories/ docs/phases/` (the literal current
  pattern) across both files returns zero matches.

## Out of scope

- Removing Step 1.5 entirely (still needed for `docs/phases/` and `docs/cer/`).
- Changes to the reviewer's tool restriction (BUILD-020).
- Changes to the reviewer's `git add` scope on the PASS branch (BUILD-020).
- Changes to the lessons-file revert step.

## Instructions

### 1. Tighten Step 1.5 in `CLAUDE.build.md`

Open `CLAUDE.build.md`. In Step 1.5, change the shell block from:

```bash
# Commit any orchestrator-side methodology file changes
git add docs/stories/ docs/phases/ docs/cer/ 2>/dev/null
git diff --cached --quiet || git commit -m "chore(orchestrator): pre-reviewer methodology file commit"
```

to:

```bash
# Commit any orchestrator-side methodology file changes
# Note: docs/stories/ is intentionally NOT staged here. The reviewer must
# see builder-edited story files in `git diff HEAD`. If the orchestrator
# must commit an individual story file it edited during session setup,
# stage only that file with `git add docs/stories/<RAIL>/<ID>.md`.
git add docs/phases/ docs/cer/ 2>/dev/null
git diff --cached --quiet || git commit -m "chore(orchestrator): pre-reviewer methodology file commit"
```

Add a one-sentence clarification immediately before the code fence, under
the "Before spawning the reviewer:" heading:

> `docs/stories/` is intentionally excluded from the blanket stage: the
> reviewer's "Before reviewing" step diffs `HEAD` to identify what the
> builder changed, including builder edits to story files. Pre-committing
> them would hide the diff.

Leave the `git checkout -- lessons/lessons.json lessons/LESSONS.md` block
that follows unchanged.

### 2. Mirror in `CLAUDE.build.md.j2`

Apply the same step-1 edits to
`skills/pairmode/templates/CLAUDE.build.md.j2`.

### 3. Local sanity check

```bash
grep -n "git add docs/stories/ docs/phases/" CLAUDE.build.md skills/pairmode/templates/CLAUDE.build.md.j2 || true
```

Should return no lines.

```bash
grep -n "git add docs/phases/ docs/cer/" CLAUDE.build.md skills/pairmode/templates/CLAUDE.build.md.j2
```

Should return one line per file.

## Tests

`TEST RUN: methodology story — no test file expected.`

Acceptance verified by:
1. The two grep sanity checks above behave as described.
2. The clarifying note about why `docs/stories/` is excluded is present in
   both files immediately above the shell block.
3. The lessons revert line remains unchanged.
