---
id: INFRA-250
rail: INFRA
title: Route pairmode_migrate.py's version default through _version.PAIRMODE_VERSION; fix SKILL.md migration-target doc drift
status: complete
phase: "99"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/pairmode_migrate.py
touches:
  - skills/pairmode/SKILL.md
  - tests/pairmode/test_pairmode_migrate.py
---

## Context

`skills/pairmode/scripts/_version.py` exists as the declared "single source
of truth for the pairmode scaffold version" and was bumped to `"0.3.0"` by
the fold. But `pairmode_migrate.py:489` still declares
`new_pairmode_version: str = "0.2.0"` as a hardcoded keyword default on the
state.json key-update handler. Any caller relying on the default stamps
migrated projects with 0.2.0; the same class of drift the fold just
demonstrated (a version bump that misses one hardcoded copy) will recur at
0.4.0 unless the default is derived, not duplicated.

Documentation drift in the same file family: `skills/pairmode/SKILL.md:989`
documents migration step 13 as updating `pairmode_version` "from `anchor-*`
to `0.2.0`".

Scope note: this story fixes the *derivation* of the default and the stale
doc line. Whether current callers of the handler pass the version explicitly
(masking the stale default) is for the builder to verify — the fix is
required either way, since a keyword default that silently disagrees with
`_version.py` is a loaded trap regardless of today's call sites.

## Requires

- No dependency on the other phase-99 stories; may build in any order.
- Audit call sites of the affected handler/parameter in
  `pairmode_migrate.py` (and any CLI wiring) to confirm whether the stale
  default is reachable in practice; record the finding in the build notes.

## Ensures

1. `pairmode_migrate.py` contains no hardcoded pairmode version string as a
   default; the default derives from `_version.PAIRMODE_VERSION`.
2. A pytest asserts the migrate handler's default version equals
   `_version.PAIRMODE_VERSION` (a drift canary: bumping `_version.py` alone
   can never again leave migrate stamping the old version by default).
3. `skills/pairmode/SKILL.md`'s migration table row for the state.json step
   no longer names a hardcoded target version, or names the current one with
   an explicit note that `_version.py` is authoritative.
4. A repo-wide grep for `"0.2.0"` under `skills/pairmode/` shows no remaining
   occurrence that functions as a *current-version* value (historical
   changelog/lesson references are exempt); any intentional survivors are
   listed in the build notes.
5. Existing pairmode tests pass.
