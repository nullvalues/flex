---
id: RESOLVER-001
rail: RESOLVER
title: Action grammar + schema fixture (DP1)
status: planned
phase: "HARNESS001-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
  - tests/pairmode/fixtures/next_action.schema.json
  - tests/pairmode/fixtures/next_action_samples.json
  - tests/pairmode/test_next_action_schema.py
touches:
---

## Context

This story delivers the **load-bearing contract of Era 003** (agreements
`HARNESS001-main.md` DP1): the versioned action grammar that every `next-action`
invocation emits and every later phase consumes. It defines the grammar **only** —
no position inference (RESOLVER-002), no state machine, no `flex_build.py`
subcommand (RESOLVER-003). "No CLI wiring yet" (DP1).

The emitted object is a single JSON object `{action, scalar, model, reason, meta}`
(plus a human line, added when the subcommand lands in RESOLVER-003). The action
enum is closed for this phase but **designed open-ended** — later phases add values
(gate/spec workers, checkpoint steps) without breaking consumers.

`jsonschema` is **not** a project dependency and must not be added (review-checklist
item 8). Validation is therefore a hand-rolled, stdlib-only `validate_action()` in
the module; the JSON Schema fixture is the human-readable contract artifact, and the
round-trip test asserts conformance via the in-module validator, not the library.

## Requires

- The merge of `main` into `harness` is complete (this work lands on `harness`,
  in `/mnt/work/flex-harness`, advisory-only — DP1/DP7).
- No prior RESOLVER story (this is the first).

## Ensures

- `skills/pairmode/scripts/next_action.py` exists and imports cleanly with stdlib
  only (no third-party imports; specifically no `jsonschema`).
- The module defines `SCHEMA_VERSION = 1` (int).
- The module defines the action vocabulary as named string constants whose values
  are exactly: `spawn-builder`, `spawn-loop-breaker`, `checkpoint`, `await-user`,
  `done` — and an `ACTIONS` collection containing exactly those five values and no
  others.
- The module defines `make_action(action, scalar="", model=None, reason="", meta=None)`
  returning a dict with keys exactly `{action, scalar, model, reason, meta}`, where
  `meta` is a dict that always carries `schema_version == SCHEMA_VERSION`.
- The module defines `validate_action(obj) -> list[str]` returning a list of
  human-readable violation strings; an empty list means valid. It is a pure function
  (no I/O, no global mutation).
- `validate_action` rejects, with a non-empty list: an unknown `action` value; a
  missing top-level key; a `model` that is non-null for any action other than
  `spawn-builder`/`spawn-loop-breaker`; a `meta` missing `schema_version` or whose
  `schema_version != SCHEMA_VERSION`.
- `validate_action` accepts a `done` action with empty `scalar` and null `model`.
- `tests/pairmode/fixtures/next_action.schema.json` exists, is valid JSON, declares
  the object shape (the five top-level keys, the action enum, the `meta` fields incl.
  `schema_version`, `warnings[]`), and records its version (matching `SCHEMA_VERSION`).
- `tests/pairmode/fixtures/next_action_samples.json` exists and contains at least one
  valid sample object **per action value** (≥5 samples), each produced in the shape
  `make_action` emits.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Create `skills/pairmode/scripts/next_action.py` as a pure grammar module. Suggested
  surface:
  - `SCHEMA_VERSION = 1`
  - action constants: `SPAWN_BUILDER = "spawn-builder"`, `SPAWN_LOOP_BREAKER =
    "spawn-loop-breaker"`, `CHECKPOINT = "checkpoint"`, `AWAIT_USER = "await-user"`,
    `DONE = "done"`; `ACTIONS = frozenset({...})`.
  - `make_action(action, scalar="", model=None, reason="", meta=None) -> dict` —
    constructs the canonical dict; copies `meta` (never mutates the caller's dict)
    and stamps `meta["schema_version"] = SCHEMA_VERSION`. Recognised `meta` fields
    (all optional except `schema_version`): `attempt` (int), `gate` (str), `fail_rung`
    (str), `warnings` (list[str]).
  - `validate_action(obj) -> list[str]` — stdlib-only structural check (the rules in
    Ensures). Keep messages specific enough to diagnose without reading the object.
- The `model`-population rule mirrors DP1/DP6: `model` is non-null **only** for
  auto-resolved spawn actions; `await-user`/`checkpoint`/`done` carry `model = None`.
  Encode this in `validate_action`.
- Do **not** add any `flex_build.py` subcommand here, and do not import position/model
  modules — this story is the grammar in isolation. The CLI-surface freeze test
  (RELEASE-003) must stay green precisely because nothing is added to the CLI yet.
- The JSON Schema fixture is documentation of the same contract; keep it and the
  Python validator in agreement (the round-trip test enforces this). Draft 2020-12
  vocabulary is fine; it is never fed to a validator library.

## Tests

`tests/pairmode/test_next_action_schema.py` (new). Cover:

- **Round-trip:** every sample in `next_action_samples.json` passes `validate_action`
  (returns `[]`) and survives `json.loads(json.dumps(sample))` unchanged.
- **Constructor:** `make_action(DONE)` yields `{action:"done", scalar:"", model:None,
  reason:"", meta:{schema_version:1}}`; `make_action` never mutates a passed-in `meta`.
- **Enum closure:** `ACTIONS` equals exactly the five documented values.
- **Negative cases:** unknown action; missing top-level key; `model` set on `await-user`;
  `meta` missing/own wrong `schema_version` — each yields a non-empty violation list.
- **Schema/validator agreement:** the action enum and top-level key set in
  `next_action.schema.json` match `ACTIONS` and `make_action`'s output keys.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action_schema.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

### Out of scope

- Position inference / reading durable state (RESOLVER-002).
- The state-transition machine and the `flex_build.py next-action` subcommand
  (RESOLVER-003).
- The full synthetic-state isolation suite (RESOLVER-004).
