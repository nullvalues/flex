---
id: INFRA-343
rail: INFRA
title: Fix checkpoint build gate: 60s timeout silently passes on a 175s+ suite
status: complete
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
touches:
  - skills/pairmode/scripts/next_action.py
  - tests/pairmode/test_next_action.py
  - tests/pairmode/test_checkpoint_routing.py
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

HIGH finding F9 of `docs/build-loop-cold-eyes-review-20260801.md` (opus, measured empirically):
`_run_build_gate_subprocess` (`next_action.py`, guard 3 of `check_checkpoint_guards`) runs the
pairmode test suite with a hardcoded 60-second `subprocess.run(..., timeout=60)` and returns `True`
(gate green) on any timeout or exception — documented inline as "advisory: fail open on error or
timeout." Opus measured flex's own suite at ~175 seconds — nearly 3x the timeout — meaning this
gate has never actually completed a real run in this repo; it always times out and always reports
green. The only real test-verification happening at checkpoint time in practice has been the
reviewer's own manual `pytest` run, which is not gated on by anything.

Fix direction: either raise the timeout to something that reflects reality (with margin — the
suite will keep growing; consider deriving it from a stored baseline duration rather than a fixed
constant, or removing the timeout for this specific gate context since a checkpoint call is
expected to take minutes, not seconds), or restructure so a timeout is distinguishable from a real
pass in whatever surfaces the checkpoint-report output (rather than silently fail-open to green).
Consider whether "fail open" is the right default here at all, given this guard exists specifically
to catch what the human-run reviewer suite might miss between review and checkpoint.

**Concrete decision (made in this spec, not left open for the builder):** read fresh
(2026-08-01), `_run_build_gate_subprocess` (`skills/pairmode/scripts/next_action.py:675-737`)
runs one of two commands — the config-driven `test_command` from
`.companion/pairmode_context.json` (`shell=True`), or the hardcoded fallback
`["uv", "run", "pytest", "tests/pairmode/", "-q", "--tb=no"]` that applies to flex's own
repo (no `pairmode_context.json` here) — via `subprocess.run(..., timeout=60)` at lines
719-726 and 728-734, and returns `True` (gate green) unconditionally from a single
`except Exception: return True  # advisory: fail open on error or timeout` at
lines 736-737. `check_checkpoint_guards` (guard 3, lines 778-790) calls this (or an
injected `gate_fn`) and wraps its own call in an equivalent blanket
`except Exception: gate_ok = True  # advisory: fail open` (lines 780-783). Downstream,
guard 3's boolean result is consumed only by `check_checkpoint_guards`'s own
`{"ok": bool, "failed_guard": "build-gate"}` return, which `resolve_next_action`'s Row 9
(lines 1584-1597) turns into `AWAIT_USER` with
`reason="checkpoint-guard-failed:build-gate"` on failure — there is no separate
"checkpoint-report" surface that independently renders the gate's pass/fail/timeout
state; the `AWAIT_USER` reason string *is* the only surfacing mechanism that exists
today, and it already stops the loop for a human when `gate_ok` is `False`. That
mechanism only needs a `False` to reach it — it does not need new reporting
infrastructure built alongside it.

This story chooses **(b) restructured to fail closed on a real timeout, reusing the
existing `AWAIT_USER`/`checkpoint-guard-failed:build-gate` surface**, over both
"(a) as originally framed" and blanket fail-open:

- The timeout is raised from 60s to 600s (10 minutes) — a fixed constant, not a
  stored-baseline derivation. A baseline-tracking mechanism (recording and reading back
  historical suite durations) is a materially bigger feature than this finding calls
  for and is explicitly out of scope (see `## Out of scope`); 600s gives the observed
  175-230s range roughly 2.6x-3.4x headroom, which comfortably covers ordinary suite
  growth for a long while without the operational cost of a baseline store, and a
  checkpoint call is already understood project-wide to take minutes, not seconds.
- A **genuine timeout** (`subprocess.TimeoutExpired`, i.e. the command was actually
  still running when the 600s deadline arrived) now fails the gate **closed**
  (`gate_ok = False`), because this guard's entire purpose (per the finding's own
  framing) is to catch what the human-run reviewer suite might miss between review and
  checkpoint — a suite that cannot even *finish* inside a 10-minute window is itself a
  signal worth stopping on, not something to wave through as green. This also directly
  serves the ideology's "Never silently pass contradictions" conviction
  (`docs/ideology.md` § Accepted constraints): silently reporting green on a run that
  never completed is exactly the silent-pass failure mode that conviction rules out.
- **Non-timeout execution errors** (e.g. a missing `uv`/`pytest` binary, a bad `cwd`, an
  `OSError` from the subprocess layer itself) keep today's advisory fail-open behavior
  unchanged. These indicate the *tooling* isn't runnable in this environment, not that
  the suite ran and something was wrong with it — the CER-072/INFRA-230 bootstrap
  concern (a freshly bootstrapped project without a working `test_command` must not be
  permanently blocked from ever checkpointing) still applies to that case and is
  preserved.
- The `AWAIT_USER` / `reason="checkpoint-guard-failed:build-gate"` path already exists
  and already halts the loop for human review — a timeout now reaching it via
  `gate_ok = False` is sufficient surfacing; no new report field, log line, or meta key
  is added.

## Requires

## Ensures

1. `_run_build_gate_subprocess`'s config-driven `subprocess.run` call (originally
   lines 719-726) and its hardcoded-fallback `subprocess.run` call (originally lines
   728-734) both pass `timeout=600`, not `timeout=60`. Forbidden proxy: only one of
   the two call sites updated while the other keeps `timeout=60`.
2. `_run_build_gate_subprocess` catches `subprocess.TimeoutExpired` in a dedicated
   `except` clause (ordered before, or otherwise distinguished from, a catch-all
   `except Exception`) and returns `False` from that clause. Forbidden proxy: a single
   unified `except Exception` block that cannot tell a `TimeoutExpired` apart from any
   other exception type.
3. `_run_build_gate_subprocess` still returns `True` from a separate `except Exception`
   (or equivalent) clause for any non-`TimeoutExpired` exception raised by
   `subprocess.run` — the CER-072/INFRA-230 bootstrap-tolerance behavior for a missing
   or broken test runner is unchanged. Forbidden proxy: a non-timeout execution error
   (e.g. `FileNotFoundError` for a missing `uv` binary) now also failing the gate
   closed, which would regress CER-072's original fix.
4. `check_checkpoint_guards`'s guard-3 `try`/`except` around `gate_fn()` (originally
   lines 779-783) applies the identical distinction: `gate_fn()` raising
   `subprocess.TimeoutExpired` sets `gate_ok = False`; `gate_fn()` raising any other
   exception still sets `gate_ok = True`. Forbidden proxy: the injected-`gate_fn` path
   left on the old undifferentiated fail-open while only the direct-subprocess path
   (Ensures 2-3) is fixed.
5. `_run_build_gate_subprocess`'s docstring no longer states the blanket "Returns True
   (advisory pass) on timeout or any execution error" — it documents the split:
   fail-closed on `TimeoutExpired`, fail-open (advisory) on other exceptions.
   `check_checkpoint_guards`'s docstring is updated in the same spirit if it makes the
   old blanket claim about guard 3.
5a. `docs/architecture.md:2631`'s claim "the subprocess invocation is advisory-only and
    fails open on timeout or error" (in the Era 003 additive contract, DP4 point 2) is
    updated to state the new split behavior: the subprocess invocation now fails
    **closed** on a genuine `TimeoutExpired` (per this story), and remains advisory
    fail-open only for other, non-timeout execution errors — matching Ensures 2-3.
    Forbidden proxy: the stale "fails open on timeout or error" claim (or any
    equivalent unqualified fail-open-on-timeout statement) remaining anywhere in that
    doc section after the edit.
6. `tests/pairmode/test_next_action.py`'s `TestRunBuildGateSubprocess` gains a test that
   mocks `subprocess.run` to raise `subprocess.TimeoutExpired` and asserts
   `_run_build_gate_subprocess(tmp_path) is False`.
7. `tests/pairmode/test_next_action.py`'s `TestRunBuildGateSubprocess` gains a test that
   mocks `subprocess.run` to raise a non-timeout exception (e.g. `OSError` or
   `FileNotFoundError`) and asserts `_run_build_gate_subprocess(tmp_path) is True` —
   proving Ensures 3's carve-out is real, not just claimed.
8. `tests/pairmode/test_checkpoint_routing.py` gains (or an existing test in that file
   is extended with) a case where `gate_fn` raises `subprocess.TimeoutExpired` and
   `check_checkpoint_guards(...)` returns
   `{"ok": False, "failed_guard": "build-gate"}` — proving guard 3's `AWAIT_USER`
   surfacing path (Row 9, `next_action.py:1584-1597`) is reachable from a timeout, not
   just from a real non-zero exit code.
9. `tests/pairmode/test_checkpoint_routing.py` gains (or an existing test is extended
   with) a case where `gate_fn` raises a non-timeout exception and
   `check_checkpoint_guards(...)` returns `{"ok": True}` — proving Ensures 4's
   fail-open carve-out holds at the `check_checkpoint_guards` level too.
10. `uv run pytest tests/pairmode/ -q --tb=no` exits 0 (full suite green, no regression
    introduced by the `timeout=` change or the new exception branches).

## Instructions

1. Read `_run_build_gate_subprocess` and `check_checkpoint_guards` in
   `skills/pairmode/scripts/next_action.py` fresh before editing — this file has been
   heavily edited by INFRA-339/340/341 this phase; do not assume the line numbers cited
   in `## Context` above still match exactly.
2. In `_run_build_gate_subprocess`, change both `subprocess.run(..., timeout=60, ...)`
   call sites (the config-driven `test_command` branch and the hardcoded-fallback
   `pytest` branch) to `timeout=600`.
3. Replace the single `except Exception: return True  # advisory: fail open on error or
   timeout` with two clauses:
   - `except subprocess.TimeoutExpired: return False` — with a comment explaining the
     fail-closed rationale from `## Context` above (the guard exists to catch what the
     reviewer's manual run might miss; a run that never finishes cannot honestly report
     green).
   - `except Exception: return True  # advisory: fail open — tooling/environment error,
     not a suite result` (or equivalent updated comment) — preserving today's
     CER-072/INFRA-230 bootstrap tolerance for a non-timeout failure to execute.
   Order matters: the `TimeoutExpired` clause must be checked before (or otherwise take
   precedence over) the generic `Exception` clause, since `TimeoutExpired` is itself an
   `Exception` subclass.
4. Update `_run_build_gate_subprocess`'s docstring to describe the split behavior
   (Ensures 5) instead of the old blanket claim.
5. In `check_checkpoint_guards`, apply the same split to the `try: gate_ok =
   bool(gate_fn())` block: catch `subprocess.TimeoutExpired` first and set
   `gate_ok = False`; catch other `Exception`s and set `gate_ok = True` (unchanged
   behavior), matching Ensures 4. Update the guard's docstring/inline comment if it
   currently states an undifferentiated "advisory: fail open" for this block.
6. Add the two new test cases to `TestRunBuildGateSubprocess` in
   `tests/pairmode/test_next_action.py` (Ensures 6-7), following that class's existing
   `mock.patch("subprocess.run", side_effect=...)` pattern already used elsewhere in the
   same test file/class.
7. Add or extend test cases in `tests/pairmode/test_checkpoint_routing.py`'s
   `check_checkpoint_guards` direct-unit-test section (Ensures 8-9), following that
   file's existing `gate_fn=lambda: ...` injection pattern — use
   `gate_fn=lambda: (_ for _ in ()).throw(subprocess.TimeoutExpired(cmd="x", timeout=1))`
   or a small local helper function that raises, whichever reads more clearly against
   the file's existing style; import `subprocess` in the test file if not already
   imported.
8. Do not touch the `test_command`/fallback command-selection logic, the
   `.companion/pairmode_context.json` read, or the PATH-augmentation block earlier in
   `_run_build_gate_subprocess` — none of that is in scope for this finding.
9. Do not add a stored-baseline-duration mechanism, a new meta/report field, or any new
   consumer of the guard's result beyond the existing `AWAIT_USER` reason string — see
   `## Out of scope`.
10. Update `docs/architecture.md:2631` (Era 003 additive contract, DP4 point 2, the
    sentence beginning "the subprocess invocation is advisory-only and fails open on
    timeout or error") to accurately describe the new behavior implemented above: the
    subprocess invocation now fails **closed** (returns `False`, blocking the gate) on
    a genuine `subprocess.TimeoutExpired`, and remains advisory fail-open only for
    other, non-timeout execution errors (per CER-072/INFRA-230 bootstrap-tolerance
    rationale, Ensures 3-4/5a). Keep the edit scoped to that sentence and its immediate
    surrounding context — do not otherwise rewrite the Era 003 additive contract
    section.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action.py -k TestRunBuildGateSubprocess -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_checkpoint_routing.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q --tb=no 2>&1 | tail -10
```

Acceptance: all three commands exit 0. The first two specifically must show the new
timeout/non-timeout test cases (Ensures 6-9) passing, not merely the pre-existing
tests in those files. The third confirms no regression across the full suite — run it
without `-x` so any pre-existing unrelated failure, if one exists, stays visible rather
than being masked by an early stop.

## Out of scope

- Deriving the timeout from a stored baseline-duration measurement (Fix direction (a)
  as originally framed in `## Context`) — a fixed, generously-margined constant (600s)
  is the decision made in this spec; a baseline-tracking mechanism is a separate,
  larger feature.
- Any new checkpoint-report surface, meta key, or log line distinguishing a timeout
  pass from a real pass beyond what `AWAIT_USER`'s existing
  `reason="checkpoint-guard-failed:build-gate"` string already provides — that string
  already fires only on `gate_ok is False`, which this story makes true for a timeout;
  no additional surfacing plumbing is built.
- Changing fail-open behavior for non-timeout execution errors (missing test runner,
  bad `cwd`, etc.) — CER-072/INFRA-230's bootstrap tolerance for those cases is
  preserved unchanged (Ensures 3-4).
- Guard 1 (`_check_phase_completion`) and Guard 2 (`_check_cer_do_now`) of
  `check_checkpoint_guards` — this story touches only guard 3 (the build gate).
- Any change to the `test_command`/`pairmode_context.json` config-driven selection
  logic itself, or to the PATH-augmentation block in `_run_build_gate_subprocess`.

## Evidence

Covered-contracts gate (INFRA-317): `primary_files`/`touches` includes
`skills/pairmode/scripts/next_action.py`, which intersects the
`## Module structure::skills/pairmode/scripts/next_action.py` covered-contract
pair. Both halves were read in full before editing.

- `docs/architecture.md:2628-2631` (§ Era 003 additive contract, DP4 point 2)
  documented the resolver's `check_checkpoint_guards`/`_run_build_gate_subprocess`
  relationship and stated: "the subprocess invocation is advisory-only and fails
  open on timeout or error." This was the stale claim this story's Ensures 5a
  targets — it diverged from the fix direction chosen in `## Context` above
  (fail closed on `TimeoutExpired`). Per the covered-contracts gate's divergence
  rule, the doc's *intent* (this story's own spec, not the pre-existing doc text)
  wins here since the spec explicitly directs the fix; the doc text itself was
  corrected to match the new code behavior (Ensures 5a, Instructions 10) rather
  than the code being reverted to match the stale doc.
- `skills/pairmode/scripts/next_action.py:675-737` (`_run_build_gate_subprocess`)
  and `:740-793` (`check_checkpoint_guards` guard 3) were read in full before
  editing, confirming the two `subprocess.run(..., timeout=60, ...)` call sites
  (config-driven and hardcoded-fallback) and the single blanket
  `except Exception: return True` clause described in `## Context`, and the
  guard-3 `try: gate_ok = bool(gate_fn()) except Exception: gate_ok = True`
  block in `check_checkpoint_guards`.

Resolution: `docs/architecture.md:2625-2631` updated to state the split
behavior (fail closed on genuine `TimeoutExpired`, advisory fail-open only for
other execution errors), matching the code changes made in
`_run_build_gate_subprocess` and `check_checkpoint_guards`.
