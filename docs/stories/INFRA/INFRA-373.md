---
id: INFRA-373
rail: INFRA
title: Log SubagentStop-relay worker-contract rejections instead of silently dropping them (CER-131)
status: draft
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/subagent_transcript.py
touches:
  - tests/pairmode/test_subagent_transcript.py
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

- INFRA-298 complete (it added the SubagentStop relay path in `reconcile_one`).
- INFRA-299 complete (it introduced the `rejected` out-list and the
  `skip:non-enum-outcome` recording-decision entry this story reuses; that logging shape is the
  reference implementation, not something to redesign here).

## Ensures

1. In `subagent_transcript.py`, the `parse_worker_outcome` call site at ≈:1905 and the
   `read_completed_spawn` call site at ≈:1932 inside `reconcile_one` pass through the same
   `rejected` out-list and `log_recording_event` call the two pre-existing consumers
   (`reconcile_pending_attempts`, `record_attempt_from_transcript`) use. No third logging
   mechanism, message format, or decision string is introduced.
2. A transcript whose BUILD outcome JSON carries a non-enum `outcome` value, reconciled via the
   relay path (`reconcile_one`), writes exactly one `skip:non-enum-outcome` line to
   `effort_recording.log`. **Forbidden proxy:** asserting only that the parser returned a
   rejection, or that the attempt row stayed pending — those already held before this story; the
   assertion must be on the log line reaching `effort_recording.log` from the relay path.
3. The refusal behaviour itself is unchanged: the rejected outcome is still not recorded and the
   attempt row is still left pending. This story adds visibility only.
4. A valid, enum-conforming outcome reconciled via the same relay path writes no
   `skip:non-enum-outcome` line — the logging fires on rejection, not on every relay pass.
5. A regression test in `tests/pairmode/test_subagent_transcript.py` covers Ensures 2 and 4.
6. Full `tests/pairmode/` suite green.

## Instructions

1. Read the two existing consumers of the INFRA-299 logging in `subagent_transcript.py`
   (`reconcile_pending_attempts`, `record_attempt_from_transcript`) and copy their shape: how the
   `rejected` out-list is constructed, threaded into `parse_worker_outcome`/`read_completed_spawn`,
   and drained into `log_recording_event` with the `skip:non-enum-outcome` decision.
2. Apply that same shape to `reconcile_one`'s two sites (≈:1905 `parse_worker_outcome`, ≈:1932
   `read_completed_spawn`). If `reconcile_one` has no existing out-list, add one local to the
   function and drain it before returning, rather than hoisting state to module or caller scope.
3. Leave the remaining `parse_worker_outcome`/`read_completed_spawn` sites (≈:1472, :1548, :2295,
   :2488, :2162) alone — see Out of scope.
4. Add the regression test to `tests/pairmode/test_subagent_transcript.py`. Assert on the contents
   of `effort_recording.log` (a `skip:non-enum-outcome` line present in the rejection case, absent
   in the valid-outcome case), not on captured stdout or on a return value.

Ideology note: the fix reuses the existing `log_recording_event` writer rather than adding a
second logging path, preserving the "never silently pass contradictions" constraint (a refusal
that emits nothing is exactly the invisibility that constraint protects against) and keeping one
writer for recording decisions.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_subagent_transcript.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: both green, including the new relay-path rejection-logging test.

## Out of scope

- Auditing or wiring the other `parse_worker_outcome`/`read_completed_spawn` call sites (:1472,
  :1548, :2295, :2488, :2162). CER-131 names the relay sites in `reconcile_one` as the gap; any
  further unlogged rejection site found while working here is a new CER, not an inline fix.
- Changing the refusal rule itself, the enum of accepted outcomes, or the `skip:non-enum-outcome`
  decision string. This story changes visibility, not policy.
- Any surfacing of these log lines in the observability API or sidebar.
