---
id: INFRA-178
rail: INFRA
title: "Single-source PAIRMODE_VERSION into _version.py (CER-046)"
status: complete
phase: "69"
story_class: code
primary_files:
  - skills/pairmode/scripts/_version.py
  - skills/pairmode/scripts/audit.py
  - skills/pairmode/scripts/bootstrap.py
  - skills/pairmode/scripts/sync.py
touches:
  - tests/pairmode/test_pairmode_status.py
---

# INFRA-178 — Single-source PAIRMODE_VERSION into _version.py (CER-046)

**Phase:** 69
**Rail:** INFRA
**Status:** planned

## Background

CER-046: `PAIRMODE_VERSION` is defined in two places with diverging values —
`audit.py:28` = `"0.1.0"` and `bootstrap.py:33` = `"0.2.0"`. `sync.py` imports
`PAIRMODE_VERSION` transitively from `audit.py` (via the `from audit import ...`
line at sync.py:29), so every `sync` run stamps `"0.1.0"` into the target
project's `state.json["pairmode_version"]`, silently downgrading projects that
were bootstrapped at `"0.2.0"`. The canonical version is `"0.2.0"` (the value in
bootstrap.py which writes the initial state).

## Ensures

1. A new file `skills/pairmode/scripts/_version.py` defines
   `PAIRMODE_VERSION: str = "0.2.0"` — the single source of truth.
2. `audit.py` removes its local `PAIRMODE_VERSION = "0.1.0"` definition and
   imports `PAIRMODE_VERSION` from `_version`. The `AuditResult` dataclass field
   `canonical_version: str` default is updated from the hard-coded `"0.1.0"` to
   `PAIRMODE_VERSION` (i.e., `"0.2.0"`).
3. `bootstrap.py` removes its local `PAIRMODE_VERSION = "0.2.0"` definition and
   imports `PAIRMODE_VERSION` from `_version`.
4. `sync.py` imports `PAIRMODE_VERSION` directly from `_version` instead of
   transitively from `audit`, removing the coupling.
5. `tests/pairmode/test_pairmode_status.py`: any fixture that writes
   `"pairmode_version": "0.1.0"` into state.json and asserts normal (non-outdated)
   status must be updated to `"0.2.0"` so it continues to match the new canonical.
   The test that asserts an update-hint appears for an older version must use a
   version string lower than `"0.2.0"` (e.g. `"0.1.0"` still works as the "old"
   value for that test, since `"0.1.0" < "0.2.0"`).
6. Full suite passes: `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`.

## Out of scope

- Changing the canonical version value itself (stays `"0.2.0"`).
- Any changes to `pairmode_migrate.py` or other scripts not listed above.
