---
id: INFRA-341
rail: INFRA
title: Wire spawn-gate-worker's verdict to a real consumer, closing the INFRA-331 livelock
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

CRITICAL finding F8 of `docs/build-loop-cold-eyes-review-20260801.md` (opus): `spawn-gate-worker`
(Row 4b, added by INFRA-313/INFRA-331 this era) is a livelock. `CLAUDE.build.md`'s dispatch branch
spawns the gate-worker and re-polls `next-action`, with no instruction anywhere to route the
worker's stdout to anything. `parse_worker_verdict_json`/`route_gate_verdict` have zero non-test
callers (`route_gate_verdict`'s only caller is a test). The gate-worker's own procedure document
(`skills/pairmode/skills/gate-worker/procedure.md`) asserts "the orchestrator feeds stdout directly
to `parse_worker_verdict_json`" — it does not. Since the gate's inputs (story frontmatter, phase
manifest) don't change between polls, and nothing consumes or acts on the verdict, `spawn-gate-worker`
re-emits identically on every subsequent poll — the resolver's own docstring even frames this as a
deliberate idempotence feature, when it is in fact the livelock.

Fix direction: wire `CLAUDE.build.md`'s dispatch branch (and its `.j2` template — coordinate with
INFRA-342, which is reconciling the two files this same phase) to actually capture the gate-worker's
stdout, parse it via `parse_worker_verdict_json`, and route the verdict via `route_gate_verdict` to
whatever the intended downstream effect is (blocking the story's build dispatch on a non-clean
verdict, most likely — check `docs/architecture.md`'s gate-worker design intent and this era's
CER-138/AG-13 origin for what "acting on the verdict" was supposed to mean). Coordinate with
INFRA-340 if the fix requires the action grammar to carry a real model for this action.

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
