---
id: INFRA-333
rail: INFRA
title: Model-selection completeness — select_gate_worker_model, select_spec_writer_model, select_docs_reviewer_model
status: complete
phase: "116"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/model_selector.py
touches:
  - skills/pairmode/scripts/next_action.py
  - tests/pairmode/test_model_selector.py
  - skills/pairmode/templates/agents/gate-worker.md.j2
  - skills/pairmode/templates/agents/spec-writer.md.j2
  - skills/pairmode/templates/agents/docs-reviewer.md.j2
  - tests/pairmode/test_next_action.py
  - docs/architecture.md
  - tests/pairmode/test_checkpoint_routing.py
  - tests/pairmode/test_harness004_isolation.py
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


## Scope widenings

| path | reason | widened_at |
| --- | --- | --- |
| tests/pairmode/test_checkpoint_routing.py | update baseline expectation: checkpoint-docs now carries a real model per Ensures 2, breaking model=None assertion | 2026-08-01T03:15:20Z |

| tests/pairmode/test_harness004_isolation.py | update baseline expectation: checkpoint-docs now carries a real model per Ensures 2, breaking model=None assertion | 2026-08-01T03:15:30Z |
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

## Evidence

**Covered-contracts gate (INFRA-317).** `next_action.py` is in this story's
`touches:` list and is the `source-file` half of the
`## Module structure::skills/pairmode/scripts/next_action.py` covered-contract
pair (`CLAUDE.build.md`'s `covered_contracts`). Both halves were read in full
before any edit. The relied-upon contract line (`docs/architecture.md` §
Module structure) is the `next_action.py` module-structure entry itself:

> `next_action.py            ← next-action resolver: action grammar
> (make_action, validate_action, ACTIONS), position read-model
> (infer_position), 9-state DP2 machine (resolve_next_action); ...`

No divergence found between the doc section and the source file for the
surfaces this story touches (Position dict, `_SPAWN_ACTIONS`/`validate_action`
model-null constraint, Row 2/4b/9 branches) — the doc's description of
`next_action.py` as the action-grammar/read-model/state-machine module was
accurate going in, and this story does not change that description (no new
action type, no `ACTIONS`/`_SPAWN_ACTIONS` membership change, no
`SCHEMA_VERSION` bump — see the new INFRA-333 module-docstring paragraph in
`next_action.py`).

**Requires 1 — gate-worker / docs-reviewer signature decision.** Read
`next_action.py`'s `spawn-gate-worker` emission (Row 4b, schema/auth judged
gates) and `checkpoint-docs` emission (Row 9, checkpoint step sequencing) in
full. Both are checkpoint/gate-shaped roles, not per-story roles keyed by a
single story's `story_class` — `spawn-gate-worker` fires once per tripped
story but judges the same schema/auth conformance question regardless of
which story is in front of it, and `checkpoint-docs` fires once per phase.
Both selectors are therefore keyed by `phase_class`, matching
`select_intent_reviewer_model`/`select_security_auditor_model`'s existing
pattern, not `select_builder_model`'s `story_class` pattern.

`select_gate_worker_model` reuses `select_security_auditor_model`'s tier
assignment (opus for production/pre-pr, sonnet for docs-only) — a missed
schema/auth violation is a correctness defect. `select_docs_reviewer_model`
reuses `select_intent_reviewer_model`'s tier assignment (sonnet for
production/docs-only, opus for pre-pr) — documentation-currency review is a
lower-stakes, advisory judgment.

**Ensures 1 — is the "spawn-gate-worker carries no builder model" comment
stale?** No. `validate_action` (next_action.py) requires `model=null` for
any action outside `_SPAWN_ACTIONS`, and `spawn-gate-worker` is deliberately
not a member of that set — this is locked in by the pre-existing test
`test_spawn_gate_worker_with_model_fails_validate`
(`tests/pairmode/test_next_action.py`). Promoting `spawn-gate-worker` into
`_SPAWN_ACTIONS` to let it carry a real model would be an action-grammar
redesign, out of this story's narrow "wire the missing selectors" scope (see
Context: "does not redesign ... a structurally separate axis"). The comment
therefore remains accurate for the action's `model` field after this story.
`select_gate_worker_model` is not left unused, though: Row 4b calls it
directly and surfaces the result as advisory
`meta["gate_worker_model"]`/`meta["gate_worker_model_reason"]` keys on the
emitted action — a real, tested call site (see
`test_gate_worker_model_varies_with_phase_class` and the updated
`test_schema_tripped_emits_spawn_gate_worker` in
`tests/pairmode/test_next_action.py`) — without changing the grammar.
`gate-worker.md.j2`'s frontmatter `model:` is therefore still the
authoritative default for this role, not merely a fallback (documented
explicitly in the template's updated comment).

**Requires 2 — spec-writer attempt-number decision.** Read
`next_action.py`'s Row 2 in full (`resolve_next_action`'s
`attempt_count == 0` / `needs_spec` branch). `resolve_next_action` only ever
emits `spawn-spec-writer` once, at Row 2 — there is no attempt ladder for
spec-writer anywhere in this module; a revised spec-writer pass is routed by
`SPEC-RESULT{revised}` handling in `CLAUDE.build.md` orchestrator prose, not
by a second `resolve_next_action` emission at a higher attempt number.
Decision: `select_spec_writer_model(story_class)` takes no attempt-number
parameter (unlike `select_builder_model`/`select_reviewer_model`), and is
unconditional opus across all `story_class` values — `story_class` on a
stub is frequently still the schema default rather than a considered
classification, and a bad elaboration corrupts every downstream attempt at
whatever class is eventually assigned, so there is no behavior-change
justification (per Requires 2's prompt) to downgrade any class. This is
purely a refactor of the `next_action.py:1299`-era hardcoded `model="opus"`
literal onto the shared mechanism (Ensures 3) — verified by
`grep -n 'model="opus"' skills/pairmode/scripts/next_action.py` returning
only documentary/comment occurrences, none inside the `spawn-spec-writer`
branch's executable code.
