---
era: "003"
---

# flex — Phase 84: Spec preflight verification

← [Phase 83: Spec quality gates](phase-83.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->

## Goal

Actively verify spec content against the live codebase before the builder fires, catching factual errors — hallucinated API routes, wrong constant names — before a full build cycle is wasted. Phase 83 enforces spec structure; Phase 84 enforces spec truth. Two deliverables: `spec_preflight.py`, a new script that grep-scans the project source tree for routes and constants referenced in a story's Ensures/Instructions/Implementation notes sections, and a `spec-preflight` subcommand in `flex_build.py` that plugs it into the build loop between the schema gate and the stub gate.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-190 | spec_preflight.py — route and constant reference checker | complete |
| INFRA-191 | Orchestrator integration of spec_preflight via flex_build.py spec-preflight subcommand | planned |

## Schema delivery

No new persistent schema objects introduced in this phase.
