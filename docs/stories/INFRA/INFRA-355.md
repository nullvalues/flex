---
id: INFRA-355
rail: INFRA
title: Add Narrative of Record as spec-writer's sixth bounded input (DP1.3)
status: complete
phase: "118"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/spec-writer/procedure.md
touches:
  - skills/pairmode/scripts/schema_validator.py
  - skills/pairmode/scripts/story_new.py
  - tests/pairmode/test_spec_writer.py
  - tests/pairmode/test_schema_validator.py
  - tests/pairmode/test_story_new.py
  - docs/architecture.md
  - skills/pairmode/scripts/bootstrap.py
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

The spec-writer's input contract (DP1.3, `skills/pairmode/skills/spec-writer/procedure.md` § Input
contract) reads **exactly five** bounded inputs, deliberately, to keep context cost fixed and
prevent contamination. Adding narrative-of-record as a sixth category is not a minor addition — it
needs the same rigor the first five got: a bounded, deterministic way to know *which* narrative
file(s) are relevant to a given stub, without unbounded scanning of `docs/narratives/`.

The mechanism: a story's frontmatter gains an optional `narrative_roles: []` field (empty list is
valid — not every story concerns a build-loop role narratively, e.g. a pure internal refactor with
no role-facing behavior change). When non-empty, the spec-writer reads exactly the cited
`<ROLE>-000-ideology.md` file(s) as its sixth bounded input, and — mirroring Repo-A's own two-way
trace convention (`stories:` frontmatter on the narrative file, backfilled as specs cite it) —
appends the story's own ID to each cited narrative's `stories:` frontmatter list once the spec is
drafted.

## Requires

- INFRA-351/352/353/354 (this phase) must land first — the nine harness-role narratives plus
  OPERATOR must exist as real, synced files before spec-writer can be pointed at them.


## Scope widenings

| path | reason | widened_at |
| --- | --- | --- |
| skills/pairmode/scripts/bootstrap.py | narrative_roles validation needs bootstrap.NARRATIVE_FILES as the single source of the ten known role names (INFRA-355 Instructions #2) | 2026-08-03T14:22:42Z |

## Ensures

1. `skills/pairmode/skills/spec-writer/procedure.md` § Input contract is updated to **exactly six**
   bounded input categories — the existing five, plus: "6. Any narrative file(s) named in the
   stub's `narrative_roles:` frontmatter field, if present and non-empty."
2. `schema_validator.py` gains an optional `narrative_roles: list[str]` frontmatter field
   validated against the ten known role names (nine harness roles + OPERATOR) — an unknown role
   name is a validation error, not silently ignored.
3. `story_new.py`'s scaffold gains `narrative_roles: []` to the stub template (empty by default —
   a human or spec-writer decides which roles apply, never auto-inferred from title/rail).
4. When the spec-writer drafts a story whose `narrative_roles:` is non-empty, it reads exactly
   those cited `<ROLE>-000-ideology.md` files (and any numbered descendants that exist for that
   role) as bounded input 6 — no other file under `docs/narratives/` is read.
5. On successful draft, the spec-writer backfills the story's own ID into each cited narrative
   file's `stories:` frontmatter list (idempotent — re-running on an already-cited story doesn't
   duplicate the entry).
6. A story whose `narrative_roles:` is empty or absent behaves byte-identically to the pre-this-story
   spec-writer (Ensures 2/5 don't apply; input contract stays at five reads for that story).
7. Full `tests/pairmode/` suite green.

**Forbidden proxy:** the spec-writer reading `docs/narratives/README.md` or scanning the whole
`docs/narratives/` tree "just to be safe" instead of reading exactly the cited files — this defeats
the bounded-input property the same way an unbounded sixth category would.

## Instructions

1. Update the procedure doc's Input contract section first — this is the contract every other
   change in this story serves.
2. Add `narrative_roles` to `schema_validator.py`'s frontmatter schema, validated against a fixed
   set of the ten known role names (define this set once, import it everywhere it's needed rather
   than hand-duplicating the ten-role list — `bootstrap.NARRATIVE_FILES`'s role set from INFRA-351
   is the natural single source).
3. Add the field to `story_new.py`'s stub template.
4. Implement the read-exactly-cited-files step and the `stories:` backfill step in the spec-writer's
   own procedure steps (Step 2 reads inputs; add the backfill as a new step after drafting,
   analogous to how Step 4b handles the model-proposal write-back).
5. Add tests for: empty/absent `narrative_roles` is byte-identical to current behavior; a
   populated field causes exactly those files to be read (not more, not fewer); backfill is
   idempotent.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_spec_writer.py tests/pairmode/test_schema_validator.py tests/pairmode/test_story_new.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: both green.

## Out of scope

- Intent-reviewer's narrative-alignment checking (INFRA-356) — this story only wires the
  spec-writer's *input* side.
- Any change to how a human decides which `narrative_roles:` apply to a given story — that
  judgment call stays manual (or spec-writer-proposed, flagged for operator review the same way
  model-tier raises are, if a future story wants to add that) — not automated here.
