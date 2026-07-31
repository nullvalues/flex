---
id: INFRA-332
rail: INFRA
title: Sync backfill — sync-agents gains an add-missing-file path; backfill flex and flex-harness
status: draft
phase: "116"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/pairmode_sync.py
touches:
  - .claude/agents/spec-writer.md
  - .claude/agents/docs-reviewer.md
  - .claude/agents/gate-worker.md
  - skills/pairmode/skills/session_lifecycle.py
  - tests/pairmode/test_pairmode_sync.py
  - skills/pairmode/SKILL.md
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-138 (AG-13): `pairmode_sync.py`'s `sync-agents` (also chained by
`sync-all`, and delegated to by `pairmode_migrate.py` rule 2) only rewrites
agent files that already exist on disk in a target project's
`.claude/agents/` — "sync-agents walks .claude/agents/ in a target project,
finds the matching Jinja2 template ... for each" (`pairmode_sync.py:8-9`).
It has no path to *add* a file that exists only as a template but was never
scaffolded. `bootstrap.py` is the only code path that creates new agent
files, and it runs once, at fresh-install time.

Consequence, confirmed live: `docs-reviewer.md.j2` (INFRA-325, Phase 114)
landed as "complete" in flex's own repo, but flex's own `.claude/agents/`
never received `docs-reviewer.md` — the fix updated the template and the
scaffold list for *future* bootstraps, but nothing propagated it into flex
itself, the very project that shipped the fix. `gate-worker.md.j2` predates
INFRA-325 entirely (RELEASE-010) and has the identical gap. This is the
direct mechanical cause of CER-137's live-hit (docs-reviewer dispatch
fell back to a generic subagent this session).

This story depends on INFRA-331: the `spec-writer.md.j2` template must exist
before a backfill mechanism has anything to backfill for that role.

## Requires

1. `pairmode_sync.py`'s `sync-agents` implementation (`:776-` per the module
   docstring pointer) and its file-discovery loop — understand exactly how it
   currently enumerates "agent file found in `<project-dir>/.claude/agents/`"
   before adding an inverse (template-not-yet-scaffolded) enumeration.
2. `bootstrap.py`'s `AGENT_FILES` list (post-INFRA-331: nine entries) as the
   canonical source of "which templates should exist as agent files" — do
   not hand-maintain a second list; import or otherwise reuse `AGENT_FILES`.
3. `session_lifecycle.py` (INFRA-323) — the `RESTART REQUIRED` notice
   contract. Adding a *new* file to `.claude/agents/` is exactly the kind of
   registration-surface change that contract was built for; a newly-added
   file must trigger the same notice as a rewritten one. Do not build a
   second notice mechanism.
4. Baseline suite count.

## Ensures

1. **`sync-agents` gains an add-missing-file path.** For every
   `(target_path, template_name)` pair in `bootstrap.AGENT_FILES` whose
   `target_path` does not exist in the project's `.claude/agents/`,
   `sync-agents --apply` renders the template and writes the file (mirroring
   `bootstrap`'s own render call, not a divergent implementation); without
   `--apply` it reports what would be added, consistent with the command's
   existing dry-run/apply convention. **Correct signal:** running
   `sync-agents --apply` against a fixture project missing one or more
   `AGENT_FILES` entries results in all of them present afterward, byte-for-
   byte matching what a fresh `bootstrap --apply` would have produced for the
   same entries; **forbidden proxy:** a "would add N files" report with no
   `--apply` write path, or a write path that only logs success without the
   file actually landing.
2. **Existing update behavior is unchanged.** Files already present continue
   to be rewritten exactly as before (regression-free) — this story is
   additive to the enumeration, not a rewrite of the update logic.
3. **`session_lifecycle`'s `RESTART REQUIRED` notice fires on additions.**
   A run that adds one or more new agent files prints the same notice
   `sync-agents` already prints for frontmatter rewrites (INFRA-323's
   existing wiring point) — verify by test, not by inspection only.
4. **Flex and flex-harness are backfilled.** After landing, run
   `sync-agents --apply` (or the equivalent bootstrap-parity path) against
   both `/mnt/work/flex` and `/mnt/work/flex-harness`; confirm both now have
   all nine `.claude/agents/*.md` files. Record the before/after file listing
   as evidence — this is a real, observable state change to this repo's own
   `.claude/agents/`, not just a capability added to the tool.
5. **Docs updated.** `skills/pairmode/SKILL.md`'s `sync-agents` section
   states the add-missing-file behavior; `docs/architecture.md`'s
   sync-agents description (if one exists — locate before assuming) is
   corrected from "walks .claude/agents/" (existing-files-only framing) to
   reflect the new add path.
6. **Suite green.** Full run without `-x`; baseline + added tests.

## Instructions

1. Confirm INFRA-331 has landed (spec-writer.md.j2 exists, AGENT_FILES has
   nine entries) before starting — this story's fixture tests need all nine
   template names to be real.
2. Reuse `bootstrap.AGENT_FILES` and, where practical, the same render-and-
   write helper `bootstrap.py` already calls, rather than duplicating render
   logic in `pairmode_sync.py`.
3. After the code lands and its own tests pass, run the backfill against
   flex and flex-harness as a real operational step (Ensures 4) — this is
   part of the story's acceptance, not an optional follow-up.
4. Do not change `bootstrap.py`'s own behavior — it already creates all nine
   files correctly on a fresh install; this story only closes the gap for
   already-bootstrapped projects.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_pairmode_sync.py -q 2>&1 | tail -15
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -5
```

Acceptance: green; baseline held. Reviewer negative check: `ls
.claude/agents/*.md | wc -l` in both flex and flex-harness returns 9 after
the backfill step; a fixture test asserts `sync-agents --apply` on a
project missing N of nine files results in exactly N new files with no
diff against the corresponding fresh-bootstrap output.

## Out of scope

- Any `model_selector.py` change (INFRA-333).
- Any escalation-ladder change (INFRA-334).
- The work→agent-type classification doc (INFRA-335).
- Backfilling any fleet project other than flex and flex-harness — the
  fleet-wide propagation rides the existing post-checkpoint sync campaign
  mechanism (per INFRA-311's precedent), not this story.
