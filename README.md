# Flex — Muscular Models constrained by Skeletal Intent

Agents drift quickly and very reliably get less reliable at known thresholds: constraints agreed
on two sessions ago are invisible today, modules accumulate contradictory assumptions, and
every new session starts from zero. Flex makes intent persistent in two ways: by
recording it as you decide (reactive memory) and by requiring it before you build
(proactive process). It captures what you are building and why — automatically, as you
work — and makes that record the source of truth for every agent and every session.

**Era 001 — pairmode foundation (complete)**
An Anchor evolution focused on `/flex:pairmode` context management: enforcing 150k
context limits per build, persistent refocus to the system of record, and systematic
shifts of deterministic processes to code. The result is a largely hands-free
auto-mode build loop.

**Era 002 — build loop and observability (complete)**
Extends the build loop with observability and mechanical enforcement: a browser-based
SPA for context budget and effort metrics (Phase 63), story-scoped file permissions
via hook enforcement (Phase 55), a reliable story-ID-bound context gate (Phase 73),
and ongoing closure of spec-quality gaps that cause builder friction.

**Era 003 — orchestrator as harness (active)**
Reduces the orchestrator from a procedure that runs the build loop to a harness
that dispatches it: the deterministic skeleton of the loop (sequencing, counters,
routing) moves into a code-resident `next-action` state machine, while each unit
of work runs as a thin, disposable leaf worker. The goal is a stateless harness
that can resume losslessly after a `/clear` and build whole phases unattended.

## Status

Beta — approaching production-readiness for solo developers. Core workflows are
stable and self-hosted on this repo; internal APIs and scaffold formats may still
change without notice. See Known Limitations.

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

## Observability

- **Observability SPA** — browser-based dashboard for context budget, effort metrics, and story status across multiple registered repos.

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

# 3. Start the build loop
# In Claude Code: "Build Phase 1"
# The orchestrator drives a while-loop over `flex_build.py next-action`, which
# resolves to `spawn-builder` for CORE-001 automatically — no manual
# per-story invocation needed.
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
| `/flex:observability` | on-demand | Browser-based dashboard for context budget, effort metrics, and story status across registered projects | `/flex:observability serve` | Local SPA at `127.0.0.1:7777`; phase status, context health, effort rollups, lessons with promotion candidates |
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
4. You tell Claude Code "Build Phase 1." The orchestrator does not invoke any agent by
   name or read the story file itself — it drives a while-loop over
   `flex_build.py next-action`, dispatching whatever action the resolver returns.
5. `next-action` resolves to `spawn-builder` for BILLING-001. The orchestrator creates a
   disposable git worktree (`create-story-worktree`), which stamps `current_story` into
   the main checkout's `.companion/state.json` and generates the story's file-scope
   permissions artifact, then spawns the builder (model chosen by
   `model_selector.select_builder_model()`) inside that worktree.
6. The builder implements the endpoint. If it tries to write raw SQL in the route handler,
   `hooks/pre_tool_use.py`'s `scope_guard` check blocks the Edit/Write at the tool-call
   level — the route handler is not declared in the story's `primary_files`/`touches`, so
   the write is rejected before it lands, not caught after the fact.
7. `next-action` resolves to `spawn-reviewer` (exempt from the context-budget gate — it's
   the loop's mandatory next step, never a discretionary spawn the gate could block). The
   reviewer diffs the worktree against HEAD, runs the checklist and test suite, and
   reports PASS. `merge-story-worktree` fast-forward-merges the worktree back onto main,
   clears the attempt counter, and commits with the story tag.
8. If `/flex:companion` is running, the sidebar picked up `current_story` while the story
   was active and can log the decision into `spec.json`; the constraint held either way.

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

Orchestration is code-resident, not orchestrator prose: `CLAUDE.build.md` is a ~50-line
template whose only real logic is a while-loop over
`flex_build.py next-action --json --project-dir .`. The resolver
(`skills/pairmode/scripts/next_action.py`) reads story/phase status and `state.json` and
returns exactly one action per call — `spawn-builder`, `spawn-reviewer`, a checkpoint
step, a paused/gate action awaiting an operator decision, or `done`. The orchestrator's
job is to dispatch whatever comes back.

1. Write the story spec in `docs/stories/<RAIL>/<RAIL>-NNN.md` with frontmatter and an
   `## Ensures` acceptance section.

   Pairmode owns this loop. Companion is not required to use it; if companion is running,
   the sidebar will surface the active story but does not gate the build.
2. **Story-build actions run inside a disposable worktree.** For `spawn-builder`/
   `spawn-reviewer`, the orchestrator first calls `create-story-worktree`, which creates a
   fresh git worktree at `.pairmode-worktrees/<ID>/`, stamps `current_story` into the
   *main checkout's* `.companion/state.json` (so the companion sidebar can surface the
   active story — the worktree has no `.companion/` of its own), and generates the
   story's file-scope permissions artifact (`docs/phases/permissions/<ID>.json`). The
   builder/reviewer subagent operates only inside that worktree, never the main project
   directory; `scope_guard.py` blocks any Edit/Write outside the story's declared
   `primary_files`/`touches` at the tool-call level, including writes made from inside
   the worktree.
3. **Context gate.** After each builder/reviewer spawn completes,
   `hooks/post_tool_use.py` reads the live token count from the session JSONL
   transcript and writes it to `state["context_current_tokens"]` — no orchestrator
   action required. On the next spawn, `hooks/pre_tool_use.py` fires for four
   build-cycle subagent types only (`builder`, `loop-breaker`, `security-auditor`,
   `intent-reviewer`); for those it reads that value, checks it isn't stale (predating
   the last `/clear`), and blocks if the projected total exceeds the overrun ceiling
   (`threshold × (1 + overrun_pct)`, default `130000 × 1.10` ≈ 143k). `reviewer` is
   deliberately excluded from the gate: it is the build loop's mandatory, deterministic
   next step after every builder attempt, with no alternative action for the gate to
   preserve by blocking it. The SessionStart hook resets the count to a fresh-session
   baseline (25,000 tokens) on `/clear` or startup. No LLM cooperation required — the
   write/read split between PostToolUse and PreToolUse is fully mechanical for every
   role the gate actually governs. See `docs/pairmode/context-gate-flow.md` for the
   full flow diagram.
4. **Builder spawn.** The builder receives only the story ID. The orchestrator passes
   no story text, file contents, or prior context. The builder reads
   `docs/stories/<RAIL>/<RAIL>-NNN.md` cold, derives all needed context from the live
   codebase, implements the story inside its worktree, and runs tests.
   `model_selector.select_builder_model()` picks the model: haiku for doc/lesson
   stories, sonnet baseline for code, opus on high-scope signals (5+ primary files or a
   protected file) or on retry.
5. **Reviewer spawn.** The reviewer also receives only the story ID and reads its own
   context cold. It diffs the worktree against HEAD, runs the review checklist, and
   executes the test suite. The reviewer sees what the builder actually changed — not
   what the builder reported it changed. `model_selector.select_reviewer_model()` picks
   sonnet on attempt 1 for every story class; on retry (attempt ≥ 2), `code`-class
   stories escalate to opus, `doc`/`lesson` stay sonnet, and `methodology` upgrades to
   opus only if a same-phase `code` story exists.
6. On PASS: `merge-story-worktree` fast-forward-merges the worktree back onto main,
   clears the attempt counter, and commits with the story tag. On FAIL:
   `discard-story-worktree` discards the worktree outright and the attempt counter is
   bumped — both effort recording and the attempt counter are hook-side
   (`hooks/post_tool_use.py`'s Task/Agent branch calls
   `subagent_transcript.record_attempt_from_transcript()` after every spawn, deriving
   tokens/model/outcome from the live transcript and writing an `effort.db` row; no
   separate orchestrator-side recording step is needed). After two same-story failures,
   the loop-breaker subagent (always `fable`, an escalation tier ranking above opus)
   proposes a single alternative approach; the developer decides whether to proceed
   with a third attempt or pause.
7. After each phase: three pre-checkpoint guards (phase-completion, CER Do Now, build
   gate) must pass, then the four-step checkpoint sequence runs —
   `checkpoint-security` (security-auditor) → `checkpoint-intent` (intent-reviewer) →
   `checkpoint-docs` (docs-reviewer) → `checkpoint-tag` (inline `git tag` + push).
   Completing `checkpoint-tag` also marks the phase complete in `docs/phases/index.md`
   in the same call, so no separate "mark phase complete" step is needed.

**The CER and intent refocus.** Before the checkpoint sequence starts, the
phase-completion / CER Do Now / build-gate guards check `docs/cer/backlog.md` for open
"Do Now" entries. The CER (Constraints and Exceptions Register) is the project's
structured triage log: findings from cold-eyes reviewers — security auditor, intent
reviewer, post-mortems — land in one of four quadrants (Do Now, Do Later, Do Much Later,
Do Never). The Do Now gate is a hard block: the checkpoint cannot start until every open
"Do Now" entry is resolved or formally re-triaged with an explicit reason. Findings
accumulate across phases, so each checkpoint is also a backlog grooming session — the
mechanism that prevents intent drift from compounding silently.

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

- Optimized for solo developers. No multi-developer story assignment or concurrent session
  coordination.
- The companion sidebar must be running for real-time drift detection and automatic spec
  updates. Pairmode functions without it, but decisions are not captured live.
- `lesson_review.py` annotates templates with improvement suggestions but does not apply
  them. The developer must open the template and implement the change manually.
- Story status updates and orchestrator steps that used to require manual bash
  invocations are now covered by `story_update.py` and `flex_build.py`, which together
  cover the full status lifecycle (introduced in Phases 18, 22, 45).
- Context gate enforcement is fully automatic via the PostToolUse/PreToolUse hook split
  (INFRA-182, Phase 74) for the four build-cycle subagent types it governs (`builder`,
  `loop-breaker`, `security-auditor`, `intent-reviewer`); `reviewer` is intentionally
  exempt (INFRA-246 — it is the loop's mandatory next step, not a discretionary spawn).
  The gate does not depend on orchestrator cooperation. A first spawn after `/clear`
  uses the SessionStart baseline (25,000 tokens); PostToolUse updates the count from
  the JSONL transcript after each spawn completes.
- The reconstruction workflow (ideology extraction and competing implementation seeding)
  requires a populated spec and works best after several sessions of decision capture.

## Requirements and License

**Requirements:**
- Claude Code (any version with plugin support)
- Python 3.11+
- uv (Python package manager)

**License:** MIT. See LICENSE file.

**Contact:** david@halfhorse.com
