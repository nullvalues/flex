---
era: "003"
---

# flex-harness — Phase HARNESS013-main: Era 3 Fleet Migration

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Migrate all 9 bound fleet projects from pairmode 0.2.x to 0.3.0 with the migration normalizer, per-project sync, and fold gate

## Stories

| ID | Title | Status |
|----|-------|--------|
| RELEASE-011 | pairmode_migrate.py to-030: state.json normalizer and stale-agent cleanup | complete |
| RELEASE-012 | Per-project sync-all to Era 3 with Signal-1 verification | complete |
| RELEASE-013 | Mid-build seam selection and pre-migration gate for Era 2 projects | complete |

## Schema delivery

| Object | Management surface | Exception |
|---|---|---|
| _(none)_ | — | No new persistent schema objects introduced. |

---

### CP-HARNESS013-main Cold-eyes checklist

— developer fills in after phase completion —
