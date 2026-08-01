---
id: INFRA-342
rail: INFRA
title: Reconcile CLAUDE.build.md and its .j2 template; add an automated dispatch-parity drift check
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

HIGH finding F5 of `docs/build-loop-cold-eyes-review-20260801.md`, corroborated independently by
both reviewers: `CLAUDE.build.md` (live) and `skills/pairmode/templates/CLAUDE.build.md.j2` (the
template rendered for downstream/fresh-bootstrapped projects) have drifted in both directions. Live
has three `ACTION_SUBAGENT_TYPE` dispatch entries the template lacks (`checkpoint-docs: docs-reviewer`,
`spawn-gate-worker: gate-worker`, `spawn-spec-writer: spec-writer` — from INFRA-325/331); the
template has an `intent_review=` Build-standards key and `pause-context`/`record-intent-review`
handling prose that live lacks entirely (from INFRA-315/316). Each Phase 116 story edited exactly
one of the two files. Consequence: a project freshly bootstrapped today cannot dispatch three
actions `next_action.py` already emits live; conversely, if flex's own `CLAUDE.build.md` ever opts
into `intent_review=`, there is no instruction anywhere explaining what to do with the resulting
`spawn-intent-reviewer`/`pause-context` action. `pairmode_drift_report.py`/`audit.py` nominally
compare the two files but manifestly did not catch either direction of this drift.

Fix direction: reconcile both files to a single consistent state (this may depend on how INFRA-339
and INFRA-341 land, since pause-context and gate-worker dispatch are both in flux this phase — do
this reconciliation last, after those two stories, so it captures the final shape rather than a
mid-phase snapshot), then add an automated parity check (extending `audit.py`'s existing comparison
machinery, or a new dedicated test) that would have caught this drift the moment either file was
edited without the other.

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
