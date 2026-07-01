---
era: "003"
phase_class: production
---

# project — Phase HARNESS007-main: Observability refactor (Phase G)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->

## Goal

Rework the observability SPA and API to read the resolver state model (next-action state,
per-leaf-worker effort from `effort.db`, resolver-owned index) instead of the retired
orchestrator-centric signals. Also absorbs all deferred Era 002 Phase 64 stories (INFRA-164–168)
and closes the D1/D2/D3 defects found during the Era 002 close-out (CER-053/054/055). OBS-001
adds `flex_build.py resolver-state --json` as a pure-read state-model source; OBS-002 refactors
the SPA UI to read it; OBS-003/004/005 fix the D1 (`expected_step_tokens` display provenance),
D2 (`context_current_tokens` live writer root-cause), and D3 (waypoint outcome recording + render)
defects. The five Phase 64 hardening stories (INFRA-164–168) are re-homed here with bodies intact;
only their frontmatter is updated. Expected to be the heaviest phase of Era 003. Agreements input:
`docs/agreements/HARNESS007-main.md` (all 6 DPs AGREED).

## Stories

Built in order. The OBS stories are sequenced before the INFRA re-homes so the SPA refactor is in
place before hardening. INFRA-167 before INFRA-166 (per Phase 64 dependency: the context route's
flex_factor live-read calls `parseStoryFrontmatter` fixed in INFRA-167).

| ID | Title | Status |
|----|-------|--------|
| OBS-001 | Resolver state-model read API (`resolver-state --json` + TS reader) | complete |
| OBS-002 | SPA UI refactor to the resolver state model | complete |
| OBS-003 | D1 display half — `expected_step_tokens` provenance (CER-053) | complete |
| OBS-004 | D2 — `context_current_tokens` live writer root-cause + fix (CER-054) | complete |
| OBS-005 | D3 — waypoint outcome recording + render (CER-055) | complete |
| INFRA-164 | `flex_observability.py` CLI hardening (re-homed from Phase 64) | complete |
| INFRA-165 | `context_budget.py` flex_factor correctness — NaN (re-homed from Phase 64) | planned |
| INFRA-167 | TypeScript parser robustness (re-homed from Phase 64) | planned |
| INFRA-166 | Fastify API route hardening (re-homed from Phase 64) | planned |
| INFRA-168 | `effortDb.ts` p90 + in-flight dedup (re-homed from Phase 64) | planned |

## Schema delivery

| Object | Management surface | Exception |
|---|---|---|
| _(none)_ | — | HARNESS007 introduces no new persistent schema objects. `effort.db` gains a more correct `outcome` column value (OBS-005 is a value-correctness fix, not a schema change). |

---

### CP-HARNESS007-main Cold-eyes checklist

— developer fills in after phase completion —
