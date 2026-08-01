---
era: "004"
phase_class: production
---

# project — Phase 117: Build-loop integrity remediation: escalation ladder, dead handoffs, CER-append corruption

← [Phase 116: Cora upstream: methodology gates, resolver cadence, spec-time controls; backlog truth pass and 0.3.1](phase-116.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Close the CRITICAL/HIGH gaps found by the two-model cold-eyes review of the build-loop harness itself (docs/build-loop-cold-eyes-review-20260801.md): a FAIL escalation ladder that measurably fails to advance about half the time, two features shipped in Phase 116 that are structurally unreachable in the live loop, a CER-backlog append path that can corrupt unrelated rows, a livelock in gate-worker dispatch, and the missing stage-to-stage integration test coverage that let all of the above ship reviewer-PASSed.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-336 | Fix FAIL-escalation ladder: attempt-counter bump reliably fires after discard, plus a stage-to-stage integration test harness | draft |
| INFRA-337 | Fix JSON-verdict parser: parse_worker_outcome must handle braces inside BUILD-RESULT/REVIEW-RESULT string fields | draft |
| INFRA-338 | Fix cer.py backlog-append corruption: unify the row parser between reader and writer | draft |
| INFRA-339 | Fix or remove INFRA-316 pause-context: OUTCOME_PASS is unreachable from infer_position; also fix session-scoping mismatch | draft |
| INFRA-340 | Complete INFRA-333 model-selector wiring: checkpoint-security/checkpoint-intent model dispatch, gate_worker_model consumer-or-removal | draft |
| INFRA-341 | Wire spawn-gate-worker's verdict to a real consumer, closing the INFRA-331 livelock | draft |
| INFRA-342 | Reconcile CLAUDE.build.md and its .j2 template; add an automated dispatch-parity drift check | draft |
| INFRA-343 | Fix checkpoint build gate: 60s timeout silently passes on a 175s+ suite | draft |
| INFRA-344 | Commit spec-writer output before create-story-worktree branches off HEAD | draft |
| INFRA-345 | De-duplicate attempt-recording writers: retire or reconcile the legacy record_attempt.py CLI path | draft |
| INFRA-346 | Unify the two phase-completion definitions so the resolver's own gate is at least as strict as checkpoint-tag's deferral gate | draft |

## Ordering

INFRA-336 first — it's the most foundational fix (the escalation ladder itself) and builds the
reusable stage-to-stage integration-test harness that INFRA-339 and INFRA-344 extend, so it should
land before either. INFRA-337 (the brace-regex parser) can build any time after INFRA-336, since it
feeds the same live symptom but touches a different file with no code dependency.

INFRA-338 (cer.py corruption) is independent of everything else in this phase and can build any
time.

INFRA-339 (pause-context reachability) and INFRA-340 (checkpoint-security/intent model wiring) are
independent of each other but both touch `next_action.py`'s Row 9/Row 8 region — build one, merge,
then the other, to avoid a worktree conflict. INFRA-341 (gate-worker verdict wiring) may need to
coordinate with INFRA-340 if the fix requires the action grammar to carry a real `model` for
`spawn-gate-worker` — check INFRA-340's landed shape before starting INFRA-341's Instructions.

INFRA-342 (CLAUDE.build.md/.j2 reconciliation) should build **last** among INFRA-339/340/341/342,
since it needs to capture whichever final shape those three land in, not a mid-phase snapshot.

INFRA-343 (build-gate timeout), INFRA-344 (spec-writer commit), and INFRA-345 (duplicate
attempt-writers) are each independent and can build in any order relative to the rest.

INFRA-346 (unify phase-completion definitions) should build after INFRA-339/340 land, since it
touches the same `is_formally_deferred`/phase-completion-guard machinery INFRA-314 built and those
two stories may also touch adjacent `next_action.py` code.

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-117 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
