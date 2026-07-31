---
id: INFRA-334
rail: INFRA
title: Escalation ladder redesign — every story_class gets a real retry-upgrade path
status: draft
phase: "116"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/model_selector.py
touches:
  - tests/pairmode/test_flex_build_story_cost_estimate.py
  - docs/stories/DESIGN
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-140 (AG-13): `select_builder_model`'s `story_class` table gives `doc`
and `lesson` classes `haiku` at every attempt number with no upgrade path
("auto-downgrade", never re-evaluated on retry), and gives `methodology`
`sonnet` at every attempt with escalation to `opus` only conditional on a
same-phase `code`-class story existing in the same phase manifest
(`select_reviewer_model`'s docstring table; `model_selector.py:206-` for the
builder side, `:155-` for the reviewer side). `code` is the only class with
an unconditional retry-upgrade path today.

Live-hit that surfaced this (reported by the operator from a sibling
project's build loop, cora): era-001 `docs/stories/DESIGN/*.md`
frontmatter-elaboration stories were classified `story_class: doc` — no
application-code file was ever touched, so `doc` looked like the correct fit
at spec time (commit history shows no recorded reasoning for picking `doc`
over the alternatives). The actual work involved heavy citation verification
against a live external codebase with zero tolerance for fabrication —
exactly the profile that benefits most from retry-escalation, and `doc`'s
ladder structurally cannot provide it: a haiku builder that fails on a hard
task is dispatched again at haiku, forever, with no mechanical path up. The
`story_class` taxonomy is being read by its two live consumers
(`select_builder_model`, `select_reviewer_model`) as a proxy for
verification-rigor tiering, not literally "does this touch application code"
— but only `code` currently behaves that way.

**Design decision (resolved by the operator during spec discussion, this
session):** give every class a real ladder rather than adding a fourth
"verification-heavy" class or splitting `story_class` into two axes (scope
vs. rigor). Smallest change that closes the "doomed to repeat-fail forever"
hole directly:

```
story_class   attempt=1   attempt>=2
-----------   ---------   ----------
code          sonnet      opus            (unchanged)
doc           haiku       sonnet          (was: haiku forever)
lesson        haiku       sonnet          (was: haiku forever)
methodology   sonnet      opus            (was: sonnet, conditionally opus)
```

The `methodology` same-phase-code-story conditional escalation
(`select_reviewer_model`'s `methodology-upgrade`/`methodology-baseline`
reason values, phase-manifest lookup) is **removed**, not kept as a second
path alongside the unconditional one — a class that sometimes escalates and
sometimes doesn't on the same attempt number is exactly the ambiguity this
story is closing.

## Requires

1. `select_builder_model`'s full current docstring table and decision logic
   (`model_selector.py:36-56` docstring, `:206-` implementation) — the
   `doc`/`lesson` "any complexity signal → haiku" rows and the `methodology`
   "any complexity signal → sonnet" row.
2. `select_reviewer_model`'s full current docstring table and decision logic
   (`:9-33` docstring, `:155-` implementation), including the phase-manifest
   same-phase-code-story lookup this story removes — identify every caller
   of that lookup path before deleting it (`phase_id`/`project_dir`
   parameters may become unused; if so, confirm no other consumer needs
   them before removing, or leave them as accepted-but-unused with a comment
   if API-compatibility with an external caller requires it — check before
   assuming either way).
3. Every existing test in `tests/pairmode/` that pins the current
   `doc`/`lesson`-never-escalates or `methodology`-conditional behavior —
   these are the contract this story is deliberately changing; find them
   with `grep -rn "doc-class-baseline\|methodology-upgrade\|methodology-baseline" tests/pairmode/`
   before editing, and update them to the new table rather than deleting
   coverage.
4. `story-cost-estimate`'s `(rail, story_class)` sampling
   (referenced in CER-045's resolution) — confirm this story's ladder change
   does not interact with cost-estimation sampling logic; if it does, note
   it, but do not fix cost-estimation here (out of scope).
5. Baseline suite count.

## Ensures

1. **`doc` and `lesson` escalate on retry.** `select_builder_model(story_class="doc"|"lesson", attempt_number=1, ...)` returns `haiku`;
   `attempt_number >= 2` returns `sonnet`, reason `"retry-upgrade"` (reuse
   the existing reason string `code` already uses for this transition — same
   semantic event, same name, per the file's own "duplicate-state is a
   cold-eyes checklist item" discipline elsewhere in this codebase).
2. **`methodology` escalates unconditionally.** `select_builder_model` and
   `select_reviewer_model` both return `opus` for `story_class="methodology"`,
   `attempt_number >= 2`, with no phase-manifest lookup and no dependency on
   `phase_id`/`project_dir`. The `methodology-upgrade`/`methodology-baseline`
   reason values and the same-phase-code-story query are removed from
   `select_reviewer_model`.
3. **`code`'s existing ladder is unchanged** — `sonnet`→`opus`, reason
   `"retry-upgrade"`, at every attempt number, byte-identical to current
   behavior. A regression test pins this explicitly (not just "still
   passes" — an explicit assertion that the code-class table did not move).
4. **Docstrings rewritten.** Both functions' module-docstring tables are
   updated to the new four-row shape with `attempt>=2` columns that no
   longer read "sonnet (never escalates)" for any class; the "Unknown
   story_class values default to the code rules" note is preserved
   unchanged (not part of this story's scope).
5. **No new class added.** `schema_validator.VALID_STORY_CLASSES` is
   unchanged — this story is a ladder redesign within the existing four
   classes, not a taxonomy expansion.
6. **Suite green.** Full run without `-x`; baseline + updated + added tests.
   Every test found under Requires 3 either still passes unmodified (if its
   assertion is about `code`, which didn't change) or was deliberately
   updated to assert the new `doc`/`lesson`/`methodology` behavior (list
   which tests were touched and why, in evidence).

## Instructions

1. Find and read every existing test pinning the old behavior (Requires 3)
   before writing any implementation change — know exactly what you are
   breaking and why it's correct to break it.
2. Change `select_builder_model` and `select_reviewer_model` together in one
   commit-worthy unit; they must agree with each other (a builder that
   escalates but a reviewer that doesn't, or vice versa, reintroduces the
   same kind of asymmetry this story is removing).
3. Do not touch `select_intent_reviewer_model`, `select_security_auditor_model`,
   or `select_loop_breaker_model` — those key on `phase_class`, not
   `story_class`, and are unaffected by this story's design decision.
4. Do not add a `story_class: verification` or any new class value — the
   operator's resolved decision for this story is the four-row table above,
   not a taxonomy split.
5. `docs/stories/DESIGN` is listed in `touches:` only because Requires/
   Ensures may reference it as the originating example — do not edit any
   file under it; it belongs to a different project/repo and is out of
   scope for this story to modify (if it resolves to a path that doesn't
   exist in this repo, that confirms it is illustrative only — do not
   create it).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -k "model_selector or select_builder or select_reviewer" -q 2>&1 | tail -20
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -5
```

Acceptance: green; baseline held. Reviewer negative check: grep
`model_selector.py` for `methodology-upgrade`/`methodology-baseline` and
confirm both reason strings are gone; grep for `phase_manifest` or
equivalent same-phase-code lookup inside `select_reviewer_model` and confirm
it is gone.

## Out of scope

- Adding a new `story_class` value (rejected design alternative, resolved
  during spec discussion).
- Splitting `story_class` into scope + rigor axes (rejected design
  alternative).
- `select_gate_worker_model`/`select_spec_writer_model`/`select_docs_reviewer_model`
  (INFRA-333 — those are role-scoped, not `story_class`-keyed).
- Reclassifying any specific existing story's `story_class` in this or any
  other project — that is a per-story spec-time decision, not this story's
  concern.
- `story-cost-estimate`'s sampling behavior, even if Requires 4 finds an
  interaction — file a CER row if one is found; do not fix it here.
