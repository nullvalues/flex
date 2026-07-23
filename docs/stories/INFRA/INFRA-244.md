---
id: INFRA-244
rail: INFRA
title: Bring README.md current with the 0.3 resolver-driven design — remove 8-step/0.2-workflow/pre-resolver claims
status: planned
phase: "98"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - README.md
touches:
  - docs/architecture.md
---

## Context

The adversarial review of phase-98's other 7 stories (this session) independently
verified `README.md` and `docs/architecture.md` against the actual code and found
concrete over-claims beyond anything the other 7 stories already fix. This project's
own checkpoint policy (`docs/architecture.md`, checkpoint documentation-currency
section) states "a checkpoint with a stale README is not complete" — yet none of
phase-98's other stories touch `README.md`, and this repo's own checkpoints have
evidently been passing without that gate actually catching it. Findings, each
confirmed against code this session:

1. **README's 8-step checkpoint sequence description** (build gate, security audit,
   intent review, documentation update, phase completion check, CER backlog review,
   checkpoint tag, context health report) does not match the actual
   `_CHECKPOINT_SEQUENCE` in `next_action.py` (4 steps plus 3 pre-guards) — no
   phase-completion *step* exists as described (that's the currently-uncalled
   `mark-phase-complete`, INFRA-239), and no context-health report step exists.
2. **README's retry-escalation description** ("attempt 1 → sonnet, attempt 2 → opus")
   is wrong twice over: the retry ladder is currently unreachable (INFRA-237 — the
   attempt counter is never written), and even once reachable, the tiers don't match
   `model_selector.py`'s actual escalation ladder (which includes the `fable` tier
   added in INFRA-226).
3. **README's companion-integration claim** ("`current_story` written into
   `state.json` so the sidebar surfaces story context") — that key has never been
   written in this checkout (INFRA-238).
4. **README's context-gate description** ("blocks if the projected total exceeds the
   overrun ceiling... No LLM cooperation required — fully mechanical") states this as
   unconditionally working, with no mention of the `subagent_type` allowlist gap
   (INFRA-241) that makes it currently decorative for every real build-cycle spawn.
5. **README's Quick start / Scenario A** (installing via `claude code plugin
   install`, invoking a builder agent directly, a sidebar catching a raw-SQL write)
   describes the pre-resolver 0.1-era workflow, not the current `next-action`-driven
   loop.
6. **`docs/architecture.md:602`** documents `Agent({..., subagent_type: "reviewer",
   model: "opus"})` and per-template `# upgrade:` comments referencing agent
   templates retired in HARNESS-002 — the clearest single passage describing a design
   that never ran in 0.3, and the passage INFRA-241 partly inherited its (incorrect)
   model-override assumption from.
7. **`docs/architecture.md`** disagrees with itself on checkpoint step count: one
   passage (cited in phase-97's own prior finding) describes a 0.2-era 8-step
   numbering "Step 5 between Documentation review and CER backlog review," while
   another section (§10-area, the correct one) describes the actual 4-step sequence.

The other 7 stories in this phase (INFRA-236–243) each fix the underlying mechanism
for one or more of these claims. This story's job is narrower and comes *after* those
land conceptually (though it can be written now and built whenever convenient): make
the two most-read documents in this repo — `README.md` and `docs/architecture.md` —
describe what the code in this checkout actually does once phase 98 lands, not what
0.2 did or what 0.3 was designed to eventually do.

## Requires

- Ideally built last in phase 98, after INFRA-236 through INFRA-243 land, so the
  corrected README describes the *post-remediation* state rather than needing a
  second pass. If built earlier for any reason, scope the fix to removing/correcting
  false claims about the *current* pre-remediation state rather than describing
  not-yet-built future behavior as present-tense fact.

## Ensures

- README's checkpoint-sequence description matches `next_action.py`'s actual
  `_CHECKPOINT_SEQUENCE` (or the post-INFRA-239 sequence, if that story changes step
  count/order).
- README's retry-escalation description matches `model_selector.py`'s actual tiers
  (post-INFRA-237, if that story is built first) or is caveated as
  currently-non-functional if this story is built before INFRA-237 lands.
- README's companion-integration and context-gate claims are corrected to match
  actual (post-remediation, if built last) behavior, with no unconditional "fully
  mechanical, no LLM cooperation required" language left unqualified if any gap
  remains unfixed at the time this story is built.
- README's Quick start / Scenario A sections describe the current
  `next-action`-driven build loop, not the pre-resolver 0.1 workflow — update or
  replace the walkthrough accordingly.
- `docs/architecture.md:602`'s stale `Agent({subagent_type: "reviewer", ...})`
  passage is corrected to match INFRA-241's resolved spawn contract (or flagged as
  aspirational/historical if built before INFRA-241 lands).
- `docs/architecture.md`'s two self-contradicting checkpoint-step-count passages are
  reconciled to a single, correct description.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` passes (run without
  `-x`; confirm only the known CER-070 environmental failure remains) — this is a
  documentation-only story; the test run confirms no incidental code change slipped
  in.

## Instructions

1. Confirm build order: if INFRA-236–243 have landed by the time this story builds,
   verify each corrected claim against the post-fix code directly (don't assume the
   other stories' Ensures sections were implemented exactly as specced — re-check).
2. Rewrite the 7 findings in Context to match actual current behavior.
3. Sweep the rest of `README.md` for any further over-claims the 7 findings didn't
   already catch (the adversarial review was not necessarily exhaustive — treat its 7
   findings as a floor, not a ceiling).
4. Reconcile `docs/architecture.md`'s self-contradicting checkpoint-step-count
   passages.
5. Run the full test suite without `-x`; confirm only the known CER-070 failure
   remains.

## Out of scope

- Fixing any underlying mechanism described as broken — that's INFRA-236 through
  INFRA-243's job; this story only corrects documentation to match whatever the code
  actually does at build time.
- A general README rewrite/restructure beyond correcting the identified false claims
  — don't use this story as license for unrelated prose editing.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental failure (a
documentation-only story; this run confirms no incidental code drift).
