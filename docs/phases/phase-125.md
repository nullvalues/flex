---
era: "005"
phase_class: production
---

# project — Phase 125: De-identify fleet repo references from the public repo (CER-172)

← [Phase 124: Scaffold EXEMPLAR-000.md for downstream projects (CER-171)](phase-124.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Stop real fleet/sibling-project repo names from being committed to this public repo: externalize fleet_discovery.py's hardcoded DOCUMENTED_DIRS list (currently literal directory names) into a local gitignored config, then scrub all already-committed doc files to reference those repos only via a stable anonymized Repo-A..Repo-O mapping kept in that same local config, never in git.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-393 | Externalize fleet_discovery.py's hardcoded repo list into a local gitignored config (CER-172) | draft |
| INFRA-394 | Scrub real fleet repo names from committed docs via stable Repo-A..Repo-O mapping (CER-172) | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-125 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
