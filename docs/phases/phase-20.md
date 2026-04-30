# anchor — Phase 20: PR readiness — documentation, pipe clarity, contribution packaging

← [Phase 19: Test coverage and integration verification](phase-19.md)

## Goal

Phase 20 prepares the codebase for a pull request back to the parent anchor repo.
Six stories: README.md, pipe architecture documentation, a standalone PAIRMODE.md
for the upstream maintainer, CHANGELOG.md and CONTRIBUTING.md, a final pre-PR audit
gate, and a careful git history review that pauses for developer approval before any
destructive operations.

The pipe story is the most sensitive for the PR. This fork changed the hook pipe path
from a hardcoded global singleton to a project-scoped path. That change is backwards-
compatible but touches all four hook files. The upstream maintainer needs to understand
it clearly before deciding whether to accept, adapt, or negotiate an alternative.

Prerequisites: Phase 19 complete and tagged cp19-test-coverage-integration.

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| BUILD-003 | Write README.md | planned |
| INFRA-015 | Document project-scoped pipe architecture and upstream divergence | planned |
| BUILD-004 | Write docs/pairmode/PAIRMODE.md: standalone contribution guide | planned |
| BUILD-005 | Write CHANGELOG.md and CONTRIBUTING.md | planned |
| INFRA-016 | Final pre-PR audit: full test suite, security pass, open CER review | planned |
| INFRA-017 | Git history review and squash plan — pauses for developer approval | planned |

---

### Story BUILD-003 — Write `README.md`

**Rail:** BUILD

**Acceptance criterion:** `README.md` exists at the repo root. It explains anchor +
pairmode to a developer who has never seen it, includes two concrete use case scenarios,
shows CLI examples, is honest about alpha status, and is under 400 lines. No emojis.
Tests pass (doc story; no logic tests needed).

**Instructions:**

Write `README.md` based on the following outline. Prose should be tight and direct.
No marketing language. No emojis. Every section should earn its place.

**Structure:**

```markdown
# Anchor — The IDE for Intent

(one-paragraph problem statement: code is cheap to generate; intent is scarce;
agents drift without it; anchor makes intent persistent)

## Status
alpha / under active development. Core workflows functional. See Known Limitations.

## What anchor does

Two complementary layers:
- Memory layer: /anchor:seed + /anchor:companion
- Process layer: /anchor:pairmode

One paragraph each. End with: "Used together, the memory layer supplies the spec;
the process layer enforces it."

## Installation

bash snippet for plugin-dir install + marketplace note.
Requirements: Claude Code, Python 3.11+, uv.

## Quick start

### New project
Three commands with explanatory comments. Bootstrap → story → build.

### Existing project with session history
/anchor:seed → /anchor:companion → /anchor:pairmode bootstrap.

## The three skills

Brief table or three subsections. For each: what it does, key command, key output.

## Use case scenarios (two)

Scenario A: New project with build loop (name a domain, show bootstrap + build
  loop in outline form, explain what the reviewer caught).
Scenario B: Returning developer (3 months away, run audit, sync, continue building).

## The build loop

Six-step numbered list. No prose padding.

## The canonical spec format

One JSON code block with comments.

## Known limitations

Unordered list, honest:
- alpha / sharp edges
- solo-developer optimized
- sidebar required for real-time conflict detection
- lesson annotation requires manual template edits
- story status update and some orchestrator steps require manual bash invocations
  (story_update.py introduced in Phase 18 reduces this)

## Requirements and License
```

**Tests:** None beyond ensuring the file exists and is under 400 lines
(add a test in `tests/pairmode/test_docs.py` — new file — that asserts
`len(README.md.read_text().splitlines()) < 400`).

---

### Story INFRA-015 — Document project-scoped pipe architecture and upstream divergence

**Rail:** INFRA

**Acceptance criterion:** `docs/pipe-architecture.md` exists and accurately explains:
the original single-pipe design, the fork's project-scoped change, the rationale
(multi-project concurrency), the backwards-compatibility guarantee, and what the
upstream PR touches in core files. `docs/architecture.md` cross-references it. Tests pass.

**Instructions:**

Create `docs/pipe-architecture.md` with the following sections:

**1. Original design**
The upstream anchor repo uses a single hardcoded pipe path: `/tmp/companion.pipe`.
All hook scripts write to this path. The companion sidebar reads from it.
This works correctly when one anchor project is active on a machine at a time.

**2. The multi-project problem**
When two Claude Code projects are open simultaneously — both with anchor active — their
hook scripts both write to `/tmp/companion.pipe`. Sidebar A processes messages from both
projects. Sidebar B also processes both. Decisions from project A get recorded into
project B's spec, and vice versa. This is a silent data corruption scenario.

**3. Fork change: project-scoped pipe path**
This fork changes the pipe path to be project-scoped. At startup, each hook script
reads the pipe path from `.companion/state.json["pipe_path"]`. If that key is absent
(legacy projects without a `state.json`), hooks fall back to `/tmp/companion.pipe`.

The pipe path stored in `state.json` is:
```python
f"/tmp/companion-{hashlib.md5(str(project_dir).encode()).hexdigest()[:8]}.pipe"
```
Each project gets a unique, deterministic pipe name. Two projects open simultaneously
use different pipes; their sidebars never cross-contaminate.

**4. Backwards-compatibility**
The fallback to `/tmp/companion.pipe` when `state.json` is absent means the change is
backwards-compatible for any project that has not yet run `/anchor:companion` to
establish a `state.json`. Such projects behave exactly as before.

**5. Files changed in anchor core (hook layer)**
This is the complete list of core files modified by this fork:

| File | Change |
|------|--------|
| `hooks/stop.py` | Pipe path read from `state.json["pipe_path"]` at startup; falls back to `/tmp/companion.pipe` |
| `hooks/post_tool_use.py` | Same |
| `hooks/exit_plan_mode.py` | Same |
| `hooks/session_end.py` | Same |

No other core files were modified. All pairmode additions are self-contained under
`skills/pairmode/`, `lessons/`, `tests/pairmode/`, and `docs/`.

**6. Alternative approaches and upstream negotiation**
If the upstream maintainer has a different multi-project strategy in progress, the
narrowest compatible change is: read pipe path from an env variable
(e.g., `ANCHOR_PIPE_PATH`) with fallback to `/tmp/companion.pipe`. This would require
the companion skill to set the env variable at session start, without modifying `state.json`.
Either approach achieves the same goal; the state.json approach was chosen because the
companion skill already writes `state.json` at startup and does not require shell
environment plumbing.

**`docs/architecture.md` update:**
In the "Hook architecture" section, add one sentence after the pipe description:
"See `docs/pipe-architecture.md` for the project-scoped pipe design, its
backwards-compatibility guarantee, and what changed relative to the original
single-pipe design."

**Tests:** None — doc story. Add a line to `tests/pairmode/test_docs.py` asserting
`docs/pipe-architecture.md` exists.

---

### Story BUILD-004 — Write `docs/pairmode/PAIRMODE.md`: standalone contribution guide

**Rail:** BUILD

**Acceptance criterion:** `docs/pairmode/PAIRMODE.md` exists as a self-contained document
for an upstream maintainer reviewing the PR. It covers what pairmode adds, what it changed
in anchor core, design decisions, known limitations, and how to run the tests. Tests pass.

**Instructions:**

Create `docs/pairmode/` directory (mkdir if absent) and write `PAIRMODE.md`:

**Structure:**

**What pairmode is (one paragraph)**
A structured builder/reviewer workflow methodology shipped as a new anchor skill.
Stories are specced before building. Permission scoping pre-authorizes declared file edits.
The reviewer subagent enforces a checklist and commits or reverts. A 5-step checkpoint
sequence gates each phase.

**What pairmode adds to anchor (enumerated)**
New files only. Organized by category:
- New skill: `skills/pairmode/` (SKILL.md, scripts/, templates/)
- New tests: `tests/pairmode/`
- New docs: `docs/phases/`, `docs/stories/`, `docs/eras/`, `docs/cer/`
- New lessons store: `lessons/lessons.json`, `lessons/LESSONS.md`
- Updated plugin manifest: `.claude-plugin/plugin.json` (pairmode skill entry added)

**What pairmode changed in anchor core (explicit table)**

| File | Change | Reason |
|------|--------|--------|
| `hooks/stop.py` | Pipe path read from `.companion/state.json["pipe_path"]`; fallback to `/tmp/companion.pipe` | Multi-project concurrency: prevent cross-project pipe contamination |
| `hooks/post_tool_use.py` | Same | Same |
| `hooks/exit_plan_mode.py` | Same | Same |
| `hooks/session_end.py` | Same | Same |
| `.claude-plugin/plugin.json` | Added `pairmode` skill entry | Register the new skill |

See `docs/pipe-architecture.md` for full rationale and backwards-compatibility notes.

**What pairmode did NOT change**
- `skills/seed/` — unchanged
- `skills/companion/scripts/sidebar.py` — unchanged except Story INFRA-013 (spec_exception handler)
- `skills/companion/scripts/start_sidebar.sh` and launchers — unchanged
- `.claude-plugin/marketplace.json` — unchanged
- Any existing docs in `docs/` (only new docs were added)

**Design decisions (brief, justified)**

| Decision | Rationale |
|----------|-----------|
| Rails over flat story IDs | Enforces architectural lane ownership; cross-rail touches are surfaced explicitly |
| Eras as strategic containers | Intent-scoped (not version/release-scoped); supports solo developers who don't release on a schedule |
| Permission pre-scoping per story | Eliminates mid-build approval prompts without permanently widening permissions |
| Reviewer as subagent, not rule set | Can apply judgment to ambiguous cases; can run full test suite; commit-or-revert removes human bottleneck for routine stories |
| 5-step checkpoint (not just tests) | Security audit and intent review catch classes of problems tests cannot: API key exposure, design pivots, architectural drift |

**Known limitations and open work**
- Solo-developer optimized: no multi-developer story assignment or pipe collision avoidance between developers
- Sidebar required for real-time conflict detection; pairmode works without it (generic deny list, no live spec surfacing)
- `lesson_review.py` annotates templates but does not implement changes; developer must open templates manually
- Story status updates require bash invocations (Phase 18 introduced `story_update.py` to reduce friction but does not fully automate status lifecycle)

**Running the tests**
```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```
All 1000+ pairmode tests run in under 15 seconds on a standard laptop.

**Tests:** `tests/pairmode/test_docs.py` asserts `docs/pairmode/PAIRMODE.md` exists.

---

### Story BUILD-005 — Write `CHANGELOG.md` and `CONTRIBUTING.md`

**Rail:** BUILD

**Acceptance criterion:** `CHANGELOG.md` covers all phases in summary form using
keep-a-changelog style. `CONTRIBUTING.md` explains how to run tests, add a lesson,
propose a template change, and file a CER. Both files exist and are under 200 lines
each. Tests pass.

**Instructions:**

**`CHANGELOG.md`:**

Use keep-a-changelog format. Two top-level entries:

```markdown
# Changelog

All notable changes to anchor are documented here. Pairmode changes are marked [pairmode].

## [Unreleased]

### Added [pairmode]
- Phase 17–20: correctness fixes, missing tooling, test coverage, PR preparation
  (story_update.py, .pairmode-overrides, --yes flag, schema_validator integration,
  spec_exception sidebar handler, README, pipe docs, PAIRMODE.md)

### Changed [core]
- hooks/{stop,post_tool_use,exit_plan_mode,session_end}.py: pipe path is now
  project-scoped via .companion/state.json["pipe_path"] with fallback to
  /tmp/companion.pipe. Backwards-compatible. See docs/pipe-architecture.md.

## [pairmode v0.0.x] — Phases 1–16 (anchor era2 branch)

### Added [pairmode]
- Phase 1–7: core scaffold, spec-derived generation, lessons, audit/sync,
  companion enhancements, audit noise reduction, template coherence
- Phase 8–9: sync confirmation, tooling fixes, dead code cleanup, pipe contract
- Phase 10: ideology capture (guided, non-interactive, reconstruction seeding)
- Phase 11–12: reconstruction workflow, seeding, RECONSTRUCTION.md.j2
- Phase 13: CER cleanup, e2e reconstruction verification
- Phase 14: reconstruction agent tooling, score.py
- Phase 15: rails, eras, discrete story files, schema_validator, story_new, era_new
- Phase 16: permission_scope.py, story_resolver.py, manifest-aware CLAUDE.build.md,
  rail violation detection, sync rail gap detection
```

**`CONTRIBUTING.md`:**

Sections:
- **Running tests**: exact command
- **Adding a lesson**: `/anchor:pairmode lesson` walkthrough
- **Proposing a template change**: lesson → review → template annotation → implement → test
- **Filing a CER**: `cer.py` command + format
- **Story and phase conventions**: rail assignment, commit format `feat(story-RAIL-NNN):`, checkpoint sequence
- **Protected files**: list them, explain why, explain how to justify a modification
- **Pipe architecture**: one sentence + pointer to `docs/pipe-architecture.md`

**Tests:** `tests/pairmode/test_docs.py` asserts both files exist and are under 200 lines.

---

### Story INFRA-016 — Final pre-PR audit: full test suite, security pass, open CER review

**Rail:** INFRA

**Acceptance criterion:** All tests pass (pairmode suite + any other tests in the repo).
No CRITICAL or HIGH security findings. All CER Do Later items either resolved or have
a corresponding backlog story file. Do Now section is empty. `docs/pairmode/PAIRMODE.md`
"What pairmode changed in anchor core" table is verified against the actual hook files.
This is a gate story — no code changes, only verification. On pass: tagged
`pr-candidate-v0.1`.

**Instructions:**

This story has no code changes. It is a checkpoint gate.

1. Run `PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -x -q`. Report count and
   any failures.

2. Spawn a security audit subagent:
   "Full security audit of skills/pairmode/ — Phase 20 pre-PR checkpoint."
   Any CRITICAL or HIGH finding causes this story to FAIL. Create a new INFRA story
   to fix it and re-run before tagging.

3. Read `docs/cer/backlog.md`. For each Do Later item without a resolution note:
   verify a corresponding backlog story file exists in `docs/stories/INFRA/` or the
   appropriate rail. If any Do Later item has no story: create one (via `story_new.py`,
   status `backlog`). Confirm Do Now is empty.

4. Read `docs/pairmode/PAIRMODE.md` table "What pairmode changed in anchor core".
   Read each hook file listed. Verify the description in the table accurately reflects
   what the file actually does. If any discrepancy: update the table (not the hook).

5. Read `docs/pipe-architecture.md` section "Files changed in anchor core". Cross-check
   against `git diff` from the fork point. Confirm no core files were changed that are
   not listed.

On pass: tag `pr-candidate-v0.1`. Do not push without user confirmation.

---

### Story INFRA-017 — Git history review and squash plan — pauses for developer approval

**Rail:** INFRA

**Acceptance criterion:** A clean, readable analysis of the current commit history is
produced relative to the fork point. A specific squash plan is drafted and presented to
the developer for approval. No git operations that rewrite history are performed without
explicit developer sign-off. This story STOPS and presents the plan before doing anything
destructive.

**Instructions:**

**This story does not rewrite history. It produces a plan and stops.**

**Step 1 — Identify the fork point:**
```bash
git log --oneline origin/main..HEAD 2>/dev/null || git log --oneline main..HEAD 2>/dev/null
```
If the upstream remote is not configured, use `git log --oneline` from the first commit
that appears to be pairmode-related (look for `feat(story-` prefix).

**Step 2 — Categorize commits:**
Group all commits since the fork point into categories:
- `[CORE]` — changes to hook files, plugin.json, or other non-pairmode files
- `[PAIRMODE-PHASE-N]` — story commits for a given phase
- `[DOCS]` — checkpoint/intent-review doc commits
- `[CHORE]` — developer action gates, era initialization, etc.

**Step 3 — Produce the squash plan:**
Write a structured proposal in the following format:
```
SQUASH PLAN — for review before execution

Option A: Keep full history (no squash)
  PRO: Complete audit trail of how pairmode was built
  CON: ~120+ commits in the PR; harder for maintainer to review

Option B: Squash by phase (recommended)
  One commit per phase + one commit for core changes
  Draft commit list:
    [CORE] Project-scoped pipe path for multi-project concurrency
    [PAIRMODE] Phase 1-7: core scaffold, lessons, audit/sync, templates
    [PAIRMODE] Phase 8-9: sync confirmation, tooling fixes
    [PAIRMODE] Phase 10: ideology capture infrastructure
    [PAIRMODE] Phase 11-12: reconstruction workflow and seeding
    [PAIRMODE] Phase 13-14: CER cleanup, reconstruction agent tooling
    [PAIRMODE] Phase 15-16: rails, eras, story structure, build loop
    [PAIRMODE] Phase 17-18: correctness fixes, missing tooling
    [PAIRMODE] Phase 19-20: test coverage, documentation, PR prep
  Estimated commit count: ~10
  Command to execute (requires developer confirmation before running):
    git rebase -i <fork-point-sha>

Option C: Single squash commit
  "feat: add pairmode structured build methodology"
  PRO: Simplest for upstream merge
  CON: Loses all phase history; harder to bisect later
```

**Step 4 — STOP:**
Print:
```
SQUASH PLAN COMPLETE — waiting for developer approval.

Review the plan above. To proceed:
  - "Accept Option A": no history rewrite; proceed to push
  - "Accept Option B": I will execute the phase-level squash
  - "Accept Option C": I will execute the single squash commit
  - "Modify the plan": tell me which commits to change

No git rewrite operations have been performed. The working tree is unchanged.
```

**Do not proceed past this point until the developer explicitly approves a plan.**

Tag for this story is deferred until after the developer approves and the squash
(if any) is executed.

---

⚙️ DEVELOPER ACTION — Push and open the PR

After Story INFRA-017 is resolved and the developer has approved the commit strategy:

1. Push the branch:
   ```bash
   git push origin era2
   ```
   (Or the squashed branch if Option B/C was chosen.)

2. Open the PR against the upstream repo. Use `docs/pairmode/PAIRMODE.md` as the
   basis for the PR description. Key points for the PR body:
   - What pairmode is (one paragraph)
   - The two core changes (pipe scoping, plugin.json)
   - Link to `docs/pipe-architecture.md` for the pipe rationale
   - "All 1000+ pairmode tests pass. The existing anchor skill tests are unaffected."

Tag: `cp20-pr-ready` (applied after developer approves the history plan)
