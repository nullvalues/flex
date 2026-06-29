---
id: RESOLVER-005
rail: RESOLVER
title: spawn-gate-worker action + Row-4 split + verdict routing (DP4, DP6)
status: planned
phase: "HARNESS002-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
  - tests/pairmode/test_next_action.py
touches:
  - skills/pairmode/scripts/gate_verdict.py
---

## Context

The RESOLVER touch of HARNESS002 (agreements `HARNESS002-main.md` DP4 + DP6):
the worker enters the loop via a new resolver action, and its verdict re-enters
and routes — but the resolver **never computes** the verdict (the era invariant
"it does not codify judgment"). Today `next_action.py` Row 4 is a *dumb* stop:
any tripped gate (stub/schema/auth) emits `await-user:gate-blocked:<which>` with
no judgment. This story splits Row 4 along the DP2 boundary and adds the routing
that consumes the WORKER-001 verdict grammar.

DP2 boundary (binding): **stub** is mechanical (route straight to
`await-user`); **schema** and **auth** are judged gates (spawn the worker only
when one trips — spawn-on-trip, DP2.2); **scope/context** stay advisory
`meta.warnings[]`. The worker→verdict→route micro-sequence has **no durable
inter-step seam** — it stays orchestrator-held within the turn; the resolver
stays **pure-read** (no "worker ran" marker — DP7 of HARNESS001 holds). Re-running
the worker is idempotent (durable, unchanged inputs), so across a `/clear` the
resolver simply re-emits `spawn-gate-worker` (DP4.3).

The `spawn-gate-worker` action is also the **safe-clear seam** (DP4.5): the point
where `pre_tool_use`/`post_tool_use` budget hooks fire before any mutation. This
story documents that seam contract; it makes **no change to the hooks**
(protected) and **no `check-*` signature change** — the freeze test stays green
(DP6).

This story is built and tested with **injected** verdicts (the real worker is
WORKER-002), so the resolver wiring is provable before the worker exists.

## Requires

- WORKER-001 complete: the verdict grammar (`clean | block:<reason> |
  flag:<reason>`), the per-gate verdict-map shape, and `gate_verdict.py`'s
  parse/validate helpers — this story's parse helper and aggregation routing
  consume them.
- RESOLVER-001/-002/-003 complete (inherited): the action grammar,
  `infer_position`, and `resolve_next_action` with the existing Row-4 handling.

## Ensures

- **New action `spawn-gate-worker`** added to the open action enum (`ACTIONS`)
  in `next_action.py`; `scalar` = story ID. It is an auto-spawn-class action for
  validator purposes only insofar as DP4 requires (no model is attached — the
  gate worker tier is not a builder-model decision); `validate_action` accepts
  the new value and the existing model/meta constraints still hold.
- **Row 4 splits by the DP2 boundary** in `resolve_next_action`:
  - **stub** signal tripped → `await-user` with `reason="gate-blocked:stub"`
    directly (mechanical, exactly as today — no worker).
  - any **schema/auth** signal tripped (and stub clean) → emit
    `spawn-gate-worker` with `scalar = next_story_id`. The meta records which
    judged gate(s) tripped.
  - **no judged gate trips** → fall through to the existing Row-2/Row-3 path
    (`spawn-builder` / `await-user:model-upgrade`) unchanged.
- A **module-level parse helper** (in `next_action.py`, importing
  `gate_verdict.py`'s primitives — DP6.2: a function, **not** a new CLI) turns a
  worker's text return into the DP3 per-gate verdict map.
- An **aggregation routing** function/branch applies the DP3.2 rule to a verdict
  map: any `block` → `await-user` with `reason="gate-blocked:<gate(s)>"` carrying
  the worker's reason(s) in `meta`; else any `flag` → proceed (`spawn-builder`)
  with the flag reason(s) appended to `meta.warnings[]`; else all `clean` →
  proceed (`spawn-builder`). The aggregation is a **pure function** of the
  verdict map (no I/O), separately testable from the resolver state machine.
- The resolver remains **pure-read**: `grep` confirms no new `write_text` /
  `json.dump` / durable "worker ran" state is introduced by this story.
- The `check-*` CLI signatures are **unchanged** and no new gate-check CLI is
  added; `test_cli_surface_freeze.py` stays green (additions allowed,
  removals/renames forbidden — and this story adds no command).
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Add `SPAWN_GATE_WORKER = "spawn-gate-worker"` to `next_action.py` and include
  it in `ACTIONS`. Decide its model constraint explicitly: the gate worker
  carries no builder model, so it should validate with `model = None` (treat it
  like the non-spawn-builder actions for the model rule).
- In the Row-4 block of `resolve_next_action`, replace the single
  stub→schema→auth precedence loop with the DP4.2 split: stub first (mechanical
  `await-user`), then a single "any judged gate (schema or auth) tripped" check
  that emits `spawn-gate-worker`.
- Keep verdict **routing** out of the state-machine row itself where practical:
  the state machine decides *whether to spawn the worker*; a separate
  `route_gate_verdict(verdict_map, ...)`-style helper decides *what the verdict
  means*. This mirrors HARNESS001's grammar/state-machine separation and makes
  the injected-verdict tests clean.
- Do **not** call the real worker or make any API call from `next_action.py` —
  the verdict arrives as data (orchestrator-held re-entry, DP4.3). Tests inject
  verdict maps directly into the routing helper.
- Add a short module docstring note that `spawn-gate-worker` is the safe-clear
  seam (budget hooks fire here before mutation, DP4.5) and that re-emission
  across `/clear` is idempotent (DP4.3).

## Tests

Extend `tests/pairmode/test_next_action.py`:

- A schema-tripped position (stub clean, schema blocked) ⇒ `resolve_next_action`
  emits `spawn-gate-worker` with `scalar == story_id`, `model is None`,
  `validate_action == []`.
- An auth-tripped position ⇒ same.
- A stub-tripped position ⇒ `await-user` `reason="gate-blocked:stub"` directly
  (no `spawn-gate-worker`), preserving today's mechanical behaviour.
- No-gate position ⇒ falls through to `spawn-builder` (Row 2) unchanged.
- Injected-verdict routing via the aggregation helper (DP3.2 table):
  - `{"schema": "block:..."}` ⇒ `await-user` `reason` contains `gate-blocked`
    and the worker reason is carried in `meta`.
  - `{"auth": "clean", "schema": "block:..."}` ⇒ `await-user` (any block wins).
  - `{"auth": "flag:..."}` ⇒ `spawn-builder` with the flag reason in
    `meta.warnings[]`.
  - `{"schema": "clean", "auth": "clean"}` ⇒ `spawn-builder` (proceed).
- The verdict parse helper turns a representative worker text return into the
  correct per-gate map (round-trips against WORKER-001's grammar).
- `test_cli_surface_freeze.py` passes (no command added/removed).

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_cli_surface_freeze.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

### Out of scope

- The gate worker itself (agent shell + procedure skill) — WORKER-002; this
  story uses **injected** verdicts only.
- The CF-1/CER-060 retry-path model composition fix — RESOLVER-006.
- The exhaustive isolation matrix (DP8) — WORKER-003 (this story carries its own
  focused cases).
- Any new `flex_build.py` CLI command or `check-*` signature change (DP6).
- Wiring into the live `CLAUDE.build.md` loop (the flip — HARNESS006).
