---
id: INFRA-350
rail: INFRA
title: De-couple pairmode tests from operator gpg-signing config
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

CER-157 (LOW), filed from `docs/build-loop-cold-eyes-review-20260801.md`'s §5 (opus finding M8):
137 pairmode tests fail headless (no interactive gpg agent available for pinentry) because they
shell out to real `git commit` and inherit the operator's global `commit.gpgsign` config; all 137
pass with `commit.gpgsign=false`. This is not hypothetical: this exact failure mode hit live in this
session while committing the artifacts for this very phase (`git commit` failed with "gpg: signing
failed: Operation cancelled" on the first attempt, resolved only because the operator was available
at a keyboard to unlock the agent). A CI or any headless/background build session would read red
for a non-reason. Same general class as CER-146 (a different environment-coupling axis — cwd path
substring matching rather than signing config).

Fix direction: the affected tests should set `commit.gpgsign=false` (or an equivalent
no-signing config) scoped to their own throwaway git fixture repos — never the operator's real
global config — so the tests verify actual git-commit behavior without depending on whether an
interactive pinentry is available in the environment they happen to run in.

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
