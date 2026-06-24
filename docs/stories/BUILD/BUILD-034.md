---
id: BUILD-034
rail: BUILD
title: "pre-flight gate CLIs: check-stub, check-schema-gate, check-auth-gate"
status: planned
phase: "78"
story_class: code
primary_files:
  - skills/pairmode/scripts/flex_build.py
touches:
  - tests/pairmode/test_flex_build.py
auth_gated: false
schema_introduces: false
---

# BUILD-034 — pre-flight gate CLIs: check-stub, check-schema-gate, check-auth-gate

**Phase:** 78
**Rail:** BUILD

## Background

Three orchestrator pre-flight checks currently require the orchestrator to read
the full story spec file and apply LLM judgment. This story replaces them with
three `flex_build.py` CLI subcommands that the orchestrator calls and reads a
short, structured response from — keeping story spec content out of orchestrator
context entirely.

Depends on INFRA-184 (the `auth_gated` and `schema_introduces` frontmatter fields).

## Ensures

### check-stub

1. `flex_build.py check-stub RAIL-NNN --project-dir .` exits 0 (clean) when the
   story file has no delegation language and has at least one acceptance surface section.
2. Exits 1 and prints a structured block when delegation language is found
   (`"See phase doc"`, `"See docs/phases/"`, `"See phase-"`).
3. Exits 1 and prints a structured block when no acceptance surface section is present
   (`## Ensures`, `## Acceptance criterion`, `## Acceptance criteria` — any one suffices).
4. Prints nothing on exit 0 (silent pass; orchestrator proceeds without noise).

Output on exit 1:
```
PRE-STORY BLOCK — Story [RAIL-NNN] is a stub.
[reason line(s)]
Action required: ...
When resolved, say: "Continue building"
```

### check-schema-gate

5. `flex_build.py check-schema-gate RAIL-NNN --project-dir .` exits 0 when
   `schema_introduces` is absent or `false` in the story frontmatter.
6. Exits 0 when `schema_introduces: true` AND a management surface story exists
   in the remaining phase stories (any story whose title contains "management",
   "UI", "CRUD", "admin", "route", "page", or "command" — same heuristic as the
   current manual check), OR when the story's `## Out of scope` or `## Background`
   contains an explicit exception phrase (`append-only`, `junction table`,
   `cron-output cache`).
7. Exits 1 and prints a structured block when `schema_introduces: true` and no
   management surface or documented exception is found.

Output on exit 1:
```
PRE-STORY BLOCK — Story [RAIL-NNN] introduces a schema object with no management surface.
Options:
1. Add a management UI story to the phase spec before building.
2. Note an explicit exception in the story spec (append-only, junction table,
   or cron-output cache) if one of those categories applies.
```

### check-auth-gate

8. `flex_build.py check-auth-gate RAIL-NNN --project-dir .` exits 0 when
   `auth_gated` is absent or `false` in the story frontmatter.
9. Exits 0 when `auth_gated: true` AND `docs/architecture.md` contains a line
   beginning with `**Classification:**` (recorded auth model classification).
10. Exits 1 and prints a structured block when `auth_gated: true` and no
    classification line is found in `docs/architecture.md`.
11. All three commands exit with a clear error message (stderr, exit 2) when the
    story file cannot be found.

Output on exit 1 (auth gate):
```
AUTH GATE — Story [RAIL-NNN] is auth-gated but no classification is recorded.
Load ~/.claude/policies/auth-coexistence.md and classify the auth model
(RBAC / ABAC / both), then record it in docs/architecture.md before building.
```

## Out of scope

- Changes to CLAUDE.build.md or its Jinja2 template (BUILD-035).
- Backfilling `auth_gated` or `schema_introduces` on existing story files.
- The management-surface heuristic does not need to be exhaustive — it covers
  the common cases; the story author is still responsible for correct declaration.

## Instructions

Add three new Click subcommands to `flex_build.py`:

### `check-stub`

Read the story file. Scan for:
- Delegation language: any of `"See phase doc"`, `"See docs/phases/"`, `"See phase-"` 
  appearing anywhere in the body (after the closing `---` of frontmatter).
- Acceptance surface: presence of a line starting with `## Ensures`,
  `## Acceptance criterion`, or `## Acceptance criteria` (case-insensitive).

Exit 0 silently if no delegation language found AND acceptance surface present.
Exit 1 with the structured block otherwise.

### `check-schema-gate`

Parse story frontmatter. Read `schema_introduces` (default `False` if absent or
non-boolean). If `False`: exit 0 silently.

If `True`:
1. Load the phase manifest to find remaining unbuilt stories (status != `complete`).
2. Scan each remaining story title for management-surface keywords (case-insensitive):
   `management`, `ui`, `crud`, `admin`, `route`, `page`, `command`, `dashboard`.
3. Also scan the current story's body for exception phrases: `append-only`,
   `junction table`, `cron-output cache`.
4. Exit 0 silently if a management surface story or exception phrase is found.
5. Exit 1 with the structured block if neither is found.

Phase manifest is located via `_find_phase_file(phase_id, project_dir)` where
`phase_id` comes from the story's frontmatter `phase` field.

### `check-auth-gate`

Parse story frontmatter. Read `auth_gated` (default `False` if absent or non-boolean).
If `False`: exit 0 silently.

If `True`:
1. Read `docs/architecture.md` (relative to `project_dir`).
2. Search for a line beginning with `**Classification:**`.
3. Exit 0 silently if found (auto-satisfied).
4. Exit 1 with the structured block if not found.

## Tests

Add to `tests/pairmode/test_flex_build.py`:

### check-stub tests
- `test_check_stub_clean_story_exits_0` — story with `## Ensures` and no delegation language
- `test_check_stub_delegation_language_exits_1` — story body contains "See phase doc"
- `test_check_stub_missing_acceptance_surface_exits_1` — no `## Ensures` or equivalent
- `test_check_stub_missing_story_file_exits_2` — nonexistent story ID

### check-schema-gate tests
- `test_check_schema_gate_false_exits_0` — `schema_introduces: false`
- `test_check_schema_gate_absent_exits_0` — field absent from frontmatter
- `test_check_schema_gate_true_with_mgmt_story_exits_0` — management story in phase
- `test_check_schema_gate_true_with_exception_phrase_exits_0` — "append-only" in story body
- `test_check_schema_gate_true_no_mgmt_exits_1` — `schema_introduces: true`, no surface, no exception

### check-auth-gate tests
- `test_check_auth_gate_false_exits_0` — `auth_gated: false`
- `test_check_auth_gate_absent_exits_0` — field absent from frontmatter
- `test_check_auth_gate_true_with_classification_exits_0` — architecture.md has `**Classification:**`
- `test_check_auth_gate_true_no_classification_exits_1` — `auth_gated: true`, no classification recorded
