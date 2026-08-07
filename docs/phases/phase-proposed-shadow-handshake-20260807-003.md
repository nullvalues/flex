---
era: "004"
phase_class: production
status: proposed
sequenced: false
---

# project — Proposed phase (shadow-handshake): Shadow handshake — findings before the story commit

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Close the intra-attempt gap in the shadow protocol: today the shadow's stop condition is the story commit itself, so final-diff findings land after the build is sealed and can only save the NEXT attempt. A three-artifact handshake (builder-owned review-request marker; shadow-owned .pairmode-review.lck carrying OPEN/CLOSED as a discrete liveness ack; typed findings + builder dispositions in the suggestions log) puts findings on disk before the commit and lets the builder revise within the attempt — dead-shadow detection is one ack cycle, not a tuned timeout, and the advisory invariant is intact.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-437 | REVIEW-OPEN/REVIEW-CLOSED entries and the final-diff pass (shadow procedure v2) | stub |
| INFRA-438 | builder quiescence, dispositions, reviewer procedure gains the exchange record | stub |
| INFRA-439 | guard + stop-condition updates for the handshake artifacts | stub |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-<assigned at sequencing> Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?
- [ ] dark feature — does any new role, flag, event type, or surface lack a narrative and a landing spot?

— developer fills in after phase completion —
