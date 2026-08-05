---
id: INFRA-395
rail: INFRA
title: Scrub real fleet repo names from lessons.json/LESSONS.md via scoped append-only exception (CER-173)
status: draft
phase: "122"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - lessons/lessons.json
  - skills/pairmode/scripts/scrub_fleet_names.py
touches:
  - tests/pairmode/test_scrub_fleet_names.py
  - lessons/LESSONS.md
  - skills/pairmode/scripts/lesson_utils.py
  - skills/pairmode/skills/builder/procedure.md
  - skills/pairmode/skills/reviewer/procedure.md
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

CER-172's `scrub_fleet_names.py` (built in INFRA-394) deliberately excludes
`lessons/lessons.json` and its generated `lessons/LESSONS.md` from both
`apply` and `verify`, because both are a declared `protected_path`
(`CLAUDE.build.md`) and the builder procedure's append-only "Lessons
integrity" rule forbids rewriting an existing entry's field content. Real
sibling-repo names still literally appear in several existing entries'
`source_project`/`trigger`/free-text fields as a result — a residual public
leak CER-172's fix didn't reach. CER-173 (`docs/cer/backlog.md`) records the
operator's decision: fix it via a scoped, narrow exception (option a) — a
real-name-only text substitution on lessons.json's *existing* entries,
touching no ID, date, status, `enforced_by`, `applies_to`,
`methodology_change.affects`, `validation_phase`, or entry ordering — then
regenerate `LESSONS.md` from the result.

## Requires

- `skills/pairmode/scripts/scrub_fleet_names.py` (INFRA-394, merged to main)
  exists and its `apply()`/`verify()` continue to exclude
  `lessons/lessons.json`/`lessons/LESSONS.md` from the general tracked-file
  loop — this story adds a separate, explicit lessons-scoped path; it does
  not remove that exclusion from the general loop.
- `lessons/lessons.json`'s existing entry shape (`id`, `date`,
  `source_project`, `trigger`, `problem`, `learning`, `methodology_change`
  [`affects`, `description`], `applies_to`, `status`, `enforced_by`, and the
  optional `validation_phase`/`value_framing` fields present on some
  entries) holds as read from the file on disk at build time.
- A local, gitignored fleet-name mapping file (`.pairmode-fleet.local.json`,
  INFRA-393) is present in the working tree at build time, in the same
  `{label: real_absolute_path}` shape `scrub_fleet_names.py` already reads.

## Ensures

- `scrub_fleet_names.py` exposes a lessons-scoped mode (e.g. a `--lessons`
  CLI flag, or an equivalently named `apply_lessons()`/`verify_lessons()`
  function pair) that is never invoked by the existing bare `apply()`/
  `verify()` tracked-file loop — the general loop's exclusion of
  `lessons/lessons.json`/`lessons/LESSONS.md` is unchanged by this story.
- Running the lessons-scoped apply substitutes real fleet-repo names with
  their mapped anonymized label, using the same runtime-loaded
  `.pairmode-fleet.local.json` map and matching logic
  (`_real_names_to_labels`/`_expand_case_variants`/`_build_pattern`/
  domain-context skip) `scrub_fleet_names.py` already uses, applied only to
  each existing lesson entry's free-text fields: `source_project`,
  `trigger`, `problem`, `learning`, `methodology_change.description` (when
  present), and `value_framing` (when present).
- For every entry, after the lessons-scoped apply: entry count, the ordered
  list of `id`s, and each entry's `date`, `status`, `enforced_by`,
  `applies_to`, `methodology_change.affects`, and `validation_phase` are
  byte-identical to before the apply ran — only the free-text field values
  listed above may differ, and only where they contained a mapped real
  name. Forbidden proxy: a diff that changes entry order, adds/removes an
  entry, or flips a `status` value while still reporting substitutions
  applied.
- `lessons/lessons.json` on disk is written with the same `json.dumps(...,
  indent=2)` + trailing-newline formatting `lesson_utils.save_lessons`
  already uses (no incidental reformatting of unrelated entries).
- `lessons/LESSONS.md` is regenerated from the updated `lessons.json` using
  the existing `lesson_utils.generate_lessons_md`, not a second hand-rolled
  renderer.
- After the lessons-scoped apply runs against the real project
  `lessons/lessons.json`/`lessons/LESSONS.md`, the lessons-scoped verify
  (or `scrub_fleet_names.py --verify --lessons`) reports zero remaining
  real-name hits in either file. Forbidden proxy: a verify pass that still
  scans the general tracked-file loop (which continues to skip both files)
  instead of actually re-reading `lessons.json`/`LESSONS.md` content.
- `lesson_utils.save_lessons`'s docstring, `skills/pairmode/skills/builder/procedure.md`'s
  "Lessons integrity" bullet, and `skills/pairmode/skills/reviewer/procedure.md`'s
  "LESSONS INTEGRITY" checklist item each name this one exception explicitly
  (citing CER-173): a real-name-only text substitution via
  `scrub_fleet_names.py`'s lessons-scoped mode on existing entries' free-text
  fields is not an append-only violation; any other field change, addition,
  removal, or reorder still is.
- `CLAUDE.build.md`'s `protected_paths` line is unchanged — `lessons/lessons.json`
  remains formally protected; this story documents one narrow, named
  exception to the append-only rule, not a blanket unprotection.

## Instructions

1. In `skills/pairmode/scripts/scrub_fleet_names.py`, add a lessons-scoped
   apply/verify path (CLI flag or dedicated function pair — builder's
   choice, consistent with the module's existing style) that:
   - Loads `lessons/lessons.json` directly (this is the deliberate,
     narrow exception to routing through `lesson_utils.save_lessons`'s
     append-only guard — do not weaken `save_lessons` itself, and do not
     make this path reachable from the general `apply()`/`verify()` loop).
   - Reuses the existing name-matching helpers
     (`_load_local_fleet_map`, `_real_names_to_labels`,
     `_validate_one_to_one`, `_expand_case_variants`, `_build_pattern`,
     `_is_domain_context`) rather than duplicating matching logic.
   - Substitutes matches only within the free-text field values named in
     `## Ensures` above, per entry — never touching `id`, `date`, `status`,
     `enforced_by`, `applies_to`, `methodology_change.affects`, or
     `validation_phase`, and never adding, removing, or reordering entries.
   - Before writing, assert entry count and the ordered `id` list are
     unchanged from what was read (raise, do not silently proceed, if
     either check fails).
   - Writes `lessons.json` back with `json.dumps(data, indent=2)` +
     trailing newline (matching `lesson_utils.save_lessons`'s format), then
     calls `lesson_utils.generate_lessons_md(data)` and writes the result
     to `lessons/LESSONS.md`.
   - On verify, re-reads both files and reports any remaining real-name hit
     using the same domain-context-aware matching as the existing
     `verify()`, without scanning the rest of the tracked tree (that stays
     the general loop's job).
2. Run the new lessons-scoped apply against the real
   `lessons/lessons.json`/`lessons/LESSONS.md`, then the lessons-scoped
   verify, to confirm zero real-name hits remain in either file — this is
   the actual CER-173 fix, not just new tooling.
3. Update `lesson_utils.save_lessons`'s docstring,
   `skills/pairmode/skills/builder/procedure.md`'s "Lessons integrity"
   bullet, and `skills/pairmode/skills/reviewer/procedure.md`'s "LESSONS
   INTEGRITY" checklist item to name the CER-173 exception precisely (real-
   name text substitution only, via `scrub_fleet_names.py`'s lessons-scoped
   mode; no other field change, addition, removal, or reorder is permitted
   under it) — so a future reviewer does not flag a legitimate CER-173-style
   diff as an append-only violation, and does not read the new text as
   license for a broader lessons.json rewrite.
4. Add regression tests to `tests/pairmode/test_scrub_fleet_names.py`
   covering the lessons-scoped path against fake fixture `lessons.json`
   data (never real fleet names — mirror the existing `FAKE_MAP` fixture
   pattern already in this test file):
   - A fixture entry whose `trigger`/`source_project` contains a fake
     mapped name is substituted with its label; entries with no match are
     unchanged.
   - Entry count, ordered `id` list, and every entry's `date`, `status`,
     `enforced_by`, `applies_to`, `methodology_change.affects`, and
     `validation_phase` are identical before and after.
   - The regenerated `LESSONS.md` fixture output reflects the substituted
     text.
   - Lessons-scoped verify reports zero hits after apply, and a nonzero
     hit count against unmodified fixture data containing a fake mapped
     name before apply runs.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_scrub_fleet_names.py -q
```
Acceptance: green, including the new lessons-scoped test cases.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```
Acceptance: full suite green (no regression to `lesson_utils`/`lesson.py`
tests from the docstring change).

**Proportionality note (INFRA-357/Step 4d):** this spec runs longer than the
project's 14-36-line baseline; the length is load-bearing here, not
padding — it spans a protected-file exception mechanism, a byte-identical
structural-field invariant across every existing lesson entry, and three
separate append-only-rule documentation sites (`lesson_utils.py`, builder
procedure, reviewer procedure) that must each name the same exception
precisely enough that a future reviewer doesn't misread it as either a
violation or a license to widen it.

## Out of scope

- Removing `lessons/lessons.json`/`lessons/LESSONS.md` from
  `CLAUDE.build.md`'s `protected_paths` list, or from the general
  `scrub_fleet_names.py` `apply()`/`verify()` tracked-file loop — both stay
  excluded there; only the new, separate lessons-scoped path may touch
  these two files.
- Any change to `methodology_change.affects`, `applies_to`, `status`,
  `enforced_by`, `date`, `id`, or `validation_phase` values, or to entry
  order — this story's substitution is text-value-only within the named
  free-text fields.
- Scrubbing real names from any file outside `lessons/lessons.json`/
  `lessons/LESSONS.md` — that is CER-172/INFRA-394's already-shipped scope.
- Widening `lesson_utils.save_lessons`'s append-only guard itself to accept
  arbitrary field edits — the guard is unchanged; the new lessons-scoped
  path in `scrub_fleet_names.py` deliberately bypasses it for this one
  narrow, audited operation instead of loosening it for all callers.
