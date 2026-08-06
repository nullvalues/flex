---
era: "005"
phase_class: production
---

# project — Phase 137: Overrides/audit key-shape quality fixes (CER-182/184/185/202)

← [Phase 136: Fleet-gate coverage and leak-closure fixes (CER-190/191/197/206)](phase-136.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Close four residual gaps in the .pairmode-overrides section-key handling chain (CER-170/180/181): a stale-shape diagnostic that suggests an already-broken corrected form (CER-182), lesson_review.py's rejected-pattern persistence keys stranded by the CER-181 key-shape change (CER-184), a case-handling divergence between audit.py/sync.py and pairmode_drift_report.py for mixed-case override keys (CER-185), and audit.py's generic remediation advice that can't actually fix an overrides-shape finding (CER-202).

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-407 | Overrides/audit key-shape quality fixes (CER-182/184/185/202) | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-137 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
