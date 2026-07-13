---
era: "003"
phase_class: production
---

# flex-harness — Phase HARNESS014-main: Lessons enforcement instrumentation

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Make the lessons-enforcement backlog queryable and repair the broken lesson-to-template fold path, per the L012 instrument-before-formalize lifecycle.

## Background

A cross-agent review proposed treating flex's lessons system as an
enforcement runtime rather than a passive doc: promote lessons to standalone
skills with sharp trigger descriptions, compile lessons into lint/hook gates,
inject relevant lessons via a PreToolUse hook keyed on file path, add an
`enforced_by` field, and pin fleet distribution so sibling projects can't
silently drift onto stale lessons.

A fable-model review against this codebase and the 9-project fleet
(coherra, forqsite, radar, asp, aab, cora, lumin, halfhorse, meander) found:
~3,300 build attempts / ~1,350 stories fleet-wide with zero recorded
incidents of an orchestrator failing to consume an applied lesson; the
unenforced backlog is real but small (~5-7 of 15 applied lessons); and the
fleet is mid-cutover on the `fold-prep` branch (0.2.x → 0.3.0), so touching
every sibling's hook `matcher` config now would double migration surface for
unevidenced payoff. Per L012 (instrument → wait ≥2 phases of data →
validate/formalize), this phase ships only the instrument: `enforced_by` and
the query it enables. Skill promotion, PreToolUse lesson injection, and a
Signal-2-style lessons-currency check in `fleet_discovery.py` are explicitly
**not** in this phase — revisit after the fold completes and this phase's
`enforced_by` data has had ≥2 phases to accrue.

## Stories

| ID | Title | Status |
|----|-------|--------|
| LESSON-007 | enforced_by field on lesson schema and unenforced-backlog query | complete |
| LESSON-008 | Repoint _AFFECTS_TO_TEMPLATE map to procedure.md files | planned |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| `enforced_by` field on `lessons.json` entries | `lesson.py` (capture), `lesson_review.py --list-unenforced` (query) | Field addition to an existing store, not a new persistent object — no dedicated management UI needed; it's already managed through the existing lesson capture/review CLI surface. |

---

### CP-HARNESS014-main Cold-eyes checklist

— developer fills in after phase completion —
