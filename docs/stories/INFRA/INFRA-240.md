---
id: INFRA-240
rail: INFRA
title: Restore per-project parameterization in procedure skills (fold-blocking)
status: complete
phase: "98"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/builder/procedure.md
  - skills/pairmode/skills/reviewer/procedure.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - skills/pairmode/templates/CLAUDE.md.j2
touches:
  - skills/pairmode/scripts/bootstrap.py
  - docs/architecture.md
  - tests/pairmode/test_templates.py
  - tests/pairmode/test_bootstrap.py
---

## Context

0.2's per-role agent templates were rendered per project with real Jinja fields:
`{{ test_command }}` (`builder.md.j2:76`; `reviewer.md.j2:85,188,198`),
`{{ protected_paths }}` (`builder.md.j2:35-38`), `{{ domain_isolation_rule }}`
(`builder.md.j2:45`). 0.3's procedure skills ship **unrendered** — they're plugin-versioned,
not per-project templates — and bake in flex's own values directly:
`uv run pytest tests/pairmode/ -x -q` (`builder/procedure.md:119`;
`reviewer/procedure.md:263,297`), the `tests/pairmode/` test-location convention,
flex's specific `hooks/`-layer rules and `/tmp/companion.pipe` reference
(`builder/procedure.md:80-87`), and flex's own protected-file list
(`reviewer/procedure.md:232-237`).

The builder procedure's declared input contract says it reads `CLAUDE.build.md` for
"build standards and test command" (`builder/procedure.md:48`) — but the current
51-line rendered `CLAUDE.build.md` template no longer contains a test command or
build-standards section at all (0.2's had a dedicated `## Running tests` section that
0.3's template dropped along with the rest of its prose). So the procedure's actual
test command comes from the hardcoded flex-specific literal in the procedure file
itself, not from anything the project's own rendered `CLAUDE.build.md` supplies.

This directly blocks the fold: per `docs/phases/phase-97.md`'s Deferred stories
section, 14 fleet projects are queued to migrate to pairmode 0.3.0, each following its
own `CLAUDE.build.md` Spec workflow in its own session. Any project bootstrapped or
synced onto 0.3 today inherits a reviewer that runs *flex's* pytest invocation against
*its own* test suite and checks *flex's* protected-file list — this is the same class
of bug flagged in `docs/checkpoints.md:103` (flex-internal identifiers leaking into a
downstream project's synced files), just in the procedure skill rather than a rendered
artifact.

## Ensures

- Per-project-varying facts (test command, test-directory convention, protected-file
  list, domain-isolation rules, companion-pipe path) live in a rendered per-project
  surface (`CLAUDE.md`/`CLAUDE.build.md` template fields, consistent with how 0.2 did
  it, or a new project-config file if that's a cleaner fit for the 0.3 architecture) —
  procedure skills reference that surface rather than containing project-specific
  literals.
- `builder/procedure.md` and `reviewer/procedure.md` contain zero hardcoded
  flex-specific literals (`tests/pairmode/`, the specific pytest invocation flags,
  flex's own protected-file list) — a test asserts this by scanning both files for the
  literal strings.
- `bootstrap.py`'s rendered `CLAUDE.build.md.j2` output for a project supplies whatever
  field the procedure skills now reference (test command, protected paths, etc.), and
  the builder's "read CLAUDE.build.md for build standards and test command" input
  contract is actually satisfiable again.
- A synthetic non-flex project (a `tmp_path`-based bootstrap in a test, per
  `test_bootstrap.py`'s existing pattern) produces a rendered `CLAUDE.build.md` whose
  test command differs from flex's own, and a check confirms nothing in the procedure
  skills would override it with flex's literal.
- `docs/architecture.md` updated to describe where project-varying facts live in the
  0.3 design.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` passes (run without
  `-x`; confirm only the known CER-070 environmental failure remains).

## Instructions

1. Enumerate every flex-specific literal in `builder/procedure.md` and
   `reviewer/procedure.md` (test command, test-dir convention, protected paths,
   companion-pipe path, domain rules).
2. For each, decide the parameterization surface: a rendered field in
   `CLAUDE.build.md.j2`/`CLAUDE.md.j2` that the procedure reads at build time, versus a
   project-config file the procedure reads directly. Prefer extending the existing
   `CLAUDE.build.md.j2` rendering since the builder's input contract already names
   that file.
3. Update `bootstrap.py`'s template context to supply these fields per project (they
   likely already exist as bootstrap inputs from the 0.2 templates — confirm before
   assuming new plumbing is needed).
4. Update the procedure skills to reference the parameterized surface instead of
   hardcoded literals.
5. Add the literal-scan test and the synthetic-project rendering test.
6. Update `docs/architecture.md`.
7. Run the full test suite without `-x`; confirm only the known CER-070 failure
   remains.

## Out of scope

- Re-rendering procedure skills per project (they remain plugin-versioned, shared
  across all projects) — only the *values* they reference become per-project, not the
  files themselves.
- Migrating the 14 pending fleet projects — that's phase-97's Deferred stories work,
  resumed per-project in each project's own session; this story only fixes what they'd
  inherit when they do.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental failure; new
coverage proves a non-flex synthetic project gets its own test command/protected paths
into the procedures' effective input, not flex's.
