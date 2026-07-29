---
id: "004"
name: flex — Operational closeout and 0.3.1
status: active
---

## Strategic intent

Drain the CER backlog's operational defects and ship pairmode 0.3.1 clean: zero
unresolved operational findings, docs matching code, a fleet that can actually
*receive* the release, and a version-consistent plugin tagged with exactly one
era active. Group-3 blockers land first because both rails stand on them; the
phase-107 stub drain is superseded into this era.

**Scope revision (2026-07-29):** the era was deliberately scaffolded incomplete
at inception, pending external review. Two reviews arrived — the cold-eyes pass
(`docs/closeout-planning-cold-eyes-review_20260729.md`) and cora's
hand-migration findings — and were reconciled into
`docs/closeout-agreements-20260729.md` (AG-1..AG-7), which is the authority for
this era's final shape. The review's containment sizing ("no new phase") was
set aside by operator decision: the era gains INFRA-311 (sync canon-shrink —
the CRITICAL propagation fix), INFRA-312 (observability functional validation),
a widened INFRA-310 (era-003 closure folded in, check-index driven to zero),
and phase 116 (cora upstream, pre-tag). The 0.3.1 record and tag move to
phase 116 as the era's last act.

## Rails

| Rail | Primary domain |
|------|----------------|

## Phases

| Phase | Title | Status |
|-------|-------|--------|
| 113 | Shared blockers: frontmatter, resolver evidence, recording determinism | planned |
| 114 | Build-loop closeout: worktrees, scaffolding, migration tooling, doc currency | planned |
| 115 | Observability closeout: API hardening, payload guards, rollup hygiene, functional validation | planned |
| 116 | Cora upstream: methodology gates, resolver cadence, spec-time controls; backlog truth pass and 0.3.1 | planned |
