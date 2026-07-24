# Fleet Snapshot

**Generated:** 2026-07-24 03:03:22 UTC
**Flex checkout:** `/mnt/work/flex-harness`

## Pre-fold gate notice (DP8)

The **authoritative pre-fold run of this tool is a hard gate immediately before
the fold** (DP8). Under Option Y, the fold makes `/mnt/work/flex` the 0.3.0
checkout; any un-migrated bound project breaks at the fold. The fleet may change
across the era, so the pre-fold run is what licenses the fold.

`registered_projects` stays drift-opt-in (distinct purpose; optionally seeded
from the discovered fleet, never forced).

## Flex itself (hub, not a discovered fleet member)

flex is the hub repo this tool runs from, so it is not one of the "discovered"
bound projects below. As of INFRA-249, flex's own `.companion/state.json`
records `"pairmode_version": "0.3.0"` (matching
`skills/pairmode/scripts/_version.PAIRMODE_VERSION`), self-synced by an
operator/orchestrator-applied edit — see INFRA-249's Build notes for why the
write could not be made by an in-worktree builder. This gives the phase-97
fleet re-sync an accurate baseline row for the hub itself.

## Discovered fleet

Found **16** bound project(s):

### `/mnt/work/aab`

- **Binding:** both
- **Signal 1 (scripts path):** present — `/mnt/work/flex-harness/skills/pairmode/scripts`
- **Signal 2 (pairmode_version):** present — `0.3.0`

### `/mnt/work/asp`

- **Binding:** both
- **Signal 1 (scripts path):** present — `/mnt/work/flex-harness/skills/pairmode/scripts`
- **Signal 2 (pairmode_version):** present — `0.3.0`

### `/mnt/work/base56`

- **Binding:** version
- **Signal 1 (scripts path):** absent
- **Signal 2 (pairmode_version):** present — `0.2.0`

### `/mnt/work/caddy`

- **Binding:** version
- **Signal 1 (scripts path):** absent
- **Signal 2 (pairmode_version):** present — `0.2.0`

### `/mnt/work/coherra`

- **Binding:** both
- **Signal 1 (scripts path):** present — `/mnt/work/flex-harness/skills/pairmode/scripts`
- **Signal 2 (pairmode_version):** present — `0.3.0`

### `/mnt/work/cora`

- **Binding:** version
- **Signal 1 (scripts path):** absent
- **Signal 2 (pairmode_version):** present — `0.1.0`

### `/mnt/work/forqsite`

- **Binding:** both
- **Signal 1 (scripts path):** present — `/mnt/work/flex-harness/skills/pairmode/scripts`
- **Signal 2 (pairmode_version):** present — `0.3.0`

### `/mnt/work/forqsite.help`

- **Binding:** version
- **Signal 1 (scripts path):** absent
- **Signal 2 (pairmode_version):** present — `0.2.0`

### `/mnt/work/halfhorse`

- **Binding:** version
- **Signal 1 (scripts path):** absent
- **Signal 2 (pairmode_version):** present — `0.2.0`

### `/mnt/work/lumin`

- **Binding:** version
- **Signal 1 (scripts path):** absent
- **Signal 2 (pairmode_version):** present — `0.2.0`

### `/mnt/work/meander`

- **Binding:** version
- **Signal 1 (scripts path):** absent
- **Signal 2 (pairmode_version):** present — `0.2.0`

### `/mnt/work/pokus`

- **Binding:** version
- **Signal 1 (scripts path):** absent
- **Signal 2 (pairmode_version):** present — `0.2.0`

### `/mnt/work/radar`

- **Binding:** both
- **Signal 1 (scripts path):** present — `/mnt/work/flex-harness/skills/pairmode/scripts`
- **Signal 2 (pairmode_version):** present — `0.3.0`

### `/mnt/work/rockue`

- **Binding:** both
- **Signal 1 (scripts path):** present — `/mnt/work/flex-harness/skills/pairmode/scripts`
- **Signal 2 (pairmode_version):** present — `0.3.0`

### `/mnt/work/stackabid`

- **Binding:** both
- **Signal 1 (scripts path):** present — `/mnt/work/flex-harness/skills/pairmode/scripts`
- **Signal 2 (pairmode_version):** present — `0.3.0`

### `/mnt/work/ud`

- **Binding:** both
- **Signal 1 (scripts path):** present — `/mnt/work/flex-harness/skills/pairmode/scripts`
- **Signal 2 (pairmode_version):** present — `0.3.0`

