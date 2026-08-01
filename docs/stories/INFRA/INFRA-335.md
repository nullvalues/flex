---
id: INFRA-335
rail: INFRA
title: Work→agent-type classification doc and new-agent-type definition-of-done
status: complete
phase: "116"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - docs/architecture.md
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-141 (AG-13): no document states which agent type is the correct dispatch
target for a given kind of work, or what a new agent type must have before
it is considered fully wired up. CER-137/138/139/140 each independently
rediscovered a piece of this same underlying gap — three separate
incomplete-registration findings (template missing, template unregistered,
backfill mechanism missing) and two separate escalation-completeness
findings (no model selector, no retry ladder) existed simultaneously with no
single reference that would have caught any of them at spec-review or
cold-eyes time. This story is strictly last in the INFRA-331..335 cluster:
it documents the finished shape of the other four, not a plan for them.

## Requires

1. INFRA-331, INFRA-332, INFRA-333, INFRA-334 all complete — this story
   describes their shipped state, not a proposal. Do not start this story
   until all four have landed; re-verify each of the claims below against
   the actual shipped code, not against this spec's description of them
   (this spec was written before any of the four built, and INFRA-334 in
   particular explicitly names design decisions that were resolved during
   spec discussion — confirm the shipped ladder matches).
2. `docs/architecture.md`'s existing structure — locate the section(s)
   currently describing agent dispatch, `ACTION_SUBAGENT_TYPE`, and the
   `model_selector.py` selection tables (referenced piecemeal throughout the
   Spawn contract sections cited by earlier phase docs, e.g. `CLAUDE.build.md`'s
   own reference to "docs/architecture.md § Spawn contract"). Add this
   story's content as a new subsection near that existing material, not as
   a disconnected new top-level section.

## Ensures

1. **Work→agent-type table.** A single table or equivalent structured list
   in `docs/architecture.md` naming each of the eight `templates/agents/`
   roles (builder, reviewer, intent-reviewer, security-auditor, loop-breaker,
   docs-reviewer, gate-worker, spec-writer — `reconstruction-agent` noted
   separately as belonging to a different skill, not the story build loop),
   what kind of work each is the correct dispatch target for, and which
   `next_action.py` action(s) route to it.
2. **New-agent-type definition-of-done.** A checklist stating what a new
   agent type must have before it is considered wired up, derived directly
   from what INFRA-331..333 actually built (not aspirational — each item
   must map to a real, checkable artifact that exists today for all eight
   current roles minus the noted `reconstruction-agent` exception):
   - a `templates/agents/<role>.md.j2` template
   - a materialized `.claude/agents/<role>.md` in every bootstrapped project
     (and a `sync-agents` add-path that reaches already-bootstrapped
     projects, INFRA-332)
   - a dispatch-action entry (`next_action.py` `ACTIONS`/`_SPAWN_ACTIONS`
     as applicable, plus `CLAUDE.build.md`'s `ACTION_SUBAGENT_TYPE`)
   - a `model_selector.py` `select_<role>_model` function, called from its
     real dispatch site rather than a hardcoded literal
   - an explicit escalation behavior for attempt >= 2 — even if the correct
     answer for a given role is "never escalates," that must be a stated,
     deliberate table row (as `code`/`doc`/`lesson`/`methodology` now all
     are post-INFRA-334), not an absent case.
3. **Escalation ladder documented in one place.** The full post-INFRA-334
   `story_class` table (all four classes, both attempt columns) is
   reproduced in `docs/architecture.md`, not left implicit in
   `model_selector.py`'s own docstring only — so a spec-writer choosing a
   `story_class` for a new story can read the escalation consequence of
   that choice without opening the source file.
4. **Cross-reference from the classification table to the ladder.** The
   work→agent-type table (Ensures 1) and the escalation table (Ensures 3)
   are linked or co-located so a reader following "what agent handles this
   work" naturally lands on "what happens if that agent fails."
5. **No behavior change.** This story is documentation-only; `touches: []`
   is deliberate — if writing this doc surfaces an actual code gap not
   already covered by INFRA-331..334, file a CER row for it rather than
   fixing it inline (this story's own scope discipline mirrors the policy
   it is documenting).

## Instructions

1. Do not draft this story's content speculatively — write it by reading
   the actual shipped `model_selector.py`, `CLAUDE.build.md`, and
   `bootstrap.py`/`pairmode_sync.py` state after INFRA-331..334 land, and
   transcribe what is actually true.
2. Keep the definition-of-done checklist short and checkable — five items,
   matching Ensures 2's list — not an essay. This is meant to be consulted
   at spec-review time for a future ninth agent type, not read once and
   forgotten.
3. If any of INFRA-331..334's actual shipped behavior diverges from this
   spec's description (e.g., `select_spec_writer_model`'s attempt-number
   handling depended on evidence gathered during that story), document what
   actually shipped, not what this spec predicted.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_docs.py -q 2>&1 | tail -10
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -5
```

Acceptance: green; baseline held. `test_docs.py` — if it structurally checks
`docs/architecture.md` section presence (as prior doc-currency stories have
used it) — is the natural home for a parametrized check that the new
subsection and both tables exist; extend it if such a pattern is already
established, otherwise a plain content-presence assertion is sufficient
(story_class: doc — no code-file test is required beyond the existing
doc-currency pattern this repo already uses for similar stories, e.g.
INFRA-305).

## Out of scope

- Any code change to `model_selector.py`, `next_action.py`,
  `CLAUDE.build.md`, `bootstrap.py`, or `pairmode_sync.py` — those are
  INFRA-331..334.
- Retroactively re-auditing every existing story's `story_class` assignment
  against the new documented rule — a separate, much larger undertaking not
  in scope for the closeout.
- `reconstruction-agent`'s own documentation — it belongs to a different
  skill's docs, not this table.
