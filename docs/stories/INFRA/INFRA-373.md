---
id: INFRA-373
rail: INFRA
title: Log SubagentStop-relay worker-contract rejections instead of silently dropping them (CER-131)
status: draft
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-131 (MEDIUM): worker-contract rejections arriving via the INFRA-298 SubagentStop relay are
refused correctly but logged nowhere. `parse_worker_outcome` is called from five sites in
`subagent_transcript.py` (:1472, :1548, :1905, :2295, :2488) and `read_completed_spawn` from two
(:1932, :2162), but INFRA-299's rejected-outcome logging (the `rejected` out-list plus
`skip:non-enum-outcome` recording-decision entry in `effort_recording.log`) was wired into only the
two sites its spec enumerated (`reconcile_pending_attempts`, `record_attempt_from_transcript`) —
the `:1905`/`:1932` relay sites in `reconcile_one` were added later by INFRA-298, after INFRA-299
was specced. Correctness is uniform (the gate lives in the parser, so a non-enum outcome leaves the
row pending on every path), but a rejection on the relay path — now the primary reconciliation
path post-INFRA-298 — emits no log entry, recreating the invisibility CER-091(1) was originally
about. Fix: thread the `rejected` out-list and `log_recording_event` call through
`reconcile_one`'s parse/read sites, mirroring the two existing consumers, with a regression test
that a refused JSON BUILD outcome via the relay writes a `skip:non-enum-outcome` line. File:
`skills/pairmode/scripts/subagent_transcript.py` (`reconcile_one`).

Picked up now as part of era 004's Phase 119 goal of draining the CER backlog to zero unresolved
operational findings.

## Requires
<!-- Prior stories, system state, or file conditions that must hold before building. -->

## Ensures
<!-- Binary assertions the reviewer checks independently. One per line.
     Each must be verifiable without interpretation: file exists, command output
     contains X, function Y returns Z. -->
<!-- State the correct signal AND the forbidden proxy (INFRA-314): e.g. "the
     write is absent after refusal; forbidden proxy: a warning line while the
     write happens anyway." -->

## Instructions

## Tests
