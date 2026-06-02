---
era: "001"
---

# flex — Phase 42: Context budget session-relative token tracking

← [Phase 41: Re-frame docs around pairmode as the lead capability](phase-41.md)

## Goal

`context_budget_check.py` sums `tokens_total` for all attempts `WHERE phase = ?` —
a phase-lifetime cumulative total. This conflates two different things:

- **Total phase cost** — how expensive the whole phase has been (useful for
  retrospective analysis, not relevant to current session health)
- **Current session context pressure** — how many tokens the orchestrator has
  absorbed in this session (what the gate is actually trying to measure)

After a `/clear` and "Continue building" resume, the orchestrator's context window
is fresh, but the phase-lifetime total is unchanged. The gate fires again immediately
after the first new story, even though there is no real context pressure. The
orchestrator is then forced to re-acknowledge the gate after every story for the
rest of the phase — a false positive that trains it to dismiss the signal.

Observed in the radar project Phase 75: after 155k tokens from session 1, every
story in session 2 triggered the gate. The useful signal (approach the context limit)
became noise (always over after a clear).

**The fix:** use a session-start timestamp to make the sum session-relative. The
`attempts.ts` column (ISO-8601 UTC) already exists. A `context_budget_session_start`
key in `.companion/state.json` marks when the current build session began. The
check sums only attempts recorded at or after that timestamp. On resume after a
clear, the orchestrator writes a new session-start before continuing — the gate
resets to zero and counts fresh tokens only.

**Secondary issue:** the Phase 75 orchestrator added its own "My honest read"
commentary instead of surfacing the blocking prompt verbatim. The template must
explicitly prohibit editorial additions.

**Two stories:**

| ID | Title | Status |
|----|-------|--------|
| INFRA-110 | Add session-relative token summing to `context_budget_check.py` | planned |
| INFRA-111 | Update `CLAUDE.build.md.j2` for session-start recording and verbatim prompt | planned |

**Story dependencies:** INFRA-111 does not depend on INFRA-110 (the template change
records session start in state.json; the script reads it independently). Both may
be built in parallel.

---

## Stories

### Story INFRA-110 — Add session-relative token summing to `context_budget_check.py`

**Rail:** INFRA | **story_class:** code

#### Requires

- `skills/pairmode/scripts/context_budget_check.py` exists.
- `tests/pairmode/test_context_budget_check.py` exists with 6 passing tests.
- `attempts` table has a `ts TEXT NOT NULL` column (ISO-8601 UTC, set by
  `record_attempt.py`).

#### Ensures

**`skills/pairmode/scripts/context_budget_check.py`**

- A new `_load_session_start_from_state(project_dir)` helper reads
  `context_budget_session_start` from `.companion/state.json`. Returns the
  value as a string if present and non-empty, or `None` if absent/invalid.

- `_sum_tokens_for_phase(db_path, phase, since=None)` accepts an optional
  `since` parameter (ISO-8601 UTC string). When `since` is not None, the query
  filters `WHERE phase = ? AND ts >= ?`. When None, the existing cumulative
  query runs unchanged (backward compatibility).

- A `--since` CLI argument (optional, ISO-8601 UTC string) is added to
  `argparse`. Overrides the state.json value.

- Session-start resolution priority (parallel to threshold priority):
  `--since` arg → `state.json["context_budget_session_start"]` → `None`
  (cumulative, backward compatible).

- The machine-parseable stdout line gains a `since=<value>` field when
  session filtering is active, `since=lifetime` when cumulative:
  `context_budget phase=<p> tokens=<t> threshold=<n> since=<value|lifetime> status=<ok|over>`

- All existing behaviour (exit codes 0/1/2, threshold priority, DB resolution)
  is preserved unchanged.

**`tests/pairmode/test_context_budget_check.py`**

Three new tests added to the existing 6:

7. `test_session_start_excludes_pre_session_tokens` — DB has two attempts for
   phase X: one with ts before session_start, one after. state.json has
   `context_budget_session_start` set. Assert only the post-session-start
   attempt's tokens are summed; status reflects the session-only total.

8. `test_since_arg_overrides_state_session_start` — state.json has one
   session_start value, `--since` arg passes a different (later) timestamp.
   Assert that only tokens after the `--since` timestamp are counted (the
   `--since` arg wins).

9. `test_missing_session_start_falls_back_to_cumulative` — state.json has no
   `context_budget_session_start` key and no `--since` arg. Assert all tokens
   for the phase are summed (cumulative, existing behaviour).

The output line for tests 7 and 8 must contain `since=` (not `since=lifetime`).
The output line for test 9 must contain `since=lifetime`.

#### Instructions

**`skills/pairmode/scripts/context_budget_check.py`**

1. Add `_load_session_start_from_state(project_dir: Path) -> str | None` after
   `_load_threshold_from_state`. It reads `state.json["context_budget_session_start"]`,
   returns the string value if present and truthy, else `None`.

2. Update `_sum_tokens_for_phase` signature to
   `_sum_tokens_for_phase(db_path: Path, phase: str, since: str | None = None) -> int`.
   When `since` is not None:
   ```python
   cur.execute(
       "SELECT COALESCE(SUM(COALESCE(tokens_total, 0)), 0) FROM attempts WHERE phase = ? AND ts >= ?",
       (phase, since),
   )
   ```
   When None, use the existing query unchanged.

3. Add `--since` to argparse (optional, default None).

4. In `main()`, resolve `since`:
   ```python
   if args.since is not None:
       since = args.since
   else:
       since = _load_session_start_from_state(project_dir)
   ```

5. Pass `since` to `_sum_tokens_for_phase`.

6. Update the stdout print to include the `since` field:
   ```python
   since_label = since if since is not None else "lifetime"
   print(
       f"context_budget phase={args.phase} tokens={token_sum} "
       f"threshold={threshold} since={since_label} status={status}"
   )
   ```

**`tests/pairmode/test_context_budget_check.py`**

Add the three new test functions. Use the existing `_create_db` and
`_create_state` helpers. For timestamp values, use ISO strings like
`"2026-01-01T00:00:00+00:00"` (before session start) and
`"2026-06-01T00:00:00+00:00"` (after session start), with session_start
set to `"2026-03-01T00:00:00+00:00"`.

The `_create_db` helper must support inserting attempts with an explicit `ts`
value. If the existing helper does not support this, extend it with an optional
`ts` parameter that defaults to the current time.

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_context_budget_check.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

All 9 tests in the file must pass. Full suite must pass.

---

### Story INFRA-111 — Update `CLAUDE.build.md.j2` for session-start recording and verbatim prompt

**Rail:** INFRA | **story_class:** methodology

#### Requires

- INFRA-110 complete (or building in parallel — the template change is independent
  of the script change; `context_budget_session_start` in state.json is read by
  the script regardless of build order).
- `CLAUDE.build.md.j2` contains the `## Context budget check (between stories)`
  section with the current blocking prompt.
- `CLAUDE.build.md.j2` has a `## Build loop (repeat for each story)` opening.

#### Ensures

**`skills/pairmode/templates/CLAUDE.build.md.j2`**

1. A "Record session start" step is added to the build loop preamble — immediately
   after the existing "Read the phase manifest" / story-identification steps and
   before spawning the first builder. It instructs the orchestrator to write the
   current UTC timestamp to `context_budget_session_start` in
   `.companion/state.json`:

   ```
   **Record session start** (once per build session, before the first builder):

   Write the current UTC time to `.companion/state.json` under the key
   `context_budget_session_start`. Use ISO-8601 format. This marks the session
   boundary so the context budget check counts only tokens from this session,
   not the full phase lifetime.

   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python -c "
   import json, datetime
   from pathlib import Path
   state_path = Path('.companion/state.json')
   state = json.loads(state_path.read_text()) if state_path.exists() else {}
   state['context_budget_session_start'] = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
   state_path.write_text(json.dumps(state, indent=2))
   "
   ```

   On resume after a `/clear`: run this again before the first "Continue building"
   story. The new timestamp resets the session-relative sum to zero.
   ```

2. The `## Context budget check (between stories)` section is updated:
   - The bash invocation already passes `--project-dir` and `--phase`; no change
     to the command itself (the script reads session_start from state.json
     automatically).
   - The stdout format description is updated to show the new `since=` field:
     `context_budget phase=<phase> tokens=<sum> threshold=<n> since=<session_start|lifetime> status=<ok|over>`
   - The Exit 1 blocking instructions add one sentence before the verbatim prompt:
     "Surface the following prompt **verbatim** — do not add editorial commentary,
     reasoning, or a recommendation. Wait for user response."

**`CLAUDE.build.md`** (flex's own)

Apply the identical changes directly — no `sync-build`. Same two edits:
the session-start step in the build loop preamble, and the updated context
budget check section.

**Do not run `pairmode_sync sync-build`** — flex's `.companion/state.json` has no
`build_command` or `test_command`, so sync-build would wipe the build gate.

#### Tests

No test file expected for this methodology story.

The reviewer verifies:
1. `CLAUDE.build.md.j2` contains a "Record session start" step with the Python
   snippet that writes `context_budget_session_start`.
2. The context budget check stdout format description includes `since=`.
3. The Exit 1 block contains the phrase "verbatim — do not add editorial
   commentary".
4. `CLAUDE.build.md` mirrors all three changes.
5. Full test suite passes.

`TEST RUN: methodology story — no test file expected`

---

Tag: `cp42-context-budget-session-relative`
