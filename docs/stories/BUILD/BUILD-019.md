---
id: BUILD-019
rail: BUILD
title: "Remove verbose return blocks and align commit-message convention in builder/reviewer templates"
status: planned
phase: "53"
story_class: methodology
primary_files:
  - .claude/agents/builder.md
  - .claude/agents/reviewer.md
  - skills/pairmode/templates/agents/builder.md.j2
  - skills/pairmode/templates/agents/reviewer.md.j2
touches: []
---

# BUILD-019 — Remove verbose return blocks and align commit-message convention in builder/reviewer templates

## Background

Phase 52's BUILD-013 added minimal structured return blocks
(`BUILD-RESULT: DONE`, `REVIEW-RESULT: PASS/FAIL` + `SUMMARY:` + `<usage>`)
that the orchestrator now parses exclusively. But the prior verbose blocks
were never deleted from `builder.md` and `reviewer.md` (or their `.j2`
templates). Both surfaces ship with two end-of-output instructions:

- `builder.md`: the legacy `BUILT: Story [N.X] — [one-line description]` block
  ending with `Build gate: PASS`.
- `reviewer.md`: the legacy `REVIEW PASS — Story [N.X]` and
  `REVIEW FAIL — Story [N.X]` blocks with full checklist findings.

Agents currently emit both. The verbose block sits in the agent's own context
while it is being assembled and then arrives in the orchestrator's transcript
even though the orchestrator parses only the minimal block — wasted tokens on
both sides. **H1** in the Phase 52 cold-eyes review.

Separately, **H2**: `CLAUDE.build.md` states "Story commits use the format:
`feat(story-RAIL-NNN)`", but the reviewer template's commit block still shows
`feat(story-N.X):`. The reviewer has the story ID (from the agent's "Starting
a review" step) and can format the correct prefix directly — but the template
instructs the wrong format.

Both fixes are confined to the four agent files; the orchestrator already
parses correctly and states the right convention.

## Ensures

- `.claude/agents/builder.md` no longer contains a
  `BUILT: Story [N.X] — ...` / `Files changed: ...` / `Tests: ...` /
  `Build gate: PASS` output block. The only end-of-output instruction is the
  `BUILD-RESULT: DONE` / `SUMMARY:` / `<usage>` block.
- The builder's "When you are done" section retains its three verification
  bullets (pytest passes; no hardcoded absolute paths; no hook scripts
  modified to make API calls) but its "Then output exactly:" sample collapses
  into the minimal block only.
- `.claude/agents/reviewer.md` no longer contains the
  `REVIEW PASS — Story [N.X]` block under the PASS branch, nor the
  `REVIEW FAIL — Story [N.X] ─────...` block under the FAIL branch. The PASS
  and FAIL branches keep their commit/revert commands but the verbose
  "Then output:" sample is removed from both.
- The reviewer's "Final output to orchestrator" section (the existing minimal
  block) remains as the single source of truth for what the reviewer emits.
- The reviewer's PASS-branch commit message template uses
  `feat(story-RAIL-NNN):` (literal placeholder `RAIL-NNN`, not `N.X`).
- A note in the reviewer commit block instructs the reviewer to substitute
  the actual story ID it parsed in "Starting a review".
- `skills/pairmode/templates/agents/builder.md.j2` and
  `skills/pairmode/templates/agents/reviewer.md.j2` are updated to match
  byte-for-byte in the affected sections.
- A grep for `BUILT: Story \[N\.X\]` across the four files returns zero
  matches; a grep for `REVIEW PASS — Story` and `REVIEW FAIL — Story` returns
  zero matches; a grep for `feat(story-N.X)` returns zero matches.

## Out of scope

- Any changes to `CLAUDE.build.md` parsing or to the minimal return block
  itself (BUILD-013 is canonical).
- Reviewer's `tools:` frontmatter or `git add` scope (covered by BUILD-020).
- Loop-breaker, security-auditor, intent-reviewer output formats.
- The reviewer's checklist, contract check, test run, or "What you must not
  do" sections — only the legacy output samples and the commit-message
  template are touched.

## Instructions

### 1. Trim `builder.md`

Open `.claude/agents/builder.md`. Locate the "When you are done" section.
Remove the "Then output exactly:" paragraph and the `BUILT: Story [N.X] —`
through `Build gate: PASS` block that follows it, plus the "Then stop. Do not
commit." line that appears between the verbose block and the "If you cannot
complete" section. Replace with a single line:

```
Then stop. Do not commit. Do not proceed to the next story.
```

The "If you cannot complete the story" `BUILDER STUCK` block stays as-is.
The existing "Final output to orchestrator" section remains unchanged.

### 2. Trim `reviewer.md`

Open `.claude/agents/reviewer.md`. Locate the "Decision" section.

Under "PASS conditions":
- Keep the bullet list and the `git add`/`git commit` block.
- Delete the `Then output:` block and its `REVIEW PASS — Story [N.X]` sample.

Under "FAIL conditions":
- Keep the `git checkout .` / `git clean -fd` revert block.
- Delete the `Then output:` block and its `REVIEW FAIL — Story [N.X] ─────...`
  sample.

In the PASS-branch commit block, change the commit message template line from:

```
feat(story-N.X): [one-line description matching the ## Ensures / ## Acceptance criterion]
```

to:

```
feat(story-RAIL-NNN): [one-line description matching the ## Ensures / ## Acceptance criterion]
```

Add a note immediately above the heredoc:

> Substitute the actual story ID you parsed in "Starting a review" — e.g.
> `feat(story-BUILD-019): ...`. `RAIL-NNN` is a placeholder.

The "Final output to orchestrator" section (the `REVIEW-RESULT:` minimal
block) remains unchanged.

### 3. Mirror in `builder.md.j2`

Apply the same step-1 changes to `skills/pairmode/templates/agents/builder.md.j2`.

### 4. Mirror in `reviewer.md.j2`

Apply the same step-2 changes to `skills/pairmode/templates/agents/reviewer.md.j2`.

### 5. Local sanity check

```bash
grep -n "BUILT: Story \[N\.X\]" .claude/agents/builder.md skills/pairmode/templates/agents/builder.md.j2 || true
grep -n "REVIEW PASS — Story\|REVIEW FAIL — Story" .claude/agents/reviewer.md skills/pairmode/templates/agents/reviewer.md.j2 || true
grep -n "feat(story-N\.X)" .claude/agents/reviewer.md skills/pairmode/templates/agents/reviewer.md.j2 || true
```

All three should return no lines.

## Tests

`TEST RUN: methodology story — no test file expected.`

Acceptance verified by:
1. The three grep patterns above return zero matches across all four files.
2. `grep -n "feat(story-RAIL-NNN)" .claude/agents/reviewer.md skills/pairmode/templates/agents/reviewer.md.j2`
   returns a match in each file inside the PASS-branch commit block.
3. The "Final output to orchestrator" sections in `builder.md` and
   `reviewer.md` remain present and unchanged.
