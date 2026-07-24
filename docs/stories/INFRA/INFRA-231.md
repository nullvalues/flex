---
id: INFRA-231
rail: INFRA
title: Update fleet_discovery.py's hardcoded candidate list to include 7 missing fleet projects
status: complete
phase: "97"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/fleet_discovery.py
touches: []
---

## Context

A cold-eyes review this session found fleet-discovery coverage silently
shrank: `docs/fleet-snapshot.md`'s 2026-07-22 snapshot shows only 10 bound
projects, down from 16 on 2026-07-17, with six known fleet projects
(base56, caddy, forqsite.help, pokus, rockue, stackabid) missing entirely
from discovery output, despite all of them being real, active projects with
pending or in-flight pairmode 0.3.0 migration work this session directly
interacted with.

Root cause, confirmed by direct code read: `fleet_discovery.py`'s default
candidate list is `_DOCUMENTED_CANDIDATES` (`fleet_discovery.py:48`), a
hardcoded 9-name list (`coherra`, `forqsite`, `radar`, `asp`, `aab`, `cora`,
`lumin`, `halfhorse`, `meander`) that was never updated as the fleet grew.
The tool's separate `registered_projects` mechanism (read from *this*
checkout's own `.companion/state.json`) is confirmed empty (`[]`) in this
repo, and is explicitly documented as "drift-opt-in (distinct purpose;
optionally seeded from the discovered fleet, never forced)" — i.e. it is
not meant to be the completeness source for DP8; `_DOCUMENTED_CANDIDATES`
is. This is a stale hardcoded list, not a design gap.

This matters directly for the DP8 pre-fold gate (RELEASE-058): if the gate
is run using the tool's default candidate resolution without explicit
`--candidate-dir` flags for every project, it would silently pass while
leaving six real, potentially un-migrated projects undiscovered — exactly
the "no partial folds" guarantee DP8 exists to protect.

## Requires

- `fleet_discovery.py::_DOCUMENTED_CANDIDATES` in its current form
  (confirmed present and missing 7 projects this session: base56, caddy,
  forqsite.help, pokus, rockue, stackabid, ud).

## Ensures

- `_DOCUMENTED_CANDIDATES` includes all 15 known, currently-bound fleet
  projects: the existing 9 (`coherra`, `forqsite`, `radar`, `asp`, `aab`,
  `cora`, `lumin`, `halfhorse`, `meander`) plus the 6 missing ones
  identified this session (`base56`, `caddy`, `forqsite.help`, `pokus`,
  `rockue`, `stackabid`) plus `ud` (confirmed a real, active fleet project
  this session — `/mnt/work/ud`, "ud migration" project).
- `anchor` is **not** added — confirmed this session and previously
  documented (HARNESS016-main) as flex's frozen, non-pairmode-consumer
  predecessor, explicitly excluded from the managed fleet.
- The list stays alphabetically sorted (matching its current order) for
  readability and easy future diffing.
- No other logic in `fleet_discovery.py` is changed — this is a pure data
  update to one list literal.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` passes
  (run without `-x`; report every failure, confirm only the known CER-070
  environmental one remains).

## Instructions

1. In `skills/pairmode/scripts/fleet_discovery.py`, locate
   `_DOCUMENTED_CANDIDATES` (`fleet_discovery.py:48`) and add the 7 missing
   project name strings (`"base56"`, `"caddy"`, `"forqsite.help"`,
   `"pokus"`, `"rockue"`, `"stackabid"`, `"ud"`), keeping the list
   alphabetically sorted.
2. Do not add `anchor` or `cora` beyond `cora`'s existing entry (it's
   already present; leave it as-is — its parked/excluded status is handled
   elsewhere, not by removing it from discovery candidates).
3. Do not change any other line in the file.
4. Run the full test suite without `-x` and confirm the only failure is the
   known CER-070 environmental one.

## Out of scope

- Actually running the DP8 gate or a fresh fleet-discovery snapshot — that
  happens separately, closer to the actual fold attempt.
- Any change to the `registered_projects` mechanism or its documented
  "drift-opt-in, never forced" semantics.
- Adding `anchor` to any candidate list — explicitly excluded, not part of
  the managed fleet.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental
failure — run without `-x` and report every failure seen, not just the
first.
