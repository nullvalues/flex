# Anchor Pairmode — Checkpoints

Each checkpoint is tagged after all stories in the phase pass the full checkpoint sequence
(build gate → security audit → intent review).

---

## cp1-scaffold-complete

**Phase:** 1 — Pairmode Skill Scaffold
**Tag command:** `git tag cp1-scaffold-complete && git push origin cp1-scaffold-complete`
**Acceptance:** `/anchor:pairmode bootstrap` runs against a test project and produces
correct scaffold files. All Phase 1 tests pass.

---

## cp2-spec-derived-complete

**Phase:** 2 — Spec-Derived Generation
**Tag command:** `git tag cp2-spec-derived-complete && git push origin cp2-spec-derived-complete`
**Acceptance:** Bootstrap reads an Anchor spec and produces a checklist and deny list
derived from non-negotiables and business rules. All Phase 2 tests pass.

---

## cp3-lessons-complete

**Phase:** 3 — Lessons System
**Tag command:** `git tag cp3-lessons-complete && git push origin cp3-lessons-complete`
**Acceptance:** `/anchor:pairmode lesson` captures a lesson to lessons.json.
`/anchor:pairmode review` surfaces lessons and writes template updates. All Phase 3 tests pass.

---

## cp4-audit-sync-complete

**Phase:** 4 — Audit and Sync
**Tag command:** `git tag cp4-audit-sync-complete && git push origin cp4-audit-sync-complete`
**Acceptance:** `/anchor:pairmode audit` produces correct diff for cora, radar, and forqsite.
`/anchor:pairmode sync` applies deltas non-destructively. All Phase 4 tests pass.
Sibling repos audited and findings documented.

---

## cp5-companion-complete

**Phase:** 5 — Companion Enhancements
**Tag command:** `git tag cp5-companion-complete && git push origin cp5-companion-complete`
**Acceptance:** Sidebar shows story context panel when current_story is set.
Multi-module boundary alerts fire correctly. Permission overrides are captured to spec.
All Phase 5 tests pass.
