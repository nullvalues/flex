---
id: INFRA-185
rail: INFRA
title: "Isolate lesson_review CLIOutputClarity tests from live drift promotion (CER-057)"
status: complete
phase: "HARNESS001-ante1"
story_class: code
primary_files:
  - tests/pairmode/test_lesson_review.py
touches:
---

# INFRA-185 — Isolate lesson_review CLIOutputClarity tests from live drift promotion (CER-057)

## Context

Gate-blocker surfaced during the RELEASE-003 build (HARNESS001-ante1). Two tests
in `tests/pairmode/test_lesson_review.py::TestCLIOutputClarity` invoke the real
`lesson_review` CLI via `CliRunner().invoke(lr_mod.cli, ["--approve", "L001", ...])`
**without** `--project-dir` or `--skip-drift`. Because no `--project-dir` is
passed, the post-review **drift-promotion step** (`drift_promotion_step`) reads the
live `.companion/state.json` `registered_projects` and runs real drift detection
against the actual fleet.

When two or more registered projects share a convergence pattern (observed
2026-06-26 with `registered_projects = [coherra, meander]`), the CLI reaches the
interactive prompt `Promote to canonical? [y/n/skip]`, receives no stdin under
`CliRunner`, and aborts with exit code 1. The tests assert `result.exit_code == 0`,
so they fail:

- `test_approved_lesson_output_contains_action_required`
- `test_end_of_run_summary_contains_review_complete`

This is **environment-dependent**: the tests were green at session start (effectively
<2 projects sharing a pattern) and went red when a second project (`meander`) was
present. A unit test must never invoke live, interactive fleet drift promotion. The
two affected tests assert on the lesson-annotation output ("ACTION REQUIRED",
"REVIEW COMPLETE"), not on drift behaviour — so the drift step is pure contamination
for them.

The `lesson_review` CLI already exposes a `--skip-drift` flag (and sibling tests in
the same file isolate via `--project-dir <tmp>`); the production default (drift runs
when `registered_projects` is present and `--project-dir` defaults to cwd) is correct
and is **not** changed by this story.

## Acceptance criteria

1. `test_approved_lesson_output_contains_action_required` passes deterministically,
   independent of the host's `.companion/state.json` `registered_projects`.

2. `test_end_of_run_summary_contains_review_complete` passes deterministically,
   independent of `registered_projects`.

3. The fix is **test-only**: no change to `skills/pairmode/scripts/lesson_review.py`
   or any production module. Production drift-promotion behaviour is unchanged.

4. The two invocations no longer reach the live drift-promotion path — preferred
   mechanism is adding `--skip-drift` to each `runner.invoke(lr_mod.cli, [...])` call
   (these tests do not exercise drift). An isolated `--project-dir` pointing at a
   `registered_projects`-free tmp dir is an acceptable alternative if `--skip-drift`
   proves unsuitable.

5. The `TestCLIOutputClarity` class is scanned for any **other** test that invokes
   the real `lesson_review` CLI without drift isolation (no `--skip-drift` and no
   isolated `--project-dir`). Any such sibling is given the same isolation. If none
   exist beyond the two named, note that in the build summary.

6. The full build gate is green:
   `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` — and the gate
   stays green regardless of how many projects are in the host `registered_projects`.

## Implementation guidance

- The two failing invocations are at approximately
  `tests/pairmode/test_lesson_review.py:613` and `:638`:
  ```python
  result = runner.invoke(lr_mod.cli, ["--approve", "L001"])
  result = runner.invoke(lr_mod.cli, ["--approve", "L001", "--reject", "L002"])
  ```
  Add `"--skip-drift"` to each argument list, e.g.
  `["--approve", "L001", "--skip-drift"]`.
- `--skip-drift` is mutually exclusive with `--drift-only` (CLI raises a
  `UsageError`) but is independently valid alongside `--approve`/`--reject`.
- Do not touch `lesson_review.py`. Do not alter the assertions on output strings —
  only isolate the drift step so the CLI exits 0.
- Verify the gate twice if practical: it must pass whether or not the host
  `.companion/state.json` lists ≥2 registered projects (the whole point of CER-057).

## Tests

Modifies existing tests in `tests/pairmode/test_lesson_review.py` (test-only story).
Run:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_lesson_review.py::TestCLIOutputClarity -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

### Out of scope

- The provenance of `meander` in `registered_projects` (how a brand-new project was
  registered without the operator running the registration flow) — captured
  separately as **CER-058** (Do Later); not fixed here.
- Any change to `lesson_review.py` production drift-promotion behaviour.
- Re-running drift detection or convergence logic — only the test's coupling to it
  is removed.
