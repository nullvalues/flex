---
id: BUILD-012
rail: BUILD
title: Story-ID-only spawn protocol
status: complete
phase: "52"
story_class: methodology
primary_files:
  - CLAUDE.build.md
  - CLAUDE.build.md.j2
  - .claude/agents/builder.md
  - .claude/agents/reviewer.md
touches:
  - skills/pairmode/templates/agents/builder.md.j2
  - skills/pairmode/templates/agents/reviewer.md.j2
---

# BUILD-012 — Story-ID-only spawn protocol

## Background

The orchestrator currently passes the complete story text verbatim to the
builder and the acceptance criteria to the reviewer. This means the
orchestrator reads every story file and that content accumulates in its
context across stories. After four stories a phase, the orchestrator carries
the full text of each story it has built, plus all the bash output from
spawning them.

If the builder and reviewer are given only a story ID, they locate and read
their own spec cold. The orchestrator's per-story context cost drops to the
story ID (one line) plus the agent's pass/fail result.

## Ensures

- `CLAUDE.build.md` Step 1 (spawn builder) reads: "Spawn with: story ID only
  (e.g. `BUILD-012`). Do not pass story text."
- `CLAUDE.build.md` Step 2 (spawn reviewer) reads: "Spawn with: story ID only.
  Do not pass story spec or acceptance criteria."
- `agents/builder.md` opens with: "You are given a story ID. Your first action
  is to read `docs/stories/<RAIL>/<ID>.md` in full before taking any other
  action."
- `agents/reviewer.md` opens with: "You are given a story ID. Your first action
  is to read `docs/stories/<RAIL>/<ID>.md` in full before taking any other
  action."
- The "last 5 git commits summary" is removed from the builder spawn; the
  builder runs `git log --oneline -5` itself if needed.
- `CLAUDE.build.md.j2` and both agent `.j2` templates are updated to match.

## Out of scope

- What agents return to the orchestrator (BUILD-013).
- The `/context` gate (BUILD-014).

## Instructions

### 1. Update `CLAUDE.build.md` Step 1

Replace the builder spawn instruction block. Change from:
```
Spawn the `builder` subagent with:
- The complete story text (verbatim from the story file)
- The story ID
- A summary of the last 5 git commits
```
To:
```
Spawn the `builder` subagent with:
- The story ID only (e.g. `BUILD-012`)

Do not pass story text, file contents, or git history.
The builder reads its own story spec and any context it needs.
```

### 2. Update `CLAUDE.build.md` Step 2

Replace the reviewer spawn instruction block. Change from:
```
Spawn the `reviewer` subagent with:
- The story ID
- The story spec (acceptance criterion + key requirements)
```
To:
```
Spawn the `reviewer` subagent with:
- The story ID only (e.g. `BUILD-012`)

Do not pass story spec or acceptance criteria.
The reviewer reads its own story spec cold.
```

### 3. Update `agents/builder.md`

Add as the first instruction after the preamble:

```
## Starting a story

You are given a story ID (e.g. `BUILD-012`). Before taking any other action:

1. Parse the rail from the story ID (characters before the `-`).
2. Read `docs/stories/<RAIL>/<ID>.md` in full.
3. Proceed with implementation based on `## Ensures` and `## Instructions`
   in that file.
```

### 4. Update `agents/reviewer.md`

Add as the first instruction after the preamble:

```
## Starting a review

You are given a story ID (e.g. `BUILD-012`). Before taking any other action:

1. Parse the rail from the story ID.
2. Read `docs/stories/<RAIL>/<ID>.md` in full.
3. Use `## Ensures` and `## Acceptance criterion` as your review contract.
```

### 5. Update both `.j2` templates

Mirror all changes to `skills/pairmode/templates/agents/builder.md.j2` and
`skills/pairmode/templates/agents/reviewer.md.j2`.

## Tests

`TEST RUN: methodology story — no logic module.`

Acceptance verified by: orchestrator output showing no story text in the spawn
call, and both agents successfully resolving their story file from the ID alone.
