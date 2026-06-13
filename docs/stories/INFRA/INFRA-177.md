---
id: INFRA-177
rail: INFRA
title: "Remove completed one-time lessons bypass rule from pairmode_migrate.py (security audit cp-69)"
status: planned
phase: "69"
story_class: code
primary_files:
  - skills/pairmode/scripts/pairmode_migrate.py
touches:
  - tests/pairmode/test_pairmode_migrate.py
---

# INFRA-177 — Remove completed one-time lessons bypass rule from pairmode_migrate.py

**Phase:** 69
**Rail:** INFRA
**Status:** planned

## Background

The Phase 69 checkpoint security audit (cp-69) found a HIGH violation: rule 14
in `pairmode_migrate.py` (strategy `"bypass"`, handler `"lessons_json"`) performs
string substitution across all fields of existing lesson entries — not just the
`status` field — and writes directly to `lessons.json` via `write_text()`,
bypassing the `save_lessons()` append-only invariant. The rule was a one-time
migration tool (anchor→flex rename) gated on `--migrate-lessons`. That migration
is complete. Resolution: option (c) — remove the rule entirely.

## Ensures

1. Rule 14 (`rule_id=14`, `strategy="bypass"`, `handler="lessons_json"`) is
   removed from the `MIGRATION_RULES` list in `pairmode_migrate.py`.
2. `_apply_bypass_rule()` function is removed entirely (it has no other callers).
3. The `elif rule.strategy == "bypass":` dispatch branch in `migrate()` is removed.
4. The `MigrationRule.lessons_gated` field and rule 15 (`strategy="regenerate"`,
   `handler="lessons_md"`) are left in place — they are not part of this fix.
5. The `--migrate-lessons` CLI flag and `migrate_lessons` parameter remain
   (rule 15 still uses them to gate LESSONS.md regeneration).
6. `tests/pairmode/test_pairmode_migrate.py`:
   - `test_migrate_lessons_with_flag` is removed (tested bypass behavior; no longer
     applicable after rule 14 is gone).
   - `test_lessons_gated_rules_are_14_and_15` is updated to expect only rule 15
     as lessons-gated.
   - `test_migrate_lessons_default_skip` is retained — it tests that `lessons.json`
     is not modified without the flag; that invariant still holds (now trivially,
     since no rule touches lessons.json at all).
7. Full suite passes: `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`.

## Out of scope

- Changing any other migration rules or their behavior.
- Removing the `--migrate-lessons` flag or `lessons_gated` dataclass field.
- Any changes to `lesson_utils.py` or `save_lessons()`.
