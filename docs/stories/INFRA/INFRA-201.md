---
id: INFRA-201
rail: INFRA
title: Fix stale pre-INFRA-191 scope-check assertion in test_templates.py
status: complete
phase: "90"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - tests/pairmode/test_templates.py
touches:
---

# INFRA-201 — Fix stale pre-INFRA-191 scope-check assertion in test_templates.py

## Context

INFRA-191 (`docs/stories/INFRA/INFRA-191.md`, `docs/phases/phase-84.md`, both
`status: complete`) specced inserting a "spec preflight" step into the
build-loop template, positioned between the stub gate and the pre-story scope
check. INFRA-191 updated `skills/pairmode/templates/CLAUDE.build.md.j2` and
added `test_rendered_template_stub_gate_points_to_spec_preflight`
(`tests/pairmode/test_templates.py:2462-2465`), which correctly asserts the
*rendered template* contains `"proceed to the **Spec preflight**"`. INFRA-191
never re-synced flex's own live `CLAUDE.build.md` to pick up this change —
confirmed via `git show HEAD:CLAUDE.build.md` (pre-this-session), which
contained no "spec preflight" content anywhere, and via `git log -S` on
`CLAUDE.build.md`, which shows no commit ever introduced that string to the
file.

A `/flex:pairmode sync-all --apply` run in this session (no code changes
prompted it — a routine methodology sync) ran `sync-build`, which fully
re-renders `CLAUDE.build.md` from the canonical template and overwrites the
file (`skills/pairmode/scripts/pairmode_sync.py:681`,
`build_file.write_text(rendered, ...)` — a whole-file replace, not a
section-merge). This correctly caught flex's own file up to the INFRA-191
flow: stub gate → Spec preflight → Pre-story scope check. `CLAUDE.build.md`
now reads, at line 380: `"If the gate passes: proceed to the **Spec
preflight**."`, with `### Spec preflight` at line 382 and `### Pre-story scope
check` at line 403 — this is the correct, already-approved INFRA-191 flow
finally landing on flex's own file.

This broke `TestBuild025PreStoryScopeCheck::test_flex_claude_build_md_stub_gate_points_to_scope_check`
(`tests/pairmode/test_templates.py:2487-2488`), which asserts flex's own
`CLAUDE.build.md` contains the pre-INFRA-191 wording
`"proceed to the **Pre-story scope check**"` immediately after the stub gate.
That assertion predates INFRA-191 and was never updated when INFRA-191 shipped
the new flow into the canonical template — it is the test that is stale, not
`CLAUDE.build.md`. The current (post-sync) `CLAUDE.build.md` content is
correct and must not be reverted.

## Ensures

1. `test_flex_claude_build_md_stub_gate_points_to_scope_check`
   (`tests/pairmode/test_templates.py`) no longer asserts
   `"proceed to the **Pre-story scope check**"` immediately follows the stub
   gate in flex's own `CLAUDE.build.md`. It instead asserts the INFRA-191 flow:
   the stub gate proceeds to `"proceed to the **Spec preflight**"`, and
   somewhere after the `### Spec preflight` section, the file proceeds to
   `### Pre-story scope check` (matching the already-passing
   `test_flex_claude_build_md_scope_check_appears_between_stub_gate_and_step1`
   test at line 2490, which checks ordering by index, not adjacency).
2. No other test in `TestBuild025PreStoryScopeCheck` is weakened, deleted, or
   has its assertion scope reduced.
3. `CLAUDE.build.md` is not modified by this story — only the test file
   changes. The current (post-sync-build) content, which matches INFRA-191's
   spec, is preserved as-is.
4. `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes
   with zero failures.

## Instructions

- In `tests/pairmode/test_templates.py`, update
  `test_flex_claude_build_md_stub_gate_points_to_scope_check` (currently
  lines 2487-2488) to assert the post-INFRA-191 flow instead of the stale
  pre-INFRA-191 wording. Replace the single assertion
  `assert "proceed to the **Pre-story scope check**" in self.flex_build_md`
  with an assertion that `"proceed to the **Spec preflight**"` is present in
  `self.flex_build_md` (mirroring
  `test_rendered_template_stub_gate_points_to_spec_preflight` at line 2462-2465,
  but against flex's own live file rather than the rendered template).
- Consider renaming the test method to reflect what it now checks (e.g.
  `test_flex_claude_build_md_stub_gate_points_to_spec_preflight`) if doing so
  does not require touching any other test infrastructure (test discovery,
  fixtures, or other references to the old name). If a rename risks
  additional scope, leave the method name as-is and only change the
  assertion body.
- Do not modify `CLAUDE.build.md`, `CLAUDE.build.md.j2`, or any other template
  file. Do not modify `test_rendered_template_stub_gate_points_to_spec_preflight`
  or `test_flex_claude_build_md_scope_check_appears_between_stub_gate_and_step1`
  — both already pass and already assert the correct, current behavior.
- Do not touch `docs/stories/INFRA/INFRA-191.md` or `docs/phases/phase-84.md`
  — those are historical records of a completed phase.

## Tests

`story_class: doc` — this story corrects test text to match already-shipped,
already-spec'd behavior; it introduces no new logic. Run the full gate:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

### Out of scope

- Any change to the content or structure of `CLAUDE.build.md` itself. The
  current post-sync-build content is correct per INFRA-191 and must not be
  reverted or altered.
- Re-litigating whether `sync-build`'s whole-file-overwrite mechanism (as
  opposed to `sync.py`'s section-merge mechanism) is the right design for
  propagating template changes. That is a separate methodology question, not
  in scope here.
- The unrelated spurious `CORE`/`TEST` placeholder rows added to
  `docs/eras/003-flex-orchestrator-as-harness.md` by the same `sync-all` run
  (caused by `.companion/state.json` lacking a `stack`/`project_name` field).
  That is tracked separately and not touched by this story.
