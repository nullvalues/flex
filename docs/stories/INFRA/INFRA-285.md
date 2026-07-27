---
id: INFRA-285
rail: INFRA
title: "Side-session safety: session-scoped context accounting, atomic state writers, advisory state lock (CER-097)"
status: complete
phase: "109"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/session_state.py
  - skills/pairmode/scripts/state_utils.py
  - skills/pairmode/scripts/context_budget.py
  - skills/pairmode/scripts/subagent_transcript.py
  - skills/pairmode/scripts/effort_db.py
  - hooks/session_start.py
  - hooks/post_tool_use.py
  - hooks/pre_tool_use.py
touches:
  - docs/architecture.md
  - skills/pairmode/scripts/user_turn_seq.py
  - skills/pairmode/scripts/sync.py
  - skills/pairmode/scripts/phase_new.py
  - skills/pairmode/scripts/story_update.py
  - skills/pairmode/scripts/story_context.py
  - tests/pairmode/test_session_state.py
  - tests/pairmode/test_state_utils.py
  - tests/pairmode/test_context_budget.py
  - tests/pairmode/test_session_start_hook.py
  - tests/pairmode/test_post_tool_use.py
  - tests/pairmode/test_subagent_transcript.py
  - tests/pairmode/test_effort_db.py
  - tests/pairmode/test_user_turn_seq.py
  - docs/cer/backlog.md
  - docs/stories/INFRA/INFRA-285.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase 109 restores **one orchestrator running parallel story builds**. INFRA-280..283
made the *coordination* state story- and phase-keyed; INFRA-284 made the *effort
ledger* survive concurrent writers. This story closes the last shared-state hole:
the **companion state file and the context-budget accounting built on top of it**,
which are still global to the project and are written by *every* Claude Code session
that has the plugin's hooks installed — including a purely-investigative side
session the operator opened to read a file.

CER-097 (HIGH) names four live corruptions plus two structural gaps:

**A — SessionStart clobbers the build loop's context counter.**
`hooks/session_start.py:72-93` delegates to `session_reset.decide_reset()` and, on
`startup`/`clear`/`compact`, writes `context_current_tokens`,
`context_current_tokens_recorded_at`, and `context_session_reset_at` to the single
global `state.json`. A second session starting mid-build resets the counter to the
`DEFAULT_BASELINE_TOKENS` (25 000) of *its own* fresh window. The build loop's
budget gate (`hooks/pre_tool_use.py:120` → `context_budget.decide`, which reads
those same flat keys at `context_budget.py:734-760`) then evaluates the loop's next
builder spawn against a window it is not in — under-blocking by however much the
loop had actually accumulated.

**B — both sessions' PostToolUse write the same token key from different
transcripts.** `hooks/post_tool_use.py:91-113` derives a live count from *its own*
session's JSONL (`context_budget.read_current_tokens(project_dir, session_id)`) and
writes it, plus a `record_step_growth()` sample, into the same flat keys. Two
sessions interleaving produce a `context_step_growth_samples` ring buffer whose
deltas are differences between two unrelated windows, and `expected_step_tokens` is
re-derived from that mixture on every write (`context_budget.py:447-500`) — so the
corruption propagates into the gate's forward estimate, not just its display.

**C — every SessionStart sweeps the other session's live effort rows.**
`session_start.py:103-107` calls `subagent_transcript.reconcile_pending_attempts`
with no ownership filter. INFRA-284 (CER-096 item D) built the mechanism to fix this
— `effort_db.pending_reconcilable` gained an escaped-LIKE `output_prefix` ownership
filter and an `order` parameter, threaded through `reconcile_pending_attempts` — and
explicitly left the wiring here: *"wiring a real session-scoped `output_prefix` value
at any call site is INFRA-285's (CER-097)"*. Today the parameter exists and every
call site passes `None`.

**D — the sweep can bump another story's attempt counter.** The reconciliation-time
FAIL bump is gated by `subagent_transcript._story_accepts_late_bump`
(`subagent_transcript.py:907-...`), which INFRA-282 already taught to resolve
liveness against the story-keyed `current_stories` record. That guard stops a bump
for a story *nobody* is building; it does not stop a side session from bumping a
story that the *build loop* is actively building, because from the counter's point
of view that story is live. Fixing C fixes D by construction — a session that never
reaches another session's rows never bumps their counters — so D gets an assertion
here, not its own mechanism.

**E — non-atomic whole-file writers.** `user_turn_seq.record_user_turn` does a
read-modify-write of the *entire* `state.json` on every prompt in every session and
persists it with a bare `state_path.write_text(...)` (`user_turn_seq.py:125`). A
torn write there is not a lost counter — it is a truncated `state.json`, and every
reader in the system fails open on `JSONDecodeError`, so the observable symptom is
the whole companion state silently reverting to defaults. `sync.py:650` has the same
shape for state.json; `phase_new.py:201,231` and `story_update.py:111,211` have it
for the phase index and story/phase markdown. `state_utils._atomic_write_json`
(INFRA-200) has existed for exactly this since CER-050 — these sites simply never
adopted it. (`pairmode_register.py:89-98` and `pairmode_sync.py:768-775` already
hand-roll a correct temp-file + `os.replace`.)

**F — no cross-process lock anywhere.** Atomic replace makes a write all-or-nothing;
it does nothing about the *read-modify-write* window. Two sessions that both read
`state.json`, mutate different keys, and both write back produce a clean file with
one session's mutation silently dropped. CER-050's note that "concurrent writers are
not expected" is the doctrine that made this acceptable, and it is no longer true.

**Ordering and boundaries.** This story is independent of INFRA-280..283 (it touches
none of `current_stories`, the attempt counter's shape, or `checkpoint_steps`) and
builds *on top of* INFRA-284's merged `output_prefix`/`order` mechanism. INFRA-286
follows and owns the merge paths and the stale serialism prose — including retiring
CER-050's "concurrent writers are not expected" note, which is listed in CER-098's
fix, not CER-097's.

## Requires

- **INFRA-284 is complete and merged to `main`**, and this story's worktree is cut
  from a `HEAD` that contains it. Verify before building:
  `git log --oneline -1 --grep 'INFRA-284'` returns a commit reachable from `HEAD`.
- `skills/pairmode/scripts/effort_db.py` exposes `pending_reconcilable(path, limit,
  *, max_age_days=None, output_prefix=None, order=...)`, the module-private
  `_escape_like_prefix`, and `PENDING_MAX_AGE_DAYS` (INFRA-284/INFRA-266).
- `skills/pairmode/scripts/subagent_transcript.py` exposes
  `reconcile_pending_attempts(...)` with `max_age_days` / `output_prefix` keywords,
  `record_attempt_from_transcript(...)`, `_extract_spawn_ref(tool_response)`,
  `_contained_spawn_output(...)`, `default_spawn_output_roots()`,
  `SPAWN_TASKS_DIR_NAME`, `RECONCILE_MAX_ROWS`, `RECONCILE_OLDEST_ROWS`,
  `RECONCILE_MAX_AGE_DAYS`, and `_story_accepts_late_bump(project_dir, story_id)`.
- `skills/pairmode/scripts/state_utils.py` exposes `_atomic_write_json(path, data)`
  and is stdlib-only (it is imported by `hooks/` via the `sys.path` injection at
  `hooks/session_start.py:20-23`, `hooks/post_tool_use.py:46-47`,
  `hooks/pre_tool_use.py:53-56`). **It must remain stdlib-only and import-cheap.**
- `skills/pairmode/scripts/context_budget.py` exposes `decide(project_dir,
  flex_factor=1.0)`, `should_block(...)`, `record_step_growth(state, previous, new)`,
  `derive_expected_step_tokens(state)`, `_read_state(project_dir)`, `_is_stale(state)`,
  `CONTEXT_STEP_GROWTH_SAMPLES_KEY`, and `CONTEXT_STEP_GROWTH_SAMPLES_CAP`.
- `skills/pairmode/scripts/session_reset.py` exposes the **pure** `decide_reset(source,
  state)` returning `{"should_reset", "context_current_tokens",
  "context_current_tokens_recorded_at", "context_session_reset_at"}` or `None`, and
  performs no filesystem I/O (design boundary D11).
- Claude Code hook stdin payloads carry `session_id` for `SessionStart`,
  `PreToolUse`, and `PostToolUse`. `hooks/post_tool_use.py:66` and
  `hooks/pre_tool_use.py` already read it; `hooks/session_start.py` currently reads
  only `source` (`_read_source_from_stdin`, `:35-55`).
- The observed spawn-output path shape is
  `<tmp>/claude-<uid>/<project-slug>/<session-id>/tasks/<hash>.output` (INFRA-266
  § Context, effort.db rows 357-362).
- `docs/cer/backlog.md` contains a `CER-097` row whose `Phase` cell reads `109`.

## Ensures

Grouped by item. Every assertion is checkable from the diff or by running a command.

### A — a session-scoped context record exists

**A1. A new module `skills/pairmode/scripts/session_state.py` exists and is
stdlib-only.** It imports nothing outside the Python standard library and nothing
from the `skills/` tree except `state_utils`. `grep -n '^import \|^from '
skills/pairmode/scripts/session_state.py` shows no third-party import.
(`spec-preflight` will report `session_state`, `SESSION_SCOPED_KEYS`,
`CONTEXT_SESSIONS_KEY`, `session_view`, `apply_session_view`,
`prune_stale_sessions`, `other_live_session_prefixes`, `SESSION_LIVE_TTL_MINUTES`
and `STATE_LOCK_TIMEOUT_SECONDS` as undefined — intentional; this story creates
them.)

**A2. The keyed record and its key set are named constants.**
`session_state.CONTEXT_SESSIONS_KEY == "context_sessions"`, and
`session_state.SESSION_SCOPED_KEYS` is a `frozenset` equal to exactly
`{"context_current_tokens", "context_current_tokens_recorded_at",
"context_session_reset_at", "context_step_growth_samples",
"expected_step_tokens"}`. The record's shape is
`state["context_sessions"][<session_id>] = {<subset of SESSION_SCOPED_KEYS>,
"spawn_output_prefix": str|None, "last_seen_at": <iso8601 utc>}`.

**A3. `session_view(state, session_id)` overlays, and never mutates.** It returns a
**new** dict: a shallow copy of `state` in which each key in `SESSION_SCOPED_KEYS`
present in `state["context_sessions"][session_id]` replaces the flat value, and each
key *absent* from that entry keeps the flat value. `state` itself is unchanged
(a test asserts `state == deepcopy_before` after the call). With `session_id` falsy,
or with no `context_sessions` record, it returns a copy of `state` unchanged.
It never raises on a malformed `context_sessions` value (non-dict, list, `None`).

**A4. `apply_session_view(state, session_id, view)` writes back keyed, then
mirrors.** It mutates `state` in place: every key of `SESSION_SCOPED_KEYS` present
in `view` is written into `state["context_sessions"][session_id]`;
`last_seen_at` is stamped with `datetime.now(timezone.utc).isoformat()`; and the
same values are **also** written to the flat top-level keys. A test asserts that
after `apply_session_view(state, "S2", view)`, `state["context_sessions"]["S1"]`
is byte-for-byte unchanged. With a falsy `session_id` it writes the flat keys only
and creates no `context_sessions` entry (legacy/no-session callers keep working).

**A5. The flat keys are a derived mirror, documented as display-only.** The module
docstring states that the flat `context_current_tokens` /
`context_current_tokens_recorded_at` / `context_session_reset_at` /
`context_step_growth_samples` / `expected_step_tokens` keys are retained as a
last-writer-wins mirror for readers outside this fix's scope — named explicitly:
`skills/observability/api/src/routes/context.ts:132-140,239-240` and any CLI reader
with no session id — and that no *gating* decision may be made from them once a
`context_sessions` record exists. This mirrors INFRA-281/282/283's keyed-record +
derived-mirror pattern; the same wording convention is used.

**A6. Stale session entries are pruned, bounded.**
`session_state.prune_stale_sessions(state, ttl_minutes=SESSION_LIVE_TTL_MINUTES)`
removes every `context_sessions` entry whose `last_seen_at` is older than the TTL or
unparseable, **except** the entry named by an optional `keep=` argument.
`SESSION_LIVE_TTL_MINUTES == 180`. A test inserts 3 entries (one fresh, one 4 hours
old, one with `last_seen_at: "garbage"`) and asserts only the fresh one and `keep`
survive. Pruning is called exactly once per SessionStart and nowhere else
(`grep -rn 'prune_stale_sessions' skills/ hooks/` shows one non-test call site).

### B — SessionStart no longer clobbers another session's counter

**B1. SessionStart reads its own session id.** `hooks/session_start.py`'s stdin
reader returns the whole payload dict (renamed `_read_payload_from_stdin`, still
returning a safe `{}` on any parse failure, tty stdin, or empty input) and `source`
is taken from it. A test that passes a payload with no `session_id` asserts the hook
still runs and still emits its `additionalContext` block.

**B2. The reset is written into the starting session's own keyed entry.** When
`session_reset.decide_reset()` returns `should_reset=True`, the three returned keys
are written via `session_state.apply_session_view(state, session_id, result)` —
`session_reset.py` is **not** modified and stays pure (D11). A test with a
pre-populated `context_sessions["LOOP"]` entry holding
`context_current_tokens: 140000` fires a `{"source": "startup", "session_id":
"SIDE"}` SessionStart and asserts `context_sessions["LOOP"]["context_current_tokens"]
== 140000` afterwards, while `context_sessions["SIDE"]["context_current_tokens"] ==
25000`.

**B3. A non-reset source still registers the session.** For a source not in
`RESET_SOURCES | COMPACT_RESET_SOURCES` (i.e. `"resume"`, or a missing/unknown
source) the hook creates the session's `context_sessions` entry if absent by seeding
it from the current flat mirror, and stamps `last_seen_at` — but writes no baseline
and does not change the flat mirror's token values. This is what keeps C1's fail-safe
from firing on a legitimate `--resume`. A test asserts the seeded entry equals the
flat values and that `context_current_tokens` at top level is unchanged.

**B4. SessionStart performs exactly one state write.** The reset write, the seed
write and the prune are folded into a single locked read-modify-write (see E2);
`grep -c '_atomic_write_json\|update_state_json' hooks/session_start.py` shows the
hook calls the state writer at most once per invocation. Its existing
best-effort contract is preserved: any failure in this block leaves the status
block intact and the hook exits 0 (existing test coverage in
`tests/pairmode/test_session_start_hook.py` still passes unchanged).

### C — the gate and the token writer are session-resolved

**C1. `context_budget.decide` accepts a session id and resolves through it.** Its
signature becomes `decide(project_dir, flex_factor=1.0, *, session_id=None)`. When
`session_id` is truthy, the state dict it evaluates is
`session_state.session_view(state, session_id)`; when falsy, behaviour is byte-for-byte
today's (flat read). `decide` remains strictly read-only — it writes nothing to
`state.json` or `effort.db` (D11); a test asserts the state file's mtime and content
are unchanged across a `decide()` call.

**C2. An unregistered session with live siblings fails safe.** When `session_id` is
truthy, has **no** entry in `context_sessions`, and `context_sessions` holds at least
one other entry that is live per `SESSION_LIVE_TTL_MINUTES`, `decide` returns the
existing `{"block": True, "reason": _CONTEXT_CHECK_REQUIRED_MSG, "tokens": 0,
"acknowledged_at": 0}` shape rather than reading the flat mirror. No new block reason
string is introduced. A test asserts this, and a companion test asserts that the same
call with an *empty* `context_sessions` returns today's flat-read result (so a
single-session project is unaffected).

**C3. The PreToolUse gate passes its session id.** `hooks/pre_tool_use.py`'s
Task/Agent branch calls `context_budget.decide(project_dir=..., flex_factor=...,
session_id=data.get("session_id"))`. `grep -n 'context_budget.decide' hooks/pre_tool_use.py`
shows the `session_id=` keyword present. The `BUILD_CYCLE_SUBAGENTS` early exit,
the `_resolve_flex_factor` call, and the `context_budget_acknowledged_at` /
`context_budget_acknowledged_user_turn_seq` write-back are unchanged.

**C4. The PostToolUse token writer is session-scoped.** In `hooks/post_tool_use.py`'s
delegated call 1, `previous_tokens`, the `record_step_growth` call, and the
`context_current_tokens` / `context_current_tokens_recorded_at` writes all operate on
`session_state.session_view(state, session_id)` and are persisted via
`session_state.apply_session_view(state, session_id, view)`. A test drives two
PostToolUse invocations with different `session_id`s and different live token counts
and asserts each session's `context_step_growth_samples` contains only deltas derived
from its own two consecutive reads — specifically, that a session whose count went
30000 → 45000 records `[15000]` and is not polluted by the other session's
140000 → 150000 observation.

**C5. `expected_step_tokens` is derived per session.** `record_step_growth` is called
with the session view, so `derive_expected_step_tokens` reads that session's own ring
buffer. `context_budget.record_step_growth` and `derive_expected_step_tokens`
themselves are **unchanged** — they keep taking a flat dict; the view is what makes
them session-correct. `git diff --stat` shows no edit to either function body.

### D — the reconcile sweep is session-owned

**D1. A session's spawn-output prefix is derivable and stored.**
`subagent_transcript.session_output_prefix(output_file)` is a pure function returning
the string prefix of a validated spawn-output path up to and including the parent of
its `SPAWN_TASKS_DIR_NAME` component, with a trailing `os.sep` — e.g.
`/tmp/claude-1000/-mnt-work-flex/abc-123/tasks/x.output` →
`/tmp/claude-1000/-mnt-work-flex/abc-123/`. It returns `None` for a path with no
`tasks` component, for `None`, and for anything that raises. It performs no I/O
beyond `Path.resolve()` and never raises.

**D2. PostToolUse records the prefix inside the write it already performs.** In
delegated call 1's existing read-modify-write, the hook derives the prefix from
`subagent_transcript._extract_spawn_ref(data.get("tool_response"))` plus
`session_output_prefix(...)` and stores it as
`state["context_sessions"][session_id]["spawn_output_prefix"]`. No additional
`state.json` write, read, or `open()` is introduced anywhere in the hook — a test
asserts the hook's state-writer call count for one Task PostToolUse payload is 1.

**D3. `pending_reconcilable` gains an exclusion filter.**
`effort_db.pending_reconcilable` accepts `exclude_output_prefixes: "tuple[str, ...] |
list[str] | None" = None`. For each non-empty string it appends
`AND (output_file IS NULL OR output_file NOT LIKE ? ESCAPE '\')` to the WHERE clause,
binding `_escape_like_prefix(p) + '%'` as a parameter — never interpolated into the
query text. `None`, an empty sequence, and non-string members are ignored, not
errors. The existing inclusive `output_prefix` filter, `order`, `max_age_days`, and
the never-raises contract (every failure path returns `[]`) are unchanged, and both
filters may be supplied together.

**D4. `reconcile_pending_attempts` threads it through.** It accepts
`exclude_output_prefixes` and forwards it, unchanged, to **both** the newest-first and
the oldest-first `pending_reconcilable` calls (`subagent_transcript.py:1145-1157`),
so INFRA-284's anti-starvation cursor cannot route around the exclusion.

**D5. SessionStart excludes other live sessions' rows.** The `reconcile_pending_attempts`
call in `hooks/session_start.py` passes
`exclude_output_prefixes=session_state.other_live_session_prefixes(state, session_id)`.
That helper returns a deduplicated tuple of the non-empty `spawn_output_prefix` values
of every `context_sessions` entry **other than** `session_id` whose `last_seen_at` is
within `SESSION_LIVE_TTL_MINUTES`. With no other live session it returns `()` and the
sweep behaves exactly as today — a test asserts this explicitly, because a
single-session project must not lose orphan-row reconciliation.

**D6. The PostToolUse sweep is scoped to its own rows.**
`subagent_transcript.record_attempt_from_transcript` accepts
`output_prefix: "str | None" = None` and forwards it to its internal
`reconcile_pending_attempts` call; `hooks/post_tool_use.py`'s delegated call 2 passes
the calling session's stored `spawn_output_prefix` (or `None` when not yet known,
preserving today's behaviour on a session's very first spawn). A `None` prefix must
**not** be turned into an exclusion here — the first spawn of a session legitimately
sweeps globally, and turning that into a no-op would strand orphan rows.

**D7. Cross-story counter bumps stop by construction (CER-097's fourth symptom).** A
test builds two pending rows under two different session prefixes, both for stories
recorded as live in `current_stories`, fires a SessionStart for session A, and asserts
`.companion/attempt_counter.json`'s entry for session B's story is unchanged.
`subagent_transcript._story_accepts_late_bump` is **not** modified — INFRA-282 owns it,
and the fix here is that the row is never reached.

### E — atomic writers and an advisory lock

**E1. `state_utils` gains an advisory lock and a text writer.**
`state_utils.state_lock(path, timeout_seconds=STATE_LOCK_TIMEOUT_SECONDS)` is a
`contextlib.contextmanager` that takes an exclusive `fcntl.flock` on a sibling lock
file `<path>.lock`, yields, and always releases and closes the descriptor in a
`finally`. `STATE_LOCK_TIMEOUT_SECONDS == 2.0`. `state_utils._atomic_write_text(path,
text)` mirrors `_atomic_write_json`'s temp-file + `os.replace` + cleanup-and-re-raise
contract for `str` payloads. `state_utils.py` remains stdlib-only.

**E2. The lock fails open, bounded, and never blocks a hook.** Acquisition uses
non-blocking `flock(LOCK_EX | LOCK_NB)` in a poll loop with a sleep of at most 0.02 s
per iteration, bounded by `timeout_seconds`. On timeout, on `ImportError` for `fcntl`
(non-POSIX), on a read-only or missing directory, or on any `OSError`, the manager
**yields anyway** — degrading to today's atomic-replace-only behaviour — and never
raises. A test monkeypatches the acquisition to always fail and asserts the wrapped
write still happens and no exception escapes. A second test asserts the whole
`state_lock` body completes in under `timeout_seconds + 0.5` when the lock is held by
a live second descriptor.

**E3. A single locked read-modify-write helper exists and is the conversion target.**
`state_utils.update_state_json(path, mutate)` acquires `state_lock(path)`, reads and
JSON-parses `path` (treating a missing/malformed/non-dict file as "no update" and
returning `None`), calls `mutate(state)`, and persists via `_atomic_write_json` —
returning the written dict. If `mutate` returns `False` the write is skipped
(the idempotency case in `user_turn_seq`). It never raises: any exception returns
`None` with `state.json` untouched.

**E4. Every CER-097-named writer is converted.** After this story:
- `grep -n 'state_path.write_text' skills/pairmode/scripts/user_turn_seq.py` prints
  nothing; `record_user_turn` is expressed as one `update_state_json` call whose
  `mutate` performs the fingerprint check and returns `False` on a duplicate. Its
  documented fail-open contract (§ module docstring) and every existing test in
  `tests/pairmode/test_user_turn_seq.py` still pass **by name**.
- `grep -n 'state_path.write_text' skills/pairmode/scripts/sync.py` prints nothing
  (`sync.py:650` → `_atomic_write_json` under `state_lock`).
- `grep -n 'write_text' skills/pairmode/scripts/phase_new.py` and
  `... skills/pairmode/scripts/story_update.py` show only `_atomic_write_text` call
  sites for the four named markdown writers (`phase_new.py:201,231`;
  `story_update.py:111,211`).
- `skills/pairmode/scripts/story_context.py`'s `set_current_story` /
  `clear_current_story` read-modify-writes are wrapped in `state_lock` (INFRA-281 made
  this record concurrency-critical; it is the one writer CER-097 did not name that
  this story must not leave unlocked).
- `hooks/session_start.py`, `hooks/post_tool_use.py` and `hooks/pre_tool_use.py`
  perform their state read-modify-writes under `state_lock`.

**E5. A concurrency regression test exists.**
`tests/pairmode/test_state_utils.py` gains a test that forks or threads two writers
performing `update_state_json` against the same file, each incrementing a distinct
key 50 times, and asserts both keys reach 50 and the file parses as JSON at the end.
It must be skipped with an explicit reason (not silently passed) when `fcntl` is
unavailable.

**E6. `.lock` files are ignored, not committed.** `.companion/state.json.lock` is
covered by `.gitignore` (either via an existing `.companion/` rule — verify — or a
new `*.lock` line), and `git status --porcelain` after running the full suite shows no
untracked lock file.

### Cross-cutting

**F1. Documentation.** `docs/architecture.md` records, in at most three short
paragraphs: the `context_sessions` keyed record and its flat derived mirror (naming
the mirror's two consumers); the sweep-ownership rule (inclusive own-prefix on the
PostToolUse path, exclusion of other live sessions on the SessionStart path, and why
the two directions differ); and the `state_lock` advisory-lock contract, including
that it is *advisory, bounded, and fail-open* and therefore reduces — but does not
eliminate — lost-update risk. No new `##`-level heading is added.

**F2. The CER row carries a RESOLVED note.** `docs/cer/backlog.md`'s `CER-097` row
gains a bolded `**RESOLVED Phase 109 — INFRA-285 …**` note appended to its Finding
cell, naming each of A–F, and its `Phase` cell reads `109`. The row is not deleted or
moved between quadrants. The note must state plainly that the lock is advisory and
fail-open and that **multi-orchestrator operation remains out of scope** (phase doc
§ Scope statement), so the row is not read later as a stronger guarantee than was
built.

**F3. `schema_introduces` stays `false`.** `context_sessions` is a new key inside the
existing `.companion/state.json`, not a new persistent schema object — no
management-surface row is owed in `docs/phases/phase-109.md` § Schema delivery. The
existing observability context route remains the human-visible surface.

**F4. No legacy state file breaks, and no migration step is added.** A `state.json`
with no `context_sessions` key is read correctly by every changed reader, and is
upgraded to the keyed shape on its next successful write. A test loads a
pre-INFRA-285 fixture state dict and asserts `decide()`, `session_view()`, and the
SessionStart hook all behave.

## Instructions

You are the builder. Work only in this repository, inside your story worktree. Build
in order A → E, running the suite after each item; A and E are the foundations that
B, C and D sit on.

**0. Rebase check.** Confirm INFRA-284 is in your `HEAD` (§ Requires). Read the
current bodies of `pending_reconcilable`, `reconcile_pending_attempts`,
`record_attempt_from_transcript`, `_story_accepts_late_bump`, and
`context_budget.decide` as they exist *after* INFRA-284 — the line numbers cited
throughout this spec are anchors, not coordinates. Layer on top of INFRA-280..284's
changes; never revert them to make an assertion here easier to satisfy. If a genuine
conflict exists, stop and report `FAIL-CAUSE`.

**1. (A) Write `session_state.py`.** New module, stdlib-only, importing only
`json`/`os`/`datetime`/`pathlib` and `state_utils`. Implement `CONTEXT_SESSIONS_KEY`,
`SESSION_SCOPED_KEYS`, `SESSION_LIVE_TTL_MINUTES = 180`, `session_view`,
`apply_session_view`, `prune_stale_sessions`, `other_live_session_prefixes`, and a
small `_is_live(entry, now, ttl_minutes)` predicate shared by the last two. Every
public function must be total: malformed input returns the safe value, never raises.

Put the design reasoning in the module docstring, because the obvious "just key
everything" reflex breaks two live consumers: the flat keys stay as a **derived
mirror** precisely because `skills/observability/api/src/routes/context.ts` and
CLI readers with no session id have no session to resolve against, and rewriting them
is Phase G / OBS-rail work, not this story's. Say which reader is which, and say that
the mirror is never consulted to *gate* once `context_sessions` exists.

`SESSION_LIVE_TTL_MINUTES = 180` is deliberately much longer than
`context_budget`'s existing 60-minute `_CONTEXT_TOKEN_STALE_MINUTES` staleness TTL,
and the two must not be conflated: the token TTL asks "is this number still
trustworthy?", the session TTL asks "might that other process still be running?".
An unattended build loop can sit idle far longer than its counter stays fresh, and
treating it as dead is exactly the clobber this story exists to prevent. Comment the
number with that reason.

**2. (E) Extend `state_utils.py` first — B/C/D all write through it.** Add
`_atomic_write_text`, `STATE_LOCK_TIMEOUT_SECONDS = 2.0`, `state_lock`, and
`update_state_json` per E1–E3. Import `fcntl` lazily inside `state_lock`
(`try: import fcntl except ImportError: fcntl = None`) so the module keeps importing
on every platform and the hooks' `sys.path` injection keeps working unchanged.

**This is the ideology pressure point — read before writing it.** "Hooks are thin
relays only" (`docs/ideology.md` § Accepted constraints, **no override permitted**)
protects session performance and forbids blocking logic in hooks. A lock *is*
blocking logic, so the constraint's rationale — not its letter — decides the design:
the bound must be short (2 s), the wait non-blocking-with-poll rather than a blocking
`flock`, and **every** failure path must yield rather than raise, so the worst case
for a hook is an unchanged-from-today racy write, never a stalled session. Do not add
retry-until-success, a lock daemon, or logging of contention. Record this reasoning in
`state_lock`'s docstring — a future reviewer's "make the lock reliable" instinct is a
regression.

Do **not** convert the `hooks/pre_tool_use.py` scope-guard, cold-read-guard, or
`exit_plan_mode` branches; only the context-budget acknowledgment write-back at
`pre_tool_use.py:139-152` is in scope.

**3. (B) Session-scope SessionStart.** In `hooks/session_start.py`, replace
`_read_source_from_stdin` with `_read_payload_from_stdin() -> dict` (same
never-raises, `{}`-on-failure contract), take `source = payload.get("source")` and
`session_id = payload.get("session_id")`. Fold the reset write, the B3 seed, and the
A6 prune into one `state_utils.update_state_json` call whose `mutate`:
`prune_stale_sessions(state, keep=session_id)`; then, if `decide_reset` returned
`should_reset`, `apply_session_view(state, session_id, result)`; else ensure the
session's entry exists by seeding it from the flat mirror and stamping `last_seen_at`.
Keep `session_reset.decide_reset` pure and unmodified — it still receives the *flat*
state dict for its `pairmode_version` / baseline-override lookups, which are
project-scoped, not session-scoped.

Keep the whole block inside its existing `try/except Exception: pass` — the reset path
is best-effort and must never break the status block.

**4. (C) Thread the session id through the gate and the writer.** Add
`*, session_id: "str | None" = None` to `context_budget.decide`; immediately after
`state = _read_state(project_dir)` and the existing `None` handling, apply C2's
fail-safe check and then `state = session_state.session_view(state, session_id)`.
Everything downstream — the `context_current_tokens` read, `_is_stale`, `should_block`
— is untouched and operates on the view. Import `session_state` lazily inside
`decide` to keep `context_budget`'s import cost where it is.

In `hooks/pre_tool_use.py`, pass `session_id=data.get("session_id")`. In
`hooks/post_tool_use.py`'s delegated call 1, wrap the existing read-modify-write in
`update_state_json`, take `view = session_view(state, session_id)`, read
`previous_tokens` from the *view*, call `record_step_growth(view, previous, live)`,
set the two token keys on the view, and finish with
`apply_session_view(state, session_id, view)`.

**5. (D) Wire sweep ownership.** Add `session_output_prefix` to
`subagent_transcript.py` next to `_contained_spawn_output`; implement it by locating
`SPAWN_TASKS_DIR_NAME` in `Path(output_file).resolve().parts` and rebuilding the path
up to (not including) it. Then:

- `effort_db.pending_reconcilable`: add `exclude_output_prefixes` per D3, reusing
  `_escape_like_prefix` — do not write a second escaping routine. The
  `output_file IS NULL OR` disjunct is required: `NOT LIKE` on a NULL yields NULL,
  which SQLite treats as false, and would silently drop every row whose
  `output_file` has not been set yet.
- `subagent_transcript.reconcile_pending_attempts`: accept and forward it to both
  `pending_reconcilable` calls (D4).
- `subagent_transcript.record_attempt_from_transcript`: accept `output_prefix` and
  forward it to its internal sweep (D6).
- `hooks/session_start.py`: pass `exclude_output_prefixes=other_live_session_prefixes(
  state, session_id)`, computed from the state dict the hook already has in hand.
- `hooks/post_tool_use.py` call 1: derive and store `spawn_output_prefix` (D2);
  call 2: pass the stored prefix as `output_prefix`.

The asymmetry in D5/D6 is deliberate and must be stated in
`reconcile_pending_attempts`'s docstring: the PostToolUse sweep runs *inside* a
session that just spawned, so an inclusive own-prefix filter is both correct and
cheapest; the SessionStart sweep runs when the *only* rows it must not touch are other
live sessions', and an inclusive filter there would strand every orphan row from a
dead session — the exact rows INFRA-258 built the sweep to collect.

**6. (E cont.) Convert the writers.** Apply E4 site by site. `user_turn_seq` is the
one that changes shape: its fingerprint check becomes the `mutate` callback's
`return False` branch, so the whole read-check-write becomes one locked operation
rather than a read, a decision, and an unrelated write. Do not change its fail-open
semantics, its fingerprint algorithm, or `compute_fingerprint`'s signature — INFRA-248
established that the counter is only ever compared ordinally, and a behavioural change
here would be out of scope and unobservable in the tests that exist.

Leave `permission_scope.py:172`, `lesson_utils.py:61`, `spec_exception.py:130`,
`sidebar.py:196,906` and everything under `skills/seed/` alone (see § Out of scope).

**7. Tests.** New `tests/pairmode/test_session_state.py` (A2–A6, D1). Extend
`test_state_utils.py` (E1–E3, E5), `test_context_budget.py` (C1, C2, C5, F4),
`test_session_start_hook.py` (B1–B4, D5, D7), `test_post_tool_use.py` (C4, D2, D6),
`test_subagent_transcript.py` (D1, D4, D6), `test_effort_db.py` (D3),
`test_user_turn_seq.py` (E4 — every existing test by name). Follow each file's
existing fixture style. Delete no test.

**8. Docs and CER row.** Write F1's architecture paragraphs and F2's RESOLVED note.
The note must not overclaim: the lock is advisory and fail-open, and multi-orchestrator
operation is explicitly still out of scope.

**9. Ideology note (Step 4a — resolved inline, no conflict).** Three entries shaped
this spec. *"Hooks are thin relays only"* (no override permitted) is why the lock is
bounded, non-blocking and fail-open rather than reliable, and why D2 forbids any new
read or write on the hook path — the prefix capture rides inside the write the hook
already performs. *"Sidebar owns all state writes"* (no override permitted) is
respected by not widening the grandfathered hook-writer surface: the hooks that write
`state.json` today are exactly the hooks that write it after this story, and no new
writer is introduced. *"Rationale-bearing decisions over bare rules"* is why four
specific reasons must survive into the code as comments rather than living only here:
why `SESSION_LIVE_TTL_MINUTES` is not the token-staleness TTL, why the flat keys are
kept as a mirror, why the two sweep call sites filter in opposite directions, and why
the lock deliberately gives up after 2 s.

## Tests

Run from the story worktree root. After each item:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_session_state.py \
  tests/pairmode/test_state_utils.py \
  tests/pairmode/test_context_budget.py \
  tests/pairmode/test_session_start_hook.py \
  tests/pairmode/test_post_tool_use.py \
  tests/pairmode/test_subagent_transcript.py \
  tests/pairmode/test_effort_db.py \
  tests/pairmode/test_user_turn_seq.py \
  -q 2>&1 | tail -30
```

Then the adjacent surface, to catch collateral damage from the writer conversions and
the `decide()` signature change:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_session_reset.py \
  tests/pairmode/test_pre_tool_use_hook.py \
  tests/pairmode/test_pre_tool_use_scope_guard.py \
  tests/pairmode/test_post_tool_use_hook.py \
  tests/pairmode/test_context_budget_check.py \
  tests/pairmode/test_sync.py \
  tests/pairmode/test_phase_new.py \
  tests/pairmode/test_story_update.py \
  tests/pairmode/test_pairmode_sync.py \
  -q 2>&1 | tail -30
```

Then the full suite **without `-x`**, so a known failure cannot mask a new one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Machine-checkable Ensures:

```bash
grep -n 'state_path.write_text' skills/pairmode/scripts/user_turn_seq.py   # must print nothing
grep -n 'state_path.write_text' skills/pairmode/scripts/sync.py            # must print nothing
grep -n 'write_text' skills/pairmode/scripts/phase_new.py                  # only _atomic_write_text
grep -n 'write_text' skills/pairmode/scripts/story_update.py               # only _atomic_write_text
grep -n 'session_id=' hooks/pre_tool_use.py                                # decide() gets the session id
grep -rn 'prune_stale_sessions' skills/ hooks/ --include=*.py | grep -v tests   # exactly one call site
grep -c '109' <<< "$(grep 'CER-097' docs/cer/backlog.md)"                  # row carries the phase
git status --porcelain | grep '\.lock'                                     # must print nothing
```

Acceptance:

- every new test from A2–A6, B1–B4, C1–C5, D1–D7, E1–E6, F4 passes;
- every pre-existing test in the eight primary test files passes **by its original
  name** — especially `test_user_turn_seq.py` and `test_session_start_hook.py`, whose
  functions are restructured rather than extended;
- the full suite is green. If a failure appears, verify it reproduces on clean `HEAD`
  before attributing it elsewhere, and say so explicitly in the build result.

## Out of scope

- **Multi-orchestrator operation.** Per `docs/phases/phase-109.md` § Scope statement,
  the target is one orchestrator with parallel builds; this story protects a build
  loop from *side sessions*, not from a second full build loop. The advisory lock
  narrows the read-modify-write window; it does not make the system safe for two
  competing loops, and the CER note must not imply it does.
- **Everything CER-098 / INFRA-286 owns.** Merge return-code checks, the failed-merge
  cleanup contract, merge serialization, the stale serialism prose in
  `docs/architecture.md`, and retiring CER-050's "concurrent writers are not expected"
  doctrine note — that last one is listed in CER-098's fix, not CER-097's, and doing it
  here would collide with INFRA-286's diff.
- **Re-keying the observability surface.** `skills/observability/api/src/routes/context.ts`
  keeps reading the flat mirror. Teaching the SPA/API to render per-session context is
  OBS-rail work (era doc § Phase G scope) and would widen this story into a
  cross-language change.
- **Converting every non-atomic JSON writer in the repo.** `permission_scope.py:172`,
  `lesson_utils.py:61`, `spec_exception.py:130`, `sidebar.py:196,906`, and all of
  `skills/seed/scripts/` write files CER-097 does not name and that no hook writes
  concurrently. A general audit is its own story.
- **A real cross-process mutex, lock daemon, or lock-contention telemetry.** Forbidden
  by "hooks are thin relays only"; the lock is advisory, bounded and fail-open by
  design (E2).
- **Migrating existing `state.json` files.** No migration step, no `pairmode_migrate.py`
  entry — the keyed record is created on first write (F4), matching INFRA-282/283's
  precedent.
- **Changing `session_reset.decide_reset`'s purity, its baseline constants, or the
  `resume`-never-resets rule.** INFRA-175/180/245 own that logic; this story changes
  only *where* the returned keys are written.
- **Deriving a true post-compact token count from the transcript.** Still reserved
  (INFRA-245 § module docstring); `COMPACT_BASELINE_TOKENS` remains a constant.
