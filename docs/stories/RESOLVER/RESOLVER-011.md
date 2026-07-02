---
id: RESOLVER-011
rail: RESOLVER
title: Resolver read-model integration + housekeeper isolation suite
status: complete
phase: "HARNESS008-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
  - tests/pairmode/test_housekeeper_isolation.py
touches:
  - skills/pairmode/scripts/index_integrity.py
---

## Context

The integration + acceptance backbone of HARNESS008 (agreements `HARNESS008-main.md` DP2/DP3):
the `index_integrity.py` checker becomes a first-class part of the resolver read-model (sharing
the CER-056 deferred-as-inactive rule with `infer_position`), and the consolidated isolation
suite pins the graph-invariant checker deterministically.

## Requires

- RESOLVER-010 complete: `index_integrity.py` + the `check-index` CLI.

## Ensures

- `next_action.py`'s read-model composes `index_integrity` for its index read so the resolver
  and `check-index` share **one** deferred/backlog-as-inactive implementation (CER-056) — no
  divergence. The resolver stays **pure-read** (`grep` confirms no writes added); the checker
  is **advisory** at the resolver level (it does not change `resolve_next_action` routing).
- `tests/pairmode/test_housekeeper_isolation.py` — the consolidated, hermetic matrix: a fixture
  per violation class (drifted story, broken cross-link, orphan file, deferred-without-section)
  flags exactly it; a clean tree → exit 0 / no violations; a CER-056 fixture (a `deferred`
  phase) → treated as inactive by **both** `check-index` and `infer_position` (the active phase
  is the last non-deferred/non-complete, not the deferred one). No network, no live
  git-history dependence.
- Existing resolver tests (RESOLVER-004 matrix, the checkpoint/spec suites) still pass — the
  read-model composition does not regress position inference.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Share the deferred-as-inactive rule: have `infer_position` and `index_integrity` call the
  same helper (move it to `index_integrity.py` if cleaner — `touches`), so CER-056 is fixed
  once.
- Keep the integration read-only and routing-neutral (the checker reports; it does not alter
  the emitted action).
- Table-driven fixtures via `resolver_fixtures`; assert both the CLI and the resolver honor the
  deferred rule on the same fixture.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_housekeeper_isolation.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action_states.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: shared deferred-as-inactive rule (CLI + resolver); per-violation-class fixtures
green; clean-tree clean; CER-056 fixture inactive in both; resolver pure-read; RESOLVER-004
matrix unchanged; suite green.

### Out of scope

- The checker itself / the `check-index` CLI — RESOLVER-010.
- Auto-repair; hard-gating the checkpoint on `check-index`.
- Observability (Phase G).
