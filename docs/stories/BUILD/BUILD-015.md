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

The Plan subagent receives a tight, well-defined input surface — not the full
architecture.md, just the three things it needs to produce conforming files:
project orientation (CLAUDE.md), the story file format (an exemplar), and the
user's intent for the new phase. It writes the files; the orchestrator commits
and reports ready.

This is a parallel workflow to build mode. It never enters the build loop.

## Ensures

- `CLAUDE.build.md` gains a "Spec mode" section at the same level as "Build
  mode", triggered by:
  - `"spec next phase [intent]"` — derives phase number automatically
  - `"spec phase N: [intent]"` — uses the given phase number
- Spec mode workflow:
  1. Calls `flex_build.py current-phase` to find the last phase; derives N+1
     as the new phase number. If `"spec phase N"` was given, uses N directly.
  2. Calls `phase_new.py --phase N --project-dir .` to scaffold the phase file.
  3. Spawns a `Plan` subagent (model: opus) with:
     - Content of `CLAUDE.md` (project orientation — what/why)
     - Content of one exemplar story file from `docs/stories/` (format reference)
     - Content of `skills/pairmode/templates/docs/phases/phase.md.j2`
       (phase file format)
     - The user's intent string
     - Instruction: "Write a phase spec for Phase N with the given intent.
       Produce: (a) a completed Stories table for `docs/phases/phase-N.md`,
       replacing the empty scaffold; (b) one story file per story under
       `docs/stories/<RAIL>/`. Use the story format from the exemplar.
       Do not write implementation detail into the phase doc — story-level
       detail belongs in story files only."
  4. Plan subagent writes the phase file (Stories table) and all story files.
  5. Orchestrator commits: `docs/phases/phase-N.md` + all story files under
     `docs/stories/` with message
     `"spec(phase-N): scaffold phase and story specs [spec-mode]"`.
  6. Orchestrator reports:
     ```
     Phase N spec committed (M stories).
     Story files: [list IDs]
     Say "build phase N" to start the build loop.
     ```
- Spec mode explicitly does not spawn a builder or reviewer.
- `CLAUDE.build.md.j2` updated to match.

## Out of scope

- Iterative spec refinement or user feedback mid-spec.
- Multi-rail phase planning with inter-story dependencies.
- Automatic story ID allocation (Plan subagent proposes IDs; operator adjusts
  before building if needed).
- Validation of produced story files against the stub gate (BUILD-011/BUILD-012
  gates catch issues at build time).

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
   If trigger was `"spec next phase"`: call `flex_build.py current-phase
   --project-dir .` and add 1 to the returned phase number.
   If trigger was `"spec phase N"`: use N directly.

2. **Scaffold the phase file.**
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python /path/to/phase_new.py \
     --phase N --project-dir .
   ```

3. **Spawn the Plan subagent** (model: opus) with:
   - Content of `CLAUDE.md`
   - Content of one recent story file as format exemplar
     (choose a `story_class: code` story from `docs/stories/`)
   - Content of `skills/pairmode/templates/docs/phases/phase.md.j2`
   - The user's intent string
   - Instruction:
     "Write a phase spec for Phase [N]: [intent].
     Produce:
     (a) A completed Stories table for `docs/phases/phase-N.md` — replace the
         empty scaffold. Phase doc = planning surface only: Goal + Stories table.
         No implementation detail in the phase doc.
     (b) One story file per story at `docs/stories/<RAIL>/<RAIL>-NNN.md`.
         Match the exemplar format: frontmatter + Background + Ensures +
         Out of scope + Instructions + Tests sections.
         Story files carry the full spec; phase doc carries only the table row.
     Propose story IDs continuing from the last used ID in that rail."

4. **Commit the spec files.**
   ```bash
   git add docs/phases/phase-N.md docs/stories/
   git commit -m "spec(phase-N): scaffold phase and story specs [spec-mode]"
   ```

5. **Report.**
   ```
   Phase N spec committed (M stories).
   Stories: [RAIL-NNN list]
   Say "build phase N" to start the build loop.
   ```
```

### 2. Update `CLAUDE.build.md.j2`

Mirror the spec mode section in the Jinja2 template.

## Tests

`TEST RUN: methodology story — no logic module.`

Acceptance verified by: running `"spec next phase [intent]"` producing
committed phase and story files that pass the BUILD-011 stub gate check
(`flex_build.py check-stubs --project-dir .` exits 0 on the new files).
