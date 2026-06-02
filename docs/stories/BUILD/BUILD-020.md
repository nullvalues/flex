---
id: BUILD-020
rail: BUILD
title: "Reviewer-class `tools:` frontmatter and scoped `git add` for story commits"
status: complete
phase: "53"
story_class: methodology
primary_files:
  - .claude/agents/reviewer.md
  - .claude/agents/loop-breaker.md
  - .claude/agents/security-auditor.md
  - .claude/agents/intent-reviewer.md
  - skills/pairmode/templates/agents/reviewer.md.j2
  - skills/pairmode/templates/agents/loop-breaker.md.j2
  - skills/pairmode/templates/agents/security-auditor.md.j2
  - skills/pairmode/templates/agents/intent-reviewer.md.j2
touches: []
---

# BUILD-020 — Reviewer-class `tools:` frontmatter and scoped `git add` for story commits

## Background

`CLAUDE.build.md` Step 1.5 asserts that reviewer-class agents are protected
by a tool restriction:

> This is the second of two layers protecting the working tree from reviewer
> reverts. The first layer is the reviewer-class agent tool restriction
> (read-only tools plus Bash; see `docs/architecture.md`).

Cold-eyes finding **C3**: that first layer is not enforced. None of
`reviewer.md`, `loop-breaker.md`, `security-auditor.md`, or `intent-reviewer.md`
declare a `tools:` field in their frontmatter. Without an explicit list, the
Claude Code agent runtime grants the full tool set including `Write` and
`Edit`, so a misbehaving reviewer can clobber the working tree directly
instead of by `git checkout .`. The orchestrator's stated safety story is
load-bearing on a property the agent definitions do not actually have.

The fix is mechanical: add `tools: [Read, Bash, Glob, Grep]` to each
reviewer-class agent's frontmatter, in both the live `.claude/agents/` files
and the bootstrapped `.j2` templates. Reviewer-class work is reading the
working tree, grepping for patterns, running tests via `Bash`, and committing
or reverting via `git` commands run through `Bash` — `Write` and `Edit` are
not needed.

Separately, cold-eyes finding **H3**: the reviewer's PASS-branch commit
stages with `git add -A`. That stages every file in the working tree
regardless of whether it falls within the story's declared scope. The reviewer
has already read the story spec frontmatter as part of "Starting a review",
so it has `primary_files` and `touches` in hand and can build a scoped `git
add` command from those fields.

## Ensures

- `.claude/agents/reviewer.md` frontmatter declares
  `tools: [Read, Bash, Glob, Grep]`.
- `.claude/agents/loop-breaker.md` frontmatter declares
  `tools: [Read, Bash, Glob, Grep]`.
- `.claude/agents/security-auditor.md` frontmatter declares
  `tools: [Read, Bash, Glob, Grep]`.
- `.claude/agents/intent-reviewer.md` frontmatter declares
  `tools: [Read, Bash, Glob, Grep]`.
- The same four declarations are mirrored in
  `skills/pairmode/templates/agents/reviewer.md.j2`,
  `loop-breaker.md.j2`, `security-auditor.md.j2`, and `intent-reviewer.md.j2`.
- The `builder.md` (and `.j2`) frontmatter's existing
  `tools: [Read, Write, Edit, Glob, Grep, Bash]` declaration is unchanged.
- `.claude/agents/reviewer.md` PASS-branch commit block replaces the
  unconditional `git add -A` with a scoped staging sequence that:
  1. Reads `primary_files` and `touches` from the story's frontmatter
     (already done in "Starting a review").
  2. Runs `git add <path>` for each declared file.
  3. Falls back to `git add -A` only when both `primary_files` and `touches`
     are empty/absent (legacy stories with no declared scope).
- The reviewer's commit block carries an explanatory note:
  > Stage only files declared in the story's `primary_files` and `touches`
  > frontmatter. If both are empty (legacy story), fall back to `git add -A`.
- `skills/pairmode/templates/agents/reviewer.md.j2` carries the same scoped
  `git add` sequence.
- A grep for `^tools:` across the four reviewer-class agent files and their
  four templates returns eight matches (one per file).
- A grep for `git add -A` in `.claude/agents/reviewer.md` and its template
  finds it only inside the legacy-fallback branch, not as the unconditional
  default.

## Out of scope

- Changes to `builder.md`'s tool set — builder must keep `Write` and `Edit`.
- Changes to the Claude Code runtime's handling of missing `tools:` fields.
- Adding a helper script that reads frontmatter and emits a staging command.
- Removing the orchestrator's Step 1.5 pre-commit (that's BUILD-021).
- Adjusting the `reconstruction-agent` definition (not a reviewer-class agent).

## Instructions

### 1. Add `tools:` frontmatter to the four reviewer-class agents

For each of `.claude/agents/reviewer.md`, `.claude/agents/loop-breaker.md`,
`.claude/agents/security-auditor.md`, `.claude/agents/intent-reviewer.md`:

Add `tools: [Read, Bash, Glob, Grep]` as a new line in the frontmatter
between `description:` and `model:`. Example for `reviewer.md`:

```yaml
---
name: reviewer
description: Cold-eyes reviewer. Diffs the working tree against the story spec, runs the full checklist and tests, then commits on PASS or reverts on FAIL. Never writes code.
tools: [Read, Bash, Glob, Grep]
model: sonnet
# upgrade: opus  (when retry / pre-PR audit / mid-phase pivot)
# fallback: sonnet  (never below)
---
```

Preserve all existing comments and the order of other fields.

### 2. Mirror in the four `.j2` templates

Apply the same `tools:` insertion in:

- `skills/pairmode/templates/agents/reviewer.md.j2`
- `skills/pairmode/templates/agents/loop-breaker.md.j2`
- `skills/pairmode/templates/agents/security-auditor.md.j2`
- `skills/pairmode/templates/agents/intent-reviewer.md.j2`

### 3. Scope `git add` in `reviewer.md` PASS branch

Open `.claude/agents/reviewer.md`. Under "Decision" → "PASS conditions",
replace the unconditional `git add -A` line with the following block:

```
Stage only files declared in the story's `primary_files` and `touches`
frontmatter (already read in "Starting a review"). For each declared path:

  git add <path>

If both `primary_files` and `touches` are empty or absent (legacy story
with no declared scope), fall back to:

  git add -A
```

Then the commit heredoc follows as before (with the `feat(story-RAIL-NNN):`
format from BUILD-019).

### 4. Mirror in `reviewer.md.j2`

Apply the same scoped-staging change in
`skills/pairmode/templates/agents/reviewer.md.j2`.

### 5. Local sanity check

```bash
grep -c "^tools:" \
  .claude/agents/reviewer.md \
  .claude/agents/loop-breaker.md \
  .claude/agents/security-auditor.md \
  .claude/agents/intent-reviewer.md \
  skills/pairmode/templates/agents/reviewer.md.j2 \
  skills/pairmode/templates/agents/loop-breaker.md.j2 \
  skills/pairmode/templates/agents/security-auditor.md.j2 \
  skills/pairmode/templates/agents/intent-reviewer.md.j2
```

Each line should show `1`.

```bash
grep -n "git add -A" .claude/agents/reviewer.md skills/pairmode/templates/agents/reviewer.md.j2
```

Each match must sit inside the legacy-fallback branch only.

## Tests

`TEST RUN: methodology story — no test file expected.`

Acceptance verified by:
1. The `grep -c "^tools:"` block above yields `1` per file across all eight
   reviewer-class files.
2. `.claude/agents/builder.md` frontmatter still contains
   `tools: [Read, Write, Edit, Glob, Grep, Bash]` (untouched).
3. `git add -A` in `.claude/agents/reviewer.md` appears only inside the
   "If both `primary_files` and `touches` are empty" fallback branch.
4. The scoped staging text explicitly references the `primary_files` and
   `touches` frontmatter fields.
