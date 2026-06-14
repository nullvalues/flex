---
era: "002"
---

# flex — Phase 66: PAIRMODE_VERSION single-source

← [Phase 65: Context budget per-story drift fix](phase-65.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Eliminate the silent version downgrade caused by three diverging `PAIRMODE_VERSION` constants by collapsing them to a single source of truth. Today `audit.py` declares `0.1.0`, `bootstrap.py` declares `0.2.0`, and `sync.py` re-exports the stale `audit.py` value, so every `sync` run rewrites `state.json["pairmode_version"]` to `0.1.0` and effectively downgrades target projects. Phase 66 introduces `skills/pairmode/scripts/_version.py` as the canonical home for `PAIRMODE_VERSION`, points `audit.py`, `bootstrap.py`, and `sync.py` at that module, and locks the invariant in place with a test that asserts all three import sites resolve to the same string.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-173 | `skills/pairmode/scripts/_version.py` — single-source `PAIRMODE_VERSION` consumed by `audit.py`, `bootstrap.py`, and `sync.py` | deferred |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

## Deferred stories

| Story | Reason | Resumed in |
|-------|--------|-----------|
| INFRA-173 | CER-046 (the blocking finding this story was written to fix) remained open Do Now through Phases 67 and 68; build was deferred to avoid compaction. The fix was ultimately delivered as Phase 69 INFRA-178 (`_version.py` single-source, same design). | Phase 69 INFRA-178 |

---

### CP-66 Cold-eyes checklist

— developer fills in after phase completion —
