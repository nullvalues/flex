---
era: "003"
---

# project — Phase 110: Effort-recording data-flow remediation (CER-101..104)

← [Phase 109: Single-orchestrator parallel build concurrency](phase-109.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
**Parent phase:** Phase 106 (fleet migration campaign). The RELEASE-063 canary
completed the meander migration but failed E6 (effort recording), gating
RELEASE-064..070. This phase remediates the recording cluster; phase 106 resumes
after cp-110.

## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Restore truthful effort recording end-to-end: fix the reconciliation pipeline (symlink containment + terminator predicate), dedupe double-inserted rows via agent_id, resolve attribution to the spawn's target project, revive the FAIL-escalation ladder, and add data-flow consistency checks to the cold-eyes review procedures. Builds before the phase-106 campaign resumes (RELEASE-064..070 gated on this phase per RELEASE-063 canary).

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-287 | Reconciliation pipeline: symlink-aware containment and current-format terminator predicate (CER-101) | complete |
| INFRA-288 | Attempt-row dedupe via agent_id idempotency key and merged-view duplicate-hook detection (CER-104) | complete |
| INFRA-289 | Attribution and escalation: target-project recording, strict phase-key parsing, async FAIL-bump (CER-102, CER-103) | complete |
| INFRA-290 | Data-flow checks in cold-eyes procedures and recording-state hygiene (dead keys, stale counters, permissions GC) | complete |


## Audit dossier (2026-07-28 fable data-flow audit — spec-writer source material)

Root causes, verified live against code and both effort.db files. Story specs
must be written against these exact break sites.

### CER-101 — rows never reconcile (INFRA-287)
Two independent fatal breaks in the reconciliation pipeline:
- **Containment rejects every real output file.** Claude Code writes
  `tasks/<hash>.output` as a **symlink** to
  `~/.claude/projects/<slug>/<session>/subagents/agent-<id>.jsonl`.
  `subagent_transcript.py` `_contained_spawn_output` (lines ~585-639) calls
  `Path.resolve()` (~line 621) which follows the symlink; the resolved path lands
  outside the `/tmp` root (~line 631) with no `tasks` component (~line 633) →
  returns None → `read_completed_spawn` (~line 807) returns None →
  `reconcile_pending_attempts` (~lines 1228-1230) skips the row. Every row, every sweep.
- **Completion detection matches an obsolete format.** `read_completed_spawn` /
  `classify_pending_reason` require last JSONL entry `type=assistant` with
  `message.stop_reason == "end_turn"` (~lines 785-791). Completed spawn files
  contain only `stop_reason: None` and `"tool_use"` — no `end_turn` exists anymore.
  Honest terminator: last-entry-assistant + file mtime quiescence (half-built in
  the quiescent branch already).
- **Predicate split:** `classify_pending_reason` (~lines 767-768) opens the raw path
  directly and never calls `_contained_spawn_output`, while the sweep does — hence
  cp-109's "14 reconcilable, 0 reconciled". Unify: one shared containment+terminator
  predicate; report `uncontained` as an explicit pending reason.

### CER-104 — double-inserted rows (INFRA-288)
One insert per hook invocation, but **two hook invocations per spawn** in migrated
consumer projects: the project's `.claude/settings.json` PostToolUse entry
(`/mnt/work/flex-harness/hooks/post_tool_use.py`) AND the user-installed flex
plugin's own `hooks.json` (`PostToolUse: Task|Agent|SendMessage →
${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.py`). Verified in meander's
`effort_recording.log`: same `tool_use_id`, `decision=recorded` twice, 15-30ms
apart. flex sessions single-insert only because flex's settings.json lacks a
Task|Agent PostToolUse entry. INFRA-269's dedupe, `audit-hooks`, and
`fleet_discovery._check_duplicate_hooks` (~lines 284-303) read only
`.claude/settings.json` — structurally blind to plugin hooks.json and
settings.local.json, which is why discovery reported 0 duplicates while every row
doubled. Fix both ends: (a) `attempts.agent_id` (persisted by `set_spawn_ref`,
currently read by nothing) becomes the idempotency key — second insert for a live
`(agent_id, agent_role)` pending row updates instead of inserting; (b) duplicate-hook
detection/dedupe operates on the merged hook view (settings + settings.local +
enabled plugin hooks.json); fleet rule: plugin-installed projects get no
settings-level Task|Agent PostToolUse entry.

### CER-102 + CER-103 — dead escalation, session-bound attribution (INFRA-289)
- `hooks/post_tool_use.py` ~line 65: `project_dir = Path(data.get("cwd") or ".")` —
  session cwd, so spawns targeting another project (worktree path in prompt,
  `--project-dir`) record into the session project's db (canary: LEGAL-001 rows in
  flex's db, zero in meander's). Resolve the recording target from the spawn itself
  (worktree cwd / explicit target), fall back to session cwd — same precedence
  shape as `scope_guard.resolve_call_story`.
- `_derive_phase_key` (~lines 495-518) bare `Phase\s+(\w+)` fallback captured
  `phase:key` (flex row 416) and `phase:checkpoint` (meander rows 233-236). Parse
  strictly or take an explicit field.
- FAIL-bump: insert-time bump (`record_attempt_from_transcript` ~lines 1439-1443)
  requires outcome==FAIL at PostToolUse time — but async spawns' tool_response is
  the launch stub, so outcome is always None; reconcile-time bump (~lines 1250-1257)
  is correct but unreachable behind CER-101. Once INFRA-287 lands, verify the
  reconcile-time bump actually revives the ladder (`next-action` attempt/model
  escalation) end-to-end; add the missing async-path test.
- Collateral (fix if cheap, else note): `attempts.model` NULL on reviewer rows —
  orchestrator omits `model=` on reviewer spawns and async usage extraction fails
  pre-reconcile.

### INFRA-290 — methodology + hygiene
- Add the four data-flow checks (written-never-read, required-never-written,
  duplicate state, half-implementations) as standing items in the reviewer and
  security-auditor procedure skills and the CP-NN cold-eyes checklist template.
- Hygiene (small, mechanical): delete dead `context_story_tokens` state key
  (to-030 normalizer strips it); to-030 deletes stale legacy-shape
  `attempt_counter.json`; merged/discarded stories' `docs/phases/permissions/*.json`
  artifacts deleted on merge/discard plus a GC pass for the ~120 (flex) / ~150
  (meander) already stranded.
- Consolidation direction (document in architecture.md): keyed `current_stories`
  is truth; retire flat `current_story` from readers (`_derive_story_id` ~line 480
  last), then writers.

### Deferred to CER backlog (filed at scaffold time, not in this phase)
CER-105 (`attempts.phase` NULL-on-story-rows split semantics), CER-106
(`context_budget_acknowledged_at` holds a token count, not a timestamp), CER-107
(sidebar-extractor rows pollute role medians).

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-110 Cold-eyes checklist

— developer fills in after phase completion —
