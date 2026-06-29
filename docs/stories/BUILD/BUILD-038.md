---
id: BUILD-038
rail: BUILD
title: "reviewer FAIL-revert: drop git clean -fd"
status: complete
phase: "79"
story_class: doc
primary_files:
  - .claude/agents/reviewer.md
touches:
---

# BUILD-038 — reviewer FAIL-revert: drop `git clean -fd`

## Context

On a FAIL verdict the reviewer agent reverts the working tree with
(`.claude/agents/reviewer.md:171–176`):

```bash
git checkout .
git clean -fd
```

`git clean -fd` deletes **all** untracked files and directories in the repo,
not just files the builder created for the failed story. Any legitimate
untracked content unrelated to the story is destroyed — for example this repo
currently has an untracked `flex_eph/` directory that a FAIL revert would wipe.
No loss has occurred yet, but the blast radius is wrong: the intended revert is
to restore tracked files to their committed state, leaving untracked content
alone.

`git checkout .` already restores all tracked files the builder modified. The
only thing it does not undo is **newly created untracked files** from the failed
build. Per the agreed decision, the safe correction is to drop `git clean -fd`
entirely and revert with `git checkout .` only — accepting that a builder's
newly-created files survive a FAIL (they will be caught by the reviewer's scope
checks and the next build attempt, and are far less costly than deleting a
user's untracked work).

## Acceptance criteria

1. The FAIL-revert block in `.claude/agents/reviewer.md` performs `git checkout .`
   only. The `git clean -fd` line is removed.

2. The surrounding prose is updated so it does not promise that revert removes
   builder-created untracked files. Add a one-line note that `git checkout .`
   restores tracked files and that untracked files are intentionally left in
   place (to avoid deleting unrelated untracked work).

3. No other behavioural instruction in `reviewer.md` is changed (the commit-on-
   PASS path, the scope-staged `git add`, the FAIL conditions, and the
   "What you must not do" list are untouched).

4. `.claude/agents/reviewer.md` is **not** a protected file per CLAUDE.md
   check 7 (protected set: `hooks/`, `skills/seed/scripts/`,
   `skills/companion/scripts/sidebar.py`, `.claude-plugin/plugin.json`,
   `.claude-plugin/marketplace.json`). This story changes only the agent doc.

## Implementation guidance

- Edit only the fenced bash block at `reviewer.md:173–176` and the immediately
  surrounding sentence. Resulting block:
  ```bash
  git checkout .
  ```
- If any other agent or template doc (e.g. the seeded
  `CLAUDE.build.md` reviewer instructions or a `.j2` mirror of reviewer.md)
  carries the same `git clean -fd` revert, note it in the build summary — but do
  **not** change it under this story (out of scope; surface for a follow-up
  story so the template fix gets its own spec).

## Tests

Documentation/agent-config story — no logic module changed, no test file
expected. Reviewer states `TEST RUN: documentation story — no test file
expected`.

Verification is a manual read of the revert block:

```bash
sed -n '167,180p' .claude/agents/reviewer.md
```

Confirm `git clean -fd` is absent and `git checkout .` remains.

### Out of scope

- Scoping a narrower clean to story `primary_files`/`touches` (the decision was
  to drop clean entirely, not scope it).
- Propagating the same fix into any seeded template / `.j2` mirror — surface in
  the build summary for a separate story if such a mirror exists.
- `current-phase` (BUILD-036) and `mark-phase-complete` (BUILD-037) changes.
