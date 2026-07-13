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
| LESSON-008 | Repoint _AFFECTS_TO_TEMPLATE map to procedure.md files | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| `enforced_by` field on `lessons.json` entries | `lesson.py` (capture), `lesson_review.py --list-unenforced` (query) | Field addition to an existing store, not a new persistent object — no dedicated management UI needed; it's already managed through the existing lesson capture/review CLI surface. |

---

### CP-HARNESS014-main Cold-eyes checklist

Reviewed diff: `git diff cp-HARNESS013-main..HEAD` (LESSON-007, LESSON-008).

PASS — HOOK PERFORMANCE (no hook files touched)
PASS — PIPE CONTRACT (no hook files touched)
PASS — SPEC SAFETY (only lesson.py/lesson_review.py/lesson_utils.py write lessons.json; no spec-file writers added)
PASS — SKILL ISOLATION (no hardcoded absolute paths introduced)
PASS — LESSONS INTEGRITY (`lesson_utils.save_lessons` append-only invariant extended, not weakened: `enforced_by` may only be *added* once to a pre-existing entry lacking it, then becomes append-only itself — verified in `test_lesson_utils.py`)
PASS — TEST COVERAGE (lesson.py, lesson_review.py, lesson_utils.py each have corresponding tests in tests/pairmode/)
PASS — PROTECTED FILES (none touched: hooks/, skills/seed/scripts/, sidebar.py, plugin.json, marketplace.json)
PASS — PYTHON STANDARDS (no direct `python`/`pip` invocation; no new unlisted imports)
PASS — RAIL SCOPE (diff confined to lessons/, skills/pairmode/scripts/lesson*.py, tests/pairmode/test_lesson*.py, docs/phases, docs/stories/LESSON — matches primary_files/touches on both stories)
PASS — BUILD GATE (`uv run pytest tests/pairmode/ -x -q` → 2982 passed, 211 skipped, 1 xpassed, 0 failed)

Summary: 10 passed, 0 failed. Overall: PASS

### CP-HARNESS014-main Phase completion check

Both stories (LESSON-007, LESSON-008) are `complete` in the Stories table above. No deferred stories this phase.

### CP-HARNESS014-main CER backlog review

`docs/cer/backlog.md` Do Now section: empty — no unresolved items. Guard clear.

**Backlog items ready to pull forward:** none of the current Do Later items are
low-effort given this diff or directly related to LESSON-007/LESSON-008's scope
(lesson schema + `_AFFECTS_TO_TEMPLATE` repointing). No pull-forward candidates
identified.

**New finding surfaced during this checkpoint (added to Do Later, see CER-066):**
`state.json["checkpoint_step"]` is never cleared between phases. `next-action`
computed `_remaining` against the full 4-step `_CHECKPOINT_SEQUENCE` regardless
of which phase is active, so after HARNESS013-main's checkpoint left all four
step names recorded, `flex_build.py next-action` reported `"action": "done"`
for HARNESS014-main without ever dispatching `checkpoint-security`,
`checkpoint-intent`, `checkpoint-docs`, or `checkpoint-tag`. This checkpoint was
completed manually (cold-eyes checklist, phase completion check, and CER
backlog review performed directly against the diff per the reviewer procedure,
in place of the skipped `checkpoint-security`/`checkpoint-intent`/
`checkpoint-docs` spawns) to avoid blocking on the bug. The fix (reset
`checkpoint_step` to `[]` once `checkpoint-tag` completes, or scope it by
phase key) needs its own spec before building, per policy.
