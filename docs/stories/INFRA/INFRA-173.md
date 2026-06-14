---
id: INFRA-173
rail: INFRA
title: "`skills/pairmode/scripts/_version.py` — single-source `PAIRMODE_VERSION` consumed by `audit.py`, `bootstrap.py`, and `sync.py`"
status: deferred
phase: "66"
story_class: code
primary_files:
  - skills/pairmode/scripts/_version.py
  - skills/pairmode/scripts/audit.py
  - skills/pairmode/scripts/bootstrap.py
  - skills/pairmode/scripts/sync.py
touches:
  - skills/pairmode/scripts/pairmode_status.py
  - tests/pairmode/test_audit.py
  - tests/pairmode/test_pairmode_version_single_source.py
---

# INFRA-173 — `_version.py`: single-source `PAIRMODE_VERSION`

## Context

`PAIRMODE_VERSION` is declared in two places with diverging values: `audit.py:28`
pins `"0.1.0"` while `bootstrap.py:33` pins `"0.2.0"`. `sync.py` imports from
`audit` and gets the stale value, so every `sync` run stamps `state["pairmode_version"]
= "0.1.0"` — silently downgrading any project that was bootstrapped at `"0.2.0"`.
The fix creates a single `_version.py` module and has all three files import from it.

## Acceptance criteria

1. `skills/pairmode/scripts/_version.py` exists and contains exactly one public
   constant: `PAIRMODE_VERSION = "0.2.0"`.

2. `audit.py` no longer declares `PAIRMODE_VERSION` at module scope; it imports
   from `_version`. The name remains reachable at `audit.PAIRMODE_VERSION` so
   `sync.py`'s existing `from ... audit import PAIRMODE_VERSION` continues to work.

3. `bootstrap.py` no longer declares `PAIRMODE_VERSION` at module scope; it imports
   from `_version`. The name remains reachable at `bootstrap.PAIRMODE_VERSION` so
   `pairmode_status.py`'s existing import continues to work.

4. `sync.py` requires no source change — its existing import from `audit` now
   transitively resolves to `"0.2.0"`. A `SyncResult()` default
   `pairmode_version` is `"0.2.0"`.

5. `AuditResult.canonical_version` (the dataclass field default in `audit.py`) is
   no longer a hardcoded `"0.1.0"` literal. It uses `field(default_factory=lambda:
   PAIRMODE_VERSION)` so it tracks the canonical value. `format_audit_output` will
   now print `vs pairmode v0.2.0`.

6. `test_audit.py` lines asserting `canonical_version == "0.1.0"` are updated to
   assert against the imported `PAIRMODE_VERSION` constant from `_version`.

7. New `tests/pairmode/test_pairmode_version_single_source.py` locks the invariant:
   all three import sites resolve to the same string, that string equals
   `_version.PAIRMODE_VERSION`, and no consumer file contains a literal
   `PAIRMODE_VERSION = "..."` assignment.

8. All existing tests (`test_audit.py`, `test_bootstrap.py`, `test_pairmode_sync.py`,
   `test_pairmode_status.py`) continue to pass after the targeted edits.

## Implementation guidance

### `_version.py` (new file)

```python
"""Single source of truth for PAIRMODE_VERSION.

All pairmode modules must import from here — never redeclare this constant.
A divergent literal in audit.py, bootstrap.py, or sync.py causes silent
state.json downgrades on every sync run.
"""
from __future__ import annotations

PAIRMODE_VERSION: str = "0.2.0"
```

### `audit.py`

Replace line 28 (`PAIRMODE_VERSION = "0.1.0"`) with an import from `_version`.
Use a relative-style path consistent with how the file imports its siblings
(check the existing import block and mirror the pattern — either
`from skills.pairmode.scripts._version import PAIRMODE_VERSION` or a
`sys.path`-relative import, whichever matches the file's existing style).

Also change `AuditResult.canonical_version` from a literal default to:
```python
canonical_version: str = field(default_factory=lambda: PAIRMODE_VERSION)
```

### `bootstrap.py`

Replace line 33 (`PAIRMODE_VERSION = "0.2.0"`) with the same import as above.

### `sync.py`

No source change needed — verify by running the test suite.

### `test_audit.py` fixups

Import `PAIRMODE_VERSION` from `_version` at the top of the test module and
replace all `"0.1.0"` literal assertions in `canonical_version` checks with
the imported constant.

## Tests

File: `tests/pairmode/test_pairmode_version_single_source.py`

Test cases:
1. `test_version_module_exposes_semver_constant` — import from `_version`; assert
   non-empty string matching `^\d+\.\d+\.\d+$`.
2. `test_audit_reexports_canonical_version` — `audit.PAIRMODE_VERSION` equals
   `_version.PAIRMODE_VERSION`.
3. `test_bootstrap_reexports_canonical_version` — `bootstrap.PAIRMODE_VERSION`
   equals `_version.PAIRMODE_VERSION`.
4. `test_sync_reexports_canonical_version` — `sync.PAIRMODE_VERSION` equals
   `_version.PAIRMODE_VERSION`.
5. `test_all_three_modules_agree` — all three re-exports equal each other and
   `_version.PAIRMODE_VERSION`.
6. `test_no_literal_version_assignment_in_consumers` — open `audit.py`,
   `bootstrap.py`, `sync.py` as text; assert no line matches
   `^PAIRMODE_VERSION\s*=\s*["']`. (Regression-prevention test.)
7. `test_audit_result_canonical_version_tracks_version_module` — construct
   `AuditResult(project_name="x", project_dir=Path("."))` and assert
   `result.canonical_version == _version.PAIRMODE_VERSION`.
8. `test_sync_result_default_version_is_canonical` — construct
   `SyncResult(project_dir=Path("."))` and assert
   `result.pairmode_version == _version.PAIRMODE_VERSION`.
