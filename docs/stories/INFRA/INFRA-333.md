---
id: INFRA-333
rail: INFRA
title: Model-selection completeness — select_gate_worker_model, select_spec_writer_model, select_docs_reviewer_model
status: draft
phase: "116"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/model_selector.py
touches:
  - skills/pairmode/scripts/next_action.py
  - skills/pairmode/templates/agents/gate-worker.md.j2
  - skills/pairmode/templates/agents/spec-writer.md.j2
  - skills/pairmode/templates/agents/docs-reviewer.md.j2
  - tests/pairmode/test_next_action.py
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-139 (AG-13): `model_selector.py` defines a `select_*_model` function for
five of the eight agent roles — `select_builder_model`, `select_reviewer_model`,
`select_intent_reviewer_model`, `select_security_auditor_model`,
`select_loop_breaker_model`. `gate-worker` and `docs-reviewer` hardcode
`model: sonnet` directly in their template frontmatter with no attempt-based
variation at all; `docs-reviewer.md.j2` already carries a comment naming this
exact gap ("checkpoint-docs currently resolves with model=None from
next_action.py ... adding a dedicated model-selection tier is separate
follow-on scope"). `spec-writer`'s model is hardcoded inline at
`next_action.py:1299` (`model="opus"`) rather than resolved through
`model_selector.py` like every other dispatch site.

Consequence: these three roles cannot be tuned, tiered, or audited through
the same mechanism as the other five — changing their model requires an
inline code or template edit at the call site instead of a table entry in
one file, and there is no attempt-2+ behavior defined for any of them at
all (not even a deliberate "never escalates" — just absent).

This story adds the missing selection functions and wires their real call
sites. It does **not** redesign the `doc`/`lesson`/`methodology`
`story_class` ladder (INFRA-334) — `gate-worker`/`spec-writer`/`docs-reviewer`
are phase-class or role-scoped selections (like `select_intent_reviewer_model`
takes `phase_class`, not `story_class`), a structurally separate axis.

## Requires

1. `model_selector.py`'s existing four checkpoint/role-scoped functions
   (`select_intent_reviewer_model`, `select_security_auditor_model`,
   `select_loop_breaker_model`) as the pattern to follow for `gate-worker`
   and `docs-reviewer` — both are checkpoint/gate-shaped roles, not per-story
   builder/reviewer roles, so their signature should take `phase_class` (or
   be parameter-free like `select_loop_breaker_model`) rather than
   `story_class`. Determine which by reading how each role is actually
   invoked (`next_action.py`'s `spawn-gate-worker` and `checkpoint-docs`
   call sites) — do not guess the signature.
2. `select_builder_model`'s pattern (`story_class`-keyed) as the closest
   analogue for `select_spec_writer_model`, since spec-writer operates on a
   specific story's stub, not a whole-phase checkpoint — but note
   spec-writer's dispatch is currently unconditional `opus` regardless of
   attempt number or story class; read `next_action.py:1290-1300`'s Row-2
   branch in full before deciding whether attempt-number variation belongs
   here at all, and state the decision's reasoning in the story's evidence.
3. `next_action.py:1299`'s literal `model="opus"` and its surrounding
   Row-2 branch — this is the one call site that must change to call the
   new `select_spec_writer_model` instead of hardcoding.
4. Baseline suite count.

## Ensures

1. **`select_gate_worker_model` exists**, follows the established docstring-table
   convention (see any existing `select_*_model` for the format), and its
   selected model is consumed by the `gate-worker` dispatch path in
   `next_action.py` (verify: does `next_action.py` currently pass a model at
   all for `spawn-gate-worker`, per the comment at `next_action.py:221`
   "spawn-gate-worker carries no builder model" — read that comment fully
   and either confirm it is now stale after this story or explain why the
   gate-worker tier is deliberately still frontmatter-only).
2. **`select_docs_reviewer_model` exists** and `next_action.py`'s
   `checkpoint-docs` action gains a `model=` value from it instead of the
   `model=None` the `docs-reviewer.md.j2` comment currently describes.
3. **`select_spec_writer_model` exists**, and `next_action.py:1299`'s
   Row-2 branch calls it instead of the literal `model="opus"`. The
   function's return for the current single known case (attempt 1, no
   attempt-number parameter yet exercised in production) must still resolve
   to `"opus"` — this is a refactor of the call site to the shared
   mechanism, not a change in effective behavior for the one case that
   exists today, unless the evidence from Requires 2 justifies an actual
   behavior change (state which, explicitly, in the story's evidence).
4. **Frontmatter comments corrected.** `gate-worker.md.j2` and
   `docs-reviewer.md.j2` drop or update their "model: sonnet, no selector"
   comments to reflect that a selector now exists and is authoritative
   (frontmatter `model:` becomes the fallback-only default, matching the
   `# fallback: haiku (never below)` convention already used elsewhere).
5. **`docs/architecture.md`'s model-selection table** (wherever the existing
   five-function table is documented — locate before assuming a location)
   gains the three new functions.
6. **Suite green.** Full run without `-x`; baseline + added tests, including
   at least one test per new function exercising its full selection table.

## Instructions

1. Read the full `spawn-gate-worker` and `checkpoint-docs` dispatch code
   paths in `next_action.py` before writing either new function's signature
   — do not assume `story_class` is the right key for either.
2. Add the three functions to `model_selector.py` following the file's
   existing docstring-table documentation convention exactly (each function's
   selection table documented in the module docstring, matching the five
   existing entries' format).
3. Wire each new function into its real call site; do not leave any of the
   three defined-but-unused.
4. Do not touch `select_builder_model`, `select_reviewer_model`,
   `select_intent_reviewer_model`, `select_security_auditor_model`, or
   `select_loop_breaker_model` — those five are out of scope (INFRA-334
   owns the `story_class` ladder those first two consume).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action.py -q 2>&1 | tail -15
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -5
```

Acceptance: green; baseline held. Reviewer negative check: grep
`model_selector.py` for exactly eight `^def select_` matches; grep
`next_action.py` for the literal string `model="opus"` and confirm it no
longer appears in the `spawn-spec-writer` branch.

## Out of scope

- Any `story_class` ladder redesign for `doc`/`lesson`/`methodology`
  (INFRA-334).
- Agent registration/template/backfill work (INFRA-331, INFRA-332).
- The work→agent-type classification doc (INFRA-335).
- `select_builder_model`/`select_reviewer_model`'s existing `code` ladder —
  unchanged.
