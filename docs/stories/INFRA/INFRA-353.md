---
id: INFRA-353
rail: INFRA
title: OPERATOR seed-then-extend: templated typical-operator baseline plus bootstrap-led project extension
status: draft
phase: "118"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/bootstrap.py
touches:
  - skills/pairmode/templates/narratives/OPERATOR/OPERATOR-000-ideology.md.j2
  - docs/narratives/README.md
  - tests/pairmode/test_bootstrap.py
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Operator decision (this era): OPERATOR should not be purely project-authored the way a coherra
PATIENT or stackabid SELLER narrative is — pairmode should **lead** its construction the same way
bootstrap leads every other part of project setup, seeding a "typical operator" baseline and then
inviting project-specific extension, rather than leaving the file entirely to whoever happens to
author it later (or never). This makes OPERATOR a **tenth** templated/scaffolded narrative
(`NARRATIVE_FILES`, INFRA-351) — but unlike the nine harness-role narratives, its seed content is
generic ("a" typical operator, not "the" flex operator) and is explicitly meant to be extended, not
just consumed as-is.

The existing narrative numbering convention already expresses "seed, then extend without touching
the seed" cleanly: `<ROLE>-000-ideology.md` is the creed, and numbered descendants (steps of 10)
insert without renumbering. So: `OPERATOR-000-ideology.md` is the templated, generic seed (scaffolded
like the other nine); a project-specific extension lives at `OPERATOR-010-<project-slug>.md` or
similar, authored (or at least invited) during bootstrap's existing interactive prompt flow —
`bootstrap.py` already asks free-text, blank-to-skip questions ("What does this project produce?",
"Why does this project exist?") at exactly the right point in its flow to add one more.

## Requires

- INFRA-351 must land first (`NARRATIVE_FILES` mechanism must exist for `OPERATOR-000` to be added
  to it).

## Ensures

1. `skills/pairmode/templates/narratives/OPERATOR/OPERATOR-000-ideology.md.j2` exists: a genuinely
   generic "typical operator" seed — narrative/always-true/never/open-gaps sections that describe
   the operator role in any pairmode-adopting project (final authority on protected/release
   actions, dependence on the loop's PASS meaning something, no standing visibility into loop
   health between checkpoints), with no flex-specific content, no reference to this era's specific
   findings, and no reference to a specific human.
2. `OPERATOR-000` is added to `bootstrap.NARRATIVE_FILES` (INFRA-351) and scaffolds at fresh
   bootstrap like the other nine.
3. Bootstrap's interactive flow gains one additional free-text, blank-to-skip prompt (matching the
   existing style of "What does this project produce?") asking the operator something like:
   "Anything specific about how you want to work with this build loop — priorities, review
   habits, risk tolerance? (blank to skip)". A non-blank answer is written to a new
   `docs/narratives/OPERATOR/OPERATOR-010-project.md` extension file (numbered per the
   steps-of-10 convention); a blank answer skips file creation entirely — no empty extension file
   is ever written.
4. The seed (`OPERATOR-000`) is never edited by this prompt — only the separate `-010` extension
   file is written, preserving "seed, then extend without touching the seed."
5. `docs/narratives/README.md` documents this OPERATOR-specific seed-then-extend mechanism as
   distinct from the other nine roles' plain template-and-sync path.
6. Full `tests/pairmode/` suite green.

**Forbidden proxy:** writing the operator's free-text answer directly into `OPERATOR-000`
(clobbering the seed) instead of a separate numbered extension file — this defeats the entire
seed-then-extend design and would silently diverge every project's `OPERATOR-000` from the
template, exactly the drift `NARRATIVE_FILES`/`sync-narratives` exist to prevent.

## Instructions

1. Author the generic `OPERATOR-000-ideology.md.j2` seed first — read
   `docs/narratives/OPERATOR/OPERATOR-000-ideology.md` (this era's flex-specific draft) for
   structure and tone, but rewrite the content to be genuinely project-agnostic. Strip references
   to "this era," specific INFRA-IDs, or flex's own cold-eyes-review findings — replace with
   general statements about what any pairmode operator role entails.
2. Find bootstrap's existing interactive prompt block (`bootstrap.py`, the `click.prompt(...,
   default="")` sequence around line 1311-1318) and add one more prompt in that same style and
   location.
3. On a non-blank answer, write `docs/narratives/OPERATOR/OPERATOR-010-project.md` with minimal
   structure (a `## Narrative` section is sufficient for a first extension; don't force the full
   four-section shape onto a short operator answer).
4. Update `docs/narratives/README.md`'s role table/structure section to note OPERATOR's distinct
   seed-then-extend mechanism.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_bootstrap.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: both green; a fixture-driven bootstrap test confirms (a) `OPERATOR-000` scaffolds
identically regardless of the prompt answer, (b) a non-blank prompt answer produces
`OPERATOR-010-project.md` with that content, (c) a blank answer produces no `-010` file at all.

## Out of scope

- Any further OPERATOR extension mechanism beyond the initial bootstrap-time prompt (e.g. a later
  "revise your operator narrative" CLI command) — out of scope for this story; a human can always
  hand-author further `OPERATOR-0NN-*.md` files directly, no tooling required for that.
