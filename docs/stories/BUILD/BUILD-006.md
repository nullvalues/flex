---
id: BUILD-006
rail: BUILD
title: Update CER-030 with boundary-collapse framing
status: complete
phase: "50"
story_class: doc
primary_files:
  - docs/cer/backlog.md
---

# BUILD-006 — Update CER-030 with boundary-collapse framing

## Background

CER-030 (Do Later) diagnosed phase-spec drift as "no canonical source of truth /
template gap." The diagnosis is correct but incomplete. The primary driver,
confirmed 2026-06-01 across forqsite, radar, and cora, is **boundary collapse**:
orchestrators embed story-level implementation specs (file paths, test instructions,
acceptance criteria) and codebase recon prose directly in the phase doc during
plan time. The template being thin is a secondary contributing factor.

CER-030's current "fix shape" — enrich the template, add exemplars, add a
structural lint — addresses the template gap but does not name the boundary
collapse as the root cause or prohibit the practice.

## Acceptance criterion

`docs/cer/backlog.md` CER-030 entry is updated:

1. A "**Root cause (updated 2026-06-01):**" paragraph is prepended to the finding
   body, naming boundary collapse as the primary driver with the two failure modes:
   (a) embedded specs — story-level implementation detail written inline in the
   phase doc; (b) recon accumulation — codebase recon prose preserved in the phase
   doc after drafting.

2. A partial-resolution note is appended to the Phase column cell:
   `**PARTIAL-RESOLUTION Phase 50 BUILD-006/007/008** — root-cause diagnosis
   updated; policy gap addressed. Template structural enrichment (type flags,
   exemplars, lint) remains open.`

3. CER-030 stays in Do Later (the structural template work is not addressed by
   Phase 50).

## Out of scope

- Do not change the original finding text — prepend to it.
- Do not move CER-030 to Do Now or Do Never.
- Do not update any other CER entry.
