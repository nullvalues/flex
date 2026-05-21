# flex — Phase 35: Rename anchor → flex

← [Phase 34: Checkpoint context health report](phase-34.md)

## Goal

The project is being hard-forked under new ownership (David Jacobsen / `nullvalues`)
and renamed from **anchor** to **flex**. The fork severs the upstream development
relationship — no PRs will flow back — so all references to the old name and old
owner are renamed at the source, not bridged behind a compatibility shim.

This phase performs that rename across three concentric layers:

1. **Identity layer** — project manifests, ownership metadata, attribution to the
   upstream author, hardcoded filesystem paths, internal Python identifiers.
2. **Surface layer** — slash command namespace (`/anchor:*` → `/flex:*`), template
   strings, error messages, and any other emitted text the user sees.
3. **Content layer** — all documentation (forward-looking and historical), phase
   docs, lessons.json content, the era table, and derived companion state.

The user explicitly elected to rewrite history (phase docs, lessons.json,
CER backlog, era file) rather than preserve the "anchor" name as a record of when
the project carried it. The phase respects that decision but isolates the
append-only invariant violation to a single story (INFRA-091) where it is named
as a one-time migration and not a precedent.

**Out of scope:** Adding a LICENSE file. The upstream `nraychaudhuri/anchor` repo
has no LICENSE; this fork inherits that gap. Choosing and adding a license is a
separate decision for a future phase. INFRA-087 only records attribution to the
upstream author; it does not invent a license.

**Out of scope:** Refactoring the `.claude/settings.json` PostToolUse hook to
remove its hardcoded absolute path. The path is updated in place
(`/mnt/work/anchor` → `/mnt/work/flex`) but the underlying portability issue —
that the hook only works on this user's machine — remains as a CER backlog item.

**Story dependencies:**

```
INFRA-087 (manifests + attribution)
    └── INFRA-089 (slash namespace; depends on plugin.json name=flex)
INFRA-088 (paths + vars) ── independent
INFRA-090 (docs rewrite) ── independent
INFRA-091 (state + verify) ── depends on all of the above
```

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-087 | Project manifests, ownership, and upstream attribution | complete |
| INFRA-088 | Hardcoded paths and `_ANCHOR_ROOT` → `_REPO_ROOT` rename | complete |
| INFRA-089 | Slash command namespace migration (`/anchor:*` → `/flex:*`) | planned |
| INFRA-090 | Documentation rewrite (forward-looking + historical) | planned |
| INFRA-091 | JSON state migration, re-render derived files, final verification | planned |

---

### Story INFRA-087 — Project manifests, ownership, and upstream attribution

**Rail:** INFRA | **story_class:** code

## Requires

- The three manifest files exist in their current locations:
  - `pyproject.toml`
  - `.claude-plugin/plugin.json`
  - `.claude-plugin/marketplace.json`
- No `LICENSE` file in the repo root (confirmed absent in both this fork and the
  upstream repo).

## Ensures

**`pyproject.toml`** — the `[project]` block reflects the new identity:

```toml
[project]
name = "flex"
version = "0.1.0"
description = "Claude Code plugin for persistent architectural memory"
readme = "readme.md"
requires-python = ">=3.11"
```

Authors field is added (currently absent):

```toml
authors = [
    { name = "David Jacobsen", email = "david@halfhorse.com" },
]
```

**`.claude-plugin/plugin.json`** — name, description, and author rewritten:

```json
{
  "name": "flex",
  "description": "A context companion plugin for Claude Code — persistent memory of decisions, specs, and architectural constraints across sessions.",
  "version": "0.1.0",
  "author": {
    "name": "David Jacobsen"
  }
}
```

> Note: the `name` field here governs the slash command namespace. Changing it
> from `anchor` to `flex` is what makes installed slash commands resolve as
> `/flex:pairmode` etc. INFRA-089 depends on this change.

**`.claude-plugin/marketplace.json`** — marketplace identity, owner, and source
repo all rewritten:

```json
{
  "name": "nullvalues-flex",
  "owner": {
    "name": "David Jacobsen"
  },
  "metadata": {
    "description": "A context companion plugin for Claude Code — persistent memory of decisions, specs, and architectural constraints across sessions."
  },
  "plugins": [
    {
      "name": "flex",
      "source": {
        "source": "github",
        "repo": "nullvalues/flex"
      },
      "description": "A context companion plugin for Claude Code — persistent memory of decisions, specs, and architectural constraints across sessions.",
      "version": "0.1.0"
    }
  ]
}
```

**New file: `ATTRIBUTION.md`** at the repo root:

```markdown
# Attribution

flex is a hard fork of **anchor**, originally created by Nilanjan Raychaudhuri.

- Upstream project: `nraychaudhuri/anchor`
- Original author: Nilanjan Raychaudhuri
- Fork point: 2026-05-19

This fork is maintained independently by David Jacobsen (`nullvalues`). It is
not affiliated with the upstream project, and changes made here will not flow
back as pull requests. The conceptual design, original implementation of the
pairmode methodology, the companion sidebar pattern, and the spec-first
architecture all originate with the upstream project.

The upstream repository carries no LICENSE file. This fork preserves that state
pending a deliberate licensing decision in a future phase.
```

**Primary files:**
- `pyproject.toml`
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `ATTRIBUTION.md`

**Touches:** (none)

**Tests:** This is a configuration story — no test file expected. Verify by:

1. `python -c "import tomllib; d = tomllib.loads(open('pyproject.toml').read()); assert d['project']['name'] == 'flex'"` exits 0.
2. `jq -e '.name == "flex"' .claude-plugin/plugin.json` exits 0.
3. `jq -e '.plugins[0].source.repo == "nullvalues/flex"' .claude-plugin/marketplace.json` exits 0.
4. `ATTRIBUTION.md` exists and contains the strings `Nilanjan Raychaudhuri` and `nraychaudhuri/anchor`.
5. `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes (no regressions).

---

### Story INFRA-088 — Filesystem paths and identifier rename (`_ANCHOR_ROOT` → `_REPO_ROOT`, `~/.anchor/` → `~/.flex/`, `/tmp/anchor_*` → `/tmp/flex_*`, `ANCHOR_*` env vars → `FLEX_*`)

**Rail:** INFRA | **story_class:** code

## Requires

- INFRA-087 may be in any state (this story is independent).

## Ensures

This story covers every filesystem-path-shaped reference to "anchor", grouped
into five mechanical substitutions:

| # | From | To | Where |
|---|------|----|----|
| 1 | `_ANCHOR_ROOT` (Python identifier) | `_REPO_ROOT` (brand-neutral) | 14 Python files |
| 2 | "anchor repo root" (Python comments) | "repo root" | 3 Python files |
| 3 | `/mnt/work/anchor` (hardcoded absolute path) | `/mnt/work/flex` | `.claude/settings.json` |
| 4 | `$HOME/.anchor/` (user-home directory) | `$HOME/.flex/` | 3 launcher scripts + 1 agent file |
| 5 | `/tmp/anchor_project_dir`, `ANCHOR_PROJECT_DIR`, `ANCHOR_PROJECT_HASH` | `/tmp/flex_project_dir`, `FLEX_PROJECT_DIR`, `FLEX_PROJECT_HASH` | 3 launcher scripts + `hooks/session_start.py` |

**Substitution 1 — `_ANCHOR_ROOT` → `_REPO_ROOT`** (the identifier carries an
underscore prefix; rename keeps the underscore). This is brand-neutral,
deliberately not `_FLEX_ROOT`, so the variable does not require renaming again
if the project is renamed in the future. Files (must be exhaustive):

```
skills/seed/scripts/mine_sessions.py
skills/seed/scripts/reconcile.py
skills/pairmode/scripts/story_context.py
skills/pairmode/scripts/effort_recorder.py
skills/companion/scripts/sidebar.py
skills/pairmode/scripts/lesson.py
skills/pairmode/scripts/lesson_review.py
skills/pairmode/scripts/pairmode_status.py
tests/pairmode/test_pairmode_status.py
tests/pairmode/test_sidebar_story_panel.py
tests/pairmode/test_pairmode_sync.py
tests/pairmode/test_drift_evidence.py
tests/pairmode/test_sync_agents.py
tests/pairmode/test_lesson_review.py
```

**Substitution 2 — comment phrase "anchor repo root" → "repo root"** (the word
"anchor" is removed, not replaced with "flex", because the variable's purpose
is to locate the project root, not to encode the project's name). Files:

```
skills/pairmode/scripts/phase_new.py
skills/pairmode/scripts/cer.py
skills/pairmode/scripts/record_attempt.py
```

Also `bootstrap.py` and `session_start.py` use a local variable
`anchor_root` (lowercase, no underscore prefix) — rename to `repo_root`.

**Substitution 3 — `/mnt/work/anchor` → `/mnt/work/flex`** in:

```
.claude/settings.json
```

The hook's broader portability problem (machine-specific absolute path) is
**out of scope**; this story only retargets the path.

**Substitution 4 — user-home directory rename**. The auth handshake file moves
from `~/.anchor/auth.json` to `~/.flex/auth.json`. Files:

```
skills/companion/scripts/launch_sidebar.sh
skills/companion/scripts/launch_sidebar.command
.claude/agents/security-auditor.md
skills/pairmode/templates/agents/security-auditor.md.j2
```

> **Operator note (post-build):** After this phase ships, run
> `mv ~/.anchor ~/.flex` on each developer machine to migrate the existing
> auth state. This is a one-time manual action, not a script — the launcher
> will fail with a clear "auth file missing" message until migrated.

**Substitution 5 — `/tmp/anchor_project_dir*` and `ANCHOR_PROJECT_*` env
vars**. The runtime project-dir handshake between hook and sidebar uses these
paths and env vars:

```
skills/companion/scripts/launch_sidebar.sh
skills/companion/scripts/launch_sidebar.command
skills/companion/scripts/start_sidebar.sh
hooks/session_start.py
```

Specifically:
- `/tmp/anchor_project_dir_<hash>` → `/tmp/flex_project_dir_<hash>`
- `/tmp/anchor_project_dir` (legacy fallback) → `/tmp/flex_project_dir`
- `ANCHOR_PROJECT_DIR` → `FLEX_PROJECT_DIR`
- `ANCHOR_PROJECT_HASH` → `FLEX_PROJECT_HASH`

> **Protected-file note for hooks/session_start.py:** `hooks/` is in the
> protected files list per CLAUDE.md item 7. The modification reason is
> stated and bounded: substitution 2 (one local variable rename) and
> substitution 5 (env var name rename). No other logic changes.

**Acceptance:**

```bash
# Substitution 1 — word-boundary match so it does NOT trip on ANCHOR_PROJECT_HASH
grep -rwn "_ANCHOR_ROOT" . --exclude-dir=.git --exclude-dir=__pycache__ && exit 1 || true

# Substitution 2 — no "anchor repo" / "anchor_root" comments in Python
grep -rn "anchor[ _]repo\|anchor_root" . --include="*.py" --exclude-dir=.git --exclude-dir=__pycache__ && exit 1 || true

# Substitution 3
grep -rn "/mnt/work/anchor" . --exclude-dir=.git --exclude="phase-35.md" && exit 1 || true

# Substitution 4
grep -rn "\.anchor/" . --exclude-dir=.git --exclude=ATTRIBUTION.md && exit 1 || true

# Substitution 5
grep -rn "anchor_project_dir\|ANCHOR_PROJECT_DIR\|ANCHOR_PROJECT_HASH" . --exclude-dir=.git && exit 1 || true

# Tests still green
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

**Primary files** (code-touching, scoped to substitution boundaries):
- `.claude/settings.json`
- `skills/seed/scripts/mine_sessions.py`
- `skills/seed/scripts/reconcile.py`
- `skills/pairmode/scripts/story_context.py`
- `skills/pairmode/scripts/effort_recorder.py`
- `skills/companion/scripts/sidebar.py`
- `skills/companion/scripts/launch_sidebar.sh`
- `skills/companion/scripts/launch_sidebar.command`
- `skills/companion/scripts/start_sidebar.sh`
- `skills/pairmode/scripts/lesson.py`
- `skills/pairmode/scripts/lesson_review.py`
- `skills/pairmode/scripts/pairmode_status.py`
- `skills/pairmode/scripts/phase_new.py`
- `skills/pairmode/scripts/cer.py`
- `skills/pairmode/scripts/record_attempt.py`
- `skills/pairmode/scripts/bootstrap.py` (local var `anchor_root` only — broader bootstrap.py changes are in INFRA-089)
- `skills/pairmode/scripts/spec_exception.py` (one comment with `PYTHONPATH=/mnt/work/anchor` — substitution 3)
- `hooks/session_start.py` (PROTECTED — reason stated above)
- `.claude/agents/security-auditor.md` (`$HOME/.anchor/auth.json` reference only)
- `skills/pairmode/templates/agents/security-auditor.md.j2` (same)

**Touches:**
- `tests/pairmode/test_pairmode_status.py`
- `tests/pairmode/test_sidebar_story_panel.py`
- `tests/pairmode/test_pairmode_sync.py`
- `tests/pairmode/test_drift_evidence.py`
- `tests/pairmode/test_sync_agents.py`
- `tests/pairmode/test_lesson_review.py`

**Tests:** No new test file. Existing tests for affected modules must continue
to pass. Verify:
- All five grep gates above return zero matches.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

---

### Story INFRA-089 — Slash command namespace migration (`/anchor:*` → `/flex:*`) plus emitted/embedded namespace strings

**Rail:** INFRA | **story_class:** code

## Requires

- INFRA-087 complete: `.claude-plugin/plugin.json` has `"name": "flex"`, so the
  installed plugin namespace is `/flex:` going forward. Without this, the
  rewrite below would render the slash commands non-functional rather than
  retargeted.

## Ensures

Every occurrence of the **namespace strings** `/anchor:pairmode`,
`/anchor:seed`, `/anchor:companion`, the bare token `anchor:pairmode` (used by
`bootstrap.py` to write a `"generated_by"` provenance string), and the YAML
`name: anchor:seed` (in the seed skill manifest) is replaced with the `flex:`
form. The rewrite is mechanical and case-sensitive.

**Substitutions:**

| Pattern | Replacement | Notes |
|---|---|---|
| `/anchor:pairmode` | `/flex:pairmode` | slash command form |
| `/anchor:seed` | `/flex:seed` | slash command form |
| `/anchor:companion` | `/flex:companion` | slash command form |
| `"anchor:pairmode"` | `"flex:pairmode"` | quoted string literal — bootstrap.py `"generated_by"` value, deny-rationale.json `"generated_by"` value |
| `anchor:seed` | `flex:seed` | bare YAML value in `skills/seed/SKILL.md`'s `name:` frontmatter field |
| `# Anchor Methodology Lessons` | `# Flex Methodology Lessons` | heading string in `lesson_utils.py` (lines 61 and 75 — both the docstring example and the generated heading) |

**Files to update:**

```
.claude/agents/reconstruction-agent.md
.claude/settings.deny-rationale.json
CONTRIBUTING.md
README.md
readme.md
skills/seed/SKILL.md
skills/companion/SKILL.md
skills/companion/scripts/sidebar.py
skills/pairmode/SKILL.md
skills/pairmode/scripts/reconstruct.py
skills/pairmode/scripts/score.py
skills/pairmode/scripts/lesson_utils.py
skills/pairmode/scripts/audit.py
skills/pairmode/scripts/pairmode_status.py
skills/pairmode/scripts/bootstrap.py
skills/pairmode/templates/agents/reconstruction-agent.md.j2
skills/pairmode/templates/docs/reconstruction.md.j2
docs/brief.md
docs/checkpoints.md
docs/phases/phase-17.md
tests/pairmode/test_skill_md.py
tests/pairmode/test_phase2_coverage.py
tests/pairmode/test_bootstrap.py
tests/pairmode/test_audit.py
```

> **Note on test files:** `test_phase2_coverage.py:477` and
> `test_bootstrap.py:664` assert `data["generated_by"] == "anchor:pairmode"` —
> these asserts must flip to `"flex:pairmode"` in this same story so the test
> suite is green at end of INFRA-089. `test_audit.py:1775` has the expected
> output string `by `/anchor:pairmode reconstruct`` — flip to `/flex:`.

> **Note on lesson_utils.py:** Both the docstring example AND the runtime
> heading at lines 61 and 75 must change in this story. INFRA-091 regenerates
> `LESSONS.md` from this function — if the heading isn't updated here, the
> regenerated `LESSONS.md` will reintroduce "Anchor Methodology Lessons" and
> trip the final grep gate.

`lessons/lessons.json` and `lessons/LESSONS.md` also carry `/anchor:`
references but are handled in **INFRA-091** alongside the broader lessons
migration.

`bootstrap.py` is touched for **substring 4** only (`"anchor:pairmode"` ->
`"flex:pairmode"`). Its other anchor-name prose (docstrings, comments) is
covered by INFRA-090.

**Acceptance:**
- `grep -rn "/anchor:" .` (excluding `.git/`, `lessons/lessons.json`,
  `lessons/LESSONS.md`, and `ATTRIBUTION.md`) returns no matches.
- `grep -rn '"anchor:pairmode"' .` (excluding `.git/`) returns no matches.
- `grep -rn 'name: anchor:' .` (excluding `.git/`) returns no matches.
- `grep -rn "Anchor Methodology Lessons" .` (excluding `.git/`) returns no matches.
- All tests pass, including `tests/pairmode/test_skill_md.py`,
  `test_phase2_coverage.py`, `test_bootstrap.py`, and `test_audit.py`.

**Primary files:** all files listed in "Files to update" above.

**Touches:** (none beyond primary files)

**Tests:**
- All four grep gates return zero matches.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

---

### Story INFRA-090 — Project-name prose rewrite (docs + agent bodies + code docstrings + JSON state + historical artifacts)

**Rail:** INFRA | **story_class:** methodology

## Requires

- INFRA-088 should be complete first if possible: it owns path-shaped
  substitutions, and several files in this story's scope contain both
  project-name prose AND path references. If INFRA-088 has already retargeted
  those paths, INFRA-090 only needs to rewrite project-name prose. If INFRA-088
  has not run yet, INFRA-090 must avoid touching path-shaped strings (`.anchor/`,
  `/mnt/work/anchor`, `_ANCHOR_ROOT`, `ANCHOR_PROJECT_*`).
- INFRA-089 should be complete first if possible: it owns slash-namespace and
  emitted-string substitutions. INFRA-090 must avoid touching `/anchor:*` and
  `"anchor:pairmode"` strings.

In practice, this story runs last among 088/089/090 in build order.

## Ensures

Every remaining occurrence of `anchor` / `Anchor` / `ANCHOR` used as a
**project name** is rewritten to `flex` / `Flex` / `FLEX`. Case is preserved.
The rewrite covers Markdown documentation, Python docstrings and comments,
JSON value strings (where the string is project-name prose, not a slash
namespace token), and historical artifacts.

**Files in scope — grouped by location:**

Forward-looking documentation (canonical project description):
- `docs/brief.md`
- `docs/architecture.md`
- `docs/ideology.md`
- `docs/reconstruction.md`
- `docs/pairmode/PAIRMODE.md`
- `docs/checkpoints.md`
- `docs/pipe-architecture.md`
- `docs/eras/001-initial.md` (era `name:` frontmatter field and body refs)
- `README.md`
- `readme.md`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `CLAUDE.md`
- `CLAUDE.build.md`
- `.gitignore` (one comment line: `# Anchor runtime` → `# Flex runtime`)

Historical phase docs and the legacy phase-prompts mono-doc:
- `docs/phases/index.md` (heading + body)
- `docs/phases/phase-8.md` through `docs/phases/phase-34.md` (every file)
- `docs/phase-prompts.md` (legacy mono-doc — 30+ refs)

Historical story files (rewritten per the user's explicit "rewrite everywhere"
choice — these are stub redirects to phase docs, plus a few that carry
substantive anchor refs):
- `docs/stories/INFRA/INFRA-016.md`
- `docs/stories/INFRA/INFRA-020.md`
- `docs/stories/INFRA/INFRA-021.md`
- `docs/stories/INFRA/INFRA-041.md`
- `docs/stories/INFRA/INFRA-042.md`
- `docs/stories/INFRA/INFRA-063.md`
- `docs/stories/BUILD/BUILD-003.md`
- `docs/stories/BUILD/BUILD-004.md`

The CER backlog:
- `docs/cer/backlog.md`

Agent file body prose (frontmatter is regenerated by sync-agents in INFRA-091;
body is project-owned and contains "anchor project" prose at line 9 of each):
- `.claude/agents/builder.md`
- `.claude/agents/reviewer.md`
- `.claude/agents/loop-breaker.md`
- `.claude/agents/intent-reviewer.md`

> `.claude/agents/security-auditor.md` and `.claude/agents/reconstruction-agent.md`
> are owned by **INFRA-088** (for the `$HOME/.anchor/auth.json` path) and
> **INFRA-089** (for slash refs and prose) respectively. INFRA-088 and INFRA-089
> must also rewrite the "anchor project" prose on line 9 of those two files as
> part of their respective passes — explicitly noted as a small bookkeeping
> concession so the file lives in exactly one story.

Python docstring/comment prose where the project name appears:
- `skills/pairmode/scripts/pairmode_register.py` (3 docstring/comment refs)
- `skills/pairmode/scripts/pairmode_drift_report.py` (1 docstring ref)
- `skills/pairmode/scripts/pairmode_effort.py` (2 docstring/comment refs)
- `skills/pairmode/scripts/bootstrap.py` (any docstring/comment refs that
  remain after INFRA-088 and INFRA-089's targeted edits — likely zero, but
  re-grep to confirm)

JSON value strings (project-name prose only — `"generated_by"` is INFRA-089):
- `.claude/settings.deny-rationale.json` (the two `"non_negotiable"` strings
  containing "anchor intercepts")

The canonical openspec (historical product spec):
- `product-spec/openspec/specs/companion-skill/spec.json`
- `product-spec/openspec/specs/hooks/spec.json`
- `product-spec/openspec/specs/lessons/spec.json`
- `product-spec/openspec/specs/pairmode-skill/spec.json`
- `product-spec/openspec/specs/docs/spec.json`
- `product-spec/openspec/specs/plugin-manifest/spec.json`
- `product-spec/openspec/specs/seed-skill/spec.json`
- `product-spec/openspec/changes/0fac6655-0a31-4841-b1a9-8549cde560e7/proposal.md`
- `product-spec/openspec/changes/0fac6655-0a31-4841-b1a9-8549cde560e7/extraction.json`
- `product-spec/openspec/changes/a3d48ab2-becb-4fe4-9d9d-75bce40de4d8/proposal.md`
- `product-spec/openspec/changes/a3d48ab2-becb-4fe4-9d9d-75bce40de4d8/design.md`
- `product-spec/openspec/changes/a3d48ab2-becb-4fe4-9d9d-75bce40de4d8/extraction.json`
- `product-spec/openspec/changes/743632e3-5fb0-4fa8-87ce-56ab1da01280/proposal.md`
- `product-spec/openspec/changes/743632e3-5fb0-4fa8-87ce-56ab1da01280/extraction.json`

**Excluded from rewrite:**
- `ATTRIBUTION.md` — intentionally retains "anchor" to credit the upstream.
- `.git/` — git history is immutable.
- `lessons/lessons.json` and `lessons/LESSONS.md` — owned by INFRA-091.
- Path-shaped strings owned by INFRA-088 (`/mnt/work/anchor`, `~/.anchor/`,
  `_ANCHOR_ROOT`, `/tmp/anchor_*`, `ANCHOR_PROJECT_*`).
- Slash-namespace strings owned by INFRA-089 (`/anchor:*`, `"anchor:pairmode"`,
  `name: anchor:`, `# Anchor Methodology Lessons`).

**Builder notes:**
- `docs/phases/index.md` first heading is `# anchor — Phase Index`; this
  becomes `# flex — Phase Index`.
- Each `phase-NN.md` first heading follows the pattern
  `# anchor — Phase NN: …` and becomes `# flex — Phase NN: …`.
- The string `non-anchor machines` in `tests/pairmode/test_pairmode_sync.py`
  line 66 uses "anchor" in a generic "anchored at a path" sense. After
  INFRA-088 retargets the path itself, the comment becomes stale; either
  remove the comment or rephrase to "non-`/mnt/work/flex` machines". This is
  one line in a Python test file. Treat as in-scope for INFRA-090 and add
  to its touches.
- `docs/phases/phase-35.md` and `docs/stories/INFRA/INFRA-087.md` through
  `INFRA-091.md` (this phase's own spec files) DO contain "anchor" because
  they describe the rename. Leave them alone — the spec exists to describe
  the migration; rewriting it would erase the description of what was done.
  The final grep gate in INFRA-091 explicitly excludes these files.

**Acceptance:**

```bash
# Project-name prose in scoped files: zero remaining
grep -rni "anchor" docs/ *.md .gitignore \
  --exclude=ATTRIBUTION.md \
  --exclude=phase-35.md \
  --exclude=INFRA-087.md --exclude=INFRA-088.md --exclude=INFRA-089.md \
  --exclude=INFRA-090.md --exclude=INFRA-091.md \
  && exit 1 || true

grep -rni "anchor" product-spec/ && exit 1 || true

grep -rni "anchor" .claude/agents/ && exit 1 || true

grep -rni "anchor" .claude/settings.deny-rationale.json && exit 1 || true

grep -rn "anchor" skills/pairmode/scripts/pairmode_register.py \
  skills/pairmode/scripts/pairmode_drift_report.py \
  skills/pairmode/scripts/pairmode_effort.py && exit 1 || true

PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

The phase doc and per-story spec files for this very phase (35) are
**deliberately excluded** because they describe the rename and rewriting them
would erase that description.

**Primary files:** all files listed under "Files in scope" above.

**Touches:**
- `tests/pairmode/test_pairmode_sync.py` (the `non-anchor machines` comment)

**Tests:** Methodology + doc rewrite story — no new test file. Verify by:
- All five grep gates above return zero matches.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

---

### Story INFRA-091 — JSON state migration, re-render derived files, final verification

**Rail:** INFRA | **story_class:** methodology

## Requires

- INFRA-087 through INFRA-090 all complete.
- `lessons/lessons.json` exists and is valid JSON.
- INFRA-089 has already updated `lesson_utils.py`'s heading string from
  "Anchor Methodology Lessons" to "Flex Methodology Lessons" (Part 1 below
  depends on this — `generate_lessons_md()` uses the new heading).

## Ensures

**Part 1: Lessons migration (one-time append-only exception).**

`lessons/lessons.json` carries the upstream project name in three places per
lesson record:
- `source_project: "anchor"` — rewritten to `"flex"` for every record.
- Free-text fields (`trigger`, `problem`, `learning`,
  `methodology_change.description`) — every case-sensitive occurrence of
  `anchor`, `Anchor`, or `ANCHOR` rewritten to `flex`, `Flex`, or `FLEX`.
- `/anchor:` slash references in free-text — rewritten to `/flex:`.

This story deliberately bypasses `lesson_utils.save_lessons()` because that
function enforces the append-only invariant: for every existing record, every
field other than `status` must equal the prior value, else it raises
`ValueError`. The rewrite is performed by reading the file with
`json.load(...)`, mutating in memory, and writing back with `json.dump(..., indent=2)`
— bypassing `save_lessons` entirely.

The migration is **a one-time exception**, not a precedent. Future edits to
`lessons.json` must continue to use `save_lessons` and observe the append-only
rule. The rationale lives in this spec and in the commit message — the JSON
file cannot carry the explanation inline because it is structured data.

After the migration, regenerate `lessons/LESSONS.md` by calling
`lesson_utils.generate_lessons_md()` (read-only with respect to the
invariant — it only reads the lessons and renders Markdown). Because INFRA-089
already changed the heading string to "Flex Methodology Lessons", the
regenerated file will carry the new heading.

**Part 2: Companion state migration (conditional).**

If `.companion/state.json` exists in the project root AND contains
`"project_name": "anchor"`, rewrite the value to `"flex"`. If
`.companion/pairmode_context.json` exists with the same key/value, rewrite
there too. If either file is absent or the value differs, leave that file
alone — do not invent new keys, do not create the file.

> **Note:** At spec time, neither `.companion/state.json` nor
> `.companion/pairmode_context.json` exists in the working tree (the `.companion/`
> directory is in `.gitignore`). Part 2 may be a no-op in practice. The story
> still must check, in case the developer has these files locally.

**Part 3: Re-render derived methodology files.**

Run, in order:

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/pairmode_sync.py \
  sync-build --project-dir . --apply --yes

PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/pairmode_sync.py \
  sync-agents --project-dir . --apply --yes
```

These commands re-render `CLAUDE.build.md` and `.claude/agents/*.md`
frontmatter from the canonical templates (which themselves now refer to flex
after INFRA-088, INFRA-089, and INFRA-090). The expected result is **no
change** to body content if the prior stories were thorough — but if any
template-emitted content was missed, this step catches it. If the diff is
non-empty, the reviewer must investigate whether it represents a legitimate
re-render or a missed substitution upstream.

**Part 4: Final verification gate.**

Run the following final-state checks. All must pass. The spec files for this
phase (`docs/phases/phase-35.md` and `docs/stories/INFRA/INFRA-087.md` through
`INFRA-091.md`) are excluded from every gate because they describe the
rename — rewriting them would erase that description.

```bash
SPEC_EXCLUDES="--exclude=phase-35.md \
  --exclude=INFRA-087.md --exclude=INFRA-088.md --exclude=INFRA-089.md \
  --exclude=INFRA-090.md --exclude=INFRA-091.md \
  --exclude=ATTRIBUTION.md"

# 1. No /anchor: slash references remain in tracked source
grep -rn "/anchor:" . --exclude-dir=.git --exclude-dir=__pycache__ $SPEC_EXCLUDES \
  && exit 1 || true

# 2. No _ANCHOR_ROOT identifier remains (word-boundary so we don't trip
#    on legitimate flex_* identifiers; substitution 1 from INFRA-088)
grep -rwn "_ANCHOR_ROOT" . --exclude-dir=.git --exclude-dir=__pycache__ $SPEC_EXCLUDES \
  && exit 1 || true

# 3. No /mnt/work/anchor absolute path remains
grep -rn "/mnt/work/anchor" . --exclude-dir=.git --exclude-dir=__pycache__ $SPEC_EXCLUDES \
  && exit 1 || true

# 4. No ~/.anchor/ user-home reference remains
grep -rn "\.anchor/" . --exclude-dir=.git --exclude-dir=__pycache__ $SPEC_EXCLUDES \
  && exit 1 || true

# 5. No /tmp/anchor_* or ANCHOR_PROJECT_* runtime handshake refs remain
grep -rn "anchor_project_dir\|ANCHOR_PROJECT_DIR\|ANCHOR_PROJECT_HASH" . \
  --exclude-dir=.git --exclude-dir=__pycache__ $SPEC_EXCLUDES \
  && exit 1 || true

# 6. No /anchor:pairmode" or # Anchor Methodology Lessons strings remain
grep -rn '"anchor:pairmode"\|Anchor Methodology Lessons\|name: anchor:' . \
  --exclude-dir=.git --exclude-dir=__pycache__ $SPEC_EXCLUDES \
  && exit 1 || true

# 7. No "anchor"/"Anchor"/"ANCHOR" project-name prose remains in tracked source
#    (final sweep — should catch anything INFRA-090 missed)
grep -rni "anchor" . --exclude-dir=.git --exclude-dir=__pycache__ \
  --exclude-dir=lessons \
  $SPEC_EXCLUDES \
  && exit 1 || true

# 4. Test suite is green
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q

# 8. Lessons file is valid JSON and source_project is consistent
PATH=$HOME/.local/bin:$PATH uv run python -c "
import json
data = json.load(open('lessons/lessons.json'))
sources = {l['source_project'] for l in data['lessons']}
assert sources == {'flex'} or sources == set(), f'unexpected sources: {sources}'
print('lessons.json source_project: OK')
"

# 9. LESSONS.md heading is the new one
grep -q "^# Flex Methodology Lessons" lessons/LESSONS.md \
  || (echo 'LESSONS.md heading not migrated' && exit 1)
```

If any check fails, the build is not complete. The reviewer must investigate
each failure rather than waving them through.

**Primary files:**
- `lessons/lessons.json`
- `lessons/LESSONS.md`

**Touches:**
- `.companion/state.json` (conditional — present in some developer setups only)
- `.companion/pairmode_context.json` (conditional — same)
- `CLAUDE.build.md` (re-rendered by sync-build)
- `.claude/agents/*.md` (re-rendered by sync-agents)

**Tests:** Methodology + verification story — no new test file. Verify by:
- All nine gates in "Final verification gate" above pass (gates 1–7 are the
  grep sweep, gate 8 validates lessons.json structurally, gate 9 verifies
  the regenerated LESSONS.md heading).
- The diff for `CLAUDE.build.md` after sync-build is either empty or contains
  only legitimate template re-render effects.

---

Tag: `cp35-rename-anchor-flex`
