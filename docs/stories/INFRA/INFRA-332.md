---
id: INFRA-332
rail: INFRA
title: Sync backfill — sync-agents gains an add-missing-file path; backfill flex and flex-harness
status: complete
phase: "116"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/pairmode_sync.py
touches:
  - .claude/agents/spec-writer.md
  - .claude/agents/docs-reviewer.md
  - .claude/agents/gate-worker.md
  - skills/pairmode/skills/session_lifecycle.py
  - tests/pairmode/test_pairmode_sync.py
  - skills/pairmode/SKILL.md
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-138 (AG-13): `pairmode_sync.py`'s `sync-agents` (also chained by
`sync-all`, and delegated to by `pairmode_migrate.py` rule 2) only rewrites
agent files that already exist on disk in a target project's
`.claude/agents/` — "sync-agents walks .claude/agents/ in a target project,
finds the matching Jinja2 template ... for each" (`pairmode_sync.py:8-9`).
It has no path to *add* a file that exists only as a template but was never
scaffolded. `bootstrap.py` is the only code path that creates new agent
files, and it runs once, at fresh-install time.

Consequence, confirmed live: `docs-reviewer.md.j2` (INFRA-325, Phase 114)
landed as "complete" in flex's own repo, but flex's own `.claude/agents/`
never received `docs-reviewer.md` — the fix updated the template and the
scaffold list for *future* bootstraps, but nothing propagated it into flex
itself, the very project that shipped the fix. `gate-worker.md.j2` predates
INFRA-325 entirely (RELEASE-010) and has the identical gap. This is the
direct mechanical cause of CER-137's live-hit (docs-reviewer dispatch
fell back to a generic subagent this session).

This story depends on INFRA-331: the `spec-writer.md.j2` template must exist
before a backfill mechanism has anything to backfill for that role.

## Requires

1. `pairmode_sync.py`'s `sync-agents` implementation (`:776-` per the module
   docstring pointer) and its file-discovery loop — understand exactly how it
   currently enumerates "agent file found in `<project-dir>/.claude/agents/`"
   before adding an inverse (template-not-yet-scaffolded) enumeration.
2. `bootstrap.py`'s `AGENT_FILES` list (post-INFRA-331: nine entries) as the
   canonical source of "which templates should exist as agent files" — do
   not hand-maintain a second list; import or otherwise reuse `AGENT_FILES`.
3. `session_lifecycle.py` (INFRA-323) — the `RESTART REQUIRED` notice
   contract. Adding a *new* file to `.claude/agents/` is exactly the kind of
   registration-surface change that contract was built for; a newly-added
   file must trigger the same notice as a rewritten one. Do not build a
   second notice mechanism.
4. Baseline suite count.

## Ensures

1. **`sync-agents` gains an add-missing-file path.** For every
   `(target_path, template_name)` pair in `bootstrap.AGENT_FILES` whose
   `target_path` does not exist in the project's `.claude/agents/`,
   `sync-agents --apply` renders the template and writes the file (mirroring
   `bootstrap`'s own render call, not a divergent implementation); without
   `--apply` it reports what would be added, consistent with the command's
   existing dry-run/apply convention. **Correct signal:** running
   `sync-agents --apply` against a fixture project missing one or more
   `AGENT_FILES` entries results in all of them present afterward, byte-for-
   byte matching what a fresh `bootstrap --apply` would have produced for the
   same entries; **forbidden proxy:** a "would add N files" report with no
   `--apply` write path, or a write path that only logs success without the
   file actually landing.
2. **Existing update behavior is unchanged.** Files already present continue
   to be rewritten exactly as before (regression-free) — this story is
   additive to the enumeration, not a rewrite of the update logic.
3. **`session_lifecycle`'s `RESTART REQUIRED` notice fires on additions.**
   A run that adds one or more new agent files prints the same notice
   `sync-agents` already prints for frontmatter rewrites (INFRA-323's
   existing wiring point) — verify by test, not by inspection only.
4. **Flex and flex-harness are backfilled.** After landing, run
   `sync-agents --apply` (or the equivalent bootstrap-parity path) against
   both `/mnt/work/flex` and `/mnt/work/flex-harness`; confirm both now have
   all nine `.claude/agents/*.md` files. Record the before/after file listing
   as evidence — this is a real, observable state change to this repo's own
   `.claude/agents/`, not just a capability added to the tool.
5. **Docs updated.** `skills/pairmode/SKILL.md`'s `sync-agents` section
   states the add-missing-file behavior; `docs/architecture.md`'s
   sync-agents description (if one exists — locate before assuming) is
   corrected from "walks .claude/agents/" (existing-files-only framing) to
   reflect the new add path.
6. **Suite green.** Full run without `-x`; baseline + added tests.

## Instructions

1. Confirm INFRA-331 has landed (spec-writer.md.j2 exists, AGENT_FILES has
   nine entries) before starting — this story's fixture tests need all nine
   template names to be real.
2. Reuse `bootstrap.AGENT_FILES` and, where practical, the same render-and-
   write helper `bootstrap.py` already calls, rather than duplicating render
   logic in `pairmode_sync.py`.
3. After the code lands and its own tests pass, run the backfill against
   flex and flex-harness as a real operational step (Ensures 4) — this is
   part of the story's acceptance, not an optional follow-up.
4. Do not change `bootstrap.py`'s own behavior — it already creates all nine
   files correctly on a fresh install; this story only closes the gap for
   already-bootstrapped projects.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_pairmode_sync.py -q 2>&1 | tail -15
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -5
```

Acceptance: green; baseline held. Reviewer negative check: `ls
.claude/agents/*.md | wc -l` in both flex and flex-harness returns 9 after
the backfill step; a fixture test asserts `sync-agents --apply` on a
project missing N of nine files results in exactly N new files with no
diff against the corresponding fresh-bootstrap output.

## Out of scope

- Any `model_selector.py` change (INFRA-333).
- Any escalation-ladder change (INFRA-334).
- The work→agent-type classification doc (INFRA-335).
- Backfilling any fleet project other than flex and flex-harness — the
  fleet-wide propagation rides the existing post-checkpoint sync campaign
  mechanism (per INFRA-311's precedent), not this story.

## Evidence

**Root cause of the prior attempt's broken backfill (pre-retry corruption).**
`_build_template_context()` in `skills/pairmode/scripts/pairmode_sync.py`
unconditionally set `pairmode_scripts_dir` to `str(Path(__file__).parent)` —
the location of *whichever copy of `pairmode_sync.py` happened to be running*
— on every call, for both the `sync-build` (CLAUDE.build.md) and `sync-agents`
(agent frontmatter/add-path) render contexts. This is a deliberate,
documented design for the *initial* binding (`docs/architecture.md` §
Pairmode tooling / § Fleet discovery: "`pairmode_scripts_dir =
Path(__file__).parent` is baked in at sync time"), but it has no mechanism to
*preserve* an already-established binding across a later re-sync run — every
re-sync silently re-binds to wherever the tool is invoked from, whether or
not that location is the project's intended canonical binding.

The prior attempt ran the real-world backfill (Ensures #4) with the sync tool
physically located under `.pairmode-worktrees/INFRA-332/skills/pairmode/scripts/`
(a disposable per-story worktree) but passed `--project-dir /mnt/work/flex`
(and separately `/mnt/work/flex-harness`) as the *target*. Because
`pairmode_scripts_dir` was computed from `__file__` (the worktree) rather
than from the target `project_dir`'s own already-declared binding, the three
newly-rendered files (`docs-reviewer.md`, `gate-worker.md`, `spec-writer.md`)
in *both* real checkouts baked in
`/mnt/work/flex/.pairmode-worktrees/INFRA-332/skills/pairmode/scripts` — a
path that stops existing the moment the story worktree is discarded — instead
of each project's actual binding, `/mnt/work/flex-harness/skills/pairmode/scripts`
(flex dogfoods its own pairmode via the sibling flex-harness checkout, per
`docs/architecture.md` § Release channel — flex-harness; flex-harness's own
`CLAUDE.build.md` declares the same path for itself). The broken files were
deleted from both real checkouts before this retry.

**Fix (code, not a one-off invocation workaround).** Added
`_resolve_pairmode_scripts_dir(project_dir)` in `pairmode_sync.py`: it reads
the target project's own `CLAUDE.build.md` for an already-declared
`pairmode_scripts_dir` line (reusing `fleet_discovery.py`'s Signal-1 regex,
imported rather than duplicated) and returns that verbatim when present.
Only a project with no declaration yet (a fresh bootstrap, or a pre-0.3.0
project that has never run `sync-all --apply`) falls back to
`Path(__file__).resolve().parent` — the same first-time-binding behavior
`bootstrap.py` itself already uses. `_build_template_context()` now calls
this helper instead of computing `pairmode_scripts_dir` inline. This means
re-syncing (or backfilling) a project is anchored to *that project's own*
persisted binding regardless of where the sync tool physically runs from —
running it from a disposable worktree, from the canonical flex checkout, or
from anywhere else all produce the same, correct result for a given target
project. Verified by test:
`test_sync_agents_add_missing_files_matches_fresh_bootstrap` and the
`TestBuildTemplateContext` class in
`tests/pairmode/test_pairmode_sync.py` (existing tests continue to pass
unmodified, confirming the fallback path for undeclared/fixture projects is
unchanged).

**Add-missing-file path (Ensures #1).** `_collect_missing_agent_files()`
enumerates `bootstrap.AGENT_FILES` (imported, not hand-duplicated) against
`.claude/agents/` and renders (via `_render_full_template`, the same jinja2
`StrictUndefined`/`keep_trailing_newline` environment settings
`bootstrap._render_template` uses) any entry whose target path is missing.
Wired into `sync_agents()` alongside the pre-existing `_collect_changes()`
update path; both share the diff-printing, confirm-prompt, write, and
`_emit_restart_notice` (INFRA-323) call sites, so additions fire the same
`RESTART REQUIRED` notice as rewrites (Ensures #3) without a second notice
mechanism. Fixture test
`test_sync_agents_add_missing_files_matches_fresh_bootstrap` asserts a
project missing all nine `AGENT_FILES` entries has all nine present after
`sync-agents --apply`, each byte-for-byte identical to
`bootstrap._render_template()`'s output for the same entry and context.
`test_sync_agents_add_missing_files_dry_run_reports_without_writing` and
`test_sync_agents_add_missing_files_confirm_prompt_declined_writes_nothing`
cover the forbidden-proxy case (report-without-write). Existing-file update
behavior is regression-free (Ensures #2) — the full pre-existing
`tests/pairmode/test_pairmode_sync.py` suite (84 tests, including the
render-failure/no-op/restart-notice tests that invoke `sync_agents` via
`CliRunner`) passes unmodified in behavior; one pre-existing test
(`test_sync_agents_no_changes_prints_no_notice`) was updated to patch
`TEMPLATES_DIR` to an empty synthetic directory, since an empty
`.claude/agents/` directory is no longer a true no-op once the add-path
exists — the updated test now documents that distinction explicitly rather
than silently asserting stale behavior.

**Real backfill (Ensures #4) — before/after, verified by reading the
generated files, not by exit code.**

Before (both projects, prior to this story's `sync-agents --apply` run):
```
$ ls /mnt/work/flex/.claude/agents/*.md
builder.md  intent-reviewer.md  loop-breaker.md  reconstruction-agent.md  reviewer.md  security-auditor.md
$ ls /mnt/work/flex-harness/.claude/agents/*.md
builder.md  intent-reviewer.md  loop-breaker.md  reconstruction-agent.md  reviewer.md  security-auditor.md
```
6 of 9 present in both — missing `docs-reviewer.md`, `gate-worker.md`,
`spec-writer.md` in both.

Command run (from this story's worktree, target `--project-dir` pointed at
each real checkout in turn):
```
uv run python skills/pairmode/scripts/pairmode_sync.py sync-agents --project-dir /mnt/work/flex --yes
uv run python skills/pairmode/scripts/pairmode_sync.py sync-agents --project-dir /mnt/work/flex-harness --yes
```

After:
```
$ ls /mnt/work/flex/.claude/agents/*.md | wc -l
9
$ ls /mnt/work/flex-harness/.claude/agents/*.md | wc -l
9
```
Both now have all nine. `git status --short .claude/agents/` in each real
checkout:
```
flex:          ?? docs-reviewer.md  ?? gate-worker.md  ?? spec-writer.md
               M  builder.md  M intent-reviewer.md  M loop-breaker.md
               M  reconstruction-agent.md  M reviewer.md  M security-auditor.md
flex-harness:  ?? docs-reviewer.md  ?? gate-worker.md  ?? spec-writer.md
```
(flex's six pre-existing files also picked up a stale `description:`
frontmatter field re-render — a `flex-harness`→`flex` project-name
correction — from the ordinary, pre-existing frontmatter-sync path
unrelated to this story's add-path; flex-harness's six pre-existing files
had no drift, so `sync-agents` reported no updates for them.)

Read directly (not inferred from exit code) — every new file in both
checkouts anchors to that project's own `pairmode_scripts_dir` declaration,
never the story worktree:
```
$ grep -n '^/mnt/work' /mnt/work/flex/.claude/agents/{gate-worker,docs-reviewer,spec-writer}.md \
    /mnt/work/flex-harness/.claude/agents/{gate-worker,docs-reviewer,spec-writer}.md
flex/.claude/agents/gate-worker.md:37:/mnt/work/flex-harness/skills/pairmode/scripts/../../../skills/pairmode/gate_worker/SKILL.md
flex/.claude/agents/docs-reviewer.md:43:/mnt/work/flex-harness/skills/pairmode/scripts/../../../skills/pairmode/skills/checkpoint-docs/procedure.md
flex/.claude/agents/spec-writer.md:41:/mnt/work/flex-harness/skills/pairmode/scripts/../../../skills/pairmode/skills/spec-writer/procedure.md
flex-harness/.claude/agents/gate-worker.md:37:/mnt/work/flex-harness/skills/pairmode/scripts/../../../skills/pairmode/gate_worker/SKILL.md
flex-harness/.claude/agents/docs-reviewer.md:43:/mnt/work/flex-harness/skills/pairmode/scripts/../../../skills/pairmode/skills/checkpoint-docs/procedure.md
flex-harness/.claude/agents/spec-writer.md:41:/mnt/work/flex-harness/skills/pairmode/scripts/../../../skills/pairmode/skills/spec-writer/procedure.md
```
All six new files (three per checkout) anchor to `/mnt/work/flex-harness/...`
— each project's own registered `pairmode_scripts_dir` (both flex and
flex-harness declare that same path in their own `CLAUDE.build.md`, per the
sibling-worktree dogfood design) — with no occurrence of
`.pairmode-worktrees` anywhere in either checkout's `.claude/agents/`.

These real-checkout file writes are outside this story's own worktree and
are not part of this story's commit; they are the required, direct
operational side effect of Ensures #4, left in place in both real checkouts
per the story's instructions.

**Suite (Ensures #6).**
```
tests/pairmode/test_pairmode_sync.py: 84 passed
tests/pairmode/: 4712 passed, 211 skipped
```
