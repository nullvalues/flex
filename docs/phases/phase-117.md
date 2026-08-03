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
Close every open finding from the two-model cold-eyes review of the build-loop harness itself (docs/build-loop-cold-eyes-review-20260801.md) — CRITICAL/HIGH and the MEDIUM/LOW findings folded in alongside them, per era 004's own stated goal of zero unresolved operational findings rather than deferring fresh findings the same session the era's core mandate was to stop deferring them. Covers: a FAIL escalation ladder that measurably fails to advance about half the time, two features shipped in Phase 116 that are structurally unreachable in the live loop, a CER-backlog append path that can corrupt unrelated rows, a livelock in gate-worker dispatch, the missing stage-to-stage integration test coverage that let all of the above ship reviewer-PASSed, the recurring merge-status-flip gap (CER-136) that manually blocked this session's own Phase 115 and 116 checkpoints, and a cluster of smaller correctness/hygiene gaps (dead effort.db columns, docstring rot, era-ledger/index bookkeeping, test-environment coupling to gpg signing) that are all adjacent to files this phase is already touching.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-336 | Fix FAIL-escalation ladder: attempt-counter bump reliably fires after discard, plus a stage-to-stage integration test harness | complete |
| INFRA-337 | Fix JSON-verdict parser: parse_worker_outcome must handle braces inside BUILD-RESULT/REVIEW-RESULT string fields | complete |
| INFRA-338 | Fix cer.py backlog-append corruption: unify the row parser between reader and writer | complete |
| INFRA-339 | Fix or remove INFRA-316 pause-context: OUTCOME_PASS is unreachable from infer_position; also fix session-scoping mismatch | complete |
| INFRA-340 | Complete INFRA-333 model-selector wiring: checkpoint-security/checkpoint-intent model dispatch, gate_worker_model consumer-or-removal | complete |
| INFRA-341 | Wire spawn-gate-worker's verdict to a real consumer, closing the INFRA-331 livelock | complete |
| INFRA-342 | Reconcile CLAUDE.build.md and its .j2 template; add an automated dispatch-parity drift check | complete |
| INFRA-343 | Fix checkpoint build gate: 60s timeout silently passes on a 175s+ suite | complete |
| INFRA-344 | Commit spec-writer output before create-story-worktree branches off HEAD | complete |
| INFRA-345 | De-duplicate attempt-recording writers: retire or reconcile the legacy record_attempt.py CLI path | complete |
| INFRA-346 | Unify the two phase-completion definitions so the resolver's own gate is at least as strict as checkpoint-tag's deferral gate | complete |
| INFRA-347 | merge-story-worktree must flip a landed story's status to complete (CER-136) | complete |
| INFRA-348 | Wire or remove dead effort.db columns: tool_uses, duration_ms, story_class/model_selection_reason | complete |
| INFRA-349 | Docstring-currency sweep: fix harness docstrings/comments that misdescribe live wiring | complete |
| INFRA-350 | De-couple pairmode tests from operator gpg-signing config | complete |

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

INFRA-342 (CLAUDE.build.md/.j2 reconciliation) should build **last** among
INFRA-339/340/341/342/**344**, since it needs to capture whichever final shape those land in, not a
mid-phase snapshot — INFRA-344's fix (committing spec-writer output) also edits `CLAUDE.build.md`'s
dispatch prose, so it belongs in this same "build before 342" group even though it has no other
code dependency on 339/340/341.

INFRA-343 (build-gate timeout) and INFRA-345 (duplicate
attempt-writers) are each independent and can build in any order relative to the rest.

INFRA-346 (unify phase-completion definitions) should build after INFRA-339/340 land, since it
touches the same `is_formally_deferred`/phase-completion-guard machinery INFRA-314 built and those
two stories may also touch adjacent `next_action.py` code.

INFRA-347 (CER-136's actual merge-status-flip fix) is independent and can build any time.

INFRA-348 (dead effort.db columns) should build after INFRA-345 (duplicate-writer de-dup) lands,
since retiring `record_attempt.py` as a writer may retire `story_class`/`model_selection_reason`'s
only source along with it — check INFRA-345's landed shape before deciding those two columns' fate.

INFRA-350 (gpg-signing test decoupling) is independent and can build any time — build it early if
convenient, since every other story in this phase will hit the same commit-signing friction while
being built and reviewed.

INFRA-349 (docstring-currency sweep) should build **last** — after every other story in this phase
lands — since it's explicitly a sweep against this phase's *final* wiring, not a mid-phase
snapshot; building it earlier would just mean re-sweeping later stories' changes anyway.

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
