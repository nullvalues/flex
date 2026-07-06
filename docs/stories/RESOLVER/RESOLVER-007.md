---
id: RESOLVER-007
rail: RESOLVER
title: Checkpoint step tracker — `checkpoint_step` Position field + action vocabulary
status: complete
phase: "HARNESS004-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
  - tests/pairmode/test_checkpoint_step.py
touches:
  - tests/pairmode/resolver_fixtures.py
---

## Context

The RESOLVER half of HARNESS004 part 1 (agreements DP1 + DP4): the `checkpoint_step` Position
field and the checkpoint action vocabulary. After this story the resolver knows *which* checkpoint
step to emit next (by reading `state.json["checkpoint_step"]`), and the `ACTIONS` enum contains
all four checkpoint actions. The routing logic (which state-machine row emits a checkpoint action)
lands in RESOLVER-008.

## Requires

- WORKER-009 complete (HARNESS003 done): all five worker procedure skills exist; the return
  contract is established.

## Ensures

- **`checkpoint_step` in Position:** `infer_position` reads `state.json["checkpoint_step"]`
  (a list of completed step-ID strings, empty or absent if no checkpoint is in progress) and
  includes it as `position["checkpoint_step"]` (a `list[str]`, never `None`; defaults to `[]`).
- **New ACTIONS entries** in `next_action.py`:
  - `CHECKPOINT_SECURITY = "checkpoint-security"` added to `ACTIONS` and `_SPAWN_ACTIONS`.
  - `CHECKPOINT_INTENT = "checkpoint-intent"` added to `ACTIONS` and `_SPAWN_ACTIONS`.
  - `CHECKPOINT_DOCS = "checkpoint-docs"` added to `ACTIONS` and `_SPAWN_ACTIONS`.
  - `CHECKPOINT_TAG = "checkpoint-tag"` added to `ACTIONS` (NOT `_SPAWN_ACTIONS` — inline action).
  - Old `CHECKPOINT = "checkpoint"` action **removed** from `ACTIONS`. Any Row in
    `resolve_next_action` emitting `"checkpoint"` is updated to emit `None` / not reached
    (the routing to these rows is replaced in RESOLVER-008). Document the removal.
  - `SCHEMA_VERSION` bumped from 2 to 3.
- **Pure-read:** `infer_position` reads `state.json["checkpoint_step"]`; it does NOT write it.
  `grep` confirms no `write_text` / `json.dump` in `next_action.py`.
- `tests/pairmode/test_checkpoint_step.py` asserts deterministically (synthetic `state.json`
  fixtures):
  - A state.json with `checkpoint_step: []` → `position["checkpoint_step"] == []`.
  - A state.json with `checkpoint_step: ["checkpoint-security"]` → Position reflects it.
  - A state.json with no `checkpoint_step` key → Position defaults to `[]`.
  - `SCHEMA_VERSION == 3`; `"checkpoint-security"` in `ACTIONS`; `"checkpoint"` NOT in `ACTIONS`.
- Existing RESOLVER-004 matrix (`test_next_action_states.py`) still passes — the only changes
  are additive (new ACTIONS entries) plus the `checkpoint` removal. If any matrix row expected
  `action == "checkpoint"`, update its expectation to match the new routing or mark it as
  replaced-by-RESOLVER-008.
- `test_cli_surface_freeze.py` stays green (action-grammar additions; no CLI command change).
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- The `checkpoint` action removal is the only non-additive change. Find any `resolve_next_action`
  row that emitted `CHECKPOINT` and note it as "replaced by RESOLVER-008 checkpoint routing."
  Return a temporary `await-user` with `reason="checkpoint-decomposition-pending-RESOLVER-008"`
  from that branch so the suite stays green before RESOLVER-008 lands.
- Keep `checkpoint_step` logic strictly in `infer_position` (pure-read). Do not add any
  checkpoint step writes to `next_action.py`.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_checkpoint_step.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action_states.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: `checkpoint_step` in Position; four new checkpoint actions in `ACTIONS`; `checkpoint`
action removed; `SCHEMA_VERSION == 3`; pure-read; RESOLVER-004 matrix green; freeze green;
full suite green.

### Out of scope

- Checkpoint routing logic (`resolve_next_action` rows emitting checkpoint actions) — RESOLVER-008.
- The docs-review leaf worker — WORKER-011.
- `state.json["checkpoint_step"]` writes (harness / checkpoint workers).
