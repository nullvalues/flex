---
id: RELEASE-013
rail: RELEASE
title: Mid-build seam selection and pre-migration gate for Era 2 projects
status: draft
phase: "HARNESS013-main"
story_class: documentation
auth_gated: false
schema_introduces: false
primary_files:
  - docs/harness-cutover-runbook.md
touches: []
---

## Ensures

- `docs/harness-cutover-runbook.md` contains an explicit **"Seam gate"**
  checklist that the project operator runs before beginning migration on any
  project. The checklist covers:
  1. Last story is committed and pushed (`git status` clean).
  2. No attempt counter pending:
     `PATH=$HOME/.local/bin:$PATH uv run python flex_build.py read-attempt-count`
     returns `0`.
  3. Working tree is at a phase boundary (either at a checkpoint tag or all
     stories in the current phase are `complete`).
  4. No non-draft story in the current phase has an empty `primary_files` list
     (fails the new era 3 schema gate; operator must fill in before migrating):
     `flex_build.py check-stubs --project-dir P` returns clean.
  5. Project is registered in fleet discovery:
     `fleet_discovery.py list-projects` includes the project path.
- The runbook states that migration must **not** begin if any checklist item
  fails. Projects with a story in flight must complete or formally defer that
  story (update phase doc to `deferred`) before migrating.
- A note explains that Era 2 story specs remain valid post-migration: the
  story/phase/era schema is unchanged except relaxations (draft/backlog stories
  now accept empty `primary_files`). No spec rewrites are required unless a
  non-draft story has `primary_files: []`, in which case the operator must fill
  it in.
- A note addresses projects with customized Era 2 agent bodies: customizations
  in `.claude/agents/{builder,reviewer,...}.md` beyond what `sync-agents`
  preserves (procedure skill procedure.md files are plugin-owned) should be
  ported to a project-specific addendum in the relevant procedure skill's
  documentation before the stale agent file is deleted by RELEASE-011.
- `TEST RUN: documentation story — no test file expected`.

## Instructions

Read `docs/harness-cutover-runbook.md`. Add a **"§ Seam gate (run before
each project migration)"** section immediately before §Per-project mechanic.
Write the 5-item checklist and the prose notes described in Ensures.

Keep additions concise — one paragraph of prose maximum beyond the checklist.
