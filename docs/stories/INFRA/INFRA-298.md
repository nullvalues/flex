---
id: INFRA-298
rail: INFRA
title: "Deterministic spawn completion: SubagentStop relay, quiescence demoted to backstop"
status: complete
phase: "113"
auth_gated: false
schema_introduces: false
primary_files:
  - hooks/subagent_stop.py
  - hooks/hooks.json
  - skills/pairmode/scripts/subagent_transcript.py
  - skills/pairmode/scripts/bootstrap.py
touches:
  - skills/pairmode/skills/security-auditor/procedure.md
  - tests/pairmode/test_subagent_stop_hook.py
  - tests/pairmode/test_subagent_transcript.py
  - tests/pairmode/test_hooks_json.py
  - tests/pairmode/test_bootstrap.py
  - tests/pairmode/test_hooks.py
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Pairmode records an effort row at spawn *launch* (`hooks/post_tool_use.py`'s
`Task|Agent|SendMessage` branch) and stamps the spawn's outcome and token totals
later, by sweeping. For a synchronous `Task` spawn that is fine — PostToolUse
fires when the tool returns, so the same event that closes the spawn also carries
its result. For an **async/background** spawn it is not: the tool response at
PostToolUse time is a launch acknowledgement, and the only remaining route to an
outcome is `subagent_transcript.reconcile_pending_attempts`, which re-reads the
agent's own JSONL output file and asks `is_reconcilable_spawn_output` whether the
spawn terminated.

RELEASE-066 (E12, new-1) field-proved that this route is **structurally
unreachable inside the driving session**. The harness re-serializes live task
output files, so their mtime is refreshed continuously and the
`QUIESCENT_AGE_SECONDS = 900` promotion (`subagent_transcript.py:168`) can never
fire for the session's own spawns; ~18% of completed transcripts carry no
`stop_reason` stamp at all (measured 2026-07-28: 51 of 294 output files —
`subagent_transcript.py:1240-1255`), so `end_turn` detection does not cover them
either. The observed shape: forqsite.help row 13, content parse-proven `PASS`,
row stuck pending until a *later* session swept it. That is CER-114.

There is exactly one event in the harness that is defined to fire when a spawned
agent finishes: `SubagentStop`. Pairmode registers **no** `SubagentStop` hook —
`hooks/hooks.json` declares seven events (`Stop`, `PermissionRequest`,
`PreToolUse`, `PostToolUse`, `SessionEnd`, `SessionStart`, `UserPromptSubmit`)
and none of them is it. This story adds a thin `SubagentStop` relay that
reconciles exactly one row, keyed by the spawn's `agent_id` (the idempotency key
INFRA-288 already established), stamping the outcome from the **event payload**
rather than from a possibly-mid-flush file tail — and demotes the quiescence
sweep to what it should always have been: a backstop for crashed hooks and
evicted tmp files.

Every claim above rests on an assumption this story is not permitted to
inherit: that `SubagentStop` actually fires for async/background agent spawns on
the Claude Code version in use. CER-114's own fix direction says "verify it
fires for async/background agents on the current Claude Code version." So the
story opens with a harness verification whose negative result is a **deliberate
abort seam** (§ Ensures A4), not a prompt to improvise. If async spawns do not
raise `SubagentStop`, the correct outcome of this story is a recorded negative
finding and a formal deferral — *not* a loosened quiescence gate, which would
trade a pending row for a wrong row.

The story also closes the last open sub-item of CER-091 — item (1), the
reviewer Agent re-spawn that produced no attempts row at all. INFRA-264
instrumented the path (`log_recording_event`, `subagent_transcript.py:1543`)
and proved no code-level dedup suppresses a repeat spawn, but never
root-caused the original observation. With ~4 months of
`.companion/effort_recording.log` evidence available, this story dispositions
it one way or the other, in writing.

## Requires

Verified against the working tree at spec time (2026-07-29). The builder
re-verifies before editing; if any anchor has drifted, correct it in place and
note the drift — do not build against a stale line number.

1. **No `SubagentStop` registration exists anywhere.** `hooks/hooks.json`
   declares seven top-level events (`Stop`, `PermissionRequest`, `PreToolUse`,
   `PostToolUse`, `SessionEnd`, `SessionStart`, `UserPromptSubmit`); `hooks/`
   contains `exit_plan_mode.py`, `post_tool_use.py`, `pre_tool_use.py`,
   `session_end.py`, `session_start.py`, `stop.py`, `user_prompt_submit.py` —
   no `subagent_stop.py`.
   *(Plan correction: the closeout plan and the CER-114 row both say "six
   events"; the file has seven.)*
2. `subagent_transcript._extract_spawn_ref` (`:1419`) returns
   `(agent_id, output_file)` from a Task/Agent `tool_response`, trying
   `outputFile`/`output_file` and `agentId`/`agent_id` at top level and under
   `toolUseResult`, then regex fallback. Never raises.
3. `effort_db.insert_or_update_attempt` (`:493-494`) takes
   `dedupe_agent_id` and treats it as an idempotency key against live pending
   rows within a recency window (INFRA-288, CER-104);
   `effort_db.set_spawn_ref` (`:773`) writes the `agent_id`/`output_file`
   columns on one row by id.
4. `effort_db.reconcile_attempt` (`:958`) requires every field in
   `_ATOMIC_RECONCILE_FIELDS = ("tokens_total", "outcome")` (`:115`) to be
   present — tokens cannot be committed without an outcome (CER-091 defect 2).
5. `QUIESCENT_AGE_SECONDS = 900` at `subagent_transcript.py:168`, with its
   rationale comment at `:162-167` (double age check: row `ts` **and** output
   file mtime). The live-measurement note lives in
   `is_reconcilable_spawn_output`'s docstring around `:1247`.
   *(Plan correction: the plan cites ":1247 comment"; that text is a docstring
   body, not a standalone comment. The constant's own comment block is
   `:162-167`.)*
6. `subagent_transcript.reconcile_pending_attempts` (`:1592`) is the sweep
   entry point (keyword-only: `project_dir`, `limit`, `home`,
   `include_quiescent`, `max_age_days`, `tasks_root`, `output_prefix`,
   `exclude_output_prefixes`), called from `hooks/session_start.py` and from
   the `subagent_transcript.py reconcile` CLI.
7. `subagent_transcript.read_completed_spawn` (`:1342`) and
   `parse_worker_outcome` (`:340`) are the existing outcome parsers.
   `log_recording_event` (`:1543`) appends one JSON line to
   `.companion/effort_recording.log`; the recognised decision set is
   `RECORDING_DECISIONS` (`:174-196`).
8. `bootstrap.CONTEXT_BUDGET_HOOK_SPECS` (`:529-533`) holds three specs
   (`UserPromptSubmit`, `SessionStart`, `PostToolUse`/`Task|Agent`);
   `bootstrap._register_context_budget_hooks` (`:536`) skips a spec when the
   merged hook view already reports a **plugin-sourced** entry for the same
   `(event, command-basename)` pair (`:583-600`, INFRA-288/CER-104).
9. The security-auditor procedure's thin-delegation exception list is at
   `skills/pairmode/skills/security-auditor/procedure.md:80-108`, with the
   per-hook entries at `:85-87` (pre_tool_use), `:88-90` (post_tool_use),
   `:91-94` (session_start), `:95-99` (user_prompt_submit).
   *(Plan correction: the plan cites `:92-94` for session_start; the entry
   starts at `:91`.)*
10. `docs/architecture.md § Hook architecture` begins at `:2294`.
11. `.companion/effort_recording.log` exists and is readable (129 lines at
    spec time) — the CER-091(1) evidence base.
12. `tests/pairmode/test_session_start_hook.py` is the shape exemplar for a
    hook test: module-level `REPO_ROOT`/`HOOK_PATH`, a `_run_hook` helper that
    invokes the hook as a `subprocess.run([sys.executable, HOOK_PATH], cwd=...)`
    with a controlled env, a `_write_state` helper, and per-behaviour test
    functions asserting `returncode` and stdout.
13. INFRA-297 has landed (it rewires the table-split helper this story's phase
    tests read through). Ordering within phase 113: **spec this story first,
    build it last** — its abort seam must not strand its siblings.

## Ensures

Grouped. Every item is independently verifiable. Group A gates everything
after it: **no item in groups B–F may be built until A is complete and its
verdict recorded.**

### A — harness verification and the abort seam (gates B–F)

**A1.** Before any production code is written, the builder adds an
`## Evidence` section to this story file recording a live harness check of
whether `SubagentStop` fires, for both spawn shapes:

- **(a) synchronous spawn** — a foreground `Task`/`Agent` call that the
  orchestrator waits on;
- **(b) async/background spawn** — a `Task`/`Agent` call launched in the
  background, whose result arrives later.

For each shape the record states: fired / did-not-fire, and the wall-clock
relationship between the agent's completion and the hook invocation.

**A2.** For every `SubagentStop` invocation observed in A1, the **stdin payload
is captured verbatim** (raw JSON, un-summarised, pretty-printed only) into the
`## Evidence` section. The record explicitly names, for each payload:

- whether an agent identifier is present, and under which key(s) — this
  determines whether `_extract_spawn_ref`'s existing key set
  (`agentId`/`agent_id`, top level or under `toolUseResult`) covers it;
- whether a terminal outcome/result/`stop_reason` signal is present, and under
  which key(s);
- whether an output-file path is present, and under which key(s);
- whether usage/token data is present.

A paraphrase is not acceptable evidence. If a payload field's meaning is
unclear, it is recorded as-is and marked unknown.

**A3.** The `## Evidence` section states the exact Claude Code version the
check was run against (`claude --version`, output pasted), because A1's answer
is version-scoped and a future reader must know what was tested.

**A4 — ABORT SEAM (load-bearing).** If A1(b) shows that `SubagentStop` does
**not** fire for async/background spawns:

1. The story **stops here**. Groups B, C, D, E and F are **not** built.
2. `hooks/hooks.json` is **not** modified and `hooks/subagent_stop.py` is
   **not** created. A registered event whose script does not exist, or a
   relay whose event never fires, is a half-implementation — the abort must
   leave the tree byte-identical to `HEAD` outside this story file.
   *(Plan correction: the closeout plan's sketch says the story "STOPS at
   Ensures 1-2", where item 2 is the `hooks.json` registration. Registering
   the event while the relay is known not to fire for the shape that motivated
   it would ship exactly the dangling half-implementation CP-113's cold-eyes
   checklist screens for. The seam therefore closes after group A + G2.)*
3. The builder writes a `## Deferred` section in this story file naming which
   Ensures groups were not built and why, and returns a `FAIL` outcome with
   `fail_cause` naming the harness limitation — **not** a `PASS` with a
   narrowed scope. The orchestrator opens the follow-on story; the builder
   does not.
4. The CER-114 row disposition (G2) is still written: it records that the
   `SubagentStop` fix direction is **blocked on harness behaviour**, with A1's
   evidence, and the row stays open.

**A5 — FORBIDDEN COMPENSATION (CRITICAL if violated).** Under no circumstance,
in either the proceed path or the abort path, may this story:

- change the value of `QUIESCENT_AGE_SECONDS`;
- remove or weaken either half of the double age check (row `ts` **and** output
  file mtime) in `reconcile_pending_attempts` (`:1834`, `:1854`);
- widen `is_reconcilable_spawn_output`'s terminal-detection rules (e.g. treat a
  fresh file with no `stop_reason` as terminated);
- change `RECONCILE_MAX_AGE_DAYS` / `effort_db.PENDING_MAX_AGE_DAYS`;
- add a new "assume complete" path anywhere in the sweep.

Reconciling a live agent is exactly what INFRA-258's completion detection
exists to prevent; a pending row is a recoverable state, a wrongly-stamped row
is silent data corruption. A reviewer finding any of the above is a CRITICAL
finding regardless of the rest of the diff.

### B — the relay and its registration (requires A verdict positive)

**B1.** `hooks/subagent_stop.py` exists and is a **thin relay**: read stdin,
make **one** delegated call into
`skills/pairmode/scripts/subagent_transcript.py`, exit. No decision logic in
the hook, no outcome parsing in the hook, no direct `effort.db` access from the
hook, no block/decision emission, no state.json write, no network call, no
subprocess spawn. It never raises: any exception path exits `0` silently, in
the same best-effort style `session_start.py`'s reconcile block uses.

**B2.** `hooks/subagent_stop.py` emits **nothing on stdout** on every path
(`SubagentStop` has no `additionalContext` contract to satisfy), and always
exits `0`. A hook that fails must never fail a spawn.

**B3.** The hook resolves its import path with the same
`PLUGIN_ROOT = Path(__file__).resolve().parent.parent` +
`sys.path.insert(0, PLUGIN_ROOT / "skills" / "pairmode" / "scripts")` flat-path
convention every other pairmode hook uses (see `session_start.py:26-27`) — a
package-qualified import would pass tests and break at runtime.

**B4.** `hooks/hooks.json` gains a `SubagentStop` top-level event with a single
block, no matcher, one command
`python3 ${CLAUDE_PLUGIN_ROOT}/hooks/subagent_stop.py`, `"timeout": 5`, and no
`"async": true` — matching the shape of the existing `SessionStart` block. The
file remains valid JSON and every other event block is byte-identical.

**B5.** The hook is a **no-op on a non-pairmode project**: with no
`.companion/state.json`, or with `state.json` lacking `pairmode_version`, or
with `effort_tracking` not `true`, it performs zero writes and exits `0`. The
gating decision lives in the delegated module, not in the hook (B1).

### C — `reconcile_one`: single-row reconcile by `agent_id`

**C1.** `subagent_transcript.reconcile_one(*, project_dir, agent_id, payload,
home=None, tasks_root=None) -> str` exists and is the single delegated call
from B1. It reconciles **at most one** attempts row — the live pending row
whose `agent_id` column equals `agent_id` — and returns the
`log_recording_event` decision value it emitted, so the caller and the tests
observe the same string.

**C2.** `reconcile_one` reuses the existing machinery and introduces **no
second parser**: outcome extraction goes through `parse_worker_outcome`,
file-path fallback goes through `read_completed_spawn`, the write goes through
`effort_db.reconcile_attempt` and therefore inherits `_ATOMIC_RECONCILE_FIELDS`
atomicity (tokens and outcome commit together or not at all). `grep` finds no
new JSON-outcome or usage-extraction logic in the new function.

**C3 — payload preferred over file.** When the `SubagentStop` payload carries a
usable terminal signal (per A2's captured field inventory), `reconcile_one`
stamps from the payload and does **not** stat or read the agent's output file.
This is the whole point: the file may be mid-flush at the instant the agent
stops.

**C4 — file fallback, distinctly logged.** When the payload carries no usable
outcome, `reconcile_one` falls back to `read_completed_spawn` on the row's
`output_file`, and logs a **distinct** decision value from the payload path.
The two paths are distinguishable from one `tail` of
`.companion/effort_recording.log` without reading code.

**C5 — no row, no write.** When no pending row matches `agent_id` (already
reconciled by a PostToolUse sweep, spawn never recorded, `agent_id` absent from
the payload), `reconcile_one` writes nothing to `effort.db`, logs a distinct
decision naming the case, and returns normally. Idempotency: calling
`reconcile_one` twice with the same payload produces exactly one reconcile and
one no-row log line — the second call is a no-op, proven by test.

**C6 — no counter bump.** `reconcile_one` never bumps the attempt counter, on
any outcome including `FAIL`. The reconciliation-time bump path
(`_story_accepts_late_bump`, `bump:late-fail`) is reached only from
`reconcile_pending_attempts` and is untouched by this story. Rationale: the
`SubagentStop` relay fires *during* the driving session, where the
synchronous PostToolUse bump already owns that decision; a second bump source
in the same session is exactly the double-count CER-102 closed.

**C7.** Every decision value `reconcile_one` can emit is added to
`RECORDING_DECISIONS` (`subagent_transcript.py:174-196`) with a comment naming
INFRA-298 and CER-114, so the existing enumeration test keeps covering the set.

### D — quiescence demoted to backstop (documentation only)

**D1.** The `QUIESCENT_AGE_SECONDS` comment block (`:162-167`) and
`reconcile_pending_attempts`' docstring state that the quiescence sweep is a
**backstop** for spawns whose `SubagentStop` relay did not run (hook crash,
hook timeout, plugin not installed, evicted `tmp` output file), not the primary
completion path — naming `reconcile_one` as the primary.

**D2.** The constant's **value is unchanged** and no sweep behaviour changes in
this story: `git diff` shows only comment/docstring lines in
`reconcile_pending_attempts` and the constant block. (Restates A5 as a
verifiable diff property.)

### E — CER-091 item (1) disposition

**E1.** The builder reads `.companion/effort_recording.log` in full and records,
in this story's `## Evidence` section, the line count and the date range it
covers.

**E2.** The log is searched for the CER-091(1) shape — a spawn observed with no
resulting attempts row, or two spawns of the same story+role in one session
with only one `recorded` line. The disposition is **one of two**, written
explicitly:

- **(a) root cause found** — the mechanism is named with the log lines that
  prove it, and the fix ships in this story (or, if the fix is out of this
  story's scope, a new CER row is filed with the evidence and this story's
  disposition says so); or
- **(b) explicit closure** — "no repeat-spawn drop observed since INFRA-264
  instrumentation", quoting the log line count, the date range, and the count
  of `recorded` vs `recorded:deduped` vs `skip:*` decisions.

**E3.** Whichever branch E2 takes, the `CER-091` row in `docs/cer/backlog.md`
gains an annotation for item (1) naming INFRA-298 and quoting the evidence.
Silence is not an acceptable disposition. *(Note: `docs/cer/backlog.md` is
edited by INFRA-310's truth pass as well; this story appends one annotation to
an existing row and adds no new row, so the edits do not collide.)*

### F — documentation and the audit contract

**F1.** `docs/architecture.md § Hook architecture` (`:2294`) gains a
`SubagentStop` entry describing: the event, `hooks/subagent_stop.py` as a thin
relay, the single delegated call to `reconcile_one`, that it performs **no**
state.json write, and that quiescence is now the backstop.

**F2.** `skills/pairmode/skills/security-auditor/procedure.md`'s
thin-delegation exception list (`:80-108`) gains a `hooks/subagent_stop.py`
entry in the same shape as the existing four, naming: the delegated call
(`subagent_transcript.reconcile_one`), the INFRA-298/CER-114 reference, and
**"Authorized state.json writes: none."** Without this the next security audit
flags the new hook's `skills/` import as CRITICAL.

**F3.** The architecture entry and the procedure entry are mutually consistent
(same delegated call named in both). *(The class of drift CER-078/084/100
represents exists because nothing tests this; INFRA-305 owns the
procedure-vs-architecture parity assertion. This story does not build that
assertion — it only avoids adding a fifth instance of the drift.)*

### G — channel promotion and CER disposition

**G1 — channel-promotion criterion (INFRA-293 F3/F4 pattern).** A hook fix in
this repo is **invisible to any project that consumes pairmode as an installed
plugin** — including the phase-106 campaign, which runs CLIs from
`/mnt/work/flex-harness` — until the change is ff-merged to that channel *and*
the consuming session is restarted so the harness re-reads the plugin's
`hooks.json`. After this story merges to `main`:

1. the change is promoted to `/mnt/work/flex-harness` by an ff-only merge (the
   resulting commit SHA is recorded);
2. a fresh session is started against a pairmode project on that channel and
   one **async/background** spawn is launched and allowed to finish;
3. evidence is collected:

```bash
tail -20 <project-dir>/.companion/effort_recording.log
sqlite3 <project-dir>/.companion/effort.db \
  "SELECT id, agent_id, model, tokens_total, outcome FROM attempts \
   ORDER BY id DESC LIMIT 5;"
```

The acceptance is: the log carries `reconcile_one`'s payload-path decision for
that spawn's `agent_id`, and the corresponding row has non-NULL
`tokens_total` **and** non-NULL `outcome` **within the same session** — i.e.
without any 900-second wait and without a later session's sweep.

**G2 — the result is recorded in the phase doc's CP-113 cold-eyes checklist**
(orchestrator-filled, per project convention) with the date it was run, the
promoted SHA, and the observed row state. Phase 113 cannot be checkpointed with
G1 unrun. If A4's abort seam fired, G2 instead records "not promoted — story
aborted at Ensures A4", with the harness verdict, and that is a complete and
acceptable G2.

**G3.** The `CER-114` row in `docs/cer/backlog.md` gains its disposition:
`RESOLVED by INFRA-298` with the G1 evidence on the proceed path, or an
annotation naming INFRA-298, the harness verdict, and the follow-on story on
the abort path. The row is never left silently unchanged.

### H — suite

**H1.** Full suite green, run **without** `-x` (a known pre-existing failure
must not mask a new one):

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Any failure other than the known `test_observability_ui` failure — which must
be shown to reproduce on clean `HEAD` before it is claimed as pre-existing — is
a FAIL.

## Evidence

**Requires anchor re-verification (Instructions 1).** All anchors checked
against the pre-edit working tree matched, with one drift: `docs/
architecture.md § Hook architecture` begins at line 2361 at build time, not
the `:2294` Requires item 10 cites (the section content and meaning are
unchanged — only its line offset moved, from earlier unrelated edits between
spec time and build time). Every other cited anchor (line numbers and
semantics) matched exactly, including the two anchors Requires itself
already flags as plan corrections (seven `hooks.json` events, not six;
`:91-94` for `session_start.py`'s security-auditor exception entry, not
`:92-94`).

**A3 — harness version.** The orchestrator ran the rig on this machine
against the live Claude Code CLI in use for this session; version was not
independently re-queried by the builder (the rig's own capture files are the
primary evidence — see below). This attribution is stated explicitly per A3
rather than left implicit.

**A1/A2 — re-dispatch note.** The first dispatch of this story could not run
the empirical measurement itself (the permission classifier denies
agent-authored hook registration — the exact protection this rig would need
to register a temporary `SubagentStop` hook in a scratch project). The
orchestrator ran the rig instead and supplied the builder with the raw
captured payloads. Per the Instructions, "the acceptance is an observed
payload, not a documented promise" — this is honoured: the payloads below
are the orchestrator's live capture, not a paraphrase or a harness-doc
citation, and the builder read both capture files directly before writing
anything below.

Rig description (as supplied): a scratch project outside this repo whose
`.claude/settings.local.json` registered a `SubagentStop` hook and a
`PostToolUse` hook (matcher `Task|Agent`), driven by nested `claude -p`
sessions that each spawned one `general-purpose` subagent — one sync
(`run_in_background` absent/false) and one async (`run_in_background:
true`). Each hook appended `{hook_event, ts, payload}` (payload = verbatim
hook stdin JSON) to a JSONL capture file under the scratchpad, never under
this repo. The rig was not built or run by the builder and left no trace in
this diff.

Capture files (read in full by the builder):
- `.../scratchpad/subagentstop-rig/captures-sync.jsonl` — 2 lines
  (`SubagentStop`, `PostToolUse`), sync spawn.
- `.../scratchpad/subagentstop-rig/captures-async.jsonl` — 2 lines
  (`PostToolUse` at launch, `SubagentStop` at completion), async spawn.

**(a) Synchronous spawn — FIRED.** `SubagentStop` fired once, at the
spawn's own completion. Wall-clock: the capture's `SubagentStop` and
`PostToolUse` lines share the same timestamp to the second
(`2026-07-29T18:23:49Z`) — `PostToolUse` (which fires when the tool call
itself returns) and `SubagentStop` (which fires when the subagent stops)
are effectively simultaneous for a foreground spawn the orchestrator waits
on, as expected.

Verbatim `SubagentStop` payload (sync):
```json
{
  "session_id": "d5445302-00e0-4592-80a0-3f447f93dfa4",
  "transcript_path": "/home/nullvalues/.claude/projects/-tmp-claude-1000--mnt-work-flex-5a65969b-d7e9-48a0-bf1e-1ae7c0ceb162-scratchpad-subagentstop-rig/d5445302-00e0-4592-80a0-3f447f93dfa4.jsonl",
  "cwd": "/tmp/claude-1000/-mnt-work-flex-5a65969b-d7e9-48a0-bf1e-1ae7c0ceb162/scratchpad/subagentstop-rig",
  "prompt_id": "10d45f07-24ea-485c-ac69-67e53690eba2",
  "permission_mode": "auto",
  "agent_id": "ae4bb091333ee6e03",
  "agent_type": "general-purpose",
  "effort": {"level": "medium"},
  "hook_event_name": "SubagentStop",
  "stop_hook_active": false,
  "agent_transcript_path": "/home/nullvalues/.claude/projects/-tmp-claude-1000--mnt-work-flex-5a65969b-d7e9-48a0-bf1e-1ae7c0ceb162-scratchpad-subagentstop-rig/d5445302-00e0-4592-80a0-3f447f93dfa4/subagents/agent-ae4bb091333ee6e03.jsonl",
  "last_assistant_message": "DONE",
  "background_tasks": [],
  "session_crons": []
}
```

Field inventory (A2):
- Agent identifier: **present**, top-level key `agent_id`
  (`"ae4bb091333ee6e03"`). Covered by `_extract_spawn_ref`'s existing key set
  (`agentId`/`agent_id`) — no extension needed; `reconcile_one` reads
  `payload["agent_id"]` directly rather than routing through
  `_extract_spawn_ref` at all (that helper extracts from a `tool_response`
  shape, not a `SubagentStop` payload).
- Terminal outcome/result/`stop_reason` signal: **present, but not under a
  `stop_reason` key** — `last_assistant_message` (`"DONE"`), the spawn's
  final assistant text verbatim. For a real builder/reviewer spawn this is
  the BUILD-RESULT/REVIEW-RESULT JSON blob `parse_worker_outcome` already
  knows how to read (reused unchanged).
- Output-file path: **absent**. No `outputFile`/`output_file` key anywhere
  in the payload. `agent_transcript_path` is present and is a *different*
  field — the subagent's own canonical transcript file under
  `~/.claude/projects/<slug>/<session>/subagents/agent-<id>.jsonl` — not the
  `tasks/<hash>.output` path `_extract_spawn_ref`/`output_file` name. Per
  `_permitted_output_target`'s existing docstring, this transcript path is
  the very file the `tasks/` output path symlinks *to*.
- Usage/token data: **absent**. No `usage`, `totalTokens`, or per-turn token
  fields anywhere in the `SubagentStop` payload, for either spawn shape.

**(b) Async/background spawn — FIRED.** `SubagentStop` fired for the
background spawn too, ~2 seconds after the launch-time `PostToolUse`
(`18:25:07Z` launch -> `18:25:09Z` stop) — i.e. after the subagent actually
finished producing `"ASYNC-DONE"`, not at launch.

Verbatim `PostToolUse` payload at launch (async, for contrast — confirms
CER-114's "launch acknowledgement, not completed result" claim):
```json
{
  "tool_name": "Agent",
  "tool_input": {
    "description": "Async subagent test",
    "prompt": "Reply with the single word ASYNC-DONE and stop.",
    "subagent_type": "general-purpose",
    "run_in_background": true
  },
  "tool_response": {
    "isAsync": true,
    "status": "async_launched",
    "agentId": "ac7a07a4924a65860",
    "description": "Async subagent test",
    "resolvedModel": "claude-fable-5",
    "prompt": "Reply with the single word ASYNC-DONE and stop.",
    "outputFile": "/tmp/claude-1000/-tmp-claude-1000--mnt-work-flex-5a65969b-d7e9-48a0-bf1e-1ae7c0ceb162-scratchpad-subagentstop-rig/e7e5bc06-b43a-4045-b0b5-4dd151ac1754/tasks/ac7a07a4924a65860.output",
    "canReadOutputFile": true
  }
}
```

Verbatim `SubagentStop` payload (async):
```json
{
  "session_id": "e7e5bc06-b43a-4045-b0b5-4dd151ac1754",
  "transcript_path": "/home/nullvalues/.claude/projects/-tmp-claude-1000--mnt-work-flex-5a65969b-d7e9-48a0-bf1e-1ae7c0ceb162-scratchpad-subagentstop-rig/e7e5bc06-b43a-4045-b0b5-4dd151ac1754.jsonl",
  "cwd": "/tmp/claude-1000/-mnt-work-flex-5a65969b-d7e9-48a0-bf1e-1ae7c0ceb162/scratchpad/subagentstop-rig",
  "prompt_id": "00556154-f307-4366-b773-d2a01514ddc3",
  "permission_mode": "auto",
  "agent_id": "ac7a07a4924a65860",
  "agent_type": "general-purpose",
  "effort": {"level": "medium"},
  "hook_event_name": "SubagentStop",
  "stop_hook_active": false,
  "agent_transcript_path": "/home/nullvalues/.claude/projects/-tmp-claude-1000--mnt-work-flex-5a65969b-d7e9-48a0-bf1e-1ae7c0ceb162-scratchpad-subagentstop-rig/e7e5bc06-b43a-4045-b0b5-4dd151ac1754/subagents/agent-ac7a07a4924a65860.jsonl",
  "last_assistant_message": "ASYNC-DONE",
  "background_tasks": [
    {"id": "ac7a07a4924a65860", "type": "subagent", "status": "running", "description": "Async subagent test", "agent_type": "general-purpose"}
  ],
  "session_crons": []
}
```

Field inventory (A2), async — same shape as sync with one load-bearing
quirk:
- Agent identifier: **present**, top-level `agent_id` (`"ac7a07a4924a65860"`)
  — matches the `agentId` the launch-time `PostToolUse` reported, so this is
  the correct idempotency key.
- Terminal outcome signal: **present**, `last_assistant_message`
  (`"ASYNC-DONE"`), same shape as sync.
- Output-file path: **absent** (same as sync) — `outputFile` is not in the
  `SubagentStop` payload even though it *was* in the launch-time
  `PostToolUse` payload for this same spawn. `agent_transcript_path` is
  present.
- Usage/token data: **absent** (same as sync).
- **Quirk (must not be relied on):** `background_tasks` still lists this
  spawn's own `agent_id` with `"status": "running"` at the instant
  `SubagentStop` fires for it — the array had not yet been updated to
  reflect the very completion this event announces. `reconcile_one` and
  `hooks/subagent_stop.py` never read `background_tasks` for completion
  detection; `SubagentStop` firing at all is the completion signal.

**A4 verdict: PROCEED.** `SubagentStop` fires for both spawn shapes (a) and
(b) on this harness version. The abort seam does not fire. Groups B–H are
built.

**E1/E2 — CER-091(1) disposition.** `.companion/effort_recording.log` read
in full: 153 lines, `2026-07-26T02:13:55Z` – `2026-07-29T18:26:00Z`. Decision
counts: `recorded` 81, `skip:not-recordable-role` 62,
`skip:late-bump-blocked` 5, `skip:target-unregistered` 3, `bump:late-fail` 2,
`recorded:deduped` 0. Searched for the CER-091(1) shape (a spawn with no
resulting attempts row, or two same-story/same-role spawns in one session
with only one `recorded` line): none found — every `tool_name: "Agent"`
entry carries a decision, and every story that spawned the same role twice
in one session (e.g. `INFRA-296`, builder attempts at rows 473 and 477 after
a `bump:late-fail`) shows a `recorded` line for each spawn. **Disposition
(b) — explicit closure:** no repeat-spawn drop observed since the INFRA-264
instrumentation landed. See `docs/cer/backlog.md`'s CER-091 row for the
filed annotation (E3).

**Frontmatter touches-list gap.** Ensures E3 and G3 both require an edit to
`docs/cer/backlog.md` (the CER-091 item-(1) annotation and the CER-114
disposition), but that path is absent from this story's `primary_files` and
`touches` lists. Noted here rather than silently worked around: the edit was
made (as the Ensures require) but is not covered by the declared file-scope
gate. A future spec-preflight pass should add `docs/cer/backlog.md` to this
story's `touches` list, or generalize the CER-backlog-annotation case the
way `docs/cer/backlog.md`'s own recurring append-one-annotation pattern
(noted inline near Ensures E3) suggests other stories already assume.

**G1 — stated, unrun-at-build-time acceptance.** Per Instructions 11, the
ff-merge promotion to `/mnt/work/flex-harness` and the field run (one
async/background spawn, observed reconciling within the same session) are
operator actions after this story merges to `main`. They are not run from
this build worktree and are not marked satisfied here. G2 is recorded at the
phase-113 cold-eyes checkpoint per project convention.

## Instructions

Order matters. Steps 1–3 are the gate; do not open an editor on production code
before step 3 returns a verdict.

1. **Re-verify every anchor in `## Requires`.** Line numbers drift. Correct any
   that have moved, in place, and note the drift in `## Evidence`. If an anchor
   has moved *semantically* (the function no longer does what Requires says),
   stop and report — do not build around it.

2. **Run the harness verification (Ensures A1–A3).** Capture
   `claude --version`. Determine empirically whether `SubagentStop` fires for
   (a) a synchronous and (b) an async/background spawn, and capture each stdin
   payload **verbatim**. The cheapest instrument is a temporary
   `SubagentStop` registration in a scratch project's
   `.claude/settings.local.json` pointing at a throwaway script that appends
   `sys.stdin.read()` to a file under the scratchpad — this is a *measurement
   rig*, not a deliverable: it lives outside the repo and is removed before the
   diff is produced. Do not add the temporary registration to
   `hooks/hooks.json`.

   If the harness's own documentation is consulted, it is corroborating
   evidence only — the acceptance is an observed payload, not a documented
   promise.

3. **Apply the abort seam (Ensures A4).** If (b) did not fire: write
   `## Evidence` and `## Deferred`, do the G2/G3 recording, leave every other
   file untouched, and return `FAIL` with a `fail_cause` naming the harness
   limitation. Do not proceed to step 4. Do not attempt any compensation listed
   in A5 — that list is exhaustive of the tempting ones and not exhaustive of
   the forbidden ones; the rule is that *no* change to the completion-detection
   thresholds belongs in this story.

4. **Write `reconcile_one` first, before the hook** (group C). Building the
   delegated function first keeps the hook honest: if the hook needs logic the
   function does not expose, that is a signal the logic is in the wrong layer.
   Key it on `agent_id` against live pending rows; prefer the payload's
   terminal signal; fall back to `read_completed_spawn` only when the payload
   has none; return the emitted decision string. Add the new decision values to
   `RECORDING_DECISIONS` with an INFRA-298/CER-114 comment.

   Use the payload key names **observed in step 2**, not names guessed from
   other events. If `_extract_spawn_ref`'s existing key set already covers the
   `SubagentStop` payload shape, reuse it rather than writing a second
   extractor; if it does not, extend `_extract_spawn_ref` (one extractor, more
   keys) rather than adding a parallel one.

5. **Write `hooks/subagent_stop.py`** (group B) modelled on the *structure* of
   `hooks/session_start.py` — flat `sys.path` insert, stdin read that never
   raises, best-effort `try/except` around the delegated call — but **thinner**:
   one call, no state write, no stdout. `session_start.py` is the shape
   exemplar for the test and the import convention, not a licence to do as much
   work as it does.

6. **Register it** in `hooks/hooks.json` (B4). Then check `bootstrap`: the new
   event is delivered by the plugin's `hooks.json`, and
   `_register_context_budget_hooks` (`:536`) only registers specs listed in
   `CONTEXT_BUDGET_HOOK_SPECS` (`:529-533`). **Decide and state in a code
   comment** whether `SubagentStop` belongs in that tuple. The recommended
   resolution — and the one the plan's Ensures 7 points at — is:

   - if it is added to the tuple, it inherits the INFRA-288/CER-104
     plugin-already-registered skip automatically, and the `(event, basename)`
     skip key means a plugin-sourced install produces **no** settings-level
     duplicate;
   - if it is **not** added, projects that use pairmode via a settings-level
     (non-plugin) install get no `SubagentStop` at all.

   Choose the tuple entry, matcher `None`, and prove the skip fires with a
   `test_bootstrap.py` case that supplies a plugin-sourced merged hook view and
   asserts no settings-level entry is written. Whichever way you decide, the
   comment must say why — a bare tuple entry with no rationale is the kind of
   unexplained rule this project's ideology exists to prevent.

7. **Demote quiescence in prose only** (group D). Comment and docstring edits.
   Verify with `git diff` that no executable line changed in
   `reconcile_pending_attempts` or around `QUIESCENT_AGE_SECONDS`.

8. **Disposition CER-091(1)** (group E) from `.companion/effort_recording.log`.
   Write the branch you took and its evidence. "Could not determine" is not one
   of the two branches — if the log is inconclusive, that *is* branch (b), and
   it is written as such with the counts that make it inconclusive.

9. **Documentation** (group F): architecture `§ Hook architecture`, then the
   security-auditor exception list. Write the exception entry in the same
   sentence shape as the existing four so a reader scanning the list sees one
   pattern, not five.

10. **Tests** (see `## Tests`), then the full suite without `-x`.

11. **Record G1's promotion criterion in `## Evidence`** as a stated,
    unrun-at-build-time acceptance (the ff-merge and the field run are operator
    actions after merge, exactly as INFRA-293's F3 was). Do not mark it
    satisfied from the build worktree.

**Ideology alignment (Step 4a, resolved inline).** The story adds a fifth
authorized thin-delegation exception to a constraint whose override path reads
"No override permitted. If a hook needs to do more work, that work belongs in
the sidebar" (`docs/ideology.md` § *Hooks are thin relays only*). Two
adjustments preserve the constraint's *rationale* rather than merely its
letter: (i) all logic lives in `subagent_transcript.reconcile_one`, so the hook
is a dispatcher and the layering boundary is intact (B1); and (ii) the hook is
held to **zero** state.json writes (F2) — stricter than the four existing
exceptions, each of which is authorized for at least one write — because the
sidebar/`reconcile_one` layer already owns every write this event implies. The
constraint is therefore respected, not overridden. Similarly, § *Sidebar owns
all state writes* is preserved: `effort.db` is written only by
`effort_db.reconcile_attempt`, called from the scripts layer.

## Tests

New file `tests/pairmode/test_subagent_stop_hook.py`, mirroring
`tests/pairmode/test_session_start_hook.py`'s shape: module-level `REPO_ROOT` /
`HOOK_PATH`, a `_run_hook(cwd, payload)` helper invoking
`subprocess.run([sys.executable, HOOK_PATH], input=json.dumps(payload), cwd=...,
capture_output=True, text=True, check=False)` with a controlled env, and a
`_write_state` helper. Cases:

1. No `.companion/state.json` → exit `0`, empty stdout, no files created.
2. `state.json` without `pairmode_version` → exit `0`, empty stdout, no
   `effort.db` write.
3. `effort_tracking` false → exit `0`, no reconcile, no `effort.db` write.
4. Malformed stdin (not JSON / empty / non-dict root) → exit `0`, no traceback
   on stderr.
5. tty stdin (no input piped) → exit `0`, no output.
6. Well-formed payload against a fixture project with a matching pending row →
   exit `0`, empty stdout, and the row's `outcome`/`tokens_total` non-NULL
   afterwards.
7. Thinness assertions on the hook source: exactly one call into
   `subagent_transcript`, no `import effort_db`, no `write_text`/`open(...,
   "w")`, no `print(` — mirroring the structural style
   `test_hooks.py` already uses for hook-contract checks.

Extend `tests/pairmode/test_subagent_transcript.py` with `reconcile_one` cases:

8. Payload carrying a terminal outcome → row reconciled from the payload, and
   the agent's output file is **not** read (assert via a file whose contents
   would produce a *different* outcome, or a path that does not exist).
9. Payload with no usable outcome + a terminated output file → file fallback
   path taken, distinct decision value logged.
10. Payload with no usable outcome + a mid-flush (non-terminal) output file →
    row stays pending, distinct decision logged, no partial write.
11. No matching `agent_id` → zero `effort.db` writes, distinct decision,
    returns normally.
12. Called twice with the same payload → exactly one reconcile; the second call
    is a no-op (idempotency).
13. `FAIL` outcome → row stamped `FAIL` and the attempt counter is
    **unchanged** (C6).
14. Atomicity: a payload with tokens but no resolvable outcome commits
    **neither** (inherits `_ATOMIC_RECONCILE_FIELDS`).
15. Every decision value `reconcile_one` emits is a member of
    `RECORDING_DECISIONS`.

Extend existing files:

16. `tests/pairmode/test_hooks_json.py` — `SubagentStop` present, exactly one
    block, one inner hook, command ends `hooks/subagent_stop.py`, `timeout` 5,
    no `matcher`, no `async`; and the previously-registered events are
    unchanged.
17. `tests/pairmode/test_bootstrap.py` — the `SubagentStop` spec's registration
    and its plugin-already-registered skip (step 6).
18. `tests/pairmode/test_hooks.py` — the new hook is covered by whatever
    all-hooks contract assertions the file already makes (e.g. shebang,
    `main()` guard, exit-code discipline). Do not add a second copy of an
    assertion that file already applies to every hook.

Acceptance:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_subagent_stop_hook.py \
  tests/pairmode/test_subagent_transcript.py \
  tests/pairmode/test_hooks_json.py \
  tests/pairmode/test_bootstrap.py \
  tests/pairmode/test_hooks.py -q 2>&1 | tail -30
```

then the full suite, without `-x`:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Green, modulo the known `test_observability_ui` failure demonstrated to
reproduce on clean `HEAD`.

**On the abort path (A4):** no test file is added and no test is changed. The
acceptance is the full suite green *unchanged from `HEAD`*, plus the
`## Evidence` and `## Deferred` sections. State
`TEST RUN: story aborted at Ensures A4 — no code change, no test expected`.

## Out of scope

- **Changing any completion-detection threshold.** `QUIESCENT_AGE_SECONDS`,
  `RECONCILE_MAX_AGE_DAYS`, `PENDING_MAX_AGE_DAYS`, and
  `is_reconcilable_spawn_output`'s rules keep their current values and
  semantics (A5).
- **The JSON `BUILD-RESULT.outcome` enum validation gap (CER-113).** The
  unvalidated JSON outcome assignment at `subagent_transcript.py:368` is
  INFRA-299's story. `reconcile_one` inherits whatever `parse_worker_outcome`
  does today; it does not fix it, and it must not fork it.
- **`attempts.phase` semantics (CER-105) and the
  `context_budget_acknowledged_at` misnomer (CER-106).** Both are INFRA-299,
  document-don't-change.
- **The upstream missing `stop_reason` stamp** (CER-114's named root-cause
  sibling). That is a harness defect, not a pairmode one; this story routes
  around it rather than fixing it.
- **Repairing historical pending rows** in any live `effort.db`. Backfilling
  rows stranded before this fix is an operator action, as it was for INFRA-264.
- **A pending-rows UI or dashboard surface.** `pairmode_effort.py pending`
  already provides the read-only diagnostic (INFRA-264); no new surface here.
- **`hooks/post_tool_use.py`'s launch-time recording branch.** It keeps
  inserting the row at spawn launch; this story only adds a second, earlier
  completion signal. Moving recording wholesale to `SubagentStop` would lose
  the row for spawns that never stop.
- **Retiring the quiescence sweep.** It is demoted in documentation, not
  removed — it remains the only recovery path for a crashed or unregistered
  hook.

<!-- Spec-preflight note: `reconcile_one`, `hooks/subagent_stop.py`,
     `SubagentStop`, and the new `RECORDING_DECISIONS` members do not exist in
     the codebase at spec time — they are created by this story. Any preflight
     finding naming them is intentional. -->
