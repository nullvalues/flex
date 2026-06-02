---
id: BUILD-008
rail: BUILD
title: Add boundary reminder comment to phase.md.j2
status: complete
phase: "50"
story_class: doc
primary_files:
  - skills/pairmode/templates/docs/phases/phase.md.j2
---

# BUILD-008 — Add boundary reminder comment to phase.md.j2

## Background

Every new phase doc is scaffolded from `phase.md.j2`. The template has no
comment reminding the drafter (LLM or human) that the phase doc is a planning
surface only. Adding a visible HTML comment to the raw template means every
scaffolded file carries the constraint in its source — visible when reading
with the `Read` tool but invisible in rendered views.

## Acceptance criterion

An HTML comment is added to `phase.md.j2` immediately after the nav links block
and before `## Goal`:

```
<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
```

The comment must appear in the raw template source (not as a Jinja `{# #}`
comment — those are stripped at render time and would not appear in scaffolded
files).

## Out of scope

- Do not add sections or optional blocks to the template.
- Do not change the template's Jinja logic.
- Do not update any existing rendered phase docs.
