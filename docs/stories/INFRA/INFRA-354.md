---
id: INFRA-354
rail: INFRA
title: Backfill flex's own docs/narratives/ from the new template source (real dogfood backfill)
status: draft
phase: "118"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - docs/narratives
touches:
  - docs/stories/INFRA/INFRA-354.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

INFRA-351 moves the nine harness-role narratives' content into template source; INFRA-352 adds the
`sync-narratives` add-missing-file path; INFRA-353 adds OPERATOR's seed-then-extend mechanism. This
story is the real-world dogfood step, directly mirroring INFRA-332's own backfill discipline
(Phase 116: "ran the equivalent bootstrap-parity path against both /mnt/work/flex and
/mnt/work/flex-harness... verified by reading the generated files, not by exit code"). flex's own
`docs/narratives/<ROLE>/*.md` were hand-authored directly in this era, *before* the template
existed — this story reconciles flex's own tree to be the genuine first materialized/synced copy
of the template, not a one-off that happens to look similar to it.

## Requires

- INFRA-351, INFRA-352, INFRA-353 must all land first.

## Ensures

1. flex's own `docs/narratives/<ROLE>/<ROLE>-000-ideology.md` for all nine harness-role narratives
   is regenerated via the real `sync-narratives` (or `bootstrap`) mechanism from INFRA-351/352 —
   not hand-copied — and the regenerated content is read directly and compared against this era's
   originally-authored versions to confirm no substantive content was lost or altered in the
   template-extraction step (INFRA-351's Instructions left this as an explicit authorial judgment
   call to record — this story is where that record gets verified against the actual rendered
   output).
2. `docs/narratives/OPERATOR/OPERATOR-000-ideology.md` is regenerated from the new generic seed
   template (INFRA-353) — this **replaces** flex's era-specific hand-authored OPERATOR content at
   `-000`; that era-specific content (the concrete findings about the escalation ladder, dead
   features, etc.) is preserved by moving it into a new
   `docs/narratives/OPERATOR/OPERATOR-010-flex.md` extension file, so nothing this era wrote about
   flex's actual operator experience is lost — it just moves to where a project-specific extension
   belongs.
3. Real backfill evidence, read directly (not inferred from exit code): before/after file listing
   of `docs/narratives/` and a diff summary showing what changed in each of the ten regenerated
   `-000` files, written into this story's own `## Evidence` section.
4. `git status --short docs/narratives/` after the backfill shows exactly what's expected (content
   changes to existing `-000` files, one new `OPERATOR-010-flex.md`) — no unexpected additions or
   deletions.

## Instructions

1. Run the actual `sync-narratives`/bootstrap-parity path (per INFRA-352's landed mechanism)
   against `/mnt/work/flex` itself, the same way INFRA-332 did for `.claude/agents/`.
2. Read every regenerated file directly and diff it against the pre-backfill version (available in
   git history) — confirm the extraction in INFRA-351 preserved the substantive content (Always
   true / Never / Open gaps items), not just structural shape.
3. For OPERATOR specifically: extract this era's flex-specific findings (the escalation-ladder
   evidence, the dead-feature findings, the "no standing signal" gap) from the original
   `OPERATOR-000` into the new `OPERATOR-010-flex.md`, then let `OPERATOR-000` be overwritten by
   the generic seed.
4. Write the before/after Evidence section directly into this story file once merged — matching
   INFRA-332's own Evidence-section convention.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: green; no test regression from the content changes (these are markdown-only,
no code-path changes of their own).

## Out of scope

- Any new narrative content beyond what already exists in this era's authored drafts and the
  seed/extend split — this is a reconciliation story, not an authoring story.
