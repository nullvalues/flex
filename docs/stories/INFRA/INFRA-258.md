---
id: INFRA-258
rail: INFRA
title: Async-spawn effort recording — derive tokens and outcome at completion time; fix checkpoint-worker story misattribution
status: complete
phase: "101"
story_class: code
auth_gated: false
schema_introduces: true
primary_files:
  - skills/pairmode/scripts/subagent_transcript.py
  - skills/pairmode/scripts/effort_db.py
  - hooks/session_start.py
touches:
  - tests/pairmode/test_subagent_transcript.py
  - tests/pairmode/test_effort_db.py
  - tests/pairmode/test_session_start_hook.py
  - docs/architecture.md
---

## Context

INFRA-236 restored effort recording by calling
`subagent_transcript.record_attempt_from_transcript()` from
`hooks/post_tool_use.py`'s Task/Agent branch. That design assumed a
*synchronous* spawn: at PostToolUse time the subagent had finished, its own
turns were interleaved into the orchestrator's session JSONL as
`isSidechain: true` entries, and its final BUILD-RESULT/REVIEW-RESULT JSON was
the tool_response. Neither assumption holds in current Claude Code sessions.

Agent spawns are now **asynchronous**. Verified live in this session
(`~/.claude/projects/-mnt-work-flex/e1110027-….jsonl`):

- The PostToolUse `tool_response` is launch metadata only —
  `{"isAsync": true, "status": "async_launched", "agentId": "a8b42498d3e06fcd1",
  "outputFile": "/tmp/claude-1000/-mnt-work-flex/<session>/tasks/<agentId>.output",
  "canReadOutputFile": true}`, and its text form begins
  `"Async agent launched successfully."`. No outcome, no tokens.
- The orchestrator's own transcript contains **zero** `isSidechain` entries for
  the whole session, so `extract_subagent_usage()` finds nothing and returns
  `_EMPTY_USAGE`. The subagent's turns are written to its own `output_file`
  JSONL instead.
- Completion arrives in a *later* turn as a `<task-notification>` user message
  carrying `<task-id>`, `<tool-use-id>`, `<output-file>`, `<status>completed</status>`
  and a `<result>` block — long after the PostToolUse hook for that spawn fired.

The observed damage in `.companion/effort.db`: every build-loop row recorded
this session — ids 335–338 (`INFRA-256`/`INFRA-257` builder + reviewer) and
339–340 (checkpoint workers) — has `tokens_total = NULL` and `outcome = NULL`.
Two knock-on failures follow:

1. **Rollups report nothing.** `flex_build._query_effort_by_story_ids`
   (INFRA-256) and `_query_effort_by_role` both filter
   `tokens_total IS NOT NULL AND tokens_total > 0`, so the cp-101 checkpoint
   report says "no attempts recorded" for a phase that was genuinely built.
2. **The escalation ladder is dead.** INFRA-237's FAIL-triggered
   `bump_attempt_count` is gated on `outcome == "FAIL"`, which can never be true
   at PostToolUse time in an async session. `next_action.infer_position`'s
   retry → loop-breaker → human-pause rows (5/6/7) therefore never escalate:
   a failing story loops as attempt 1 forever.

A second, independent defect surfaced in the same rows. Ids 339 and 340 are the
**phase-level** cp-101 gate workers (`security-auditor`, `intent-reviewer`,
spawned by the resolver's `checkpoint-security` / `checkpoint-intent` actions
with `scalar=""` — they belong to no story) yet both are stamped
`story_id = INFRA-256`. Root cause is `_derive_story_id`: it applies
`_STORY_ID_RE` (`\b([A-Z][A-Z0-9]*-\d{2,})\b`) to the spawn prompt and takes the
*first* match. The checkpoint prompts enumerate the phase's stories
("…docs/phases/phase-101.md — stories INFRA-256 phase-scoped checkpoint cost
rollup, INFRA-257 …"), so the first story named in the phase absorbs the entire
phase's checkpoint cost. That silently inflates one story's recorded effort and
makes INFRA-256's per-story rollup untrue.

A third defect found while reading the transcript format, fixed here because it
governs the same numbers: a subagent's JSONL contains **multiple entries per
assistant message** (streaming snapshots sharing one `message.id`, with growing
`output_tokens`). Naively summing every `usage` block — which
`extract_subagent_usage` does today — double-counts. Verified: message
`msg_011CdMLvCkdcMj13pJQryLmP` appears three times with `output_tokens` 5, 5,
263; only the last is the true total.

This story is the fix-before-tag for cp-101: recording is deferred to
completion, attribution is made phase-aware, and token summation is deduped.

**Mechanism chosen (of the two directions weighed).** Direction (a),
*deferred reconciliation keyed on the spawn's own `output_file`*, is the primary
mechanism. Direction (b), recording at task-notification time, was rejected:
the notification is a queued user message, not a tool event, so no registered
hook fires with it in hand — capturing it would require a new hook registration
and a text-scraping correlation step for data the `output_file` holds
structurally. Reconciling from the `output_file` also works identically inside
the PostToolUse sweep and inside the already-registered SessionStart hook, so
one function serves both trigger points and no new hook is registered.

**Session-end policy (decided).** Because the tail rows of a session (the last
reviewer, or the checkpoint gate workers) would otherwise never be swept, and
because `output_file` lives under `/tmp` and can be evicted between sessions,
reconciliation is *also* invoked once from the existing `SessionStart` hook —
the earliest opportunity in the next session. Rows whose `output_file` is gone
by then keep their `NULL` tokens permanently; that residual loss is accepted and
documented rather than mirrored into a second durable store.

## Requires

- INFRA-236 and INFRA-237 are complete: `hooks/post_tool_use.py`'s Task/Agent
  branch delegates to `subagent_transcript.record_attempt_from_transcript`,
  which is the sole per-attempt writer of `.companion/effort.db` rows for the
  pairmode build loop and the sole caller of `flex_build.bump_attempt_count`.
- INFRA-257 is complete: `effort_db.next_attempt_number` exists and
  `record_attempt_from_transcript` passes an explicit `attempt_number=`.
- `hooks/session_start.py` and its `SessionStart` registration in
  `hooks/hooks.json` exist and are unchanged in shape (a registered hook with a
  5 s timeout that already performs one delegated call plus one state write).
- `.companion/effort.db` exists with the `attempts` schema and the
  `_MIGRATIONS` guarded-`ALTER TABLE` convention in
  `skills/pairmode/scripts/effort_db.py`.
- `effort_recorder.record_effort` retains its current signature and returns the
  inserted row id.

## Ensures

1. `effort_db.py` gains two nullable `TEXT` columns on `attempts` —
   `agent_id` and `output_file` — added both to `_SCHEMA_TABLE` (so fresh
   databases get them) and to `_MIGRATIONS` as guarded
   `ALTER TABLE attempts ADD COLUMN …` statements (so existing databases are
   migrated in place). `init_db` on a pre-existing database that already has the
   columns is a no-op and raises nothing.
2. `_INSERT_COLUMNS` is **not** extended and `insert_attempt`'s required-field
   set is unchanged, so `effort_recorder.record_effort` and every cross-skill
   caller (`record_attempt.py`, `mine_sessions.py`, `reconcile.py`,
   `sidebar.py`) are behaviourally untouched by this story.
3. `effort_db.set_spawn_ref(path, row_id, agent_id, output_file)` sets those two
   columns on one row by id, binding every value as a SQL parameter. It returns
   `True` on a successful update and `False` on any failure, and never raises —
   missing db, missing table, missing row, or unreadable file all return `False`.
4. `effort_db.pending_reconcilable(path, limit)` returns a list of dicts for rows
   matching `tokens_total IS NULL AND output_file IS NOT NULL`, ordered by `id`
   descending and capped by `limit` (caller-supplied; the module never queries
   unbounded). Each dict carries at least `id`, `story_id`, `agent_role`,
   `output_file`, `model`. It returns `[]` and never raises on any failure.
5. `effort_db.reconcile_attempt(path, row_id, **fields)` updates only
   `tokens_total`, `tokens_in`, `tokens_out`, `cache_read_tokens`,
   `cache_write_tokens`, `duration_ms`, `outcome`, `notes`, and `model` on one
   row by id, with all values bound as SQL parameters. It **never** writes
   `story_id`, `agent_role`, `attempt_number`, `phase`, `rail`, or `ts` — a test
   asserts `attempt_number` and `ts` are byte-identical before and after a
   reconciliation. It returns `True`/`False` and never raises. It is a
   conditional update (`WHERE id = ? AND tokens_total IS NULL`) so a second call
   for an already-reconciled row is a no-op returning `False`.
6. `subagent_transcript.read_completed_spawn(output_file)` reads a spawned
   agent's own JSONL output file and returns either `None` (not complete /
   unreadable / no usage) or a dict with `tokens_in`, `tokens_out`,
   `tokens_total`, `cache_read_tokens`, `cache_write_tokens`, `duration_ms`,
   `model`, `outcome`, `fail_cause`, `final_text`. It never raises.
7. Completion detection in `read_completed_spawn` is: the **last parseable**
   JSONL entry is `type == "assistant"` whose `message.stop_reason == "end_turn"`.
   An entry with `stop_reason == "tool_use"`, a truncated/unparseable trailing
   line with no earlier `end_turn` terminator, an empty file, or a nonexistent
   path all yield `None` — an in-flight agent is never reconciled.
8. Token summation dedupes by `message.id`, **last entry wins** per id, before
   summing. A test builds a fixture in the exact observed streaming shape (three
   entries sharing one `message.id` with `output_tokens` 5, 5, 263) and asserts
   the summed `tokens_out` is `263`, not `273`.
9. `extract_subagent_usage` (the existing synchronous/sidechain path) uses the
   **same** deduping summation helper, so the two paths report the same metric
   under the same rules. A test asserts the sidechain path also dedupes by
   `message.id`.
10. `tokens_total` is `tokens_in + tokens_out` (cache tokens excluded), matching
    the existing `extract_subagent_usage` contract, so pre- and
    post-INFRA-258 rows remain directly comparable.
11. `outcome`/`fail_cause` are parsed from the output file's final assistant
    text by the **existing, unmodified** `parse_worker_outcome`, so the
    BUILD-RESULT / REVIEW-RESULT grammar and the `FAIL-CAUSE:` fallback stay
    single-sourced.
12. `duration_ms` is derived best-effort as the millisecond delta between the
    first and last parseable entry's `timestamp` in the output file, and is
    `None` when either timestamp is absent or unparseable.
13. `record_attempt_from_transcript` persists the spawn reference: after
    `record_effort` returns a row id, it extracts `agent_id` and `output_file`
    from `tool_response` and calls `effort_db.set_spawn_ref`. Extraction handles
    **both** shapes — the structured dict (`outputFile`/`output_file`,
    `agentId`/`agent_id` keys, at the top level or nested under
    `toolUseResult`) and the flattened text form (`output_file: <path>` and
    `agentId: <id>` lines). A missing/unrecognised shape leaves both columns
    `NULL` and is not an error.
14. `subagent_transcript.reconcile_pending_attempts(project_dir, limit=…)` is a
    new public entry point that: reads state, returns `0` immediately unless
    `effort_tracking` is true, fetches at most `limit` pending rows via
    `pending_reconcilable`, calls `read_completed_spawn` on each, and writes the
    completed ones back via `reconcile_attempt`. It returns the count of rows
    reconciled and never raises.
15. Work per invocation is bounded and the bounds are module constants, not
    magic numbers: at most `RECONCILE_MAX_ROWS = 5` rows per call, and each
    output file is streamed line-by-line with a hard cap of
    `RECONCILE_MAX_LINES = 20000` lines (beyond the cap the file is treated as
    not-complete and skipped, leaving the row pending). The whole file is never
    loaded into memory at once — a test asserts `read_completed_spawn` does not
    call `Path.read_text` on the output file.
16. `record_attempt_from_transcript` calls `reconcile_pending_attempts`
    **before** recording the new spawn's row, inside its own `try/except`, so a
    reconciliation failure never prevents the new row from being written. The
    sweep runs after the `effort_tracking` early return.
17. `hooks/post_tool_use.py` is **not modified**. The sweep is internal to
    `record_attempt_from_transcript`, so no new hook registration and no new
    delegated call is added to the Task/Agent branch.
18. `hooks/session_start.py` gains exactly one new best-effort delegated call —
    `subagent_transcript.reconcile_pending_attempts(project_dir=…)` — wrapped in
    its own `try/except: pass`, placed so that it can never affect the existing
    `session_reset.decide_reset()` path or the hook's exit status. A test
    asserts the hook still performs its existing reset behaviour when the
    reconciliation call raises.
19. **Late counter bump.** When reconciliation resolves `outcome == "FAIL"` for
    a row whose `story_id` is a real story id (not a `phase:` or
    `unattributed:` synthetic), `flex_build.bump_attempt_count(story_id,
    project_dir)` is called at reconciliation time, in its own `try/except`.
    Because `next_action.infer_position` re-reads
    `.companion/attempt_counter.json` on every call, a bump that lands after an
    earlier next-action read is still honoured by the next read — the ladder
    escalates one loop iteration later than in the synchronous era, which is
    correct, not lossy. `docs/architecture.md` states this explicitly.
20. The counter is bumped **at most once per row**: because
    `reconcile_attempt`'s `WHERE … AND tokens_total IS NULL` guard makes
    reconciliation single-shot, a repeated `<task-notification>` for a resumed
    agent cannot double-bump. A test reconciles the same FAIL row twice and
    asserts the counter advanced by exactly 1.
21. **Checkpoint-worker attribution.** A new
    `CHECKPOINT_ROLES = frozenset({"security-auditor", "intent-reviewer"})`
    constant is added, and attribution for those roles never returns an
    individual story id. For a spawn whose `subagent_type` is in
    `CHECKPOINT_ROLES`, the recorded `story_id` is `phase:<phase_key>` where
    `phase_key` is derived from the spawn prompt, or `unattributed:<role>` when
    no phase key can be derived — `_STORY_ID_RE` and the `state.json`
    `current_story` fallback are both skipped for these roles.
22. Phase-key derivation tries, in order: the `docs/phases/phase-<key>.md`
    path pattern in the prompt, then a bare `Phase <key>` mention; `<key>`
    matches `[A-Za-z0-9][A-Za-z0-9._-]*` with trailing punctuation stripped, so
    both `101` and `HARNESS001-main` resolve. A test asserts the exact observed
    cp-101 prompt (`"Checkpoint security audit for Phase 101 … docs/phases/phase-101.md
    — stories INFRA-256 …, INFRA-257 …"`) yields `phase:101` and **not**
    `INFRA-256`.
23. For a row attributed to `phase:<key>`, the `phase` column is set to `<key>`
    and `rail` is `None`, so `effort_db.query_by_phase` finds the phase's
    checkpoint cost while INFRA-256's per-story rollup (which selects
    `story_id IN (<phase's story ids>)`) correctly excludes it. A test asserts a
    checkpoint-worker row does not appear in
    `flex_build._query_effort_by_story_ids` output for the phase's stories.
24. Attribution for the non-checkpoint roles (`builder`, `reviewer`,
    `loop-breaker`) is behaviourally unchanged: prompt story-id regex, then
    `state.json["current_story"]`, then `unattributed:<role>`. A test asserts a
    builder spawn prompt naming two story ids still resolves to the first one.
25. INFRA-257's `next_attempt_number` semantics are intact: the ordinal is still
    derived at record time from the count of existing rows for the effective
    `(story_id, agent_role)` pair, and reconciliation never touches it. Because
    checkpoint workers now number against `phase:<key>` rather than a story id,
    their sequences are per-phase — a test asserts two `security-auditor`
    spawns for `phase:101` yield `attempt_number` `1` then `2`.
26. **DP7 is preserved.** Nothing in the reconciliation path reads or writes
    `context_current_tokens`, `context_current_tokens_recorded_at`, or any other
    context-budget key in `state.json`; the only `state.json` access is the
    existing read of `effort_tracking`. A test asserts `state.json` is unchanged
    (byte-identical) across a reconciliation run.
27. **Documented limitation.** With `effort_tracking` disabled there is no
    effort.db row to carry the `output_file`, so an async spawn's outcome is
    unavailable and the FAIL bump cannot fire — INFRA-237's
    "bump independent of `effort_tracking`" property does not survive async
    spawning. `docs/architecture.md` states this plainly, including the
    consequence (projects that disable effort tracking lose the automatic
    retry/loop-breaker escalation) and the reason it is accepted here (adding a
    second durable pending-spawn store to work around it is a larger change than
    this fix-before-tag warrants).
28. **Regression test — async-shaped tool_response.** A test drives
    `record_attempt_from_transcript` with a fixture `tool_response` in the exact
    observed async launch shape (launch metadata only: `isAsync`,
    `status: "async_launched"`, `agentId`, `outputFile`) and asserts (a) a row is
    written with `tokens_total IS NULL` and `outcome IS NULL`, and (b) the row's
    `agent_id`/`output_file` columns are populated. A second phase of the same
    test then writes a completed output file at that path, calls
    `reconcile_pending_attempts`, and asserts the row now carries non-null
    `tokens_total`, `tokens_in`, `tokens_out`, `model`, and `outcome`.
29. **Regression test — reconciled FAIL bumps the counter.** A test reconciles a
    row whose output file ends in a `REVIEW-RESULT` with `verdict: "FAIL"` and
    asserts `flex_build.read_attempt_count` for that story increased by 1 and
    that the row's `notes` carries the parsed `fail_cause`.
30. **Regression test — in-flight spawn is not reconciled.** A test points a
    pending row at an output file whose last entry has
    `stop_reason: "tool_use"` and asserts the row is left untouched
    (`tokens_total` still `NULL`) and `reconcile_pending_attempts` returns `0`.
31. `docs/architecture.md` § Effort tracking documents: async spawning as the
    reason recording is two-phase; the spawn-ref columns and what they hold; the
    reconciliation trigger points (next Task/Agent PostToolUse, plus SessionStart)
    and their bounds; the completion-detection rule; the message-id dedupe and
    that it changes token totals relative to pre-INFRA-258 rows; the
    `phase:<phase_key>` synthetic id and why checkpoint workers must never carry
    a story id; the late-bump rule from Ensures 19; and the accepted losses from
    Ensures 27 and 33. The `attempt_counter.json` description (~line 1603) and
    the state-ownership table row (~line 1384) are updated to name reconciliation
    as a second bump site.
32. Every new function in `subagent_transcript.py` and `effort_db.py` is
    best-effort and non-raising, consistent with both modules' existing
    contracts; a test asserts `reconcile_pending_attempts` returns `0` rather
    than raising when the effort db path is a corrupt/non-sqlite file.
33. **No backfill.** Rows 335–340 and any other pre-existing `NULL`-token rows
    are not repaired: no migration backfill, no repair subcommand, no manual
    `UPDATE`. They lack `output_file` values and are therefore invisible to
    `pending_reconcilable` by construction. `docs/architecture.md` records that
    the phase-101 rollup gap is permanent for those rows.
34. Full `tests/pairmode/` suite passes, run without `-x`, with only the known
    pre-existing `test_observability_ui.py::test_ui_build_emits_dist_index_html`
    failure permitted (and only if shown to reproduce on clean `HEAD`).

## Instructions

1. **Read before editing.** `skills/pairmode/scripts/subagent_transcript.py` in
   full (in particular `_derive_story_id` ~line 300, `extract_subagent_usage`
   ~line 200, `parse_worker_outcome` ~line 151, and
   `record_attempt_from_transcript` ~line 327);
   `skills/pairmode/scripts/effort_db.py`'s `_SCHEMA_TABLE` / `_MIGRATIONS` /
   `_INSERT_COLUMNS` block (~lines 40–105) and `query_by_story` /
   `next_attempt_number`; `hooks/session_start.py`; and
   `hooks/post_tool_use.py`'s Task/Agent branch (which you must **not** modify).

2. **Schema (effort_db.py).** Append `agent_id TEXT` and `output_file TEXT` to
   `_SCHEMA_TABLE`, and add the two matching guarded `ALTER TABLE attempts ADD
   COLUMN …` entries to `_MIGRATIONS` — follow the existing pattern exactly
   (SQLite has no `IF NOT EXISTS` for `ALTER TABLE`; the existing loop swallows
   the duplicate-column error). Do **not** touch `_INSERT_COLUMNS` or
   `_REQUIRED_FIELDS`: the two new columns are written by a follow-up `UPDATE`,
   not by `insert_attempt`, which is what keeps `effort_recorder.record_effort`
   and the cross-skill callers untouched.

3. **effort_db helpers.** Add `set_spawn_ref`, `pending_reconcilable`, and
   `reconcile_attempt` next to `query_by_story`. All three: resolve through the
   existing `_depth_guard`, use the same `sqlite3.connect` /
   try-finally-`conn.close()` idiom, bind every value as a parameter, wrap the
   whole body in `try/except Exception` returning the documented failure value,
   and never introduce a context-manager or connection-pool variant.
   `reconcile_attempt` builds its `SET` clause from a fixed allow-list of the
   nine reconcilable column names — never from caller-supplied keys — and always
   appends `AND tokens_total IS NULL` to its `WHERE` so it is single-shot.
   Extend the module docstring's `Public API` list with all three.

4. **Dedupe helper.** Extract the per-entry usage accumulation currently inlined
   in `extract_subagent_usage` into a module-level helper in
   `subagent_transcript.py` that takes an iterable of parsed JSONL entries and
   returns the `_EMPTY_USAGE`-shaped dict. Inside it, key each assistant entry's
   usage by `message.id` in a dict (last write wins), then sum the values. Entries
   with no `message.id` are summed individually under a synthetic unique key.
   Point both `extract_subagent_usage` and the new `read_completed_spawn` at it.
   This is the fix for the streaming double-count; note in a comment that the
   observed shape is multiple JSONL lines per `message.id` with monotonically
   growing `output_tokens`.

5. **`read_completed_spawn(output_file)`.** Stream the file with a plain
   `for line in fh:` loop over `open(path, encoding="utf-8", errors="replace")`,
   counting lines and bailing out (return `None`) past `RECONCILE_MAX_LINES`.
   Do not call `read_text()` or `readlines()` — a builder's output file can be
   tens of megabytes and this runs in a hook path. Track: the running usage map
   (step 4), the first and last parseable `timestamp`, the last parseable entry,
   and the last assistant entry's flattened text. After the loop, require the
   last parseable entry to be `type == "assistant"` with
   `message.stop_reason == "end_turn"`; otherwise return `None`. Feed the final
   assistant text to the existing `parse_worker_outcome` — do not write a second
   result parser. Return the assembled dict.

6. **Attribution split.** Replace `_derive_story_id`'s single-path logic with a
   `_derive_attribution(tool_input, state, subagent_type)` returning a
   `(story_id, phase_key, rail)` tuple. Add
   `CHECKPOINT_ROLES = frozenset({"security-auditor", "intent-reviewer"})` next
   to `RECORDABLE_SUBAGENT_ROLES` with a comment recording *why* the split
   exists: `next_action.py` emits `checkpoint-security` / `checkpoint-intent`
   with `scalar=""` (no story), while their prompts enumerate the phase's story
   ids, so a first-match story regex attributes an entire phase's checkpoint cost
   to whichever story is named first (observed: effort.db ids 339–340 stamped
   `INFRA-256`). For a checkpoint role: derive the phase key per Ensures 22 and
   return `(f"phase:{key}", key, None)`, or `(f"unattributed:{subagent_type}",
   None, None)` when no key is found — never consult `_STORY_ID_RE` or
   `state.json["current_story"]`. For every other role, keep today's behaviour
   exactly. Pass the returned `phase` through to `record_effort(phase=…)`, which
   already accepts it and currently receives `None`.

7. **Persist the spawn ref.** In `record_attempt_from_transcript`, after
   `record_effort` returns a row id, extract `(agent_id, output_file)` from
   `tool_response` in a small helper that tries the dict shapes first
   (`outputFile`/`output_file`, `agentId`/`agent_id`, also under a
   `toolUseResult` key) and falls back to regexes over
   `_flatten_tool_response(tool_response)` for `output_file:\s*(\S+)` and
   `agentId:\s*(\S+)`. Call `effort_db.set_spawn_ref` only when at least
   `output_file` was found. Return the row id as before.

8. **The sweep.** Add `reconcile_pending_attempts(*, project_dir, limit=RECONCILE_MAX_ROWS, home=None)`.
   Read state; return `0` unless `effort_tracking`. Resolve the db path via
   `effort_db.resolve_effort_db_path`, call `pending_reconcilable(path, limit)`,
   and for each row call `read_completed_spawn(row["output_file"])`; skip on
   `None`. On a result, call `effort_db.reconcile_attempt(...)` passing tokens,
   duration, `outcome`, `notes=fail_cause`, and `model` (only when the row's
   model is currently `None`). When the update succeeds and the resolved outcome
   is `FAIL` and `row["story_id"]` contains no `:` (i.e. is a real story id, not
   a `phase:`/`unattributed:` synthetic), call
   `flex_build.bump_attempt_count(row["story_id"], project_path)` inside its own
   `try/except`. Count and return the successful reconciliations.

9. **Wire the triggers.** In `record_attempt_from_transcript`, call
   `reconcile_pending_attempts` immediately after the `effort_tracking` early
   return and before the attempt-number derivation, wrapped in
   `try/except Exception: pass`. In `hooks/session_start.py`, add one delegated
   call to `reconcile_pending_attempts` with the hook's project dir, in its own
   `try/except Exception: pass`, positioned so it cannot influence the existing
   `decide_reset()` path or the hook's exit. Import it inside the `try` using the
   module's established flat-`sys.path` import style — the hook prepends
   `skills/pairmode/scripts` to `sys.path`, so a package-qualified import will
   pass tests and break at runtime.

10. **Do not modify** `hooks/post_tool_use.py`, `effort_recorder.py`,
    `record_attempt.py`, `flex_build.py`, or `next_action.py`. If a change to
    `flex_build.py`'s counter functions or the resolver's ladder appears
    necessary, stop and flag it — their semantics are load-bearing and out of
    scope (INFRA-257 Ensures 8 still holds).

11. **Docs.** Update `docs/architecture.md` § Effort tracking (~line 1865
    onward, adjacent to the INFRA-256/257 paragraphs near line 2043) per
    Ensures 31, and add the two cross-references (the `attempt_counter.json`
    description ~line 1603 and the state-ownership table row ~line 1384) naming
    reconciliation as a second, later bump site. Also correct the
    `record_attempt_from_transcript` docstring, which currently describes null
    tokens on an async spawn as "a known limitation" — that is what this story
    removes.

12. **Ideology note (Step 4a, resolved inline).** Two checks applied.
    (a) *"Hooks are thin relays only"* (§ Accepted constraints, no override
    permitted). This story adds work to two hook paths, so the work is bounded by
    construction and the bounds are constants, not comments: at most 5 rows per
    invocation, each output file streamed with a 20 000-line cap and never
    slurped, all queries indexed-or-tiny, everything behind the `effort_tracking`
    early return, everything wrapped to never raise or block. It adds no API
    call, no network, and no new hook registration. Crucially it does not widen
    the hook's *role*: INFRA-236 already established the hook as the recorder of
    attempt rows; this only moves half of that recording to the moment the data
    actually exists. If the implementation would need an unbounded scan, a
    second db, or a new registered hook, stop and flag rather than proceeding.
    (b) *"Rationale-bearing decisions over bare rules"* (§ Core convictions).
    The reason checkpoint workers may never carry a story id, and the reason the
    FAIL bump is now allowed to land late, must land in `docs/architecture.md`
    and not only in this story file — otherwise a later agent finding
    `CHECKPOINT_ROLES` "inconsistent" with `RECORDABLE_SUBAGENT_ROLES` will
    delete it and silently reintroduce the misattribution.

## Tests

Targeted:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_subagent_transcript.py \
  tests/pairmode/test_effort_db.py \
  tests/pairmode/test_session_start_hook.py -q 2>&1 | tail -30
```

Lock-in — the untouched neighbours must stay green:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_post_tool_use.py \
  tests/pairmode/test_post_tool_use_hook.py \
  tests/pairmode/test_flex_build_attempt_counter.py \
  tests/pairmode/test_next_action.py -q 2>&1 | tail -30
```

Full suite, without `-x` so the known pre-existing failure cannot mask a real
one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Acceptance: all targeted and lock-in files green; full suite green except the
known pre-existing `test_observability_ui.py::test_ui_build_emits_dist_index_html`
failure, which must be shown to reproduce on clean `HEAD` if it appears.

`tests/pairmode/test_session_start_hook.py` already exists — extend it with the
two assertions Ensures 18 requires (existing reset behaviour preserved; a
raising reconciliation call is swallowed) rather than creating a new file.

**Spec-preflight note (Step 7).** The scan reports two constant warnings —
`CHECKPOINT_ROLES` and `RECONCILE_MAX_LINES` "referenced in story but no
definition found in source tree". Both are intentional: this story creates them
(`subagent_transcript.py`, Instructions 6 and 5). No other findings; the scan
exits 0.

## Out of scope

- **Backfilling the existing NULL-token rows** (effort.db ids 335–340 and any
  earlier ones). They carry no `output_file`, their `/tmp` transcripts are not
  guaranteed to survive, and the phase-101 rollup gap for them is accepted and
  documented (Ensures 33). No migration, no repair subcommand, no manual
  `UPDATE`.
- **Re-attributing the two misattributed checkpoint rows** (339, 340) away from
  `INFRA-256`. The fix is forward-only.
- **Making the FAIL bump work with `effort_tracking` disabled.** That needs a
  second durable pending-spawn store; the limitation is documented instead
  (Ensures 27).
- **Any change to `.companion/attempt_counter.json` semantics** or to
  `next_action.infer_position`'s escalation-ladder rows 5/6/7 — only the *timing*
  of an existing bump changes, never its meaning.
- **Any change to `hooks/post_tool_use.py`** or to the hook registrations in
  `hooks/hooks.json`.
- **Changing `RECORDABLE_SUBAGENT_ROLES`** or recording non-build-cycle spawns
  (`general-purpose`, `Plan`, `Explore`, `spec-writer`).
- **Reading the orchestrator transcript's `<task-notification>` entries.** The
  `output_file` is the chosen correlation key; notification parsing is the
  rejected direction (b) and must not be added as a second path.
- **Reworking `pairmode_effort.py`'s reports or the observability SPA** to
  surface `phase:<key>` rows — the rows become correct here; presenting them is
  Phase G (HARNESS007-main) work.
- **Adding a `SessionEnd` reconciliation pass.** `SessionEnd` is `async: true`
  with a 30 s timeout and is not a guaranteed-to-complete surface; the
  `SessionStart` sweep in the next session covers the same rows.
