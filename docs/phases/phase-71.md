---
era: "002"
---

# flex — Phase 71: Propagate BUILD-029 Context gate fix into CLAUDE.build.md.j2 template

← [Phase 70: Restore per-story `/context` call in Context gate](phase-70.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

BUILD-029 corrected the Context gate in flex's own CLAUDE.build.md (live orchestrator file) but left the Jinja2 template skills/pairmode/templates/CLAUDE.build.md.j2 carrying the broken pre-BUILD-029 design — opening the Context gate by reading context_current_tokens from state.json, retaining the CONTEXT CHECK REQUIRED branch in the gate, invoking bump-context-tokens --cost [total_tokens] after both builder (Step 1) and reviewer (Step 2) spawns, describing the primary gate as maintained by bump-context-tokens, and still using a Task-only secondary fallback matcher. Until the template is updated, pairmode_sync.py sync-build --apply will silently regress any correctly-fixed sibling project's CLAUDE.build.md back to the inflated-context-count design and reintroduce false budget blocks. Phase 71 propagates BUILD-029's gate redesign into the template so that bootstrap and sync produce — and preserve — the live /context + set-context-tokens design across every pairmode-bootstrapped project.

## Stories

| ID | Title | Status |
|----|-------|--------|
| BUILD-030 | Propagate BUILD-029 Context gate fix into `CLAUDE.build.md.j2` template | planned |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-71 Cold-eyes checklist

— developer fills in after phase completion —
