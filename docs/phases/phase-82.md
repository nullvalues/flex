---
era: "003"
---

# project — Phase 82: security-auditor: document pairmode hook exceptions + audit scope rule

← [Phase 81: — write-permissions + clear-permissions wired into build loop](phase-81.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Update the security-auditor agent template and live agent file to enumerate the documented pairmode thin-delegation hook exceptions and add an audit-scope rule so upstream plugin infrastructure findings are not counted against a downstream project's checkpoint PASS/FAIL. Eliminates false CRITICAL/HIGH findings that block radar and other era-002 projects.

## Stories

| ID | Title | Status |
|----|-------|--------|
| BUILD-041 | security-auditor: add pairmode hook exceptions + audit scope rule | complete |

## Schema delivery

No new persistent schema objects introduced in this phase.
