---
id: RESOLVER-004
rail: RESOLVER
title: Isolation test suite (DP8)
status: planned
phase: "HARNESS001-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - tests/pairmode/resolver_fixtures.py
  - tests/pairmode/test_next_action_states.py
  - tests/pairmode/test_next_action_compose.py
touches:
---

## Context

The acceptance backbone of the phase (agreements `HARNESS001-main.md` DP8): prove
`next-action` emits the **exact** action for each DP2 state, in isolation, against a
synthetic durable-state tree — no live repo, no network, no real worker spawns. This
story is what makes the resolver a trustworthy contract rather than a plausible one,
and it backs review-checklist items 6 (test coverage) and 10 (build gate).

It adds a reusable fixture-tree builder plus two test modules; it does **not** change
`next_action.py` or `flex_build.py` (if a test exposes a real defect, fix it under the
owning story, not here). Earlier RESOLVER stories carry their own focused tests; this
story is the exhaustive matrix that pins every DP2 row at once.

## Requires

- RESOLVER-001, -002, -003 complete: the grammar, the read-model (`infer_position`),
  and the state machine (`resolve_next_action`) + `flex_build.py next-action` all exist.

## Ensures

- `tests/pairmode/resolver_fixtures.py` provides a helper that constructs a **synthetic
  durable-state tree** in a tmp dir: phase doc(s) with a Stories table, story files with
  frontmatter, a seeded/faked git log driving commit-authority, `.companion/state.json`,
  and `.companion/attempt_counter.json` — parameterised enough to realise any of the 9
  DP2 states.
- `tests/pairmode/test_next_action_states.py` contains **at least one assertion per DP2
  state (≥9)**: for each state it builds the matching synthetic tree, runs
  `infer_position` → `resolve_next_action`, and asserts the emitted `{action, scalar,
  model, reason, meta}` equals the DP2-tabled expectation (including attempt number and
  reason string). The judgment-handoff rows (3, 4, 7) assert `action == "await-user"`
  with the correct reason and that no verdict was computed.
- The suite includes the **DP1 schema round-trip** at integration level: every action
  the matrix produces passes `validate_action` (returns `[]`) and survives
  `json.loads(json.dumps(...))` unchanged.
- `tests/pairmode/test_next_action_compose.py` is the **DP5 "composes, no signature
  drift" guard**: it asserts (e.g. via `inspect.signature`) that the composed
  functions — `next_story.find_next_story`, `model_selector.select_builder_model`,
  `story_resolver.resolve_story` / `list_phase_stories`, and the RESOLVER-002
  `flex_build` extractions — retain their expected signatures, and that `next_action.py`
  **imports** them rather than redefining their logic (no duplicated reimplementation).
- The suite is hermetic: no network, no dependence on the real project's phase docs or
  git history; it runs green from a clean checkout.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes (item 10).

## Instructions

- Build the fixture helper first; express each DP2 state as a small declarative config
  the helper consumes (active/complete phase, story statuses, commit presence, counter
  value, gate signal, model-selection outcome, advisory warnings). Prefer a table-driven
  test (`pytest.mark.parametrize` over the 9 rows) so the DP2 table and the test read
  as the same artifact.
- For commit-authority, seed a real git repo in the tmp tree (or stub the `_git_log_*`
  read path) so `find_next_story`'s commit check resolves deterministically — match how
  the existing `next_story` tests fake the git log.
- The signature-drift guard should fail loudly if a future phase edits a composed
  signature, naming the drifted function — that is the DP5 protection the era relies on.
- Keep the fixture helper free of production imports beyond what it must construct;
  it is test infrastructure, not a second read-model.

## Tests

This story **is** the test suite. Run:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action_states.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action_compose.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance includes the full-suite green (review-checklist item 10) and ≥9 state
assertions present (item 6).

### Out of scope

- Any change to `next_action.py` / `flex_build.py` behaviour (fix real defects under
  the owning RESOLVER story, then resume this one).
- States that belong to later phases — `spawn-reviewer`, `spec`, gate **verdicts**,
  checkpoint sub-steps (HARNESS002–005). Only the 9 HARNESS001 states are asserted.
- Wiring into the live loop (HARNESS006).
