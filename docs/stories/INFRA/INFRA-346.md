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

**Folded in (era 004's own goal is zero unresolved operational findings, not "later" — same
checkpoint/era-completion subsystem this story is already touching):**

- **CER-154 (LOW):** era-ledger flip failures are silently swallowed — `_flip_era_ledger_row`'s
  `"not_found"` return value is computed and discarded by its caller, so `checkpoint-tag` can
  silently leave the era ledger stale while the phase-index flip succeeds; compounded by the search
  being restricted to `status: active` era docs, so re-tagging a phase from an already-closed era
  silently skips the ledger entirely. Separately, `era_transition`'s disposition gate fails open on
  any unparseable `## Phases` ledger table (no cells matching exactly `phase`/`status` → vacuous
  `[]` → the gate passes and "Era N closed" prints over live, un-dispositioned phases). Surface
  `"not_found"` as a real error/warning instead of discarding it, and make the disposition gate
  fail *closed* (refuse) rather than open on an unparseable ledger.
- **CER-155 (LOW):** `docs/phases/index.md`'s `Tag` column is never mechanically written by any
  tool — rows 8-105 carry hand-written `· cpNN` suffixes, rows 106-116 carry none despite
  `cp-106`..`cp-116` all existing. Have `checkpoint-tag`'s mark-complete step also write the `Tag`
  cell, and have it verify the tag actually exists (git-side) before declaring the step done, so a
  failed `git tag && push` after a successful mark-complete is detectable rather than silently
  idempotent-and-useless on retry.
- **CER-158 (LOW):** `record-checkpoint-step` without an explicit `--phase-key` degrades ambiguity
  (one active phase plus queued `planned` rows — the common case) to a warning and stamps the step
  under key `""`, invisible to the keyed-shape resolver read — the same gate step can re-emit
  indefinitely. Since this story is already unifying the phase-completion checks, make this case a
  hard refusal (matching the "fail closed on ambiguity" spirit of CER-154's disposition-gate fix)
  rather than a silent no-op key.

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
