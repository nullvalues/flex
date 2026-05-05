---
id: INFRA-035
rail: INFRA
title: Effort recording for seed and companion subagent calls
status: planned
phase: "22"
primary_files:
  - skills/seed/scripts/mine_sessions.py
  - skills/seed/scripts/reconcile.py
  - skills/companion/scripts/sidebar.py
touches:
  - tests/pairmode/test_record_attempt_seed.py
  - tests/pairmode/test_record_attempt_companion.py
  - docs/architecture.md
---

## Acceptance criterion

Effort tracking captures invocations made by `skills/seed/` (during initial spec
mining and reconcile) and by `skills/companion/scripts/sidebar.py` (per pipe message
that triggers an LLM call). New `agent_role` values (`seed-miner`, `seed-reconcile`,
`sidebar-extractor`) are recorded alongside pairmode loop entries. A user running
`pairmode_effort.py rollup` after a seed + bootstrap + build sees all three skills'
compute effort, not just pairmode's.

## Protected file justification

This story modifies `skills/companion/scripts/sidebar.py` (a protected file) by
adding wrapper invocations of `record_attempt.py` after each LLM-extraction call.
Justification: the story is the entire point of "extending effort tracking to
companion." The wrapper invocations are purely additive — a single `subprocess.run`
or direct sqlite insert after each existing LLM call site. They do not modify the
spec/state write paths, the pipe contract, or the existing message-handler dispatch.
The `disable-model-invocation: true` flag on companion (per its SKILL.md) means the
orchestrator cannot tool-call into the sidebar; recording must therefore live inside
the sidebar's own Python code, not in the orchestrator.

The seed scripts (mine_sessions.py, reconcile.py) are NOT in the protected list but
are foundational; modifications follow the same additive pattern.

## Instructions

See `docs/phases/phase-22.md` — Story INFRA-035.

## Tests

See `docs/phases/phase-22.md` — Story INFRA-035.
