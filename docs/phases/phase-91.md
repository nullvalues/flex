---
era: "003"
---

# flex — Phase 91: Harden sync-agents body-merge against silent duplication/corruption

← [Phase 90: Fix stale pre-INFRA-191 assertion in CLAUDE.build.md test](phase-90.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Phase 91 hardens the sync-agents body-merge path in skills/pairmode/scripts/pairmode_sync.py so that a routine sync-all --apply can never again silently corrupt an agent-definition file. On 2026-07-16, commit 85a6f52 ran sync-all --apply against flex itself and appended duplicate, differently-numbered, out-of-order copies of canonical checklist content past the logical end of both .claude/agents/reviewer.md and .claude/agents/security-auditor.md (hand-repaired without a spec in 622309c), because _merge_body_sections dedups only by exact ##-heading string match and those files express their checklist items as bold-inline pseudo-headers (e.g. **1. HOOK PERFORMANCE**) rather than true ## headings. The same run also merged a nonsensical empty checklist line ("Does any data access code fail to enforce: ?") because _build_template_context pre-populates every known template variable with a ""/[] fallback (e.g. domain_isolation_rule for flex, which declares none), so the whole-render StrictUndefined guard never fires and an empty-string render slips silently into merged content. This phase makes _merge_body_sections recognize when a canonical section is already present under non-## formatting/numbering (never appending a duplicate), and makes an empty/degenerate template-variable render for a required section fail loudly (stderr error, non-zero exit, no write) rather than merging blank content — closing a live, repeatable correctness bug in the tool this project depends on to propagate its own builder/reviewer methodology.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-202 | Harden `_merge_body_sections` to recognize canonical sections already present under non-`##` heading styles and never duplicate-append | complete |
| INFRA-203 | Make empty/missing-variable template renders in the `sync-agents` body-merge path fail loudly instead of merging empty content | planned |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-91 Cold-eyes checklist

— developer fills in after phase completion —
