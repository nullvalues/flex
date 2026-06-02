---
id: BUILD-023
rail: BUILD
title: "Proposed-phase naming convention — canon and syncable policy"
status: complete
phase: "53"
story_class: methodology
primary_files:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - docs/phases/index.md
  - skills/pairmode/templates/docs/phases/index.md.j2
---

# BUILD-023 — Proposed-phase naming convention — canon and syncable policy

## Background

Sequential phase numbers create a false sense of commitment for phases that
are conceived speculatively — the number implies "this is next" when the phase
may be months away or may never ship in its original form. The result seen with
phase-49 (Observability SPA): a sequentially-numbered anchor phase sitting
between two active build phases for multiple era-1 phases, creating confusion
about era boundaries and phase ordering.

The policy established by this story: any phase conceived before it is the
literal next-in-queue gets a **proposed** filename instead of a sequential
number. When the phase is finally sequenced, its stories are absorbed into
the next available build phase and the proposed file is deleted — git history
records the transit without leaving a zombie entry in the index.

**File convention:**

```
docs/phases/phase-proposed-<kebab-name>-YYYYMMDD-NNN.md
```

- `<kebab-name>` — short kebab-cased description of the phase intent
- `YYYYMMDD` — date of proposal (ISO, no separators)
- `NNN` — same-day sequence counter, zero-padded to 3 digits (001, 002, …)

Example: `phase-proposed-observability-spa-20260602-001.md`

**Index convention:**

Proposed phases do not appear in the main `| Phase | Title | Status | Tag |`
table. They appear under a separate `## Proposed phases (not yet sequenced)`
section with their filename, title, and target era.

**Sequencing workflow:**

When a proposed phase is ready to build:
1. Move its stories into the next available sequential phase (new or existing).
2. Git-delete the proposed file (`git rm`).
3. Remove its row from the `## Proposed phases` section of `index.md`.
4. The sequential phase's commit message may reference the proposed file for
   transit traceability.

This policy must propagate to downstream projects via `sync-build`. The
`index.md.j2` template gets the `## Proposed phases` section stub so
bootstrapped projects inherit the convention.

## Ensures

- `CLAUDE.build.md` gains a "Proposed phases" subsection under
  `## Spec surface discipline` (or equivalent) documenting:
  - The filename convention `phase-proposed-<kebab-name>-YYYYMMDD-NNN.md`
  - The rule: no sequential number until the phase is literally next in queue
  - The index placement: `## Proposed phases` section, not the main table
  - The sequencing workflow: absorb stories → delete file → remove index row
- `skills/pairmode/templates/CLAUDE.build.md.j2` mirrors the new section.
- `skills/pairmode/templates/docs/phases/index.md.j2` gains the
  `## Proposed phases (not yet sequenced)` section stub with the convention
  description and an empty table (header row only), so bootstrapped projects
  get the structure from day one.
- The live `docs/phases/index.md` already has the section (applied as doc
  hygiene before this story shipped); the template update ensures downstream
  projects inherit it on next `sync-build`.
- A grep for `phase-proposed` in `CLAUDE.build.md` and its `.j2` returns at
  least one match in the spec-discipline section of each file.

## Out of scope

- Automating the sequencing workflow with a CLI script (the steps are simple
  enough to describe in prose; a future INFRA story can automate if friction
  is observed).
- Retroactively renaming any other phase docs — only future proposed phases
  use this convention; historical misnumbered phases are recorded as-is.
- Changes to `phase_new.py` — it scaffolds sequential phases on demand;
  proposed phases are created manually or via a future `phase_new.py
  --proposed` flag.

## Instructions

### 1. Add "Proposed phases" policy to `CLAUDE.build.md`

In `CLAUDE.build.md`, in the `## Spec surface discipline` section (after the
existing Phase doc / Story spec surface definitions), add:

```markdown
### Proposed phases

A phase conceived before it is literally the next build target gets a
**proposed filename** instead of a sequential number:

```
docs/phases/phase-proposed-<kebab-name>-YYYYMMDD-NNN.md
```

- `<kebab-name>` — short kebab-cased description
- `YYYYMMDD` — proposal date (ISO, no separators)
- `NNN` — same-day sequence counter (001, 002, …)

Proposed phases do not appear in the main phase table in `docs/phases/index.md`.
They appear under a `## Proposed phases (not yet sequenced)` section.

**Sequencing a proposed phase:**
1. Move its stories into the next available sequential phase.
2. `git rm` the proposed file.
3. Remove its row from the `## Proposed phases` section of `index.md`.
Git history records the transit.
```

### 2. Mirror in `CLAUDE.build.md.j2`

Apply the same addition to `skills/pairmode/templates/CLAUDE.build.md.j2`.

### 3. Add `## Proposed phases` stub to `index.md.j2`

In `skills/pairmode/templates/docs/phases/index.md.j2`, after the main
phase table, add:

```markdown
---

## Proposed phases (not yet sequenced)

Phases conceived before they enter the build queue. No sequential number
until sequenced. When sequenced, stories are absorbed into the next available
phase and this file is deleted (git history records the transit).

| Proposed file | Title | Era |
|---------------|-------|-----|
```

### 4. Local sanity check

```bash
grep -n "phase-proposed" CLAUDE.build.md skills/pairmode/templates/CLAUDE.build.md.j2
grep -n "Proposed phases" skills/pairmode/templates/docs/phases/index.md.j2
```

Both should return at least one match per file.

## Tests

`TEST RUN: methodology story — no test file expected.`

Acceptance verified by:
1. Grep checks above return matches.
2. The three files (`CLAUDE.build.md`, `CLAUDE.build.md.j2`, `index.md.j2`)
   each contain the `phase-proposed-<kebab-name>-YYYYMMDD-NNN` filename
   pattern spelled out explicitly.
3. `docs/phases/index.md` has the `## Proposed phases` section with the
   observability-spa entry (already present from doc-hygiene commit).
