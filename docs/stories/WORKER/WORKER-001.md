---
id: WORKER-001
rail: WORKER
title: Gate verdict grammar + fixture (DP3)
status: complete
phase: "HARNESS002-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/gate_verdict.py
  - tests/pairmode/test_gate_verdict.py
  - tests/pairmode/fixtures/gate_verdict_grammar.json
touches:
---

## Context

The first leaf-worker return contract for Era 003 (agreements
`HARNESS002-main.md` DP3). The gate worker (built in WORKER-002) returns a
**per-gate verdict map**, not a single scalar: because one worker faces both
the auth and schema gates at once (DP1.2 / DP2), the return is a map over the
*tripped* gates, each value using the grammar `clean | block:<reason> |
flag:<reason>` — e.g.
`{"auth": "clean", "schema": "block:introduces sessions table, no mgmt UI story in phase"}`.

This story pins **only the grammar and its fixture** — the data contract that
RESOLVER-005 routes on and WORKER-002 produces. It builds a small stdlib-only
parse/validate/round-trip module plus a JSON fixture, exactly as HARNESS001's
RESOLVER-001 pinned the action grammar before the state machine consumed it.
**No worker and no resolver/CLI wiring are built here** — this is the contract
layer only.

The shared `<verb>:<reason>` shape is deliberate forward design: HARNESS003
generalizes this contract across all leaf workers, so the grammar must be
designed to extend.

## Requires

- No prior HARNESS002 story. This is the first story in the build order; it has
  no dependency on the resolver or worker, which depend on *it*.

## Ensures

- A new module `skills/pairmode/scripts/gate_verdict.py` provides, stdlib-only
  (no third-party imports, no I/O):
  - The grammar constants — the verbs `clean`, `block`, `flag` and the set of
    judged gate names (`schema`, `auth`); `stub` is **not** a judged gate (it is
    mechanical, DP2) and is not a valid verdict-map key.
  - A parse helper that, given a single verdict **string**, returns its parsed
    form `(verb, reason)` where `reason` is `""` for `clean` and the freeform
    text after the first `:` for `block`/`flag`. The reason is a **freeform
    human string** (DP3.4) — carried verbatim, no structured sub-schema.
  - A validate helper for a **verdict map** that returns a list of
    human-readable violation strings (empty list ⇒ valid): keys must be a subset
    of the judged gate names; each value must start with a recognised verb;
    `block`/`flag` must carry a non-empty `<reason>`; `clean` must carry no
    reason payload.
- `tests/pairmode/fixtures/gate_verdict_grammar.json` is a JSON fixture
  enumerating representative verdict maps: all-clean, single block, single flag,
  mixed (`{"auth": "clean", "schema": "block:..."}`), and at least one invalid
  case (unknown verb, unknown gate key, empty block reason) for the negative
  round-trip.
- `tests/pairmode/test_gate_verdict.py` proves a **round-trip**: every valid
  fixture entry parses, re-serialises, and survives `json.loads(json.dumps(...))`
  unchanged; every invalid fixture entry yields a non-empty violation list.
- The grammar value space is exactly `clean | block:<reason> | flag:<reason>`;
  no other verb validates.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Keep `gate_verdict.py` pure and dependency-free — it is a contract module, the
  WORKER-rail analogue of RESOLVER-001's `make_action`/`validate_action`. The
  resolver-side routing of these verdicts is RESOLVER-005's parse helper, which
  may *import* this module; do not put routing logic here.
- The verdict map's keys are the **tripped judged gates only** — an all-clean
  worker over a story that only tripped schema returns `{"schema": "clean"}`,
  not a map with an `auth` key. Validation must allow any subset of the judged
  gate names (including the empty map, defensively).
- Model the `<verb>:<reason>` split on the first `:` only, so a reason string
  may itself contain colons (freeform). Round-trip must preserve that.
- Add the module to `tests/pairmode/` coverage (review-checklist item 6: a logic
  module in `skills/pairmode/scripts/` requires a test file).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_gate_verdict.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: round-trip green for every valid fixture entry; violation list
non-empty for every invalid entry; full suite green.

### Out of scope

- The gate worker itself (agent shell + procedure skill) — WORKER-002.
- The `spawn-gate-worker` action and resolver-side verdict routing /
  aggregation — RESOLVER-005.
- Any new `flex_build.py` CLI command or `check-*` signature change (DP6).
- Wiring into the live `CLAUDE.build.md` loop (the flip — HARNESS006).
