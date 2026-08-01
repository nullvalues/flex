---
era: "001"
---

# flex — Phase backlog-legacy: pre-manifest backlog stubs

<!-- This is a legacy anchor doc, not a numbered production phase. It exists
     solely so check-index's cross-link and orphan-story checks have a real
     target for a handful of pre-manifest-convention story stubs whose
     original `phase:` frontmatter named a bucket ("backlog" or empty) rather
     than a real phase file — INFRA-310, 2026-08-01. -->

## Goal

Before the phase-doc manifest convention existed, a handful of one-off CER
fixes were tracked as bare story files with `phase: "backlog"` or an empty
`phase:` value, never filed against a real phase doc. All are `status:
complete` — real, shipped fixes — the gap is purely archival. This doc is
their honest anchor: it does not represent a unit of planned work, and it is
never a build target.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-001 | Add `--yes` flag to bootstrap for non-interactive callers | complete |
| INFRA-003 | Replace `startswith` with `relative_to` in `lesson_review.py` | complete |
| INFRA-022 | Replace `str.startswith` path containment in `lesson_review.py` with `Path.relative_to` (CER-004) | complete |
| INFRA-023 | Constrain hooks `PIPE_PATH` redirection via `state.json` validation (CER-009) | complete |
| INFRA-024 | Validate `story_new.py --rail` input against rail-name regex (CER-010) | complete |
| INFRA-025 | Add formal containment check to `era_new.py` path construction (CER-011) | complete |

Each story's own file is the record of what was fixed; several (INFRA-001,
INFRA-003) are placeholder-body stubs whose "fill in" sections were never
completed even though the underlying fix shipped under a different,
unrecorded commit — `docs/cer/backlog.md`'s Requires-4 evidence table
(INFRA-310) re-verifies the live code for CER-004/009/010/011 independently
of these story bodies. Nothing here is a live acceptance criterion to build
against.

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |
