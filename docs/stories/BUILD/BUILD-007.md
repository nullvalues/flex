---
id: BUILD-007
rail: BUILD
title: Add phase/story boundary policy to CLAUDE.build.md.j2
status: complete
phase: "50"
story_class: methodology
primary_files:
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - CLAUDE.build.md
---

# BUILD-007 — Add phase/story boundary policy to CLAUDE.build.md.j2

## Background

The orchestrator's build file (`CLAUDE.build.md` and its canonical template
`CLAUDE.build.md.j2`) has no rule prohibiting implementation detail from being
written into the phase doc. The absence of the rule, combined with the natural
tendency to capture context while drafting, causes boundary collapse: phase docs
balloon with file paths, test instructions, and codebase recon that belong in
story files.

## Acceptance criterion

A **`## Spec surface discipline`** section is added to both
`skills/pairmode/templates/CLAUDE.build.md.j2` and the rendered
`CLAUDE.build.md`, placed between `## Before the first build loop` and
`## Model evaluation`.

The section must contain:

```
## Spec surface discipline

Phase doc = planning surface: Goal, Stories table, phase-exit criteria,
optional Resume marker. Nothing else.

Story spec = implementation surface: acceptance criterion, primary_files/touches,
background/context, implementation guidance, tests.

Before starting the build loop, check the phase doc for boundary violations:
- Story rows with embedded implementation sub-sections (#### Instructions,
  #### Tests, #### Changes written directly under a story heading in the phase
  file) — extract them to the story file before building that story.
- Codebase recon prose in the phase doc — move it to the relevant story spec
  or discard; it will be re-derived by the builder.

Never write implementation detail into the phase doc while planning. The plan-time
cost of drafting inline is paid again when the builder re-reads the codebase and
the stale recon creates confusion.
```

The section must be present verbatim in both files (`.j2` uses the literal text,
not a template variable).

## Out of scope

- Do not modify any other section of CLAUDE.build.md.j2.
- Do not change downstream project CLAUDE.build.md files — they pick up the
  change on their next `pairmode sync`.
