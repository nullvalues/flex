---
era: "005"
phase_class: production
---

# project — Phase 129: De-duplicate pairmode_drift_report.py's stale override-key parser (CER-181)

**Parent phase:** Phase 123 — Fix audit.py override-key normalisation mismatch (CER-170)

← [Phase 128: Fix .pairmode-overrides template/migration gap from audit.py key-format change (CER-180)](phase-128.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Fix CER-181: pairmode_drift_report.py carries an independent, unfixed copy of audit.py's section-key derivation and .pairmode-overrides loading, so the live 'pairmode drift-report' command silently ignores overrides written in the current, documented key format (post-CER-170/CER-180) and misreports operator-declared sections as fleet-wide convergence candidates. Fix by having drift_report.py reuse audit.py's current section-key/override-loading logic instead of maintaining a diverged copy.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-399 | De-duplicate pairmode_drift_report.py's stale override-key parser (CER-181) | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-129 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
