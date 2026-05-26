# Flex — The IDE for Intent

Code is cheap to generate. Intent is scarce. Agents drift without it: constraints agreed
on two sessions ago are invisible today, modules accumulate contradictory assumptions, and
every new session starts from zero. Flex makes intent persistent in two ways: by
recording it as you decide (reactive memory) and by requiring it before you build
(proactive process). It captures what you are building and why — automatically, as you
work — and makes that record the source of truth for every agent and every session.

## Status

Alpha. Under active development. Core workflows are functional and used in production on
this repo. The API and scaffold format may change without notice. See Known Limitations.

## What flex does

Flex provides two complementary layers.

**Process layer** (`/flex:pairmode`): Pairmode is the primary workflow: a structured
builder/reviewer loop with effort tracking, per-story schema gates, context budget checks,
and model selection per attempt. Bootstraps and manages the methodology on any project —
produces a full scaffold (CLAUDE.md, agent docs, permission settings, phase specs, and a
CER backlog) and enforces the build loop at every commit. Generates `docs/ideology.md` (a
conviction and constraint record that survives across implementations) and
`docs/reconstruction.md` (a handoff prompt that seeds an independent agent to produce a
competing implementation of the same project from ideology alone).

**Memory layer** (`/flex:seed` + `/flex:companion`): The companion memory layer underneath
pairmode captures decisions live and feeds them back into the build loop. `/flex:seed`
reads your codebase and historical Claude Code transcripts to build a canonical spec —
structured JSON records of decisions, rules, tradeoffs, and lineage for each module.
`/flex:companion` loads that spec at session start, detects drift between new decisions and
established rules, and runs a sidebar process that captures decisions made during the
session into the spec automatically.

Pairmode is the build loop. Companion is the memory it draws on.

### Pairmode and companion: posture comparison

| Dimension | Pairmode (`/flex:pairmode`) | Companion (`/flex:seed`, `/flex:companion`) |
|-----------|--------------------------------|-------------------------------------------------|
| **When it acts** | Before code is written, and at every commit gate | During the session, reacting to what just happened |
| **Posture** | Proactive — fixes intent in writing first, prevents drift | Reactive — observes decisions and drift live |
| **Primary artefact** | `docs/stories/<RAIL>/<RAIL>-NNN.md` and `docs/phases/phase-N.md` | `spec.json` per module |
| **Actor that writes** | Developer (story spec) and builder/reviewer subagents | Sidebar, after the fact, from the transcript |
| **Failure it prevents** | Builder hallucinating scope; reviewer-less commits; phase drift | Decision evaporation across sessions; silent contradiction of an earlier choice |
| **Failure it cannot prevent** | A decision made mid-story that nobody captures into spec.json | A story that was never specced — companion can only record what was discussed |
| **Composition** | Feeds companion: `current_story` written into `state.json` so the sidebar surfaces story context | Feeds pairmode: spec.json non-negotiables generate the deny list at bootstrap |
| **Use it when** | You want a structured build loop and want to specify intent before code | You want institutional memory across sessions and projects |
| **Use both when** | You want intent both *enforced at the build gate* (pairmode) and *captured live* (companion) — the default for serious projects |

Use pairmode when you want a structured build loop and pre-build intent capture — every
story specced before code is written, every commit gated by a reviewer.

Use companion when you want institutional memory across sessions and projects — a record
of what was decided that survives context compaction and agent restarts.

Use both when you want intent both enforced at the build gate and captured live. This is
the default for serious projects: pairmode keeps the build honest against the spec, and
companion records the decisions that surface during work.

## Installation

```bash
# Install as a Claude Code plugin from the plugin directory
claude code plugin install path/to/flex

# Or clone and install locally
git clone https://github.com/nullvalues/flex
claude code plugin install ./flex
```

Requirements: Claude Code, Python 3.11+, uv.

The plugin registers three skills: `/flex:seed`, `/flex:companion`,
and `/flex:pairmode`. Marketplace installation is available for registered users.

## Quick start

### New project

```bash
# 1. Bootstrap pairmode on your project — generates scaffold from your spec
/flex:pairmode bootstrap

# 2. Create your first story on a named rail
uv run python skills/pairmode/scripts/story_new.py --rail CORE --title "Initial data model"

# 3. Tell the builder which story to work on, then build
# In Claude Code: "Build story CORE-001"
```

The bootstrap command asks for your project name, tech stack, and key modules. It writes
CLAUDE.md, CLAUDE.build.md, agent prompt templates, and an initial phase file. Pairmode
is active immediately.

### Existing project with session history

```bash
# 1. Mine existing transcripts and build the canonical spec
/flex:seed

# 2. Start the companion sidebar to begin capturing new decisions
/flex:companion

# 3. Bootstrap pairmode on top of the populated spec
/flex:pairmode bootstrap
```

If you have prior Claude Code sessions, `/flex:seed` extracts decisions from them before
bootstrap. The spec it produces seeds the pairmode scaffold so that generated rules and
checklists reflect your actual project history.

## The three skills

| Skill | Posture | What it does | Key command | Key output |
|-------|---------|-------------|-------------|-----------|
| `/flex:pairmode` | proactive | Scaffold and enforce structured build loop | `/flex:pairmode bootstrap` | CLAUDE.md, agent docs, phase files, deny list |
| `/flex:pairmode drift-report` | on-demand | Compare registered projects against canonical templates; surface convergent improvements for promotion | `/flex:pairmode drift-report --projects <path> [--convergent]` | Per-project MISSING/EXTRA/DRIFT report; convergence candidates for promotion |
| `pairmode sync-build` | on-demand | Diff and optionally apply canonical `CLAUDE.build.md` template to an existing project | `pairmode sync-build --project-dir DIR [--dry-run] [--apply] [--yes]` | Unified diff; updated `CLAUDE.build.md` on `--apply` |
| `pairmode register` | on-demand | Manage the list of projects used by drift detection | `pairmode register/unregister/list-projects --project-dir DIR` | Updated `registered_projects` in `.companion/state.json` |
| `/flex:companion` | reactive | Load spec, capture decisions, detect drift | `/flex:companion` | Updated `spec.json`, sidebar process |
| `/flex:seed` | bootstrap-once | Mine transcripts, build canonical spec | `/flex:seed` | `openspec/specs/<module>/spec.json` |

## Use case scenarios

### Scenario A: New project with build loop

You are starting a Python API service. The codebase is empty.

1. Run `/flex:pairmode bootstrap`. Answer the prompts: project name `invoicing-api`,
   stack `Python/FastAPI/PostgreSQL`, modules `api`, `billing`, `auth`.
2. Flex writes CLAUDE.md, CLAUDE.build.md, initial ideology, and a phase-1 spec file.
   The deny list in `.claude/settings.json` is generated from your declared non-negotiables:
   "no direct database writes outside the repository layer."
3. You create story `BILLING-001: Add invoice creation endpoint` via `story_new.py`.
4. You invoke the builder subagent: "Build story BILLING-001."
5. The builder implements the endpoint. When it tries to write raw SQL in the route handler,
   the deny list blocks the write and the sidebar surfaces the conflict: the route handler
   is not in the repository layer.
6. You invoke the reviewer subagent. It checks the implementation against the checklist,
   confirms the constraint was respected, and commits with the story tag.
7. The spec gains a new lineage entry. The constraint held.

### Scenario B: Returning developer

You have been away from a project for three months. The spec and methodology are already
in place.

1. Run `/flex:pairmode audit`. It compares your project scaffold against the current
   canonical pairmode templates and reports drift: your CLAUDE.build.md is missing the
   permission-scope step added in Phase 16.
2. Run `/flex:pairmode sync`. It offers to apply the delta non-destructively. You accept.
3. Check `docs/phases/phase-3.md`. The last completed story was `BILLING-007`. The next
   planned story is `BILLING-008`. Set the story: `story_context.py --set BILLING-008`.
4. Optionally, run `/flex:companion` to load the spec into the sidebar. The sidebar will
   surface the active story and capture any new decisions made during the session.
5. You pick up where you left off. The full constraint record is intact. Nothing was lost.

## The build loop

1. Write the story spec in `docs/stories/<RAIL>/<RAIL>-NNN.md` with frontmatter and
   acceptance criterion.

   Pairmode owns this loop. Companion is not required to use it; if companion is running,
   the sidebar will surface the active story but does not gate the build.
2. Invoke the builder subagent: "Build story RAIL-NNN." The builder reads the spec,
   implements, and runs tests.
3. Invoke the reviewer subagent. It runs the review checklist and the test suite.
4. On PASS: the reviewer commits with the story tag. On FAIL: the builder fixes and
   the reviewer re-runs.
5. If the builder is stuck after two attempts: invoke the loop-breaker.
6. After each phase: run the 8-step checkpoint sequence (build gate, security audit,
   intent review, documentation update, phase completion check, CER backlog review,
   checkpoint tag, report).

## The canonical spec format

```json
{
  "module": "billing",
  "summary": "Handles invoice creation, payment tracking, and revenue reporting.",
  "business_rules": [
    "An invoice may not be marked paid unless a corresponding payment record exists."
  ],
  "non_negotiables": [
    "No direct database writes outside the repository layer."
  ],
  "tradeoffs": [
    {
      "decision": "Synchronous payment confirmation",
      "reason": "Simplicity at current scale; async adds infrastructure complexity.",
      "accepted_cost": "Slower response on payment endpoints."
    }
  ],
  "conflicts": [],
  "lineage": [
    {
      "session_id": "abc123",
      "summary": "Defined repository layer boundary and payment confirmation strategy.",
      "date": "2026-01-15",
      "resume": "claude --resume abc123"
    }
  ]
}
```

Each module has one `spec.json`. `non_negotiables` never auto-resolve — they require a
developer decision to override. `lineage` is append-only.

## Known limitations

- Alpha software. Internal APIs and scaffold formats may change without notice.
- Optimized for solo developers. No multi-developer story assignment or concurrent session
  coordination.
- The companion sidebar must be running for real-time drift detection and automatic spec
  updates. Pairmode functions without it, but decisions are not captured live.
- `lesson_review.py` annotates templates with improvement suggestions but does not apply
  them. The developer must open the template and implement the change manually.
- Story status updates and some orchestrator steps require manual bash invocations.
  `story_update.py` (introduced in Phase 18) reduces friction but does not fully automate
  the status lifecycle.
- The reconstruction workflow (ideology extraction and competing implementation seeding)
  requires a populated spec and works best after several sessions of decision capture.

## Requirements and License

**Requirements:**
- Claude Code (any version with plugin support)
- Python 3.11+
- uv (Python package manager)

**License:** MIT. See LICENSE file.

**Contact:** david@halfhorse.com
