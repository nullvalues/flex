---
id: INFRA-264
rail: INFRA
title: Fix the four async effort-recording defects from the INFRA-259 smoke test (CER-091)
status: draft
phase: "104"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - hooks/post_tool_use.py
  - skills/pairmode/scripts/subagent_transcript.py
  - skills/pairmode/scripts/effort_db.py
  - skills/pairmode/scripts/pairmode_effort.py
touches:
  - hooks/hooks.json
  - docs/architecture.md
  - docs/cer/backlog.md
  - tests/pairmode/test_subagent_transcript.py
  - tests/pairmode/test_effort_db.py
  - tests/pairmode/test_pairmode_effort.py
  - tests/pairmode/test_post_tool_use_hook.py
  - tests/pairmode/test_hooks_json.py
  - docs/stories/INFRA/INFRA-264.md
---

## Context

INFRA-258 made effort recording two-phase because Agent spawns are
asynchronous: a row is written at PostToolUse time with `tokens_total` and
`outcome` NULL plus the spawn's `agent_id`/`output_file`, and a later
reconciliation sweep fills it in from the spawn's own output JSONL. INFRA-259
was the live smoke test of that mechanism. The core claim held — the async loop
does close unaided (INFRA-259 § Smoke results C and F) — but the smoke test
also caught four real defects, filed together as **CER-091** (HIGH,
`docs/cer/backlog.md`). This story closes all four, plus the diagnostic gap
that made three of them hard to attribute.

**Defect 1 — a repeat spawn of the same story+role recorded nothing.** The
INFRA-259 re-review (second `reviewer` spawn, same story, same session,
harness-reported 39 230 tokens) produced **no attempts row at all** (§ Smoke
results D, finding 2). There is no `attempt_number = 2` reviewer row, and
because no row was written, no sweep ran, which is *also* why row 352 (the
first reviewer spawn) stayed pending through the rest of the session. No
code-level dedup exists that would suppress a second row — `record_effort`
inserts unconditionally and `next_attempt_number`
(`effort_db.py:326`) simply counts — so the row is missing because the
recording path never *ran*, not because it ran and declined. The reason cannot
be established after the fact: `hooks/post_tool_use.py:100` swallows every
exception from the delegated call with a bare `except Exception: pass`, and
the hook is registered only for `matcher: "Task|Agent"`
(`hooks/hooks.json`), so a continuation dispatched through `SendMessage`
(which resumes an existing agent rather than spawning one) never reaches the
hook at all. Either way the observable evidence is identical: silence. This
story's fix for defect 1 is therefore two-sided — prove by regression test
that a repeat spawn of the same `(story_id, agent_role)` pair records a second
row, and make the recording path leave an append-only trace so the *next*
occurrence is attributable in one command instead of an archaeology session.

**Defect 2 — reconcile can commit tokens without an outcome.** Row 344
(`phase:101`, `intent-reviewer`) sits at `tokens_total = 6597`, `outcome`
NULL, and the lifetime rollup counts it (§ Smoke results B and E). The root
cause is now identified and is not a race: `parse_worker_outcome`
(`subagent_transcript.py:195`) accepts a `REVIEW-RESULT` verdict only when it
is `PASS` or `FAIL` (`subagent_transcript.py:227`), but the WORKER-004 grammar
admits a third member — `ALIGNED`, the canonical intent-review verdict
(`worker_result.py:65`). An intent-reviewer's honest `ALIGNED` return is
therefore parsed as *no outcome*, `read_completed_spawn` returns tokens with
`outcome: None`, and `reconcile_pending_attempts` writes that partial state.
It then becomes permanent: `reconcile_attempt`'s single-shot guard is
`AND tokens_total IS NULL` (`effort_db.py:468`) and `pending_reconcilable`'s
filter is `tokens_total IS NULL AND output_file IS NOT NULL`
(`effort_db.py:419`), so once tokens land the row is invisible to every
future sweep and unreachable by every future update. Three things are wrong
and all three are fixed here: the grammar gap, the non-atomic write, and the
guard that makes the resulting state unrepairable.

**Defect 3 — a permanently-pending row with no diagnostic surface.** Row 343
(`phase:101`, `security-auditor`) has never reconciled across at least four
sweep opportunities while its output file demonstrably still exists on disk
(§ Smoke results B, C, F). `read_completed_spawn` returns `None` for six
distinct reasons — missing file, empty file, last entry not `assistant`, last
entry's `stop_reason != "end_turn"`, no usage data anywhere, and the
`RECONCILE_MAX_LINES` cap — and every one of them is reported to the caller as
the same bare `None` (`subagent_transcript.py:479-577`). An operator has no
way to distinguish "the agent is still running" from "this row will never
reconcile as long as this code is unchanged." The fix is a classifier that
names the reason, a read-only view that surfaces it with the row's age, and —
only on the explicit operator-invoked sweep, never on the hook path — a
bounded escape hatch for rows whose output file has gone quiescent.

**Defect 4 — reconciliation-time counter bumps have no lifecycle guard.**
Row 352's FAIL reconciled at a later spawn's PostToolUse *after*
`merge-story-worktree` had already cleared the attempt counter, recreating
`.companion/attempt_counter.json` as `{INFRA-259: 1}` for a story that was
already merged. `reconcile_pending_attempts` bumps whenever the resolved
outcome is FAIL and the story id carries no `:`
(`subagent_transcript.py:691-697`); it never asks whether the story is still
being built. The counter is not observability — `next_action.infer_position`
reads it as the escalation ladder's durable signal — so a resurrected counter
is live control state pointing at a finished story. The bump is correct at
PostToolUse time (the story is active by construction, it was just spawned
for) and unsafe at reconciliation time (arbitrarily later, possibly
post-merge, possibly post-`/clear`). The guard therefore goes on the
reconciliation call site only.

**The trigger-coverage gap, observed live 2026-07-25.** An async builder
spawn's row sat at `outcome = NULL` until a manual sweep was run by hand.
Reconciliation has exactly two triggers today
(`docs/architecture.md` § Effort tracking, "Reconciliation trigger points"):
the *next* Task/Agent PostToolUse, and `hooks/session_start.py`. A session's
final spawn is covered by neither until some later session happens to start —
and if the operator wants the rollup *now*, at a checkpoint, there is no
supported command to ask for it. `SessionEnd` was considered and rejected in
INFRA-258 for good reason (`async: true`, 30 s timeout, not
guaranteed-to-complete) and that rejection stands; this story adds the
*explicit* third trigger instead — an operator-invocable CLI sweep over the
same function, so "reconcile the tail rows now" is one documented command
rather than an ad-hoc `python -c`.

**Why the sweep CLI lives on `subagent_transcript.py` and not
`flex_build.py`.** `flex_build.py` is contended in this phase — INFRA-263,
INFRA-265 and INFRA-267 all edit it, and phase 104's `## Ordering` serialises
those separately from this story's group precisely to avoid worktree merge
conflicts. Adding a subcommand there would put INFRA-264 in both groups.
`subagent_transcript.py` already owns `reconcile_pending_attempts` and is
already a primary file of this story, so a thin `__main__` CLI over the
existing function adds a trigger without adding a file to the contended set.
`effort_db.py` sets the precedent for a script-module CLI (`_cli_main`,
`effort_db.py:626`).

## Recon

Verified by reading the files at HEAD; line numbers are anchors for the
builder, not assertions to preserve.

| Anchor | What is there now |
|---|---|
| `hooks/hooks.json` PostToolUse block | two matchers: `Write\|Edit\|MultiEdit` and `Task\|Agent`. `SendMessage` is registered nowhere. |
| `hooks/post_tool_use.py:56` | `if tool_name in ("Task", "Agent")` — two independently-wrapped delegated calls; the second (`subagent_transcript.record_attempt_from_transcript`, line 93) is wrapped in `except Exception: pass` (line 100). `tool_name` is not passed to the module. |
| `subagent_transcript.py:195` `parse_worker_outcome` | `BUILD-RESULT.outcome` accepted verbatim; `REVIEW-RESULT.verdict` accepted only when `in ("PASS", "FAIL")` (line 227). `ALIGNED` is silently dropped. |
| `worker_result.py:65` | `REVIEW_RESULT` enum is `{"PASS", "FAIL", "ALIGNED"}`; the security-auditor and intent-reviewer both return `REVIEW-RESULT` (`skills/pairmode/skills/security-auditor/procedure.md:217`). |
| `subagent_transcript.py:479` `read_completed_spawn` | returns `None` for six distinct conditions, indistinguishably. Streams the file, caps at `RECONCILE_MAX_LINES` (20 000). |
| `subagent_transcript.py:627` `reconcile_pending_attempts` | `effort_tracking` early return; `pending_reconcilable(db, limit)`; per row `read_completed_spawn` → `reconcile_attempt`; FAIL → `bump_attempt_count` with only a `":" not in story_id` guard (line 693). |
| `effort_db.py:394` `pending_reconcilable` | `WHERE tokens_total IS NULL AND output_file IS NOT NULL ORDER BY id DESC LIMIT ?`. |
| `effort_db.py:434` `reconcile_attempt` | fixed allow-list `_RECONCILABLE_COLUMNS` (`effort_db.py:92`); `UPDATE ... WHERE id = ? AND tokens_total IS NULL`; writes whatever subset of the allow-list the caller supplied. |
| `flex_build.py:935` `bump_attempt_count` | reads via `read_attempt_count` (0 when the file is absent *or* records another story) and writes `count + 1` — so a bump for an absent file creates it at 1. This is the resurrection mechanism. |
| `flex_build.py:1007` `clear_attempt_count` | unlinks the file; called by `merge-story-worktree`. |
| `hooks/session_start.py:103` | already sweeps via `reconcile_pending_attempts` (INFRA-258). The SessionStart trigger exists; the missing one is an explicit operator-invoked sweep. |
| `pairmode_effort.py:577` | `click` group with five commands, `_common` option decorator (`--project-dir`, `--db-path`, `--dollars`, `--json`), `_connect_or_none` + `_emit` helpers. Adding a sixth read-only command is idiomatic here. |
| `tests/pairmode/test_hooks_json.py:82` | asserts PreToolUse matcher coverage only; PostToolUse matchers are unasserted. |

## Requires

- INFRA-258 is complete: `effort_db.set_spawn_ref`, `effort_db.pending_reconcilable`,
  `effort_db.reconcile_attempt`, `subagent_transcript.read_completed_spawn`,
  `subagent_transcript.reconcile_pending_attempts` and the
  `agent_id`/`output_file` columns all exist.
- INFRA-259 is complete and its `## Smoke results` section (§§ A–F) is on
  disk — it is this story's evidence base and must not be edited.
- `docs/cer/backlog.md` contains a `CER-091` row under `## Do Later` whose
  `Phase` cell reads `102`.
- `docs/phases/phase-104.md` lists INFRA-264 in its Stories table.
- INFRA-263 is merged (phase 104 `## Ordering`: build order 263 → 264). This
  story does not edit `flex_build.py`, so the dependency is ordering
  hygiene, not a code dependency.
- Known environmental note: story worktrees are expected to build the vendored
  observability tree cleanly since INFRA-261 closed CER-090. If
  `test_observability_ui.py::test_ui_build_emits_dist_index_html` fails, verify
  it reproduces on clean `HEAD` before attributing it to this diff.

## Ensures

Numbered assertions; the reviewer verifies each independently from the diff
and the test run.

**E1. `ALIGNED` is a recognised verdict.** `parse_worker_outcome` in
`skills/pairmode/scripts/subagent_transcript.py` returns
`("ALIGNED", None)` for a flattened response containing
`{"type": "REVIEW-RESULT", "verdict": "ALIGNED", "findings": [], "reason": "..."}`.
`PASS` and `FAIL` return unchanged. The accepted set is expressed as a
module-level frozenset (not an inline tuple literal) whose members are exactly
`PASS`, `FAIL`, `ALIGNED`, with a comment citing `worker_result.py`'s
`REVIEW_RESULT` enum as its source of truth. A verdict string outside that set
(e.g. `MAYBE`) still yields `None`.

**E2. Reconciliation is atomic over tokens *and* outcome.**
`effort_db.reconcile_attempt(path, row_id, **fields)` returns `False` and
performs **no** `UPDATE` unless both `tokens_total` and `outcome` are present
in `fields` **and** both are non-`None`. The required pair is a module-level
constant (e.g. `_ATOMIC_RECONCILE_FIELDS`), not two inline string literals.
The existing fixed allow-list behaviour (`_RECONCILABLE_COLUMNS`, unknown
kwargs silently ignored, `story_id`/`agent_role`/`attempt_number`/`phase`/
`rail`/`ts` never written) is unchanged.

**E3. A partially-backfilled row is reachable again.**
`reconcile_attempt`'s `WHERE` clause is
`WHERE id = ? AND (tokens_total IS NULL OR outcome IS NULL)`, and
`effort_db.pending_reconcilable`'s filter is
`WHERE (tokens_total IS NULL OR outcome IS NULL) AND output_file IS NOT NULL`.
A row with `tokens_total` set and `outcome` NULL (the row-344 shape) is
returned by `pending_reconcilable` and can be completed by
`reconcile_attempt`; a row with **both** set is returned by neither and
updated by neither (single-shot preserved — a repeat call for a fully
reconciled row returns `False` and cannot double-bump).

**E4. The hook path never commits a partial row.** In
`reconcile_pending_attempts`, a `read_completed_spawn` result whose `outcome`
is `None` is skipped — no `reconcile_attempt` call, the row stays pending, the
returned reconciled count does not include it. (With E1 in place the common
`ALIGNED` case no longer reaches this branch; the branch exists so an
unparseable return leaves a *pending* row rather than a *partial* one.)

**E5. Pending rows carry a machine-readable reason.**
`subagent_transcript.classify_pending_reason(row) -> str` exists, is pure
(no writes, no db access — it takes an already-fetched row dict), never
raises, and returns exactly one of these literals, defined as a module-level
tuple/frozenset so the set is enumerable by tests and by the view in E6:

| value | condition |
|---|---|
| `no-output-file` | row's `output_file` is falsy |
| `file-missing` | `output_file` set, path does not exist |
| `file-empty` | path exists, no parseable JSONL entries |
| `in-flight` | last parseable entry is `assistant` with `stop_reason` present and not `end_turn` |
| `not-terminated` | last parseable entry is not an `assistant` entry (or has no `message` dict) |
| `no-usage` | terminated correctly but no `usage` data anywhere in the file |
| `line-cap` | file exceeds `RECONCILE_MAX_LINES` |
| `no-outcome` | complete and usage present, but `parse_worker_outcome` yields `None` |
| `reconcilable` | none of the above — the next sweep will complete this row |

The classifier reuses the same streaming read discipline as
`read_completed_spawn` (`for line in fh:`, `RECONCILE_MAX_LINES` cap, never
`read_text()`/`readlines()`) — verified by a test that monkeypatches
`Path.read_text` to raise.

**E6. A read-only pending view exists.**
`skills/pairmode/scripts/pairmode_effort.py` exposes a `pending` command that
prints one line per row matching `pending_reconcilable`'s filter, with at
least the columns `id`, `story_id`, `agent_role`, `attempt_number`,
`age_hours`, `has_tokens`, `has_outcome`, `reason`. `age_hours` is derived
from the row's `ts` against `datetime.now(timezone.utc)`, rendered to one
decimal. The command honours the existing `--project-dir` / `--db-path` /
`--json` options via the module's `_common` decorator, opens the database
through SQLite's read-only URI mode (`file:...?mode=ro`, `uri=True`),
performs **zero** writes, and exits 0 both when rows exist and when none do.
A test asserts the db file's mtime and byte content are unchanged across an
invocation.

**E7. An explicit sweep trigger exists.** `subagent_transcript.py` gains a
`__main__` CLI:

```bash
uv run python skills/pairmode/scripts/subagent_transcript.py reconcile \
  --project-dir . [--limit N] [--include-quiescent] [--json]
```

It calls the **same** `reconcile_pending_attempts` function the two hook call
sites use — no second reconciliation implementation exists in the tree
(asserted by a test that patches `reconcile_pending_attempts` and observes the
CLI route through it). It prints the number of rows reconciled and exits 0
even when that number is 0. `--limit` defaults to `RECONCILE_MAX_ROWS`.
Importing the module still has no side effects (the CLI is behind
`if __name__ == "__main__":`), so the hook import path is unaffected.

**E8. Quiescent rows can be retired, but only deliberately.**
`reconcile_pending_attempts` accepts a keyword-only `include_quiescent: bool = False`.
Both hook call sites (`record_attempt_from_transcript` and
`hooks/session_start.py`) leave it at its default — asserted by a grep-level
test that neither call site passes the argument. When `True`, a row whose
`classify_pending_reason` is *not* `reconcilable`/`in-flight`/`file-missing`/
`no-output-file`, whose `ts` is older than `QUIESCENT_AGE_SECONDS` (a
module-level constant, default 900), **and** whose `output_file` mtime is
older than the same threshold, is reconciled from whatever usage the file
contains, with `outcome = "UNKNOWN"` when no verdict is parseable and `notes`
prefixed `reconciled-quiescent:` naming the classifier reason. A quiescent
reconciliation **never** calls `bump_attempt_count` — `UNKNOWN` is not `FAIL`,
and a fabricated escalation is worse than a missing one. Rows with no usage
data at all are still skipped (there is nothing truthful to write).

**E9. The reconciliation-time counter bump has a story-lifecycle guard.**
A helper — `subagent_transcript._story_accepts_late_bump(project_dir, story_id) -> bool`
— gates the `bump_attempt_count` call inside `reconcile_pending_attempts`. It
returns `False` (bump skipped) when **either**:

1. the story's own file `docs/stories/<RAIL>/<story_id>.md` is readable and its
   frontmatter `status` is one of `complete`, `merged`, `deferred`, `backlog`; **or**
2. `.companion/attempt_counter.json` does not already record this
   `story_id` **and** `.companion/state.json`'s `current_story` does not
   resolve to this `story_id` — i.e. the loop is not currently building it, so
   a bump would *create* a counter file for a story nobody is working on.

It returns `True` otherwise, is a pure read (no writes on any path), and never
raises — an unreadable story file or state file falls through to rule 2. The
synchronous PostToolUse bump in `record_attempt_from_transcript`
(`subagent_transcript.py:770`) is **not** gated: the story was just spawned
for, so it is active by construction, and gating it would risk dropping a real
first FAIL. This asymmetry is stated in a code comment with that reason.

Forward-compatibility (CER-095.3): rule 2's semantics are per-story — "does
`.companion/attempt_counter.json` already record *this* `story_id`, and does
`.companion/state.json`'s `current_story` resolve to *this* `story_id`" — not
"is there exactly one counter/current-story slot." The implementation must not
assume either store can hold only one story at a time; when INFRA-282 (phase
109) converts both to story-keyed dicts, `_story_accepts_late_bump`'s logic
must keep working unchanged aside from a mechanical accessor swap (e.g. a dict
lookup by `story_id` in place of a single-value read).

**E10. The recording path leaves an attributable trace.**
`subagent_transcript.log_recording_event(project_dir, **fields) -> None`
appends one JSON object per line to `.companion/effort_recording.log`,
carrying at minimum `ts` (UTC ISO-8601), `tool_name`, `subagent_type`,
`tool_use_id`, `story_id`, `decision`, and `row_id`. `decision` is drawn from
an enumerated module-level set including at least `recorded`,
`skip:not-recordable-role`, `skip:no-tool-input`, `skip:no-state`,
`skip:effort-tracking-off`, `error:<ExceptionClassName>`, and
`observed:non-spawn-tool`. The function never raises and is bounded: when the
file exceeds `RECORDING_LOG_MAX_BYTES` (module-level constant, default
262 144) it is truncated and restarted with a single
`{"ts": ..., "decision": "log-truncated"}` line before the new entry. It is
**not** gated on `effort_tracking` — the log's purpose is to explain why
recording did or did not happen, including when tracking is off.
`record_attempt_from_transcript` calls it exactly once per invocation, on
every return path including the outer `except`.

**E11. The hook relays the missing dispatch path without gaining logic.**
`hooks/post_tool_use.py`'s spawn branch matches
`tool_name in ("Task", "Agent", "SendMessage")`; for `SendMessage` it makes
exactly one delegated call — `subagent_transcript.log_recording_event(...)`
with `decision="observed:non-spawn-tool"` — and does **not** call
`record_attempt_from_transcript` (a continuation is not a spawn; recording
rows for it is out of scope). For `Task`/`Agent` the existing two delegated
calls are unchanged except that `tool_name` is now passed through to
`record_attempt_from_transcript`, and the `except Exception` around it calls
`log_recording_event` with `decision="error:<ExceptionClassName>"` inside its
own nested `try/except`. The hook itself performs **no** file reads, **no**
JSON parsing beyond the existing stdin load, and **no** writes — every write
in this story is performed by a skill script, preserving
`docs/ideology.md` § "Hooks are thin relays only" and § "Sidebar owns all
state writes" (see `## Instructions` step 9). The net addition to
`hooks/post_tool_use.py` is under 20 lines.

**E12. The hook registration covers the relayed tool.** `hooks/hooks.json`'s
PostToolUse `Task|Agent` matcher reads `Task|Agent|SendMessage`, its inner
hook command and timeout unchanged. A new test in
`tests/pairmode/test_hooks_json.py` asserts that every tool name the
`post_tool_use.py` spawn branch dispatches on is covered by a registered
**PostToolUse** matcher — the PostToolUse mirror of the existing
`test_pretooluse_matchers_cover_all_dispatched_tool_names` (INFRA-205 /
CER-065), so this class of dead branch cannot recur.

**E13. Regression tests exist for each of the four defects**, each named for
the defect it pins, all passing:

- **Defect 1** — `tests/pairmode/test_subagent_transcript.py`: two consecutive
  `record_attempt_from_transcript` calls for the same `(story_id, "reviewer")`
  pair in one session, with the **first row still pending** (`tokens_total`
  NULL, `output_file` set to an in-flight file), produce **two** rows with
  `attempt_number` 1 and 2 — the pre-write sweep must not suppress the second
  row. A companion test asserts both invocations appended a line to
  `.companion/effort_recording.log` with `decision == "recorded"`.
- **Defect 2** — `tests/pairmode/test_effort_db.py`: `reconcile_attempt` with
  `tokens_total` but no `outcome` returns `False` and leaves the row
  byte-identical; with both, returns `True`. `pending_reconcilable` returns a
  tokens-set/outcome-NULL row (the row-344 shape) and omits a fully-reconciled
  one. In `test_subagent_transcript.py`: an output file whose final message is
  `{"type": "REVIEW-RESULT", "verdict": "ALIGNED", ...}` reconciles to
  `outcome == "ALIGNED"` with non-NULL tokens (the live row-344 scenario, end
  to end).
- **Defect 3** — `test_subagent_transcript.py`: `classify_pending_reason`
  returns the correct literal for each row in E5's table (one case per value,
  including `line-cap`); a `not-terminated`/`no-usage` row is left pending by
  a default sweep and retired to `outcome == "UNKNOWN"` by an
  `include_quiescent=True` sweep once both age conditions are met, with
  `notes` naming the reason and **no** counter bump. In
  `test_pairmode_effort.py`: `pending` renders the reason and a numeric
  `age_hours` for a seeded pending row, and writes nothing to the db.
- **Defect 4** — `test_subagent_transcript.py`: a FAIL row reconciling for a
  story whose story file frontmatter reads `status: complete` leaves
  `.companion/attempt_counter.json` **absent** (not resurrected); the same
  FAIL row for a story that is `state.json["current_story"]` and `status:
  draft` still bumps to 1; a FAIL row for a story that is neither current nor
  counter-recorded does not create the file. The existing INFRA-258 tests
  `test_reconciled_fail_bumps_attempt_counter` and
  `test_counter_bumps_at_most_once_per_row` still pass (adjust their fixtures
  to satisfy the new guard rather than weakening the guard).

**E14. Documentation records the mechanism.** `docs/architecture.md` is
updated in place — no new `##`-level heading — with:

(a) a **state-ownership table** row (§ (b), `docs/architecture.md:1474`) for
`.companion/effort_recording.log` naming
`subagent_transcript.log_recording_event` as sole writer (hooks relay, never
write) and the resolver as read-only, plus an amendment to the existing
`attempt_counter.json` row recording the new reconciliation-time lifecycle
guard and why the PostToolUse bump is deliberately ungated;

(b) § Effort tracking updates: atomic tokens+outcome reconciliation and the
`(tokens_total IS NULL OR outcome IS NULL)` guard replacing the
`tokens_total IS NULL` one; `ALIGNED` as a recorded outcome value and
`UNKNOWN` as the quiescent-retirement marker (with the note that read-side
PASS-rate views count only `PASS` — see `## Out of scope`); the pending-reason
classifier and its nine values; the third reconciliation trigger (explicit
CLI) added to the existing "Reconciliation trigger points and their bounds"
paragraph, with the `SessionEnd` rejection restated as still standing and the
reason the CLI lives on `subagent_transcript.py` rather than `flex_build.py`;
the `pending` view added to the "How to use it" list (which currently says
"five read-time views" — update the count);

(c) an update to the "Accepted losses" list: the third bullet (`/tmp`
eviction) now names `file-missing` as the classifier value that makes the loss
*visible*, and a new bullet records that a `SendMessage` continuation of an
existing agent is logged but never recorded as an attempts row.

**E15. CER-091 is closed in place.** The `CER-091` row in
`docs/cer/backlog.md` carries a bolded resolution note naming INFRA-264 and
each of the four defects' fixes, and its `Phase` cell reads `104`. The row is
not deleted, reworded, or moved — `docs/cer/backlog.md:6` requires resolved
findings to remain in place with a resolution note.

**E16. No new persistent schema object.** No `ALTER TABLE`, no new table, no
new column: every fix uses the existing `attempts` schema.
`.companion/effort_recording.log` is an append-only, size-capped diagnostic
log, not a schema object — it is explicitly the audit-log exception under
CLAUDE.md § Conceptual rebuild completeness, and it is observable via
`pairmode_effort.py pending` (for the pending rows it explains) and `tail`.
`schema_introduces: false` stands and phase 104's Schema-delivery table stays
empty.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Do not edit `skills/pairmode/scripts/flex_build.py` (contended this phase —
see `## Context`); do not edit `docs/stories/INFRA/INFRA-259.md` (it is
evidence); do not run any `UPDATE` against the live `.companion/effort.db`.

1. **`parse_worker_outcome` — accept `ALIGNED`** (E1). Replace the inline
   `verdict in ("PASS", "FAIL")` check at `subagent_transcript.py:227` with a
   membership test against a new module-level
   `RECOGNISED_REVIEW_VERDICTS: frozenset[str] = frozenset({"PASS", "FAIL", "ALIGNED"})`,
   commented with the reason: the set mirrors `worker_result._SCHEMAS`'s
   `REVIEW_RESULT` verdict enum, and dropping `ALIGNED` is what stranded row
   344. Do not import `worker_result` here — this module is on the hook path
   and must stay import-light; the comment carries the coupling.

2. **`effort_db.reconcile_attempt` — atomic and repairable** (E2, E3). Add
   `_ATOMIC_RECONCILE_FIELDS: tuple[str, ...] = ("tokens_total", "outcome")`
   next to `_RECONCILABLE_COLUMNS`. Early-return `False` when either is absent
   from `fields` or present-but-`None`. Change the `WHERE` clause to
   `WHERE id = ? AND (tokens_total IS NULL OR outcome IS NULL)`. Update the
   docstring: the guard is no longer "single-shot on tokens" but "single-shot
   on *fully reconciled*", which is what makes an existing partial row
   repairable while still making a double-bump impossible.

3. **`effort_db.pending_reconcilable` — include partial rows** (E3). Change
   the filter to `(tokens_total IS NULL OR outcome IS NULL) AND output_file IS NOT NULL`.
   Keep `ORDER BY id DESC`, the bound `LIMIT ?`, the non-positive-limit guard,
   and the never-raises contract untouched. Note in the docstring that the
   partial-row case is the row-344 shape from CER-091.

4. **`classify_pending_reason`** (E5). New pure function in
   `subagent_transcript.py`, placed immediately before `read_completed_spawn`
   so the two read the same way. Factor the file walk so the classifier and
   `read_completed_spawn` share one streaming reader rather than duplicating
   the loop — a second, divergent reader is exactly how the six-way `None`
   became opaque in the first place. Keep `read_completed_spawn`'s public
   signature and return shape unchanged (other callers and INFRA-258's tests
   depend on it); it may gain an internal call into the shared reader.

5. **`reconcile_pending_attempts` — skip partials, add the quiescent path**
   (E4, E8). Skip any result whose `outcome` is `None` unless the quiescent
   branch applies. Add keyword-only `include_quiescent: bool = False`. In the
   quiescent branch, take `usage` from the shared reader, set
   `outcome = "UNKNOWN"`, and set `notes` to
   `f"reconciled-quiescent: {reason}"`. Age is checked twice — the row's `ts`
   *and* the output file's mtime — because a row can be old while its agent is
   still writing, and reconciling a live agent is the one thing INFRA-258's
   completion detection exists to prevent. Never call `bump_attempt_count`
   from this branch.

6. **The lifecycle guard** (E9). Add `_story_accepts_late_bump` and gate the
   existing FAIL bump at `subagent_transcript.py:691-697` on it. Derive the
   rail as the substring before the first `-` (the same derivation
   `_derive_attribution` already uses at line 470) to locate
   `docs/stories/<RAIL>/<story_id>.md`. Parse only the `status:` line from the
   frontmatter with a small local regex — do **not** import
   `schema_validator` or any other heavyweight module into this hook-path
   file. Leave the PostToolUse-time bump ungated and write the one-line reason
   as a comment.

7. **The recording log** (E10). Add `log_recording_event` and the
   `RECORDING_LOG_MAX_BYTES` cap. Write with a plain append (`open(path, "a")`)
   — this is an append-only log, not state, so the atomic-replace machinery in
   `state_utils` is neither needed nor appropriate. `mkdir(parents=True,
   exist_ok=True)` the `.companion/` directory first. Call it from
   `record_attempt_from_transcript` on **every** return path, including the
   outer `except Exception` (nested in its own `try/except` there — a logging
   failure must never change the function's never-raises contract). Add
   `tool_name: str | None = None` as a keyword parameter to
   `record_attempt_from_transcript` so the log can record which tool
   dispatched; default `None` keeps every existing caller and test valid.

8. **The hook and its registration** (E11, E12). In
   `hooks/post_tool_use.py`, widen the branch tuple to include
   `"SendMessage"`, route `SendMessage` to a single `log_recording_event`
   call, pass `tool_name=tool_name` into `record_attempt_from_transcript`, and
   add the `log_recording_event` call in the existing `except`. Update the
   module docstring's numbered list of delegated calls. In `hooks/hooks.json`,
   change the PostToolUse matcher `Task|Agent` to `Task|Agent|SendMessage`,
   leaving the command and timeout untouched. Add the PostToolUse
   matcher-coverage test to `tests/pairmode/test_hooks_json.py`, mirroring the
   existing PreToolUse one.

9. **Ideology note (Step 4a — resolved inline, no conflict).** Three entries
   in `docs/ideology.md` shaped the design above and the resolutions are
   recorded here rather than left implicit. **"Hooks are thin relays only"
   (no override permitted)** is why the diagnostic log is written by
   `subagent_transcript.log_recording_event` and merely *called* from the
   hook: the hook gains a tuple member and two delegated calls, no reads, no
   parsing, no writes — the same shape it already had for effort.db.
   **"Sidebar owns all state writes"** is why `.companion/effort_recording.log`
   has exactly one writer, and why the new `pending` view is strictly
   read-only (`mode=ro` URI) rather than a "show and repair" command: the
   repair path is a separate, explicit CLI (E7) so a diagnostic read can never
   mutate what it is diagnosing. **"Never silently pass contradictions"** is
   the whole shape of this story — every one of the four defects was a silent
   pass (a swallowed exception, a dropped verdict, a six-way `None`, an
   ungated bump), and each fix replaces the silence with a named, enumerable
   value rather than merely making the happy path more likely.

10. **`pairmode_effort.py pending`** (E6). Add the sixth command next to
    `models_cmd`, decorated with `@_common`, reusing `_emit` for table/JSON
    output and `_render_cell` for formatting. Open the database read-only via
    `sqlite3.connect(f"file:{db}?mode=ro", uri=True)` rather than
    `_connect_or_none` (which opens read-write); handle the missing-file and
    empty-table cases with the existing `_no_data_message()`. Call
    `subagent_transcript.classify_pending_reason` for the `reason` column —
    import it lazily inside the command body so the reporting CLI does not
    take a module-import dependency on the hook path at startup.

11. **The sweep CLI** (E7). Add an `argparse` (not `click` — this module has no
    click dependency and is imported by hooks; keep it stdlib-only) `main()`
    behind `if __name__ == "__main__":` in `subagent_transcript.py`, with the
    single `reconcile` subcommand and the flags in E7. It must be a thin shell
    over `reconcile_pending_attempts` — argument parsing, one call, one printed
    line, `return 0`.

12. **Close CER-091** (E15): append the bolded resolution note to the existing
    row's Finding cell and set its `Phase` cell to `104`. Leave the row where
    it is, under `## Do Later`.

13. **Documentation** (E14): make the three `docs/architecture.md` edits.
    Every one of them must carry its *reason*, not just its rule — the
    `ALIGNED` gap and the `tokens_total IS NULL` guard were both individually
    reasonable decisions whose interaction produced an unrepairable row, and a
    future editor "simplifying" either one back needs to be able to read why
    they are the shape they are.

14. **Do not** attempt to repair the live rows 343/344 in
    `/mnt/work/flex/.companion/effort.db` as part of the build. They are the
    field cases the new code should be able to handle, and the orchestrator
    may run the new CLI against them after merge; a builder writing directly
    to the live database would destroy the evidence and the verification
    opportunity in one step.

## Tests

Run from the story worktree root. Targeted first:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_subagent_transcript.py \
  tests/pairmode/test_effort_db.py \
  tests/pairmode/test_pairmode_effort.py \
  tests/pairmode/test_post_tool_use_hook.py \
  tests/pairmode/test_post_tool_use.py \
  tests/pairmode/test_hooks_json.py \
  tests/pairmode/test_session_start_hook.py \
  -q 2>&1 | tail -30
```

Then the full suite, **without `-x`**, so a known failure cannot mask a new
one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Acceptance:

- every new test from E13 passes, with each defect's tests named for the
  defect they pin;
- the existing INFRA-258 reconciliation tests
  (`test_reconciles_a_pending_row`, `test_in_flight_spawn_not_reconciled`,
  `test_reconciled_fail_bumps_attempt_counter`,
  `test_counter_bumps_at_most_once_per_row`,
  `test_checkpoint_phase_row_fail_does_not_bump`,
  `test_dp7_state_json_byte_identical_across_reconciliation`,
  `test_async_launch_then_reconcile`) all still pass — fixtures may be
  extended to satisfy the new guard, but no assertion may be weakened or
  deleted;
- `test_session_start_hook.py` still passes unchanged: SessionStart's sweep
  keeps the default `include_quiescent=False`;
- the full suite is green.

Manual verification of the two read paths, recorded in the build result:

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/pairmode_effort.py \
  pending --project-dir .
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/subagent_transcript.py \
  reconcile --project-dir . --help
```

The first must exit 0 and print a table (or the no-data message) without
modifying `.companion/effort.db`; the second must exit 0 and show the flags.
Do **not** run the sweep itself against the live database (Instructions
step 14).

Documentation-only assertions (E14, E15) are verified by the reviewer from the
diff. E16 is machine-checkable:

```bash
git diff -- skills/pairmode/scripts/effort_db.py | grep -c 'ALTER TABLE'   # must print 0
```

## Out of scope

- **Read-side treatment of the new outcome values.** `ALIGNED` and `UNKNOWN`
  are written by this story but no rollup, PASS-rate, or `validate-rebalance`
  query is taught about them — `pairmode_effort.py models` will continue to
  score an `ALIGNED` intent-review as not-a-PASS. That is a read-side change
  across several queries with its own test surface; it belongs in a separate
  finding, and the orchestrator should route it. Fixing the *write* side first
  is deliberate: no read-side change is meaningful while the value being read
  is NULL.
- **Excluding partially-backfilled rows from existing rollups.** INFRA-259 § E
  observed the lifetime rollup counting row 344's median from an
  outcome-NULL row. E2/E3 stop new partial rows from being created and make
  the existing one repairable; changing what the rollup *counts* is the
  read-side story above.
- **Repairing rows 343/344 in the live database.** An operator action after
  merge, not a build action (Instructions step 14). Rows ≤ 342 remain
  permanently unrecoverable per INFRA-259's `## Accepted limitations`.
- **Recording an attempts row for a `SendMessage` continuation.** This story
  makes the path *visible* in the recording log; deciding whether a
  continuation is a new attempt (and if so how `attempt_number` and the
  spawn's `output_file` are derived for it) is a modelling question, not a
  defect fix.
- **A `SessionEnd` reconciliation sweep.** Considered and rejected in
  INFRA-258 for reasons that still hold (`async: true`, 30 s timeout, not
  guaranteed to complete). The explicit CLI (E7) covers the same rows
  deterministically. Reopening this needs a story carrying the counter-argument.
- **Adding the sweep to the checkpoint sequence** — e.g. a
  `record-checkpoint-step`-adjacent "reconcile before rollup" step. It is the
  obvious next move now that the CLI exists, but it edits `flex_build.py` and
  `CLAUDE.build.md`, both contended in phase 104.
- **Root-causing defect 1 to a specific mechanism.** The evidence for the
  single observed occurrence is gone. This story proves no code-level dedup
  causes it (E13, defect 1) and guarantees the next occurrence is
  attributable in one `tail` (E10–E12); it does not speculate further in
  code.
- **`effort_db.py` hardening items** — bounded `pending_reconcilable` scan
  semantics, `output_file` containment, path-guard parity. Those are CER-088 /
  CER-089 / CER-016 and belong to **INFRA-266**, the next story in this phase
  and the other member of this story's serialisation group. Do not
  opportunistically fix them here; the ordering exists to keep the two diffs
  separable.
- **Fleet rollout.** No sibling project is synced with the new hook matcher or
  the new CLI by this story.
