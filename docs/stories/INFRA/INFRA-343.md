---
id: INFRA-343
rail: INFRA
title: Fix checkpoint build gate: 60s timeout silently passes on a 175s+ suite
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

HIGH finding F9 of `docs/build-loop-cold-eyes-review-20260801.md` (opus, measured empirically):
`_run_build_gate_subprocess` (`next_action.py`, guard 3 of `check_checkpoint_guards`) runs the
pairmode test suite with a hardcoded 60-second `subprocess.run(..., timeout=60)` and returns `True`
(gate green) on any timeout or exception — documented inline as "advisory: fail open on error or
timeout." Opus measured flex's own suite at ~175 seconds — nearly 3x the timeout — meaning this
gate has never actually completed a real run in this repo; it always times out and always reports
green. The only real test-verification happening at checkpoint time in practice has been the
reviewer's own manual `pytest` run, which is not gated on by anything.

Fix direction: either raise the timeout to something that reflects reality (with margin — the
suite will keep growing; consider deriving it from a stored baseline duration rather than a fixed
constant, or removing the timeout for this specific gate context since a checkpoint call is
expected to take minutes, not seconds), or restructure so a timeout is distinguishable from a real
pass in whatever surfaces the checkpoint-report output (rather than silently fail-open to green).
Consider whether "fail open" is the right default here at all, given this guard exists specifically
to catch what the human-run reviewer suite might miss between review and checkpoint.

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
