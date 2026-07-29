---
id: INFRA-318
rail: INFRA
title: Spec-time model review — story frontmatter model/reviewer_model honored by dispatch; asymmetric raise/lower prompt in spec-writer
status: draft
phase: "116"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
  - skills/pairmode/scripts/schema_validator.py
touches:
  - skills/pairmode/skills/spec-writer/procedure.md
  - tests/pairmode/test_next_action.py
  - tests/pairmode/test_schema_validator.py
  - tests/pairmode/test_spec_writer.py
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Cora item A#7 (AG-6): model choice is asymmetric and should be decided at
SPEC time, story by story. **Lowering** below the default is cheap to get
wrong (one rework cycle) — the spec-writer may do it unilaterally with a
note. **Raising** above the default is expensive to get wrong silently
(every attempt on every story pays it) — a raise requires prompting the
operator with story / proposed override / reason. And the *reviewer's* model
should be declarable per story, because review difficulty doesn't always
track build difficulty.

Mechanics that exist: the resolver's action schema already carries a `model`
key, non-null only for `spawn-builder` / `spawn-loop-breaker`
(`next_action.py:315`), with model selection logic (attempt-based
retry-upgrade, phase-37 lineage). What's missing: (a) story frontmatter
`model:` / `reviewer_model:` as validated fields, (b) dispatch honoring them
(story field overrides the default selection for attempt 1; retry-upgrade
still applies on later attempts and never downgrades below the declared
floor), (c) the reviewer spawn honoring `reviewer_model:` — which loosens
the model-null rule for `spawn-reviewer` deliberately, and (d) the
spec-writer procedure's asymmetric prompt.

**Correct signal: a story declaring `model:` demonstrably dispatches its
attempt-1 builder with that model (resolver output asserted in tests), and a
raise above default reaches the spec only alongside a recorded operator
approval note. Forbidden proxy: frontmatter fields that validate but that
dispatch never reads — a written-never-read field is the first item on this
project's cold-eyes checklist.**

## Requires

1. `schema_validator.py` field validation block (`:130-215`): optional-field
   pattern to follow (`test_gate`, `:199` area — enum-checked only when
   present). Valid model values: define one vocabulary constant (the model
   tiers the harness dispatches — read the live selection logic for the
   canonical names) shared by both new fields; do not free-text them.
2. `next_action.py` model selection: locate the existing
   attempt-1-default / retry-upgrade logic (phase-37 "builder model
   selection tuning" lineage) and the `:315` null-rule. `reviewer_model`
   requires relaxing the null-rule for `spawn-reviewer` — update the schema
   comment and any schema-version constant per that file's existing
   conventions (`SCHEMA_VERSION` history at `:69`).
3. The spec-writer procedure (`skills/pairmode/skills/spec-writer/procedure.md`)
   — the step sequence where frontmatter is authored; the asymmetric prompt
   lands there as an explicit numbered step, and the operator-approval
   record for a raise is a frontmatter-adjacent note in the story file
   (`model: opus  # raise approved: <date>, <reason>` or a body line —
   choose one form and pin it).
4. Story frontmatter parsing is the INFRA-296-hardened path — flow-style
   sequence rules don't apply to scalar fields, but re-verify the parser
   treats unknown keys as pass-through today (so old stories without the
   fields are untouched).
5. Baseline 4116/211.

## Ensures

1. **Fields validate.** `model:` / `reviewer_model:` are optional; when
   present they must be in the shared vocabulary constant; invalid values
   are validation errors. Stories without them validate exactly as today.
2. **Dispatch honors `model:`.** Attempt 1 of `spawn-builder` for a story
   declaring `model:` carries that model; retry-upgrade on attempt 2+
   upgrades from the declared value (never below it). No declaration →
   byte-identical output to today.
3. **Dispatch honors `reviewer_model:`.** `spawn-reviewer` for a declaring
   story carries the declared model (null-rule relaxed for exactly this
   action); no declaration → null, as today. Schema docs/comments updated
   in the same commit.
4. **Asymmetric prompt in the spec-writer procedure.** A numbered step:
   propose a model per story; lower-than-default → write it with a one-line
   note, no prompt; higher-than-default → present story / override / reason
   to the operator and record approval in the pinned form (Requires 3)
   before it may appear in frontmatter. `test_spec_writer.py` pins the
   step's presence and the approval-form text.
5. **No silent fleet-wide raise.** The default selection for undeclared
   stories is untouched — asserted by existing selection tests passing
   unmodified.
6. **Docs.** `docs/architecture.md` model-selection section documents both
   fields, the floor semantics under retry-upgrade, and the asymmetry
   rationale, ≤ 20 lines.
7. **Suite green** without `-x`; baseline + added tests.

## Instructions

1. Read the live selection logic before defining the vocabulary constant —
   the canonical tier names come from code, not memory.
2. Schema first (Ensures 1), dispatch second (2-3), procedure last (4);
   the null-rule relaxation and its comment land in the same commit as the
   reviewer dispatch change.
3. Fixtures: declared-builder-model attempt 1 and 2; declared-reviewer
   model; undeclared parity; invalid value rejection.

**Do not:** change the default model for any undeclared story; let
retry-upgrade downgrade below a declared floor; accept free-text model
strings; implement per-attempt frontmatter overrides (per-story is the
grain).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_schema_validator.py tests/pairmode/test_next_action.py tests/pairmode/test_spec_writer.py -q 2>&1 | tail -10
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -5
```

Acceptance: green; baseline held. Reviewer negative checks: (a) the fields
are read by dispatch (grep the resolver for both field names — written-never-
read is a FAIL); (b) undeclared-story resolver output byte-identical;
(c) the raise path's approval form is pinned by a test, not just described.

## Out of scope

- Cost accounting or effort-db changes (phase-37/110 surfaces untouched).
- Model selection for spec-writer/security-auditor/intent-reviewer spawns.
- Retroactively declaring models on existing stories.
