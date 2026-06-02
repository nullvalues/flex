---
id: BUILD-009
rail: BUILD
title: Phase doc boundary scan + pre-story stub gate in CLAUDE.build.md.j2
status: complete
phase: "51"
story_class: methodology
primary_files:
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - CLAUDE.build.md
---

# BUILD-009 — Phase doc boundary scan + pre-story stub gate

## Background

Two enforcement gaps exist in the build loop:

**Gap 1 — no phase doc scan at start.** When "Build Phase N" is triggered, the
orchestrator reads the phase doc but has no instruction to detect embedded story
sections (`#### Instructions`, `#### Tests`, `#### Changes required` written
inline under a story heading). These are left by planners who embed story specs
into phase docs during drafting. If not caught before the build loop starts,
the builder reads them and perpetuates the pattern.

**Gap 2 — no stub gate.** Before Step 1, there is a pre-story schema gate
(checking for new persistent schema objects) but no check that the story file is
a self-contained spec. Forqsite story files contain summary Ensures + "See phase
doc for full spec" delegation — the builder must read the phase doc to build. The
story file is not the contract; the phase doc is. This is the delegation failure mode.

## Acceptance criterion

### A — Phase doc boundary scan (new step in "Before the first build loop")

After step 3 ("Read the current phase file"), before step 4 ("Run `git log`"),
a new step is added:

```
### 3.5 Phase doc boundary scan

Scan the phase doc for embedded story sections — implementation detail that
belongs in story files, not the phase doc.

Signals to look for (any of these inside a heading that names a story ID or
story title):
- Sub-headings: #### Instructions, #### Tests, #### Changes required,
  #### Changes, #### Acceptance criteria, #### Acceptance criterion,
  #### Context (when it contains file paths or code), #### Design
- Code blocks (``` fenced) with language tags (```ts, ```py, ```sql, etc.)
  appearing under a named story section

If no signals found: proceed normally.

If signals found, stop and report:

  PHASE DOC BOUNDARY VIOLATION — Phase [N]
  The following story sections contain implementation detail that belongs
  in story files, not the phase doc:
    [list each: story ID or heading — what was found — approximate line]

  Action required before building:
  For each listed story:
  1. Read the embedded section in the phase doc.
  2. Copy the implementation detail into docs/stories/<RAIL>/<ID>.md
     (Ensures, Instructions, Design, Tests as appropriate).
  3. Replace the embedded section in the phase doc with a single-line
     summary (e.g., "Extract and expose observability query functions.").
  When resolved, say: "Continue building Phase [N]"

This scan runs ONCE per build session initiation, not per story.
```

### B — Pre-story stub gate (new sub-section before Step 1)

In the build loop, before Step 1 ("Spawn the builder"), after the pre-story
schema gate:

```
### Pre-story stub gate

Read the story file: docs/stories/<RAIL>/<RAIL>-NNN.md

Check for delegation language — any of these in the story body:
- "See phase doc"
- "See docs/phases/"
- "See phase-"
- "full spec" followed by a phase doc reference

Also check for missing acceptance surface:
- No ## Ensures section AND no ## Acceptance criterion section AND
  no ## Acceptance criteria section

If delegation language found OR no acceptance surface:

  PRE-STORY BLOCK — Story [RAIL-NNN] is a stub.

  [If delegation language:] Story file delegates implementation authority
  to the phase doc. The phase doc is not the builder's contract — the story
  file is.

  [If no acceptance surface:] Story file has no Ensures or Acceptance
  criterion. The builder has no spec to build against.

  Action required:
  1. Read the relevant section of the phase doc for this story.
  2. Write the full acceptance criterion and implementation guidance into
     docs/stories/<RAIL>/<RAIL>-NNN.md (## Ensures or ## Acceptance
     criterion, ## Instructions/## Design as needed).
  3. Remove or summarise the embedded section in the phase doc.
  When resolved, say: "Continue building"

Do not spawn the builder until this gate passes.
```

### C — Both changes applied to CLAUDE.build.md.j2 AND CLAUDE.build.md

The template and its rendered flex copy must be in sync after this story.

## Out of scope

- Do not change any other section of CLAUDE.build.md.j2.
- Do not add CLI calls for the stub check — the orchestrator reads the file
  directly (INFRA-134 is a future CLI story).
- Do not modify reviewer.md.j2 — that is BUILD-010.
