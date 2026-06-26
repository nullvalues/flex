---
id: "002"
name: flex — Build loop and observability
status: complete
closed_at: 2026-06-26
---

## Strategic intent

Era 002 extends the build loop with observability and intelligence: replacing the companion sidebar with a structured SPA, adding mechanical backlog grooming to the checkpoint sequence, capturing scope-miss patterns automatically, and closing the remaining spec-quality gaps that cause builder permission friction. The era's theme is surfacing what was previously invisible — scope misses, stale backlog items, context health — without requiring orchestrator recall to see them.

## Rails

| Rail | Primary domain |
|------|----------------|
| INFRA | infrastructure, CLI utilities, context budget, schema validation, observability SPA |
| BUILD | build loop, orchestrator, phase tooling |

## Phases

| Phase | Title | Status |
|-------|-------|--------|
| 58 | Context budget gate — state.json contract | complete |
| 59 | context_budget.py silent-fail edge closure (CER-040, CER-041) | complete |
| 60 | Checkpoint report intelligence — phase-key fix and next-phase detection | complete |
| 61 | Scope-Miss Capture & Pre-Story Scope Checks | complete |
| 62 | Context gate authorization clarity | complete |
| 63 | Observability SPA — read-only window glass | complete |
| 64 | Observability SPA hardening — cold-eyes review fixes | deferred |
| 65 | Context budget per-story drift fix | complete |
| 66 | PAIRMODE_VERSION single-source | complete |
| 67 | Bootstrap context-token seed | complete |
| 68 | SessionStart context-counter reset (CER-047) | complete |
| 69 | PreToolUse matcher dead under Agent rename (CER-049) | complete |
| 70 | Remove bump-context-tokens from orchestrator build loop | complete |
| 71 | Propagate BUILD-029 Context gate fix into CLAUDE.build.md.j2 template | complete |
| 72 | Restore JSONL-based context gate | complete |
| 73 | Per-story context token dict; revert Phase 72 JSONL gate | complete |
| 74 | PostToolUse JSONL context gate — deterministic, no LLM cooperation | complete |
| 75 | Phase 74 security remediation — bound JSONL scan, session_id containment, CLAUDE.md doc | complete |
| 76 | sync-build seeds context gate state on --apply | complete |
| 77 | multi-era index parser fix | complete |
| 78 | orchestrator pre-flight gate CLI offload | complete |

## Deferred stories

Per the phase-continuity policy, Phase 64 is deferred rather than abandoned:

- **Phase 64 — Observability SPA hardening (cold-eyes review fixes)** — deferred.
  Reason: Era 003's OBS rail (Phase G, `HARNESS007-main`) heavily refactors the
  observability SPA and the context-control mechanism, so hardening the current
  surface would be rebuilt-away work. Its five stories (INFRA-164, INFRA-165,
  INFRA-166, INFRA-167, INFRA-168) are deferred — **Resumed in Era 003 Phase G**.
  See `docs/agreements/era-002-closeout.md` (DC1) and the observability defects
  D1/D2/D3 captured for the same phase.
