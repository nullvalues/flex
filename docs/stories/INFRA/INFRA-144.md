---
id: INFRA-144
rail: INFRA
title: "Naming convention documentation"
status: complete
phase: "56"
primary_files:
  - skills/pairmode/SKILL.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - skills/pairmode/templates/docs/phases/index.md.j2
touches:
  - CLAUDE.build.md
  - docs/pairmode/PAIRMODE.md
---

# INFRA-144 — Naming convention documentation

## Context

The `PM-NNN-main` / `-post` / `-ante` suffix system is now supported by `phase_new.py`
(INFRA-143). This story makes the convention visible in methodology docs so other projects
can adopt it and so orchestrators know when to use each suffix type.

## Acceptance criteria

1. `SKILL.md` phase-new section updated:
   - `--phase-id N` description changed to accept a string (e.g. `PM025`).
   - `--suffix TEXT` flag documented with its purpose and common values.
   - Filename output examples updated for both integer and string forms.
   - Sort-order mnemonic documented: `-ante` < `-main` < `-post` alphabetically.

2. `templates/CLAUDE.build.md.j2` updated:
   - Adds a "Phase naming suffixes" paragraph or table under the "Phase lifecycle" section
     (or equivalent section) explaining when to use each suffix type:
     - `-main` — the primary phase
     - `-ante[N]` — preflight prerequisite that must complete before `-main` (blocks parent)
     - `-post[N]` — follow-on remediation that must complete before the next main phase
     - `-sec` — security prerequisite (same semantics as `-ante`, conventional security label)
   - Checkpoint tag naming follows the phase filename: `cp-PM025-main`, `cp-PM025-post1`, etc.

3. `CLAUDE.build.md` (the live file, not just the template) receives the same addition as
   the template, applied directly.

4. `templates/docs/phases/index.md.j2` updated:
   - Adds a `**Naming convention:**` block immediately after the project name heading (mirrors
     the structure forqsite uses in its own index.md).
   - Block documents: predicate, 3-digit zero-pad, suffix system with sort-order note, and
     checkpoint tag format. Template text uses generic placeholders (`<PRED>`) since projects
     choose their own predicates.

5. `docs/pairmode/PAIRMODE.md` updated:
   - Add a "Phase naming suffixes" subsection to the existing phase lifecycle coverage
     (or alongside "Design decisions") that names the convention and points to SKILL.md for
     the full spec.

## Out of scope

- Updating existing flex-project `docs/phases/index.md` (flex itself uses integer IDs; no
  change needed there).
- Renaming any existing phase files.
- Updating forqsite's docs (they already have the convention, this is the flex canon record).
