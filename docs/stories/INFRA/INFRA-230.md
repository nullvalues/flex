---
id: INFRA-230
rail: INFRA
title: Fix CER-072 — checkpoint build-gate guard hardcodes flex-only pytest path, blocking every downstream checkpoint
status: complete
phase: "97"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
  - tests/pairmode/test_next_action.py
touches: []
---

## Context

CER-072 (Do Now, CRITICAL, unresolved): `next_action.py::_run_build_gate_subprocess`
(`next_action.py:367-395`) hardcodes `uv run pytest tests/pairmode/ -q --tb=no`
in the target project directory and treats any non-zero exit as gate-red.
`tests/pairmode/` exists only in flex/flex-harness itself — verified absent
in every fleet project (forqsite, coherra, meander, caddy, radar, asp) — so
pytest exits non-zero with "file or directory not found," and the guard
returns `False` unconditionally. The existing fail-open branch only covers
exceptions/timeouts, not a clean non-zero exit, so it doesn't rescue this
case.

Live-hit: forqsite's first downstream 0.3.0 checkpoint (`PM065-main`, the
migration phase itself) hard-blocked with `checkpoint-guard-failed:build-gate`
while the project's real build gate (`pnpm build && pnpm typecheck && pnpm
test`, 2827 tests) was green. Every migrated fleet project will hit this at
its first checkpoint until fixed.

Confirmed this session: every bootstrapped project already carries
`.companion/pairmode_context.json` with a populated `test_command` field
(e.g. forqsite: `"pnpm test"`) — set by `bootstrap.py` at bootstrap time
(`_infer_build_command`/`_validate_test_command`, `bootstrap.py:145-160`) and
never previously read by the build-gate guard. flex-harness itself has no
`.companion/pairmode_context.json` (confirmed absent this session), so its
own checkpoint gate must keep working exactly as today via the existing
hardcoded pytest fallback.

## Requires

- `next_action.py::_run_build_gate_subprocess` in its current hardcoded form
  (confirmed present and reproducing the bug this session).
- `.companion/pairmode_context.json`'s `test_command` field, populated by
  `bootstrap.py` for every bootstrapped project (confirmed present in
  forqsite this session; confirmed absent in flex-harness's own repo).

## Ensures

- `_run_build_gate_subprocess(project_dir)` reads
  `project_dir/.companion/pairmode_context.json` first. If the file exists,
  is valid JSON, and has a non-empty `test_command` string field, that exact
  command string is run as the build gate (via a shell, since it may contain
  `&&`-chained commands like forqsite's) instead of the hardcoded pytest
  invocation.
- If `.companion/pairmode_context.json` does not exist, is not valid JSON, or
  has no non-empty `test_command` field, the function falls back to the
  existing hardcoded `uv run pytest tests/pairmode/ -q --tb=no` behavior
  exactly as today (flex-harness's own checkpoint gate is unaffected).
- The existing fail-open behavior (advisory pass on subprocess exception or
  timeout) is preserved for both the config-driven command and the fallback
  path.
- A project whose `test_command` genuinely fails (non-zero exit, command
  actually ran) still correctly reports gate-red — this fix must not turn
  the guard into an unconditional advisory pass; it must run the *correct*
  command for that project and honor its real exit code.
- New regression tests exist covering: (a) a project with
  `pairmode_context.json` + a passing `test_command` → gate green; (b) same
  but a failing `test_command` → gate red; (c) no `pairmode_context.json`
  present → falls back to the pytest-based check exactly as before
  (existing behavior/tests unaffected); (d) malformed/empty
  `pairmode_context.json` (missing or blank `test_command`) → falls back to
  pytest, not a crash.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` passes in
  full (run without `-x` — see the standing lesson from INFRA-229 about `-x`
  masking failures behind the known CER-070 environmental one).

## Instructions

1. In `skills/pairmode/scripts/next_action.py`, modify
   `_run_build_gate_subprocess` (`next_action.py:367-395`):
   a. Before running the hardcoded pytest command, check for
      `project_dir / ".companion" / "pairmode_context.json"`.
   b. If it exists, attempt to parse it as JSON and read `test_command`. Wrap
      the read/parse in a try/except so a malformed file falls through to
      the existing pytest fallback rather than raising.
   c. If a non-empty `test_command` string is found, run it via
      `subprocess.run(test_command, shell=True, cwd=project_dir, ...)`
      (shell=True is required since the command may be a `&&`-chain) with
      the same environment-PATH handling (`~/.local/bin` prepended) and the
      same fail-open behavior (exception/timeout → `True`) as the existing
      code.
   d. Otherwise, run the existing hardcoded
      `uv run pytest tests/pairmode/ -q --tb=no` exactly as before.
2. Update the function's docstring to describe both paths.
3. Add the four regression tests described in Ensures to
   `tests/pairmode/test_next_action.py`, using `tmp_path` fixtures (create a
   fake `.companion/pairmode_context.json` with a trivial always-passing or
   always-failing shell command as `test_command`, e.g. `"true"`/`"false"`,
   rather than a real pnpm/pytest invocation — keep the tests fast and
   dependency-free).
4. Run the full suite without `-x` and confirm the only failure is the
   known CER-070 environmental one.
5. Resolve CER-072 in `docs/cer/backlog.md` with a `**RESOLVED**` note
   citing this story, following the file's existing resolution-note
   convention (see nearby resolved entries for the exact format).

## Out of scope

- Any change to how `bootstrap.py` populates `test_command` in
  `pairmode_context.json` — this story only consumes that existing field.
- Any change to the CER Do-Now checkpoint gate (`_check_cer_do_now`) itself.
- Re-running any downstream project's checkpoint — that happens in each
  project's own session once this lands and it re-syncs the fixed
  `next_action.py` (via its `pairmode_scripts_dir` binding to this repo).
- CER-073 through CER-076 (the other Do Later findings from the same
  forqsite build) — separate, lower-severity items, not part of this fix.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental
failure — run without `-x` and report every failure seen, not just the
first.
