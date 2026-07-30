---
era: "004"
phase_class: production
---

# project — Phase 116: Cora upstream: methodology gates, resolver cadence, spec-time controls; backlog truth pass and 0.3.1

← [Phase 115: Observability closeout: API hardening, payload guards, rollup hygiene, functional validation](phase-115.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Upstream the six methodology extensions field-proven on cora's 0.1.0→0.3.0 hand-migration (AG-6, `docs/closeout-agreements-20260729.md`) — close-time disposition gates, backlog gate/groom, pre-build intent review, between-story context etiquette, covered contracts, spec-time model review — then make the era's record true and stamp 0.3.1 (INFRA-310, terminal). This phase exists because the operator set aside the cold-eyes review's containment sizing: era 004 was scaffolded incomplete by design, and these inputs are the revision it was waiting for.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-313 | CER backlog gate and groom: `cer.py gate` wired into checkpoint, `cer.py groom`, `gate:` field | draft |
| INFRA-314 | Deferral/disposition gates at both boundaries: checkpoint-tag refusal, era-transition check, `phase_new.py --parent-phase` and `--proposed`, forbidden-proxy template stub | draft |
| INFRA-315 | Pre-build intent review: resolver emits spawn-intent-reviewer before first build, behind Build-standards opt-in | draft |
| INFRA-316 | Between-story context etiquette: next-action consults context_budget_check between story iterations; pause-context handoff | draft |
| INFRA-317 | Covered-contracts gate: Build standards `covered_contracts:` pairs; builder pre-build read gate; doc wins on conflict | draft |
| INFRA-318 | Spec-time model review: story frontmatter `model:`/`reviewer_model:` honored by dispatch; asymmetric raise/lower prompt | draft |
| INFRA-310 | Backlog truth pass, phase-107 supersession, era-003 closure, zero-open audit, and the 0.3.1 version record | draft |

## Ordering

INFRA-313 → INFRA-314 (checkpoint/close-time tooling cluster; both touch the
checkpoint sequence and must compose), then INFRA-315 → INFRA-316 (resolver
cadence cluster), then INFRA-317, INFRA-318 in any order. INFRA-310 is strictly
terminal — it is the last story built in era 004 and requires every other
era-004 story complete. The 0.3.1 tag itself remains the operator's checkpoint
act after cp-116 gates pass.

**Cross-phase dependencies added 2026-07-30 (reconciliation sweep, AG-10a in
`docs/closeout-agreements-20260729.md`):**

- **INFRA-316 requires INFRA-321 (phase 114) complete.** Re-verify INFRA-316's
  spec against INFRA-321's shipped orchestrator-track surface
  (`context_model.py`, per INFRA-321 § F6) before build — do not consult
  `context_budget_check.py`'s phase-spend sum for the between-story pause
  decision (INFRA-321 §B6: that summed signal stops rendering an
  orchestrator-facing exceeded message once INFRA-321 ships). INFRA-316's own
  spec body (`touches`, Requires) has not yet been rewritten to match; that
  rewrite is deferred until INFRA-321 has actually shipped, per AG-10a.
- **INFRA-313 and INFRA-314 both insert at the `checkpoint-tag` seam and both
  depend on INFRA-322 (phase 114) having already rewritten the CER Do-Now
  guard's resolution predicate.** Build 313 → 314 with the seam reviewed once,
  jointly, against INFRA-322's shipped form — INFRA-313's Requires currently
  anchors on the pre-INFRA-322 predicate and a disposition-token vocabulary
  that diverges from AG-11's on-the-record rejection of vocabulary widening;
  reconcile both against INFRA-322's actual shipped predicate before build,
  not against this spec's current text.

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| `gate:` field in `docs/cer/backlog.md` rows (INFRA-313) | The backlog file itself via `cer.py` (capture, gate, groom) | Not a database table — a markdown-schema field; managed by the same CLI that owns the backlog |

---

### CP-116 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
