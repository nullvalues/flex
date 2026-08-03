---
id: INFRA-375
rail: INFRA
title: Audit hardcoded flex-harness absolute paths for release-channel staleness risk (CER-160)
status: draft
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - tests/pairmode/test_harness_path_audit.py
touches:
  - skills/pairmode/templates/agents/builder.md.j2
  - skills/pairmode/templates/agents/reviewer.md.j2
  - skills/pairmode/templates/agents/spec-writer.md.j2
  - skills/pairmode/templates/agents/docs-reviewer.md.j2
  - skills/pairmode/templates/agents/gate-worker.md.j2
  - skills/pairmode/templates/agents/intent-reviewer.md.j2
  - skills/pairmode/templates/agents/loop-breaker.md.j2
  - skills/pairmode/templates/agents/security-auditor.md.j2
  - skills/pairmode/templates/agents/shadow-reviewer.md.j2
  - .claude/agents/
  - docs/architecture.md
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-160 (MEDIUM): a worker that resolves the hardcoded absolute path to `flex-harness`'s copy of
`skills/pairmode/skills/spec-writer/procedure.md` (the path INFRA-304's E13 rationale calls for)
can silently run a stale, pre-checkpoint-promotion version of that procedure mid-phase. This
reproduced live during INFRA-362's Phase 118 dogfood exercise: a spec-writer instructed to use the
absolute harness path found a 298-line, five-bounded-input procedure with no narrative step, while
the correct in-repo copy (already updated by INFRA-355/357 in the same phase) was 381 lines with
six inputs and Steps 4c/4d. Because the release-channel design only updates the harness copy at
checkpoint-tag, any worker resolving a hardcoded harness-absolute path is running last-checkpoint's
tooling by construction. Fix direction: audit every other hardcoded `flex-harness` absolute-path
reference (agent shells, skill docs) for the same staleness risk, and consider whether
procedure/skill docs should resolve from the project's own tree rather than the pinned harness
copy. Files: `skills/pairmode/skills/spec-writer/procedure.md`, plus any other absolute-
`flex-harness`-path references found in the audit.

Picked up now as part of era 004's Phase 119 goal of draining the CER backlog to zero unresolved
operational findings.

## Requires

- No prior story in Phase 119 is a prerequisite. INFRA-369 (CER-146) also touches a
  `flex-harness` coupling but in `tests/pairmode/test_flip_dogfood.py`, which this story
  explicitly excludes — no file overlap, no ordering constraint.

## Ensures

1. `tests/pairmode/test_harness_path_audit.py` exists and defines a module-level allowlist
   mapping each repo-relative path that legitimately contains the literal
   `/mnt/work/flex-harness` to a non-empty one-line rationale string. This allowlist *is*
   the audit inventory the story owes — every reference found on the scan surface below is
   either fixed out of existence or present here with its reason.
2. A test in that file walks the scan surface — `.claude/agents/`, `skills/`, `hooks/`, and
   root-level `CLAUDE.md` / `CLAUDE.build.md`, excluding `docs/`, `CHANGELOG.md`, `tests/`,
   `node_modules/`, `.git/` — for the literal `/mnt/work/flex-harness`, and asserts the set of
   matching repo-relative paths equals the allowlist's key set exactly. A new unlisted
   reference fails; a removed listed one also fails. Forbidden proxy: a test that iterates a
   hardcoded list of file paths instead of walking the surface, or that only asserts the
   allowlist is non-empty.
3. Each of the nine `skills/pairmode/templates/agents/*.md.j2` templates' procedure/SKILL
   pointer paragraph instructs the worker to read the project's own in-tree copy at the same
   repo-relative path when that file exists, falling back to the
   `{{ pairmode_scripts_dir }}`-anchored absolute path only when it does not, and names
   CER-160 as the reason.
4. No rendered shell under `.claude/agents/` still carries the pre-INFRA-304 bare-relative
   pointer with no absolute fallback: `grep -L "/mnt/work/flex-harness" .claude/agents/*.md`
   prints exactly `.claude/agents/reconstruction-agent.md` and nothing else
   (`reconstruction-agent.md` has no procedure pointer at all — it is legitimately absent,
   not stale).
5. `docs/architecture.md` § Release channel gains a paragraph stating the resolution rule:
   a harness-absolute path resolves into the release channel, which only advances at
   checkpoint-tag, so content resolved that way is last-checkpoint's by construction;
   procedure/skill *docs* therefore prefer the project's own tree, while `flex_build.py`
   *script* invocations stay pinned to the channel on purpose.
6. `CLAUDE.build.md`'s `/mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py`
   invocations are byte-unchanged by this story; their disposition is recorded as
   pinned-by-design in the allowlist rationale (Ensures 1). Forbidden proxy: rewriting them
   to relative or project-anchored paths "for consistency".
7. `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` is green.

## Instructions

1. Run the scan first and read the result — the audit is the work, the fix follows from it:
   `grep -rn "/mnt/work/flex-harness" .claude/agents skills hooks CLAUDE.md CLAUDE.build.md`.
   At spec time this surface held references in 7 files; treat that as a starting point to
   verify, not a number to assume.
2. Classify every hit into exactly one of three dispositions, and record the classification
   as the allowlist rationale: **fixed** (the reference is removed or made
   in-tree-preferring), **pinned-by-design** (`CLAUDE.build.md`'s script invocations — the
   dogfood surface; the orchestrator is *supposed* to run the released channel's
   `flex_build.py`), or **not-a-path** (a docstring or comment quoting the string as an
   example of what a detector matches, e.g. in `hook_view.py`, `fleet_discovery.py`,
   `pairmode_migrate.py` — no runtime resolution happens, so no staleness risk).
3. Edit the nine agent templates' shared pointer paragraph to the in-tree-preferring form.
   The single rule must be correct in both deployments: flex's own worktree vendors
   `skills/pairmode/`, so the in-tree branch fires and the authoring copy wins; a bootstrapped
   consuming project does not vendor it, so the branch falls through to the absolute path and
   INFRA-304's E13 rationale is preserved unchanged.
4. Bring the rendered `.claude/agents/*.md` shells back in step with their templates. Six of
   the nine were found rendered with the old bare-relative pointer while their template
   already carried the absolute one — `sync-agents` backfills missing files rather than
   re-rendering existing ones. If that is still true, edit the rendered files directly to
   match; do not change `sync-agents`' backfill semantics here (see Out of scope).
5. Write the guard test, then add the architecture.md paragraph (Ensures 5).
6. Ideology note: the allowlist deliberately requires a rationale string per entry rather
   than a bare path list, preserving the "rationale-bearing decisions over bare rules"
   conviction — a future agent that hits the failing test must be able to see *why* each
   surviving reference was allowed.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_harness_path_audit.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
grep -L "/mnt/work/flex-harness" .claude/agents/*.md
```

Acceptance: the new test file passes; the full suite is green; the `grep -L` prints exactly
`.claude/agents/reconstruction-agent.md`.

## Out of scope

- Changing `pairmode_sync.py`'s `sync-agents` from backfill-only to re-render-existing. That is
  a real gap (it is why the rendered shells drifted), but it is a behavioural change to the
  fleet propagation path and belongs in its own story/CER, not inside an audit.
- `tests/pairmode/test_flip_dogfood.py`'s dependence on the literal checkout directory name —
  owned by INFRA-369 (CER-146) in this same phase.
- The `stale-flex-harness` classifier string values in `hook_view.py` / `pairmode_migrate.py`
  and their test fixtures: those are detector literals, not path resolution.
- Repointing `CLAUDE.build.md` away from the release channel (Ensures 6).
