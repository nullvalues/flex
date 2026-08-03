---
id: INFRA-365
rail: INFRA
title: Fix shadow-reviewer suggestions-file scope_guard block (checkpoint-security finding)
status: draft
phase: "118"
story_class: code
auth_gated: false
schema_introduces: false
touches:
  - skills/pairmode/scripts/scope_guard.py
  - tests/pairmode/test_scope_guard.py
  - tests/pairmode/test_pre_tool_use_scope_guard.py
  - tests/pairmode/test_next_action.py
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase-118 checkpoint-security audit (HIGH finding): `skills/pairmode/skills/shadow-reviewer/procedure.md:67-70`
declares `<worktree>/.pairmode-suggestions.md` as the shadow-reviewer's sole output channel, but
`skills/pairmode/scripts/scope_guard.py:210` denies it. During a build the shadow-reviewer runs in
the story worktree, so `resolve_call_story` returns the active story ID; `.pairmode-suggestions.md`
is deliberately not in the story's `primary_files`/`touches` (it is gitignored and excluded from
story artifacts, INFRA-358), is not in `STANDING_SURFACES` (`scope_guard.py:55-58`), and
`pre_tool_use.py` routes every `Edit`/`Write` through `check_path` with no agent_type exemption.
Every `Write` the shadow-reviewer issues returns `not in story scope for <ID>: .pairmode-suggestions.md`
— the producer added by INFRA-358/359 cannot fire in live dispatch. INFRA-360's integration test does
not catch this because `tests/pairmode/test_next_action.py:3636` and `:3737` write the file with
`Path.write_text` directly, bypassing the hook and the enforcement layer entirely.

## Requires

- INFRA-358, INFRA-359, INFRA-360 landed (they are; this story repairs their live path).
- `skills/pairmode/scripts/scope_guard.py` still exposes the module-level allow-list
  (`STANDING_SURFACES`) and the `check_path` entry point named in `## Context`. If either has
  been renamed since the audit, fix the real shape, not this story's re-description of it.

## Ensures

1. With an active story resolved and `.pairmode-suggestions.md` absent from that story's
   `primary_files`/`touches`, `scope_guard`'s path check **allows** a write to
   `<worktree>/.pairmode-suggestions.md`. Forbidden proxy: a warning/log line emitted while the
   deny result is still returned, or an allow that only happens when the story happens to declare
   the file.
2. The allowance is keyed on that exact repo-relative filename at the worktree root. A write to
   any other undeclared path — including a neighbouring dotfile such as `.pairmode-other.md` and a
   path like `subdir/.pairmode-suggestions.md` — is still denied. Forbidden proxy: a prefix/glob
   widening (`.pairmode*`, "any dotfile", "any gitignored path") that buys this one file by
   opening a class.
3. A test in `tests/pairmode/test_pre_tool_use_scope_guard.py` drives a `Write` to
   `<worktree>/.pairmode-suggestions.md` through the **real** `pre_tool_use` hook entry point
   (same call shape the existing tests in that file use) and asserts the hook does not block it.
   Forbidden proxy: a test that calls `check_path` directly only, or that uses `Path.write_text`
   and asserts the file exists — the bypass that let this defect ship (`## Context`).
4. A negative test in the same file asserts an undeclared non-suggestions path in the same
   worktree is still blocked, proving the fix did not disable story-scope enforcement.
5. `tests/pairmode/test_next_action.py`'s two direct-write simulations (around `:3636` and
   `:3737`) each carry a one-line docstring/comment stating they simulate the file-level protocol
   and deliberately bypass the hook, with a pointer to the enforcement-level coverage added by
   Ensures 3. Forbidden proxy: rewriting those simulations to route through the hook and thereby
   losing INFRA-360's protocol-level coverage.
6. `.pairmode-suggestions.md` remains excluded from story artifacts — the story diff / any
   `check-story-scope`-style report does not begin listing it as an in-scope story file
   (INFRA-358). Assert this, don't assume it.
7. Full `tests/pairmode/` suite green.

## Instructions

1. Fix this in `scope_guard.py`, not in `pre_tool_use.py`. Adding an `agent_type` exemption
   branch to the hook would put policy logic in a relay — `docs/ideology.md` § Accepted
   constraints, "Hooks are thin relays only", no override permitted. (Inline ideology-alignment
   adjustment, Step 4a-ii: the drafted fix was routed into the guard module to preserve that
   constraint's rationale, not just its letter.)
2. The expected shape is adding the suggestions filename to the existing standing-surface
   allow-list, matched exactly, with a comment naming *why* it is standing (shadow-reviewer's sole
   output channel, INFRA-358/359, gitignored and intentionally never in a story's declared files).
   The comment is the deliverable as much as the entry — a bare string added to a list is the
   rule without its rationale.
3. Do not add the file to any story's `primary_files`/`touches`, and do not change
   `.gitignore` — its exclusion from story artifacts is the design, and Ensures 6 protects it.
4. Run the new hook-level tests before and after the guard change; the "before" run must
   reproduce the `not in story scope for <ID>: .pairmode-suggestions.md` denial, so the test is
   proven to be watching the real failure rather than passing vacuously.
5. `primary_files:` is unset on this stub — the spec-writer does not fill it. Operator should
   confirm `skills/pairmode/scripts/scope_guard.py` as the primary file before dispatch.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_pre_tool_use_scope_guard.py tests/pairmode/test_scope_guard.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: both green, with the new hook-level allow test and the negative deny test passing.
Run the full suite without `-x` so a real failure is not masked by an earlier known one.

## Out of scope

- Any general per-agent-type scope exemption mechanism in the hook layer — this story allows one
  named standing surface, it does not introduce agent-aware permissions.
- INFRA-366's bootstrap OPERATOR-010 overwrite finding (the other checkpoint-security HIGH).
- Revisiting whether `.pairmode-suggestions.md` should be tracked in git at all.
- `docs/ideology.md` — cited in Instructions as the rationale source only; it is read, never
  edited, so it is intentionally absent from `touches:` (spec-preflight `scope:` finding, kept).
