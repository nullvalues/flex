---
id: INFRA-361
rail: INFRA
title: Establish Narrative of Record in docs/architecture.md; propose CLAUDE.md cold-start quad
status: complete
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

## Proposed CLAUDE.md addition

The following wording is proposed for `CLAUDE.md` § "read before any task" — extending the
cold-start triad to a quad. The exact edit is deferred pending explicit operator approval, not
made unilaterally by this story, per the asymmetric-caution posture INFRA-318 established.

**Proposed replacement for lines 73–78 of CLAUDE.md:**

```
## read before any task
1. `docs/brief.md` — what and why (operator intent)
2. `docs/architecture.md` — how and architectural decisions
3. Current phase file from `docs/phases/` (see current phase for active stories); or `docs/phase-prompts.md` for legacy projects that have not migrated
4. `docs/narratives/` — role expectations and how the build loop works (what each role must be able to do, expect, and avoid)

These four documents should be sufficient for any model or toolchain to cold-start this project
and reproduce a valid variant without prior session context. The triad (items 1–3) documents
the software; Narrative of Record (item 4) documents the loop that builds it — together they
make the system reproducible end-to-end.
```

This addition makes the quad explicit and documented, matching the principle that introduced
the cold-start triad itself: that a future agent or operator with no access to prior conversation
should be able to continue the work by reading only the committed artifacts.

**Operator decision recorded 2026-08-03: approved.** Applied verbatim to `CLAUDE.md`.

## Out of scope

- Deciding the CLAUDE.md change unilaterally — explicitly not this story's call to make alone.
