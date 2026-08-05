---
era: "005"
phase_class: production
---

# project — Phase 124: Scaffold EXEMPLAR-000.md for downstream projects (CER-171)

← [Phase 123: Fix audit.py override-key normalisation mismatch (CER-170)](phase-123.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Add docs/exemplars/EXEMPLAR-000.md to bootstrap.py's SCAFFOLD_FILES and sync.py/audit.py's canonical-file handling so every flex-bootstrapped project (not just flex itself) gets the frozen spec-writer format exemplar scaffolded and audited, closing the silent-degrade gap the spec-writer procedure currently hits on any downstream project.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-392 | Scaffold EXEMPLAR-000.md into downstream projects via bootstrap/sync/audit (CER-171) | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-124 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
