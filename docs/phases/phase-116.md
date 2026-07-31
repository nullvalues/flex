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
Upstream the six methodology extensions field-proven on cora's 0.1.0→0.3.0 hand-migration (AG-6, `docs/closeout-agreements-20260729.md`) — close-time disposition gates, backlog gate/groom, pre-build intent review, between-story context etiquette, covered contracts, spec-time model review — close the agent-dispatch completeness gap surfaced live during this phase's own build loop (AG-13, `docs/closeout-agreements-20260729.md`: three of eight agent roles were never registered, two more have no model-selection tier, and no class-level escalation path exists for `doc`/`lesson`/`methodology` work) — then make the era's record true and stamp 0.3.1 (INFRA-310, terminal). This phase exists because the operator set aside the cold-eyes review's containment sizing: era 004 was scaffolded incomplete by design, and these inputs are the revision it was waiting for.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-313 | CER backlog gate and groom: `cer.py gate` wired into checkpoint, `cer.py groom`, `gate:` field | draft |
| INFRA-314 | Deferral/disposition gates at both boundaries: checkpoint-tag refusal, era-transition check, `phase_new.py --parent-phase` and `--proposed`, forbidden-proxy template stub | draft |
| INFRA-315 | Pre-build intent review: resolver emits spawn-intent-reviewer before first build, behind Build-standards opt-in | draft |
| INFRA-316 | Between-story context etiquette: next-action consults context_budget_check between story iterations; pause-context handoff | draft |
| INFRA-317 | Covered-contracts gate: Build standards `covered_contracts:` pairs; builder pre-build read gate; doc wins on conflict | draft |
| INFRA-318 | Spec-time model review: story frontmatter `model:`/`reviewer_model:` honored by dispatch; asymmetric raise/lower prompt | draft |
| INFRA-331 | Agent registration completeness: `spec-writer.md.j2` template; register spec-writer/docs-reviewer/gate-worker in `ACTION_SUBAGENT_TYPE` | draft |
| INFRA-332 | Sync backfill: `sync-agents` gains an add-missing-file path for already-bootstrapped projects; backfill flex and flex-harness | draft |
| INFRA-333 | Model-selection completeness: `select_gate_worker_model`, `select_spec_writer_model`, `select_docs_reviewer_model` in `model_selector.py`; dispatch call sites route through them instead of hardcoded literals | draft |
| INFRA-334 | Escalation ladder redesign: every `story_class` gets a real retry-upgrade path (`doc`/`lesson` haiku→sonnet, `methodology` sonnet→opus unconditional) instead of dead-ending or conditional escalation | draft |
| INFRA-335 | Work→agent-type classification doc and new-agent-type definition-of-done, to prevent this class of drift recurring | draft |
| INFRA-310 | Backlog truth pass, phase-107 supersession, era-003 closure, zero-open audit, and the 0.3.1 version record | draft |

## Ordering

INFRA-313 → INFRA-314 (checkpoint/close-time tooling cluster; both touch the
checkpoint sequence and must compose), then INFRA-315 → INFRA-316 (resolver
cadence cluster), then INFRA-317, INFRA-318 in any order.

**Agent-dispatch completeness cluster (AG-13):** INFRA-331 → INFRA-332
(registration must exist before backfill can propagate it) → INFRA-333
(model-selection functions; independent of 331/332's file-existence concern
but shares the same `ACTION_SUBAGENT_TYPE`/dispatch surface, so build after
332 to avoid a merge collision on `CLAUDE.build.md`) → INFRA-334 (escalation
ladder; conceptually depends on 333's per-role selector functions existing)
→ INFRA-335 (documents the finished shape of 331–334; strictly last in the
cluster). This cluster may interleave with INFRA-317/INFRA-318 (no shared
files) but must complete before INFRA-310.

INFRA-310 is strictly terminal — it is the last story built in era 004 and
requires every other era-004 story complete (this derives the sibling set
rather than pinning story IDs, AG-7 — so INFRA-331..335 join that set
automatically). The 0.3.1 tag itself remains the operator's checkpoint act
after cp-116 gates pass.

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
