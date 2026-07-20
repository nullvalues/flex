---
era: "003"
phase_class: production
---

# flex-harness — Phase HARNESS015-main: Checkpoint-sequence reset and state.json atomic-write adoption

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Fix the checkpoint_step phase-scoping bug (CER-066) and finish adopting the shared atomic state.json writer everywhere it's still missing (CER-050).

## Background

Surfaced during the HARNESS014-main checkpoint: `state.json["checkpoint_step"]`
is never cleared between phases, so `flex_build.py next-action` silently
reported `"done"` for HARNESS014-main's checkpoint without dispatching
`checkpoint-security`/`checkpoint-intent`/`checkpoint-docs` — the sequence was
run manually instead. Logged as CER-066 (Do Later).

While auditing that, confirmed CER-050 (shared atomic `state.json` writer,
`state_utils._atomic_write_json`) is only partially adopted: four writers
(`hooks/post_tool_use.py`, `story_context.py`, `bootstrap.py`, and three sites
in `sidebar.py`) still use raw `write_text()`. Also confirmed CER-051 is
already fully resolved in code (`context_budget.py` `_derive_transcript_path`
already rejects traversal sequences, INFRA-192) — the backlog entry text was
stale; it should be marked RESOLVED as part of this phase's docs pass, no code
story needed.

RESOLVER-017 was already shipped on `main` (commit `f7d8469`, "story-RESOLVER-017")
and pulled into `fold-prep` via the RELEASE-014 reconciliation merge — its status
here was stale ("planned"); corrected to "complete" during the 2026-07-20 build
pass, no code change needed.

Surfaced 2026-07-18 during an INFRA-202 build attempt: `permission_scope.py`'s
`write-permissions` path produced a malformed allow-rule for a `touches` entry
that carried an inline `# reason: ...` comment, because
`schema_validator._parse_frontmatter()`'s block-sequence parsing doesn't strip
inline YAML comments from list items. Filed as INFRA-211.

## Stories

| ID | Title | Status |
|----|-------|--------|
| RESOLVER-017 | Reset checkpoint_step on checkpoint-tag completion (CER-066) | complete |
| INFRA-202 | Adopt state_utils atomic write in remaining state.json writers (CER-050) | complete |
| INFRA-211 | Strip inline YAML comments from frontmatter list items in `_parse_frontmatter` | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| _(none)_ | — | No new persistent schema objects introduced. |

---

### CP-HARNESS015-main Cold-eyes checklist

— developer fills in after phase completion —
