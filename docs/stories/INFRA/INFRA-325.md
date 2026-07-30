---
id: INFRA-325
rail: INFRA
title: Wire docs-reviewer (WORKER-011) into canonical scaffold and checkpoint dispatch — role is fully specced but never created
status: draft
phase: "114"
story_class: code
auth_gated: false
schema_introduces: false
touches:
  - skills/pairmode/scripts/audit.py
  - hooks/session_start.py
  - skills/templates/agents/docs-reviewer.md.j2
  - CLAUDE.build.md
  - docs/architecture.md
  - tests/pairmode/test_audit.py
  - tests/pairmode/test_bootstrap.py
  - docs/phases/phase-114.md
  - docs/stories/INFRA/INFRA-325.md
---

<!-- SPEC-WRITER NOTE (frontmatter): `touches:` is block-style per CER-115 —
     flow-style `[a, b]` parses as a string and crashes create-story-worktree's
     `generate_permissions_artifact`. `CLAUDE.build.md` is a PROTECTED path
     (touched by this project's own build loop) and requires this explicit
     declaration plus a valid permissions artifact (INFRA-253). The exact
     template path for the new `.claude/agents/docs-reviewer.md.j2` file is a
     best-guess based on the naming pattern of the other six agent templates
     (`agents/<role>.md.j2` per `audit.py`'s `CANONICAL_FILES` — confirm the
     real templates directory during Instructions step 1, it was not
     independently verified at spec time). `docs/cer/backlog.md` is NOT
     touched: this story was routed directly into phase 114 by explicit
     operator instruction, discovered via a live checkpoint-docs run on
     phase 106, not pulled from an existing CER backlog row. -->

## Context

While running phase 106's checkpoint sequence (2026-07-29), the orchestrator
needed to dispatch the `checkpoint-docs` action and discovered there is no
`docs-reviewer` subagent type available in the session's agent registry, and
no dedicated `.claude/agents/docs-reviewer.md` shell exists on disk in this
project (confirmed directly: `ls -la .claude/agents/` shows exactly the
seven canonical files, all timestamped from the original bootstrap — nothing
named `docs-reviewer.md` has ever been added; not a stale-cache artifact).

Investigation found the role is **extensively documented but never wired
into any scaffolding or dispatch mechanism**:

1. A full, complete procedure skill exists at
   `skills/pairmode/skills/checkpoint-docs/procedure.md` (WORKER-011),
   specifying a precise input contract (phase doc, era doc, index.md,
   architecture.md, CER backlog, referenced story files' frontmatter,
   CHANGELOG.md if present), a six-item documentation-currency checklist
   (story-table/disk status match, story files exist, CER Do Now clear,
   architecture.md mentions current era, architecture.md mentions current
   phase, CHANGELOG.md has a phase entry if the file exists), and a
   `REVIEW-RESULT` return contract. Its own text says: "The thin agent
   shell delegates to this skill; no review logic lives in the shell" —
   i.e. a shell file is assumed to exist.

2. `docs/architecture.md` and `README.md` both reference `docs-reviewer`
   (as `WORKER-011`) as a real step in the checkpoint sequence
   (`checkpoint-security` → `checkpoint-intent` → `checkpoint-docs`
   (docs-reviewer) → `checkpoint-tag`), described as a peer of
   `security-auditor`/`intent-reviewer`.

3. But `skills/pairmode/scripts/audit.py`'s `CANONICAL_FILES` list (the
   authoritative set of files that `sync.py`/`sync-agents` actually
   scaffold into a project) contains exactly seven agent shells —
   `reconstruction-agent`, `gate-worker`, `builder`, `reviewer`,
   `loop-breaker`, `security-auditor`, `intent-reviewer` — with no
   `docs-reviewer` entry. `grep -rn "docs-reviewer" skills/pairmode/scripts/*.py`
   returns zero hits across `bootstrap.py`, `sync.py`, `pairmode_sync.py`,
   or any other scaffolding script.

4. `CLAUDE.build.md`'s `ACTION_SUBAGENT_TYPE` map (the table the
   orchestrator uses to resolve which `subagent_type` to spawn for a given
   `next-action` action) has no `checkpoint-docs` entry — it falls under
   the map's own comment "other spawn/checkpoint actions keep their own
   existing dispatch, out of INFRA-241 scope," but there is no *other*
   dispatch defined anywhere either. In practice, an orchestrator hitting
   `checkpoint-docs` has to either improvise a substitute (e.g. dispatch
   `general-purpose` with an ad-hoc, non-canonical prompt, as happened
   live on phase 106 — which produced a review that both missed real
   checklist items, e.g. CER Do Now and CHANGELOG.md, and added
   out-of-procedure judgment calls not in the spec) or fail to run the
   check at all.

This is a genuine half-implementation, not a documentation nit: the
review logic, input contract, and return format are all fully specified
and presumably load-bearing (`architecture.md` treats `checkpoint-docs` as
a real, non-optional gate in the checkpoint sequence), but nothing creates
the shell that is supposed to load and run that spec, and nothing tells
the orchestrator what `subagent_type` to spawn for it. Every project in
the fleet that has ever run a checkpoint has either silently skipped a
real docs-currency check or had it performed by an improvised,
non-canonical substitute.

## Requires

- `skills/pairmode/skills/checkpoint-docs/procedure.md` (WORKER-011) as
  the authoritative source of the review logic — do not rewrite or
  duplicate it; the new shell only needs to point at it, exactly like the
  other six shells point at their own procedure skills.
- `skills/pairmode/scripts/audit.py`'s `CANONICAL_FILES` list and its
  companion Jinja2 templates directory as the model for adding an eighth
  canonical file/template pair.
- `CLAUDE.build.md`'s existing `ACTION_SUBAGENT_TYPE` map pattern as the
  model for adding a `checkpoint-docs: docs-reviewer` entry.

## Ensures

- A new template (path confirmed during Instructions, likely
  `skills/templates/agents/docs-reviewer.md.j2` alongside the other six
  agent templates) exists, following the same thin-shell pattern as the
  other six agent shells (frontmatter with `name`/`description`/`tools`/
  `model`, then a short instruction pointing at
  `skills/pairmode/skills/checkpoint-docs/procedure.md`).
- `audit.py`'s `CANONICAL_FILES` gains an eighth entry:
  `(".claude/agents/docs-reviewer.md", "agents/docs-reviewer.md.j2")` (or
  the correct relative template path confirmed at build time).
- Running `sync.py`/`sync-agents`/`bootstrap.py` on a project (fresh or
  existing) creates `.claude/agents/docs-reviewer.md` on disk, matching
  the same content-currency guarantees (retirement pruning, `to-030`
  normalization awareness, etc.) as the other seven canonical shells.
- `CLAUDE.build.md`'s `ACTION_SUBAGENT_TYPE` map gains a
  `checkpoint-docs: docs-reviewer` entry.
- `docs/architecture.md`'s hook/dispatch or checkpoint-sequence
  description (wherever the `ACTION_SUBAGENT_TYPE` map or equivalent
  dispatch table is documented) is updated to reflect the new entry.
- `tests/pairmode/test_audit.py` and/or `tests/pairmode/test_bootstrap.py`
  gain coverage confirming `docs-reviewer.md` is scaffolded by a fresh
  bootstrap/sync, matching the pattern used for the other six shells'
  existing tests.
- No existing test in `tests/pairmode/` regresses (full suite run without
  `-x`, per this project's pytest-no-x-before-merge convention).
- This story's own spec is retrofitted, not built as part of phase 106 —
  phase 106's own checkpoint-docs step for this checkpoint (2026-07-29)
  proceeds using the same improvised substitute dispatch it already used,
  since this story cannot retroactively fix the tooling gap in time for
  phase 106's own checkpoint; that is out of scope here and handled
  separately by the orchestrator at build time.

## Instructions

1. Confirm the real templates directory and naming convention for the
   other six agent shells (`skills/templates/agents/*.md.j2` is the
   spec-time best guess — verify against `audit.py`'s actual template
   loader before assuming the path).
2. Read `skills/pairmode/skills/checkpoint-docs/procedure.md` in full and
   one existing agent template (e.g. `intent-reviewer.md.j2`) as the shape
   model for the new `docs-reviewer.md.j2` template — match its structure
   exactly (frontmatter shape, shell-instruction wording style pointing at
   the procedure skill).
3. Write the new `docs-reviewer.md.j2` template.
4. Add the eighth `CANONICAL_FILES` entry in `audit.py`.
5. Add the `checkpoint-docs: docs-reviewer` entry to `CLAUDE.build.md`'s
   `ACTION_SUBAGENT_TYPE` map.
6. Update `docs/architecture.md`'s corresponding dispatch/checkpoint-flow
   documentation.
7. Write/extend tests per the Ensures above.
8. Run `uv run pytest tests/pairmode/ -q` (no `-x`) and confirm no
   regressions; specifically confirm a fresh `bootstrap`/`sync` run
   produces `.claude/agents/docs-reviewer.md` on disk in a scratch/test
   project directory.

## Tests

`uv run pytest tests/pairmode/test_audit.py tests/pairmode/test_bootstrap.py -q`
plus a full `uv run pytest tests/pairmode/ -q` (no `-x`) run before merge.
