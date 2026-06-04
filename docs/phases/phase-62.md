---
era: "002"
---

# project — Phase 62: Context gate authorization clarity

← [Phase 61: Scope-Miss Capture & Pre-Story Scope Checks](phase-61.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

A prior 'continue building' command does not authorize proceeding past the context gate if /context then shows at-or-above threshold. Add an explicit re-authorization rule to the Context gate section of CLAUDE.build.md and its Jinja2 template so the model cannot rationalize past the gate using inherited authorization from a command issued before /context was run.

## Stories

| ID | Title | Status |
|----|-------|--------|
| BUILD-026 | context gate: prior authorization does not survive a threshold-crossing /context read | draft |

## Schema delivery

No new persistent schema objects. No management surface needed.

---

### CP-62 Cold-eyes checklist

— developer fills in after phase completion —
