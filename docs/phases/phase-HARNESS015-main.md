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

## Stories

| ID | Title | Status |
|----|-------|--------|
| RESOLVER-017 | Reset checkpoint_step on checkpoint-tag completion (CER-066) | planned |
| INFRA-202 | Adopt state_utils atomic write in remaining state.json writers (CER-050) | planned |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| _(none)_ | — | No new persistent schema objects introduced. |

---

### CP-HARNESS015-main Cold-eyes checklist

— developer fills in after phase completion —
