---
id: INFRA-361
rail: INFRA
title: Establish Narrative of Record in docs/architecture.md; propose CLAUDE.md cold-start quad
status: draft
phase: "118"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - docs/architecture.md
touches:
  - CLAUDE.md
  - docs/narratives/README.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

`docs/architecture.md`'s existing "read before any task" convention (mirrored in `CLAUDE.md`'s own
cold-start triad: `docs/brief.md`, `docs/architecture.md`, the current phase file) is stated as
"sufficient for any model or toolchain to cold-start this project." This story makes Narrative of
Record's relationship to that triad explicit in `docs/architecture.md` (a permanent, mechanical
edit), and *proposes* — but does not unilaterally decide — extending `CLAUDE.md`'s own triad to a
quad, since that file is this project's most foundational instruction surface and every future
cold-start session depends on getting it right.

## Requires

- INFRA-351 through INFRA-357 should have landed (there should be a real, synced Narrative of
  Record to document, not a description of an aspiration).

## Ensures

1. `docs/architecture.md` gains a section documenting Narrative of Record: what it is, where it
   lives (`docs/narratives/`), how it propagates (`NARRATIVE_FILES`/`sync-narratives`, INFRA-351/352),
   the OPERATOR seed-then-extend exception (INFRA-353), and how it's consumed
   (spec-writer's sixth bounded input, intent-reviewer's alignment check — INFRA-355/356).
2. `CLAUDE.md`'s cold-start triad is **not** silently edited to a quad by this story — instead, a
   `## Proposed CLAUDE.md addition` section is added to this story's own body (or a scratch
   location), stating the exact proposed wording, and `status: "revised"`-equivalent treatment
   applies: surface it for explicit operator decision rather than landing it unilaterally, the same
   asymmetric-caution posture INFRA-318 already established for raising a model tier above default.
3. If the operator approves the CLAUDE.md change (recorded as an explicit decision, not inferred),
   a follow-up commit makes the edit with the approval noted inline, mirroring the pinned
   `model: opus  # raise approved: <date>, <reason>` convention's spirit.
4. `docs/narratives/README.md` is updated to point at `docs/architecture.md`'s new section rather
   than duplicating the propagation-mechanism explanation in two places.

## Instructions

1. Write the `docs/architecture.md` section first — this is the mechanical, uncontroversial half.
2. Draft the exact proposed `CLAUDE.md` wording as a clearly-labeled proposal, not a fait accompli
   — present it for a real decision the way this era's own AskUserQuestion pattern has done for
   every genuinely foundational choice so far.
3. Only make the actual `CLAUDE.md` edit after that decision is recorded.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: green — this is a documentation-only story; verification is a human read of the new
section for accuracy against what INFRA-351 through 356 actually shipped, not a test assertion.

## Out of scope

- Deciding the CLAUDE.md change unilaterally — explicitly not this story's call to make alone.
