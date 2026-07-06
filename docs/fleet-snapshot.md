# Fleet Snapshot

**Generated:** 2026-06-26 21:05:23 UTC
**Flex checkout:** `/mnt/work/flex`

## Pre-fold gate notice (DP8)

The **authoritative pre-fold run of this tool is a hard gate immediately before
the fold** (DP8). Under Option Y, the fold makes `/mnt/work/flex` the 0.3.0
checkout; any un-migrated bound project breaks at the fold. The fleet may change
across the era, so the pre-fold run is what licenses the fold.

`registered_projects` stays drift-opt-in (distinct purpose; optionally seeded
from the discovered fleet, never forced).

## Signal-1 zero-hit note (CER-059a)

All 9 bound projects show `Signal 1 (scripts path): absent`. This is **accurate, not a
false-negative**. Signal-1 fires only for projects whose `CLAUDE.build.md` contains an
explicit `pairmode_scripts_dir` key-value declaration — the marker written by
`pairmode_sync.py sync-all --apply` when a project is migrated to the 0.3.0 thin loop.
Pre-migration projects (all currently on 0.2.x) embed the scripts path only in inline
shell commands, not as a key-value line, so `_check_signal1`'s regex correctly returns no
match. After each project is synced, Signal-1 will fire for that project. The detection
logic requires no fix.

## Discovered fleet

Found **9** bound project(s):

### `/mnt/work/coherra`

- **Binding:** version
- **Signal 1 (scripts path):** absent
- **Signal 2 (pairmode_version):** present — `0.2.0`

### `/mnt/work/meander`

- **Binding:** version
- **Signal 1 (scripts path):** absent
- **Signal 2 (pairmode_version):** present — `0.2.0`

### `/mnt/work/forqsite`

- **Binding:** version
- **Signal 1 (scripts path):** absent
- **Signal 2 (pairmode_version):** present — `0.2.0`

### `/mnt/work/radar`

- **Binding:** version
- **Signal 1 (scripts path):** absent
- **Signal 2 (pairmode_version):** present — `0.2.0`

### `/mnt/work/asp`

- **Binding:** version
- **Signal 1 (scripts path):** absent
- **Signal 2 (pairmode_version):** present — `0.2.0`

### `/mnt/work/aab`

- **Binding:** version
- **Signal 1 (scripts path):** absent
- **Signal 2 (pairmode_version):** present — `0.1.0`

### `/mnt/work/cora`

- **Binding:** version
- **Signal 1 (scripts path):** absent
- **Signal 2 (pairmode_version):** present — `0.1.0`

### `/mnt/work/lumin`

- **Binding:** version
- **Signal 1 (scripts path):** absent
- **Signal 2 (pairmode_version):** present — `0.2.0`

### `/mnt/work/halfhorse`

- **Binding:** version
- **Signal 1 (scripts path):** absent
- **Signal 2 (pairmode_version):** present — `0.2.0`

