---
id: INFRA-349
rail: INFRA
title: Docstring-currency sweep: fix harness docstrings/comments that misdescribe live wiring
status: draft
phase: "117"
story_class: doc
auth_gated: false
schema_introduces: false
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

CER-156 (LOW), filed from `docs/build-loop-cold-eyes-review-20260801.md`'s §5: multiple docstrings
and comments in the harness actively misdescribe current wiring rather than describing it
accurately — the same class of drift CER-078/CER-085 already flagged elsewhere in this project.
Known instances found by the review (grep for the current text first — other stories in this phase
may have already fixed some of these as a side effect; don't duplicate):

- `flex_build.cmd_next_action`'s own docstring still says "Advisory only — not wired into the live
  CLAUDE.build.md loop (DP7)" when it is the live loop driver.
- `cmd_record_intent_review`'s docstring references a nonexistent `_is_fresh_phase`.
- A `next_action.py` Row-PBI comment claims `checkpoint-intent` carries a model override — it does
  not (see INFRA-340 in this same phase, which may fix the underlying behavior rather than just the
  comment — check its landed shape first).
- `.claude/agents/spec-writer.md` claims `select_spec_writer_model` doesn't exist when it's wired
  (from INFRA-333, Phase 116).

This should build after INFRA-336/338/339/340/341/342/346/347 land, since several of those stories
will change the actual wiring these comments describe — sweep for currency against the *final*
state of this phase, not a mid-phase snapshot.

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
