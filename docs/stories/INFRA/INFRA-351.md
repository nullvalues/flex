---
id: INFRA-351
rail: INFRA
title: Split harness-role narratives into pairmode template source; scaffold via bootstrap NARRATIVE_FILES
status: draft
phase: "118"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/bootstrap.py
touches:
  - skills/pairmode/templates/narratives/BUILDER/BUILDER-000-ideology.md.j2
  - skills/pairmode/templates/narratives/REVIEWER/REVIEWER-000-ideology.md.j2
  - skills/pairmode/templates/narratives/LOOP-BREAKER/LOOP-BREAKER-000-ideology.md.j2
  - skills/pairmode/templates/narratives/SECURITY-AUDITOR/SECURITY-AUDITOR-000-ideology.md.j2
  - skills/pairmode/templates/narratives/INTENT-REVIEWER/INTENT-REVIEWER-000-ideology.md.j2
  - skills/pairmode/templates/narratives/DOCS-REVIEWER/DOCS-REVIEWER-000-ideology.md.j2
  - skills/pairmode/templates/narratives/GATE-WORKER/GATE-WORKER-000-ideology.md.j2
  - skills/pairmode/templates/narratives/SPEC-WRITER/SPEC-WRITER-000-ideology.md.j2
  - skills/pairmode/templates/narratives/ORCHESTRATOR/ORCHESTRATOR-000-ideology.md.j2
  - tests/pairmode/test_bootstrap.py
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

The operator flagged a real conflation risk in this era's Narrative of Record exercise:
`/mnt/work/flex/docs/narratives/<ROLE>/*.md` (drafted directly in flex's own tree during the
review that motivated this phase) mixes two categories that need to stay separate. The nine
build-loop-role narratives (BUILDER, REVIEWER, LOOP-BREAKER, SECURITY-AUDITOR, INTENT-REVIEWER,
DOCS-REVIEWER, GATE-WORKER, SPEC-WRITER, ORCHESTRATOR) describe the **harness itself** — identical
across every pairmode project, the same way `.claude/agents/builder.md` is identical across every
project. They belong in the template, scaffolded and synced like every other harness-owned file,
not hand-authored per project. (OPERATOR is handled separately — see INFRA-353.)

`bootstrap.py`'s existing `AGENT_FILES: list[tuple[str, str]]` (line 99) is the exact precedent:
a list of `(dest_rel, template_name)` pairs, each rendered via `_render_template` and written at
bootstrap time. This story adds a parallel `NARRATIVE_FILES` list following the identical shape.

## Requires

- The nine harness-role narrative files already exist as authored content at
  `docs/narratives/<ROLE>/<ROLE>-000-ideology.md` in this repo (written this era, pre-Phase-118).
  This story's job is to *relocate* that content to template source and add the scaffolding
  mechanism — not to re-author the narratives from scratch.

## Ensures

1. `skills/pairmode/templates/narratives/<ROLE>/<ROLE>-000-ideology.md.j2` exists for all nine
   harness-role narratives, each a Jinja2 template rendering to the same content already authored
   in `docs/narratives/<ROLE>/<ROLE>-000-ideology.md` (verbatim, except any generic phrasing that
   should become `{{ project_name }}`-substituted — e.g. a narrative referencing "this project"
   or "this era" in a way that should read naturally for a downstream project, not just flex).
2. `bootstrap.py` gains `NARRATIVE_FILES: list[tuple[str, str]]` immediately after `AGENT_FILES`,
   same tuple shape, listing all nine `(dest_rel, template_name)` pairs.
3. Fresh bootstrap (`bootstrap.py` main path) scaffolds all nine files into a new project's
   `docs/narratives/<ROLE>/<ROLE>-000-ideology.md`, rendered through the same `_render_template`
   context every other scaffolded file uses.
4. A parity test (mirroring the existing `AGENT_FILES ⊆ CANONICAL_FILES`-style guard) confirms
   `NARRATIVE_FILES`' template sources all exist on disk and its destination paths are well-formed
   (`docs/narratives/<ROLE>/<ROLE>-000-ideology.md` for each of the nine `ROLE` values).
5. `docs/architecture.md` documents `NARRATIVE_FILES` alongside its existing `AGENT_FILES`
   documentation, naming the same "harness-owned, templated, never hand-diverged" contract.
6. Full `tests/pairmode/` suite green.

**Forbidden proxy:** a `NARRATIVE_FILES` list that exists but omits `bootstrap.py`'s actual
scaffold-time render call (a list that's declared but never actually written to a fresh project) —
Ensures 3 requires a live bootstrap run (or an equivalent fixture-driven test) to prove the files
land, not just that the list is populated.

## Instructions

1. For each of the nine narrative files under `docs/narratives/<ROLE>/<ROLE>-000-ideology.md`, move
   (not duplicate) its body content into `skills/pairmode/templates/narratives/<ROLE>/<ROLE>-000-ideology.md.j2`.
   Read each file first — some of this era's narrative text refers to flex-specific events (e.g.
   "this era's own cold-eyes review," "Phase 116," specific INFRA-IDs) that should either become
   generic template language (a downstream project won't have a "Phase 116") or be acknowledged as
   flex-specific illustrative examples the template keeps as historical color, at your judgment —
   note whichever choice you make in the story's own Evidence section, since this is a real
   authorial call, not mechanical.
2. Do not leave `docs/narratives/<ROLE>/<ROLE>-000-ideology.md` empty or deleted — INFRA-354 (this
   phase) backfills it from the new template as a separate, explicit step; leave the existing files
   as-is for now (they'll be regenerated, not hand-edited, by INFRA-354).
3. Add `NARRATIVE_FILES` to `bootstrap.py` directly below `AGENT_FILES`, same list shape.
4. Wire `NARRATIVE_FILES` into whichever function currently iterates `AGENT_FILES` at scaffold time
   (search for where `AGENT_FILES` is consumed, likely near line 1579) — add an equivalent loop, or
   extend the existing one if it can cleanly handle both lists without conflating them.
5. Add the parity test and the `docs/architecture.md` documentation.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_bootstrap.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: both green; a fresh-bootstrap fixture test shows all nine
`docs/narratives/<ROLE>/<ROLE>-000-ideology.md` files present with rendered (not raw Jinja2)
content.

## Out of scope

- OPERATOR's narrative (seed-then-extend mechanism) — INFRA-353.
- Backfilling flex's own `docs/narratives/` from the new template — INFRA-354.
- Any `sync-narratives` command for already-bootstrapped projects — INFRA-352.

## Evidence

- Authorial call (Instructions item 1): none of the nine harness-role
  narratives contain the literal string "flex" — all references to specific
  events (e.g. "this era's own cold-eyes review," "Phase 116," "Phase 117
  (INFRA-340/341)," SPEC-WRITER's flex story-size measurements) already read as
  generic first-person harness narration ("this era," "this project's own
  story history") rather than flex-branded text. Per the story's own guidance
  ("or be acknowledged as flex-specific illustrative examples the template
  keeps as historical color, at your judgment"), these were moved verbatim
  into the `.j2` templates as historical color/illustrative examples rather
  than genericized — a downstream project inherits the same narrative text
  flex itself authored this era, with flex's own concrete numbers (e.g.
  SPEC-WRITER's "stories 0–119... 260–319... peaking at 1317") standing as a
  real, if project-specific, illustration of the risk being described. No
  `{{ project_name }}`-substitution was applied since no narrative referenced
  "this project" in a way requiring per-project identity substitution to read
  naturally.
- Covered-contracts gate: `CLAUDE.build.md`'s `covered_contracts` pairs
  (`## Pairmode build loop::skills/pairmode/scripts/cer.py`,
  `## Module structure::skills/pairmode/scripts/next_action.py`) have no
  intersection with this story's `primary_files`/`touches`
  (`skills/pairmode/scripts/bootstrap.py` and the narrative
  templates/tests/architecture.md) — gate does not apply.
