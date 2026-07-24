---
id: INFRA-257
rail: INFRA
title: Truthful attempt_number recording — derive real attempt sequence for repeated same-story spawns
status: complete
phase: "101"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/effort_db.py
  - skills/pairmode/scripts/subagent_transcript.py
touches:
  - tests/pairmode/test_effort_db.py
  - tests/pairmode/test_subagent_transcript.py
  - docs/architecture.md
---

## Context

Every `attempts` row that the hook-side recording pipeline writes to
`.companion/effort.db` carries `attempt_number = 1`, regardless of how many
times the same story has been spawned. The cause is a single unset kwarg:
`subagent_transcript.record_attempt_from_transcript`
(`skills/pairmode/scripts/subagent_transcript.py:394`) calls
`effort_recorder.record_effort(...)` without `attempt_number`, and
`record_effort`'s signature defaults it to `1`
(`skills/pairmode/scripts/effort_recorder.py:132`). Since INFRA-236/237 made
that hook call the *only* per-attempt recorder in the pairmode build loop,
every loop row in the database is stamped `1`.

The operator's post-cp100 review of effort.db caught the consequence: Phase 99's
INFRA-247 has three `builder` rows and INFRA-248 has four, all with
`attempt_number = 1`. The database therefore cannot distinguish "this story was
retried three times under the escalation ladder" from "this story was spawned
three times for unrelated reasons" — the two histories are byte-identical in the
column that exists to tell them apart. Two downstream surfaces are already
degraded by it: `pairmode_effort.py rework`
(`skills/pairmode/scripts/pairmode_effort.py:293`) selects
`MAX(attempt_number) > threshold` and is therefore permanently empty for
loop-recorded work, and INFRA-256 had to explicitly document its checkpoint
rollup as counting *rows, not attempt numbers*, because the column could not be
trusted.

The authoritative retry signal that *does* exist —
`.companion/attempt_counter.json`, read by `flex_build.read_attempt_count`
(`flex_build.py:953`), bumped by `bump_attempt_count` on FAIL
(`flex_build.py:935`), cleared by `clear_attempt_count` on a successful merge
(`flex_build.py:1007`) — is deliberately *not* the source this story uses.
Three reasons, recorded here so a later reader does not re-litigate the choice:

1. **It counts failures, not spawns.** The counter is 0 until the first FAIL, so
   `counter + 1` would stamp `1` on both the first spawn and a second spawn that
   followed a PASS-but-re-run — the exact ambiguity this story exists to remove.
2. **It is cleared on merge.** After `merge-story-worktree` lands a story, the
   counter file is deleted; a later re-run of the same story would silently
   restart at `1`, which the operator explicitly ruled out — post-completion
   re-runs must stay distinguishable from first builds.
3. **It is a single-slot, single-story file** with no per-role dimension, while
   effort.db records five distinct recordable roles
   (`RECORDABLE_SUBAGENT_ROLES`, `subagent_transcript.py:73`) whose sequences are
   independent.

The counter's own semantics are load-bearing for
`next_action.infer_position`'s escalation ladder (resolver rows 5/6/7, the
retry → loop-breaker → human-pause progression, `next_action.py:747`) and this
story changes nothing about them. Instead the recorded `attempt_number` is
derived from effort.db itself: the count of existing rows for the same
`(story_id, agent_role)` pair, plus one. That source is monotonic by
construction, survives counter clearing, needs no new state file, and is exactly
as truthful as the row history it is derived from.

## Requires

- INFRA-236/237 are complete: `hooks/post_tool_use.py`'s Task/Agent branch
  delegates to `subagent_transcript.record_attempt_from_transcript`, which is the
  sole per-attempt writer of `.companion/effort.db` rows for the pairmode build
  loop and the sole caller of `flex_build.bump_attempt_count` on FAIL.
- `.companion/effort.db` exists with the `attempts` schema documented in
  `docs/architecture.md` § Effort tracking, including the
  `idx_attempts_story` index on `attempts(story_id)`
  (`skills/pairmode/scripts/effort_db.py:70`).
- `effort_db.insert_attempt`, `effort_recorder.record_effort`,
  `flex_build.read_attempt_count`, `flex_build.bump_attempt_count`, and
  `flex_build.clear_attempt_count` retain their current signatures.
- INFRA-256 is complete (sibling story). This story does not depend on its
  behaviour, but it edits the same `docs/architecture.md` § Effort tracking
  region INFRA-256 extended, so building it after INFRA-256 avoids a doc conflict.

## Ensures

1. A new module-level helper in `skills/pairmode/scripts/effort_db.py` —
   `next_attempt_number(path, story_id, agent_role)` — returns
   `SELECT COUNT(*) FROM attempts WHERE story_id = ? AND agent_role = ?` plus
   one. `story_id` and `agent_role` are bound as SQL parameters; neither is
   interpolated into the query text. The helper resolves its path through the
   existing `_depth_guard` and uses the same `sqlite3.connect` /
   try-finally-`conn.close()` idiom as `query_by_story` — no new db-access
   pattern is introduced.
2. `next_attempt_number` never raises. It returns `1` when the database file does
   not exist, when the `attempts` table is absent, when the file is unreadable or
   corrupt, or when `story_id` or `agent_role` is empty/`None`. `1` is the
   correct floor: an unreadable history is indistinguishable from an empty one,
   and a first attempt is the honest default.
3. `subagent_transcript.record_attempt_from_transcript` resolves the effort-db
   path (via `effort_db.resolve_effort_db_path`), calls `next_attempt_number` for
   the `(story_id, agent_role)` it is about to record, and passes the result as
   the explicit `attempt_number=` kwarg to `record_effort`. The call is made
   **after** the `effort_tracking` early-return, so a project with effort
   recording disabled performs zero additional db work in the hook path.
4. The `agent_role` used for the derivation is the same `str(subagent_type)`
   value written to the row, so each of the five `RECORDABLE_SUBAGENT_ROLES`
   maintains an independent sequence for a given story: builder spawns number
   1, 2, 3… while reviewer spawns for the same story independently number
   1, 2, 3…. A story's first `loop-breaker`, `security-auditor`, or
   `intent-reviewer` spawn is `attempt_number = 1` even when its builder is
   already on attempt 4.
5. Rows recorded under a synthetic story ID (`unattributed:<subagent_type>`, the
   fallback used when no story ID can be derived) are numbered by the same rule
   against that synthetic ID, producing a monotonic sequence per unattributed
   role rather than a wall of `1`s.
6. **Counter-cleared-after-merge case, decided and documented:** because the
   derivation counts persisted effort.db rows and never reads
   `.companion/attempt_counter.json`, a spawn that occurs after
   `merge-story-worktree` has cleared the counter continues the story's sequence
   (`… 3 → 4`) instead of resetting to `1`. A test asserts this explicitly by
   calling `flex_build.clear_attempt_count` between two recorded spawns for the
   same story and role and asserting the second row's `attempt_number` is `2`.
7. `attempt_number` is defined in `docs/architecture.md` as the **lifetime spawn
   ordinal for a `(story_id, agent_role)` pair** — not the escalation-ladder
   attempt count. The doc states plainly that the two numbers intentionally
   diverge: the ladder counts *failures since the last successful land* and
   resets on merge; `attempt_number` counts *spawns ever recorded* and never
   resets. It also states the consequence for `pairmode_effort.py rework`, whose
   `MAX(attempt_number) > threshold` predicate now means "this story/role was
   spawned more than N times in total, including post-completion re-runs", not
   "this story failed review N times".
8. No change is made to `.companion/attempt_counter.json`'s semantics, its
   writers, or its readers: `flex_build.read_attempt_count`,
   `bump_attempt_count`, `write_attempt_count`, and `clear_attempt_count` are
   unmodified in behaviour and signature, the FAIL-only bump inside
   `record_attempt_from_transcript` is unmodified and still runs before and
   independently of the `effort_tracking` guard, and
   `next_action.infer_position`'s `effective_attempt` computation and its
   escalation-ladder rows are untouched. A test asserts the counter's value is
   unaffected by attempt-number derivation.
9. `effort_recorder.record_effort` keeps its `attempt_number: int = 1` default
   and is not modified. The derivation lives at the hook call site, so
   cross-skill callers that do not pass `attempt_number`
   (`skills/seed/scripts/mine_sessions.py`, `skills/seed/scripts/reconcile.py`,
   `skills/companion/scripts/sidebar.py`) and the explicit
   `record_attempt.py --attempt-number` path are behaviourally unchanged. A
   caller-supplied `attempt_number` always wins over any derivation.
10. `record_attempt_from_transcript` remains best-effort and non-raising: the
    derivation is wrapped so that a failure to compute the attempt number
    degrades to `1` and still writes the row, rather than losing the row or
    propagating an exception into the hook. A test asserts a row is still
    written (with `attempt_number = 1`) when the derivation path fails.
11. `tests/pairmode/test_effort_db.py` covers `next_attempt_number` directly:
    empty/absent db → `1`; N existing rows for the pair → `N + 1`; rows for the
    same story under a *different* `agent_role` do not increment the sequence;
    rows for a different story under the same role do not increment it; a
    corrupt/non-sqlite file at the db path → `1` and no exception.
12. `tests/pairmode/test_subagent_transcript.py` contains a regression test
    reproducing the observed INFRA-247/248 shape: three consecutive
    `subagent_type: builder` spawns recorded for one story id yield
    `attempt_number` values `[1, 2, 3]` in insertion order, and four consecutive
    spawns for a second story yield `[1, 2, 3, 4]` — the two stories' sequences
    being independent of each other. The test name or an inline comment
    references INFRA-247/INFRA-248 so the origin of the shape is traceable.
13. A further test in the same file covers role independence end-to-end: an
    interleaved builder/reviewer/builder/reviewer spawn sequence for one story
    produces builder rows `[1, 2]` and reviewer rows `[1, 2]`. Assertions read
    the values back out of effort.db (via `effort_db.query_by_story`), not from
    the recorder's return value alone.
14. Backfill of existing rows is explicitly not performed: no migration, no
    `UPDATE attempts SET attempt_number = ...`, no repair subcommand. Historical
    rows written before this story keep their `attempt_number = 1`.
    `docs/architecture.md` records this, so a reader comparing pre- and
    post-INFRA-257 rows knows the discontinuity is deliberate and knows that
    row-count-based statistics (INFRA-256's checkpoint rollup) remain the correct
    way to read historical effort.
15. Full `tests/pairmode/` suite passes (the known pre-existing
    `test_observability_ui.py::test_ui_build_emits_dist_index_html` failure is
    acceptable only if it is shown to reproduce on clean HEAD).

## Instructions

1. Read, before editing: `skills/pairmode/scripts/effort_db.py` around
   `insert_attempt` (~line 202) and `query_by_story` (~line 253);
   `skills/pairmode/scripts/subagent_transcript.py`'s
   `record_attempt_from_transcript` (~line 325, in particular the
   `effort_tracking` early return and the `record_effort` call at ~line 394);
   `skills/pairmode/scripts/effort_recorder.py`'s `record_effort` (~line 125);
   and `flex_build.py`'s attempt-counter block (~lines 895–1015) so you can see
   for yourself that this story does not touch it.
2. Add `next_attempt_number(path: Path, story_id: str, agent_role: str) -> int`
   to `effort_db.py`, placed next to `query_by_story`. Guard empty inputs first
   and return `1`. Wrap the whole body in `try/except Exception: return 1` — this
   helper sits in a hook path and must never be the reason a hook fails. Use the
   existing `_depth_guard(path)` and the `sqlite3.connect` / try-finally-close
   idiom; do not add a context-manager or connection-pool variant. Extend the
   module docstring's `Public API` list with the new helper.
3. In `record_attempt_from_transcript`, after the
   `if not state or not state.get("effort_tracking"): return None` guard and
   before the `record_effort(...)` call: hoist the effective story id actually
   being recorded (the existing `story_id or f"unattributed:{subagent_type}"`
   expression) into a local so the derivation and the row use the identical
   value; then compute
   `attempt_number = effort_db.next_attempt_number(effort_db.resolve_effort_db_path(project_path), effective_story_id, str(subagent_type))`
   inside a `try/except Exception: attempt_number = 1`; then pass
   `attempt_number=attempt_number` explicitly to `record_effort`.
4. Import `effort_db` in `subagent_transcript.py` using the existing dual-import
   pattern at the top of the file (`try: from skills.pairmode.scripts... /
   except ImportError:` flat form). The hook loads this module with a flattened
   `sys.path`, so a package-only import will break the hook at runtime while
   passing tests — follow the established pattern exactly.
5. Do not modify `effort_recorder.record_effort`, `record_attempt.py`, or any
   cross-skill recorder. Do not add an "auto" sentinel to `record_effort`'s
   `attempt_number` parameter — a defaulted-to-derived parameter would silently
   change the behaviour of three cross-skill call sites this story has no mandate
   over.
6. Do not modify `flex_build.py`. If a change there seems necessary, stop: the
   counter's escalation-ladder semantics are load-bearing for resolver rows
   5/6/7 and are explicitly out of this story's scope.
7. Update `docs/architecture.md` § Effort tracking (~line 1857): in the
   **Data model** paragraph, replace the bare `attempt_number` mention with its
   definition — lifetime spawn ordinal per `(story_id, agent_role)`, derived at
   record time by `effort_db.next_attempt_number` from the count of existing rows
   for that pair. Add a paragraph (adjacent to the INFRA-256 scoping paragraph
   near line 2013) carrying the rationale required by Ensures 7 and 14: why
   row-counting rather than `attempt_counter.json` (counts failures not spawns;
   cleared on merge; single-slot with no role dimension), the deliberate
   divergence from the escalation-ladder count, the changed reading of
   `pairmode_effort.py rework`, and the no-backfill decision. Also correct the
   `rework` bullet (~line 1922) so it no longer implies `attempt_number > 1`
   means "needed a retry".
8. Add a cross-reference in the `.companion/attempt_counter.json` description
   (~line 1603) stating that effort.db's `attempt_number` is a *different* number
   derived from a different source, so a future reader does not assume the two
   must agree and "fix" one to match the other.
9. Concurrency note for the implementation and the doc: the derivation is a
   read-then-write with no transaction spanning both. Two genuinely concurrent
   spawns for the same `(story_id, agent_role)` could read the same count and
   both write the same `attempt_number`. This is accepted, not fixed here — the
   era's no-nested-spawning invariant makes the build loop serial (one worker in
   flight at a time), and effort.db is best-effort observability, so a
   transaction spanning the hook's read and the recorder's write would add
   locking risk to a hook path for a race the loop's own structure prevents.
   State this as a one-line comment at the derivation site and one sentence in
   `docs/architecture.md`.
10. Ideology note (Step 4a, resolved inline). Two checks applied:
    (a) *"Hooks are thin relays only"* (`docs/ideology.md` § Accepted
    constraints, no override permitted) — this story adds work to a hook path,
    which is why the added work is bounded to exactly one indexed `COUNT(*)`
    against a database the same code path already opens, is placed after the
    `effort_tracking` early return so disabled projects pay nothing, and is
    wrapped to never raise or block. It adds no API call, no network, no new
    file, and no branching logic. It does not widen the hook's role beyond what
    INFRA-236/237 already established; it makes an already-written column
    truthful. If any step of the implementation would require more than one query
    or any I/O beyond the effort db, stop and flag it rather than proceeding.
    (b) *"Rationale-bearing decisions over bare rules"* (§ Core convictions) —
    the reason the counter was rejected as the source, and the reason the two
    attempt numbers diverge, must land in `docs/architecture.md` and not only in
    this story file. A later agent finding `read_attempt_count` unused by the
    recorder will otherwise "fix" the inconsistency and reintroduce the
    reset-on-merge bug.

## Tests

Targeted:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_effort_db.py \
  tests/pairmode/test_subagent_transcript.py -q 2>&1 | tail -30
```

Counter-semantics lock-in (must remain green, unchanged):

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_flex_build_attempt_counter.py \
  tests/pairmode/test_next_action.py -q 2>&1 | tail -30
```

Then the full suite, without `-x` so the known pre-existing failure does not
mask a real one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Acceptance: all targeted files green; full suite green except the known
pre-existing `test_observability_ui.py::test_ui_build_emits_dist_index_html`
failure, which must be shown to reproduce on clean HEAD if it appears.

## Out of scope

- **Backfilling or repairing existing `attempt_number = 1` rows.** Historical
  data stays as-is; no migration, no repair subcommand, no `UPDATE`. The
  discontinuity between pre- and post-INFRA-257 rows is deliberate and is
  documented in `docs/architecture.md` (Ensures 14).
- **Any change to `.companion/attempt_counter.json` semantics** — the FAIL-only
  bump, the clear-on-merge, the single-slot schema, and
  `next_action.infer_position`'s escalation ladder (resolver rows 5/6/7) all stay
  exactly as they are.
- **Changing `effort_recorder.record_effort`'s default**, or adding derivation to
  the cross-skill recorders in `mine_sessions.py`, `reconcile.py`, or
  `sidebar.py`.
- **Reworking `pairmode_effort.py rework`'s query or threshold** to match the new
  semantics — this story documents the changed reading; adjusting the view is
  separate work.
- **Changing INFRA-256's checkpoint rollup to count `attempt_number` instead of
  rows.** Row counts remain the correct spawn count, and remain correct for
  historical rows that this story does not backfill.
- **Transactional/atomic attempt-number allocation** for concurrent same-story
  spawns (see Instructions step 9).
- **Recording spawns for non-build-cycle subagent types** —
  `RECORDABLE_SUBAGENT_ROLES` is unchanged.
