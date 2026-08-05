---
era: "005"
phase_class: production
---

# project — Phase 123: Fix audit.py override-key normalisation mismatch (CER-170)

← [Phase 122: shadow-reviewer write capability (CER-164) and shadow_review enablement](phase-122.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Fix audit.py's _normalise()/_load_overrides() key-format mismatch (## Section vs section) so .pairmode-overrides entries for missing/inconsistent canonical sections actually suppress the intended audit finding, fleet-wide.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-391 | Fix audit.py override-key format mismatch between _normalise() and _load_overrides() (CER-170) | complete |

## Downstream remediation

INFRA-391 changed audit.py's internal section-key contract without auditing every
consumer of that contract, and the checkpoint's security-auditor gate needed three
passes to actually close CER-170's real-world impact: the first pass found the
operator-facing `.pairmode-overrides.j2` template still documented the old, now-broken
key format with no migration (CER-180), fixed by a forked Phase 128 (INFRA-398); the
second pass found `pairmode_drift_report.py` carried an independent, undeduped copy
of the same section-key logic that silently ignored correctly-formatted overrides
(CER-181), fixed by a forked Phase 129 (INFRA-399). The third pass passed clean, with
two non-blocking MEDIUM findings (CER-184, CER-185 — a stale-persisted-rejection edge
case and a cross-tool case-sensitivity divergence) filed to the CER backlog rather
than blocking. See both forked phases' `**Parent phase:**` lines. The `complete`
status above reflects INFRA-391 as specced and built, not that CER-170's full
real-world impact was closed standalone — that required the two forked phases too.

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-123 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
