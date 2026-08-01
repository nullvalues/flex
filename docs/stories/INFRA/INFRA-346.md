---
id: INFRA-346
rail: INFRA
title: Unify the two phase-completion definitions so the resolver's own gate is at least as strict as checkpoint-tag's deferral gate
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

HIGH finding F13 of `docs/build-loop-cold-eyes-review-20260801.md` (opus): two disagreeing
definitions of "phase complete" exist, and the checkpoint sequence's own ordering lets the weaker
one gate all the expensive work before the stronger one gets a chance to refuse. The resolver's
own phase-completion guard (`next_action._check_phase_completion`) reads only the phase doc's
Stories table, accepting `complete`/`deferred` with no requirement that a `deferred` row actually
have a `## Deferred stories` section. The `checkpoint-tag` step's deferral gate
(`flex_build._deferral_gate_message`, built by INFRA-314) reads story-file frontmatter and
requires `index_integrity.is_formally_deferred` — the stronger, correct check. But
`CLAUDE.build.md`'s mandated order calls `record-checkpoint-step checkpoint-tag` directly after
`checkpoint-report`, without re-polling `next-action` first — so a phase with a story that's
`complete`/`deferred` in the table but missing/wrong in its own frontmatter still gets all three
checkpoint workers (security/intent/docs) spawned and their results recorded before the terminal
step finally refuses. Correct outcome, but only after the expensive part already ran.

Fix direction: make `_check_phase_completion` consult the same `is_formally_deferred` predicate
`_deferral_gate_message` already uses (both should share one definition, not two), so the weaker
check can no longer diverge from the stronger one and the resolver refuses to dispatch
`checkpoint-security` in the first place when a story's own frontmatter disagrees with its
phase-table row.

## Requires
<!-- Prior stories, system state, or file conditions that must hold before building. -->

## Ensures
<!-- Binary assertions the reviewer checks independently. One per line.
     Each must be verifiable without interpretation: file exists, command output
     contains X, function Y returns Z. -->
<!-- State the correct signal AND the forbidden proxy (INFRA-314): e.g. "the
     write is absent after refusal; forbidden proxy: a warning line while the
     write happens anyway." -->

## Instructions

## Tests
