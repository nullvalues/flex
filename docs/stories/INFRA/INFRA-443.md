---
id: INFRA-443
rail: INFRA
title: Session-start orphan detection surfacing doctor-state drift
status: complete
phase: "146"
story_class: code
auth_gated: false
schema_introduces: false
touches:
  - skills/pairmode/scripts/session_orphan_notice.py
  - hooks/session_start.py
  - tests/pairmode/test_session_orphan_notice.py
  - tests/pairmode/test_session_start_hook.py
  - skills/pairmode/skills/security-auditor/procedure.md
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

INFRA-442 ships `doctor-state`, but an operator only runs it after already
hitting the symptom — "build blocked", or `create-story-worktree` dying on
"worktree already exists" — and only if they remember the command exists. The
drift it detects (orphaned worktree, stale `current_stories` stamp,
`current_story` mirror, orphaned `docs/phases/permissions/<ID>.json`, and
frontmatter/table status mismatch) is almost always created by a session that
died, so the *next* session start is exactly the moment it is both present and
cheap to surface. This story wires `diagnose_state`'s read-only classification
into the SessionStart status block as one advisory line naming the concrete
repair invocation. It surfaces only: no gating, no auto-repair — the same
advisory-first shape as `agent_staleness_notice` (INFRA-323), which this
story's structure mirrors.

## Requires

INFRA-442 complete: `diagnose_state(project_path, *, max_age_hours=None)` exists
in `skills/pairmode/scripts/flex_build.py` and returns the `orphans` /
`in_flight` / `status_drift` classification with no writes. This story consumes
that function and reimplements none of its detection.


## Scope widenings

| path | reason | widened_at |
| --- | --- | --- |
| skills/pairmode/skills/security-auditor/procedure.md | Document hooks/session_start.py's new session_orphan_notice import in the security-auditor thin-delegation exception block, required for test_hook_delegations_are_documented_exceptions to pass (INFRA-443). | 2026-08-08T04:36:40Z |

## Ensures

1. With an orphaned claim present (INFRA-442's F1 scenario: real
   `.pairmode-worktrees/<ID>/` worktree on branch `pairmode/<ID>`, stale
   `current_stories[<ID>]` entry, `current_story` mirror naming `<ID>`, and
   `docs/phases/permissions/<ID>.json`), a SessionStart hook run exits 0 and its
   `additionalContext` contains a line naming `<ID>` and the literal
   `doctor-state` plus `--apply`. **Forbidden proxy:** emitting the line while
   any of those four artifacts was removed or modified — all four must still
   exist byte-identically after the hook run, and `git branch --list
   pairmode/<ID>` must still be non-empty.
2. With INFRA-442's F2 scenario (worktree directory and branch present,
   permissions artifact present, no state.json stamps at all) the same line is
   emitted naming `<ID>` — the post-`clear-stale-stories` state is surfaced, not
   treated as clean.
3. A project with no orphans and no status drift emits no line containing
   `doctor-state`; the status block is otherwise unchanged from today's output.
   A story that `diagnose_state` classifies `in_flight` (fresh stamp) likewise
   produces no line — mid-build `compact`/`clear` restarts must stay silent.
4. When the only finding is `status_drift`, the emitted line names the story ID
   and `--sync-status`, and does not instruct `--apply` (which by INFRA-442
   Ensures 5 never resolves a status mismatch).
5. `session_orphan_notice.orphan_state_notice(project_dir)` returns the advisory
   string or `None`, performs no writes, and derives its output entirely from
   `diagnose_state`'s return value: with `diagnose_state` monkeypatched to
   return a fixed classification, the rendered line reflects exactly those IDs,
   and with it monkeypatched to return an empty classification the function
   returns `None` even though real orphan artifacts exist on disk. **Forbidden
   proxy:** the module or the hook scanning `.pairmode-worktrees/`,
   `.companion/state.json` or `docs/phases/permissions/` itself.
6. If `orphan_state_notice` raises, the hook still exits 0, still prints its
   normal status block (`Pairmode v… is active in this repo.`), and omits only
   the advisory line — the same failure isolation
   `test_session_start_hook.py`'s existing `agent_staleness_notice` blow-up test
   asserts.

## Instructions

1. Add `skills/pairmode/scripts/session_orphan_notice.py` with
   `orphan_state_notice(project_dir) -> str | None`. Import `diagnose_state`
   from `flex_build` lazily inside the function (flat `sys.path` style, as the
   hook already relies on) so an import failure is contained. Render one line:
   the counts and IDs of `orphans` and `status_drift`, then the concrete repair
   command — `doctor-state --project-dir <dir> --apply` when orphans are
   present, `--sync-status frontmatter|table` when the only finding is status
   drift (both named when both are present). Return `None` when both lists are
   empty. Cap the enumerated IDs (e.g. first 5 plus `+N more`) so a badly
   drifted repo cannot flood the status block.
2. In `hooks/session_start.py`, call it once in its own `try/except Exception:
   pass`, alongside the existing `reconcile_pending_attempts` sweep, and append
   the result to `lines` when it is not `None` — placed after `staleness_notice`
   and before the `Current story:` line. Do not gate on `source`: freshness is
   `diagnose_state`'s job (Ensures 3), not the hook's.
3. Ideology note (resolved inline, § Accepted constraints "Hooks are thin relays
   only"): all classification and rendering live in the module; the hook adds
   one call and one `lines.append`, writes no state on this path, and never
   blocks or repairs. This is the `session_lifecycle.agent_staleness_notice` /
   `subagent_transcript.reconcile_pending_attempts` shape already accepted in
   this hook, not a new exception. Keep the advisory out of the § A4
   `RESTART REQUIRED` banner form — it is a context line only.
4. Tests: add `tests/pairmode/test_session_orphan_notice.py` for the pure
   rendering and monkeypatch cases (Ensures 4, 5), and add the Ensures 1/2/3/6
   hook-level cases to `tests/pairmode/test_session_start_hook.py` using its
   existing harness. Ensures 1 and 2 must build the fixture with a real
   `git worktree add` (as INFRA-442's tests do), and must assert the artifacts
   survive the hook run — a test that only greps the output text would pass
   against an auto-repairing implementation.
5. Spec-writer note: this stub had no `primary_files:` field;
   `skills/pairmode/scripts/session_orphan_notice.py` and
   `hooks/session_start.py` were added to `touches:` instead (the procedure
   permits widening `touches:` only). Set `primary_files:` before building.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_session_orphan_notice.py tests/pairmode/test_session_start_hook.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: both green, including the F1/F2 surfacing cases. Run the full suite
without `-x` so a real failure is not masked by an earlier one.

## Out of scope

- Any repair, including auto-`--apply`: this story detects and surfaces only.
- Blocking or gating session start, or failing the hook, on detected drift.
- Surfacing the same drift from `user_prompt_submit.py` or any other hook.
- Changing `diagnose_state`'s classification rules, its freshness window, or
  `doctor-state`'s own CLI contract (INFRA-442 owns those).
- Gate-verdict invalidation on spec revision (INFRA-444) and F5 era-ledger
  reconciliation.
