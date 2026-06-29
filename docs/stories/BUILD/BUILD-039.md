---
id: BUILD-039
rail: BUILD
title: "pre-reviewer git add: exclude story primary_files from blanket stage"
status: draft
phase: ""
story_class: doc
primary_files:
  - CLAUDE.build.md
touches:
---

# BUILD-039 — pre-reviewer git add: exclude story primary_files from blanket stage

## Context

Step 1.5 of `CLAUDE.build.md` (line 539) runs:

```bash
git add docs/phases/ docs/cer/ 2>/dev/null
git diff --cached --quiet || git commit -m "chore(orchestrator): pre-reviewer methodology file commit"
```

This blanket stage is intentional — it captures orchestrator-side methodology
edits (phase-doc annotations, CER entries) made during a session before the
reviewer fires, protecting them from the reviewer's revert path.

The bug (L018, sourced from meander INFRA-008): when a story's declared
`primary_file` is under `docs/phases/` — which is normal for doc stories and
spec stories whose deliverable *is* a phase file — the blanket `git add`
sweeps it up and commits it under the chore message before the reviewer runs.
The reviewer then diffs an empty working tree, cannot verify the deliverable,
and the story's output is committed without review under the wrong commit
message.

The story file itself is already excluded from the blanket stage (the existing
comment at line 528–531 explains why: `docs/stories/` is intentionally NOT
staged so the reviewer sees the diff). The same exclusion logic must now apply
to any `primary_files` or `touches` that fall under the blanket-staged
directories.

## Acceptance criteria

1. After the `git add docs/phases/ docs/cer/` line, a `git reset HEAD`
   exclusion pass unstages any files declared in the active story's
   `primary_files` and `touches` lists that were swept up by the blanket add.

2. The bash block is self-contained: the exclusion pass reads the story spec
   that the orchestrator already has in context (the same spec used to spawn
   the builder). No new tooling is required — the file paths are already
   known. The implementation is a simple loop:
   ```bash
   # Unstage any story primary_files/touches swept up by the blanket add
   # so the reviewer can diff the story's actual deliverable.
   for f in <primary_files> <touches>; do
     git reset HEAD -- "$f" 2>/dev/null
   done
   ```
   The orchestrator substitutes the actual paths from the story spec; the loop
   is illustrative, not literal.

3. The existing comment explaining the `docs/stories/` exclusion is extended
   (or a parallel comment added) to document why `primary_files`/`touches` are
   also excluded: "the reviewer must see the story deliverable in the diff, not
   find it already committed under the chore message."

4. No other behaviour in Step 1.5 changes — the `lessons/` checkout line and
   the commit message are untouched.

5. The `CLAUDE.build.md.j2` template in
   `skills/pairmode/templates/CLAUDE.build.md.j2` receives the same edit so
   future bootstrapped projects inherit the fix.

## Implementation guidance

- Target block: `CLAUDE.build.md` lines 533–544.
- Locate the equivalent block in `skills/pairmode/templates/CLAUDE.build.md.j2`
  by searching for `git add docs/phases/`.
- The exclusion loop goes immediately after the `git add` line and before the
  `git diff --cached --quiet || git commit` line.
- The comment should reference L018 so the rationale is traceable:
  `# L018: exclude story primary_files/touches — reviewer must see them in the diff`

## Tests

Documentation story — no logic module changed, no test file expected. Reviewer
states `TEST RUN: documentation story — no test file expected`.

Manual verification:

```bash
# Confirm the exclusion loop appears after the blanket git add in CLAUDE.build.md
grep -n "git reset HEAD" CLAUDE.build.md

# Confirm the same fix landed in the template
grep -n "git reset HEAD" skills/pairmode/templates/CLAUDE.build.md.j2
```

### Out of scope

- Automated reading of the story spec from disk (the orchestrator already has
  the paths in context; shell automation is not needed).
- Changing Step 1 (builder spawn) or Step 2 (reviewer spawn) logic.
- Any change to `docs/stories/` exclusion rationale beyond extending the comment.
