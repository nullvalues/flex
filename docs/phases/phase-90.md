---
era: "003"
---

# flex — Phase 90: Fix stale pre-INFRA-191 assertion in CLAUDE.build.md test

← [Phase 89: Remove flex-specific hook paragraph from canonical CLAUDE.md.j2 template](phase-89.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Update TestBuild025PreStoryScopeCheck to assert the INFRA-191 spec-preflight flow now present in flex's own CLAUDE.build.md after sync-build caught it up to the canonical template.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-201 | Fix stale pre-INFRA-191 scope-check assertion in test_templates.py | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-90 Cold-eyes checklist

— developer fills in after phase completion —
