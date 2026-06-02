---
id: BUILD-015
rail: BUILD
title: "`spec next phase` orchestrated workflow"
status: planned
phase: "52"
story_class: methodology
primary_files:
  - CLAUDE.build.md
  - CLAUDE.build.md.j2
touches: []
---

# BUILD-015 — `spec next phase` orchestrated workflow

## Background

Phase specs are currently written manually or drafted inline in conversation
then committed by hand. This story adds a "spec mode" trigger to the
orchestrator that produces a committed, conforming phase spec + story files
via an opus Plan subagent, ready to hand off immediately to the build loop.

The Plan subagent receives a well-defined input surface: project orientation
(CLAUDE.md), the active era doc (arc context and rail conventions), an exemplar
story file (format reference), the phase template, and the user's intent. It
drafts the Stories table; the orchestrator shows it to the user for confirmation
before writing any files.

This is a parallel workflow to build mode. It never enters the build loop.

## Ensures

- `CLAUDE.build.md` gains a "Spec mode" section triggered by:
  - `"spec next phase [intent]"` — derives phase number automatically
  - `"spec phase N: [intent]"` — uses the given phase number
- Spec mode workflow:
  1. Calls `flex_build.py current-phase --project-dir .` to find last phase;
     derives N+1. If `"spec phase N"` was given, uses N directly.
  2. Reads the active era doc (`docs/eras/NNN-*.md` where `status: active`).
  3. Spawns a `Plan` subagent (model: opus) with:
     - Content of `CLAUDE.md` (project orientation)
     - Content of the active era doc (arc, rails, what phases this era has covered)
     - Content of one recent `story_class: code` exemplar from `docs/stories/`
     - Content of `skills/pairmode/templates/docs/phases/phase.md.j2`
     - The user's intent string
     - Instruction: "Draft a phase spec for Phase N: [intent]. Return ONLY a
       proposed Stories table (ID, Title, story_class) and a one-paragraph Goal.
       Do not write files. Do not include implementation detail."
  4. **Confirm gate** — orchestrator presents the Plan subagent's draft:
     ```
     SPEC DRAFT — Phase N: [title]
     Goal: [paragraph]
     Stories:
       RAIL-NNN  [title]  [story_class]
       ...
     Proceed with commit? Say "commit spec" to write and commit these files,
     or give feedback to revise.
     ```
     Waits for user response before continuing.
  5. On "commit spec": calls `phase_new.py --phase N --project-dir .` to
     scaffold the phase file, then spawns a second Plan subagent (same inputs
     + confirmed Stories table) to write the full story files.
  6. Orchestrator commits: `docs/phases/phase-N.md` + all story files with
     message `"spec(phase-N): scaffold phase and story specs [spec-mode]"`.
  7. Reports:
     ```
     Phase N spec committed (M stories).
     Stories: [RAIL-NNN list]
     Say "build phase N" to start the build loop.
     ```
- On feedback (any response other than "commit spec"): re-spawns the Plan
  subagent with the feedback appended to the intent. Returns to the confirm
  gate. Maximum two revision rounds before asking the user to proceed or abort.
- Spec mode never spawns a builder or reviewer.
- `CLAUDE.build.md.j2` updated to match.

## Out of scope

- Multi-rail phase planning with complex inter-story dependencies (the Plan
  subagent can propose stories across rails; dependency ordering is manual).
- Automatic story ID collision detection (operator adjusts before building;
  the stub gate catches missing acceptance criteria at build time).
- Era creation during spec mode (see BUILD-017).

## Instructions

### 1. Add "Spec mode" section to `CLAUDE.build.md`

Insert after the "Session modes" section:

```markdown
## Spec mode

Triggered by:
- `"spec next phase [intent]"` — intent describes what the phase should accomplish
- `"spec phase N: [intent]"` — specifies the phase number explicitly

In spec mode: follow the spec workflow below. Do not enter the build loop.

### Spec workflow

1. **Determine phase number.**
   Call `flex_build.py current-phase --project-dir .` and add 1.
   If trigger specified a phase number, use it directly.

2. **Read the active era.**
   Scan `docs/eras/*.md` for the file with `status: active`. Read it in full.
   If no active era exists, stop and report: "No active era found. Run
   `flex_build.py transition-era` or create an era before speccing a phase."

3. **Spawn Plan subagent** (model: opus) with:
   - Content of `CLAUDE.md`
   - Content of the active era doc
   - Content of one recent `story_class: code` story from `docs/stories/`
     as format exemplar
   - Content of `skills/pairmode/templates/docs/phases/phase.md.j2`
   - The user's intent string
   - Instruction: "Draft a phase spec for Phase [N]: [intent]. Return ONLY:
     (a) a one-paragraph Goal, and (b) a proposed Stories table with columns
     ID | Title | story_class. Do not write files. Do not include
     implementation detail. Propose IDs continuing from the last used ID
     in each rail."

4. **Confirm gate.**
   Present the draft to the user:
   ```
   SPEC DRAFT — Phase N
   Goal: [paragraph from Plan subagent]

   Stories:
     [RAIL-NNN]  [Title]  [story_class]
     ...

   Say "commit spec" to write and commit these files.
   Or give feedback to revise (max 2 rounds).
   ```
   Wait for user response.

5. **On "commit spec":**
   a. Scaffold the phase file:
      ```bash
      PATH=$HOME/.local/bin:$PATH uv run python /path/to/phase_new.py \
        --phase N --project-dir .
      ```
   b. Spawn a second Plan subagent (same inputs + confirmed Stories table)
      with instruction: "Write the full story files for this phase. For each
      story in the confirmed table, produce `docs/stories/<RAIL>/<ID>.md`
      with frontmatter + Background + Ensures + Out of scope + Instructions +
      Tests. Also update `docs/phases/phase-N.md` with the Goal and Stories
      table. Phase doc = planning surface only."
   c. Commit:
      ```bash
      git add docs/phases/phase-N.md docs/stories/
      git commit -m "spec(phase-N): scaffold phase and story specs [spec-mode]"
      ```
   d. Report:
      ```
      Phase N spec committed (M stories).
      Stories: [list IDs]
      Say "build phase N" to start the build loop.
      ```

6. **On feedback (not "commit spec"):**
   Re-spawn the Plan subagent with the original inputs plus the user's feedback
   appended. Return to step 4. After two revision rounds without "commit spec",
   stop and report: "Spec revision limit reached. Edit the files manually or
   restart spec mode with a refined intent."
```

### 2. Update `CLAUDE.build.md.j2`

Mirror the spec mode section in the Jinja2 template.

## Tests

`TEST RUN: methodology story — no logic module.`

Acceptance verified by: `"spec next phase [intent]"` triggering the confirm
gate with a draft Stories table, "commit spec" producing committed files, and
`flex_build.py check-stubs --project-dir .` exiting 0 on the resulting files.
