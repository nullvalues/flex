---
id: INFRA-184
rail: INFRA
title: "story frontmatter: add auth_gated + schema_introduces fields"
status: complete
phase: "78"
story_class: code
primary_files:
  - skills/pairmode/scripts/schema_validator.py
  - skills/pairmode/scripts/story_new.py
touches:
  - tests/pairmode/test_schema_validator.py
  - tests/pairmode/test_story_new.py
auth_gated: false
schema_introduces: false
---

# INFRA-184 — story frontmatter: add auth_gated + schema_introduces fields

**Phase:** 78
**Rail:** INFRA

## Background

The Phase 78 pre-flight offload requires two new boolean fields in story
frontmatter so the schema gate and auth gate can be evaluated by CLI rather
than by the orchestrator reading and reasoning over story body text.

`schema_introduces` answers: "Does this story introduce a new persistent schema
object (DB table, migration, collection, index)?" The schema gate reads this field
instead of asking the orchestrator to judge from story prose.

`auth_gated` answers: "Does this story touch user authentication, session handling,
permission checks, role validation, or access-controlled resources?" The auth gate
reads this field instead of the orchestrator scanning story text for auth-related
terms.

Both fields default to `false` when absent. No existing story is broken by their
absence — all CLIs treat a missing field as `false` (fail-open, no block).

## Ensures

1. `schema_validator.py` accepts `auth_gated` and `schema_introduces` as optional
   boolean fields on story frontmatter without emitting validation errors.
2. A story file with neither field passes validation identically to before.
3. A story file with `auth_gated: true` or `schema_introduces: true` passes validation
   (values are booleans; non-boolean values emit a validation error).
4. `story_new.py` scaffolds both fields as `false` on every new story file, positioned
   after `story_class` and before `primary_files`.
5. The `_story_frontmatter` helper in `story_new.py` includes both fields in its output.

## Out of scope

- The CLI commands that read these fields (BUILD-034).
- Changes to CLAUDE.build.md or its template (BUILD-035).
- Backfilling existing story files with the new fields.

## Instructions

### schema_validator.py

Add `auth_gated` and `schema_introduces` to the set of known optional fields so
the validator does not flag them as unknown. Add type checks: if either field is
present and not a boolean, emit a validation error:

```
"Field 'auth_gated' must be a boolean (true/false)"
"Field 'schema_introduces' must be a boolean (true/false)"
```

### story_new.py

In `_story_frontmatter()`, add the two fields after the `story_class` line (or after
the `status` line if `story_class` is absent) and before `primary_files:`:

```yaml
auth_gated: false
schema_introduces: false
```

Both fields are always emitted with value `false` by the scaffold — the story author
changes them to `true` when the story is auth-gated or introduces a schema object.

## Tests

### test_schema_validator.py

- `test_story_validates_with_auth_gated_false` — story with `auth_gated: false` passes
- `test_story_validates_with_auth_gated_true` — story with `auth_gated: true` passes
- `test_story_validates_with_schema_introduces_false` — story with `schema_introduces: false` passes
- `test_story_validates_with_schema_introduces_true` — story with `schema_introduces: true` passes
- `test_story_validates_without_new_fields` — story missing both fields passes (backwards compat)
- `test_story_fails_validation_auth_gated_non_boolean` — `auth_gated: "yes"` emits error
- `test_story_fails_validation_schema_introduces_non_boolean` — `schema_introduces: 1` emits error

### test_story_new.py

- `test_story_frontmatter_includes_auth_gated` — `_story_frontmatter(...)` output contains `auth_gated: false`
- `test_story_frontmatter_includes_schema_introduces` — output contains `schema_introduces: false`
- `test_story_frontmatter_field_order` — `auth_gated` and `schema_introduces` appear after `story_class`
  and before `primary_files:`
