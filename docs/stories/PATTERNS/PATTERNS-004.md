---
id: PATTERNS-004
phase: '48'
rail: PATTERNS
story_class: methodology
status: complete
primary_files:
  - docs/patterns/cost-operations/per-phase-effort-seeded-prior.md
touches: []
---

# PATTERNS-004 — Draft "Per-Phase Effort.db with Seeded Prior" pattern doc (NP-4)

See phase spec: `docs/phases/phase-48.md` § NP-4.

**Dependency satisfied:** Phase 47 INFRA-127 (the seed file `effort_baseline.json`,
`refresh_effort_baseline.py` CLI, and `context_budget.py` dynamic-median logic) is
complete and checkpointed at `cp47-pairmode-methodology-consolidation`.

## Acceptance criterion

`docs/patterns/cost-operations/per-phase-effort-seeded-prior.md` exists and follows
the cloudnirvana/open-patterns catalog template verbatim. All mandatory sections filled in.
"What Broke" and "Security Implications" filled in with real content. No placeholder text.

## Pattern identity

**Name:** Per-Phase Effort.db with Seeded Prior
**Category:** Cost & Operations
**One-line intent:** A per-phase SQLite database of token-cost observations bootstraps
from a cross-project seed file (524 attempts: 261 builder, 263 reviewer; builder
median 53,416 tokens; reviewer median 49,499 tokens), then switches to the per-phase
median once ≥5 attempts accumulate — so every new phase has a defensible cost estimate
from day one, and the estimate improves automatically as the phase builds.
**Also Known As:** Seeded Cost Prior, Bootstrapped Effort Baseline, Cross-Project Token
Estimator

## Implementation to reference

The shipped implementation lives at:
- `skills/pairmode/scripts/context_budget.py` — dynamic-median logic, threshold math,
  hook integration (INFRA-127)
- `skills/pairmode/scripts/flex_build.py context-health` — per-phase health report
- `skills/pairmode/seed/effort_baseline.json` — the seed file (524 total attempts:
  261 builder median 53,416 tokens, 263 reviewer median 49,499 tokens; generated
  by `refresh_effort_baseline.py`; `source_projects: []` — project list not captured
  at generation time)
- `.companion/state.json` — configurable fields:
  `expected_step_tokens` (seeded prior, replaced by per-phase median once ≥5 attempts),
  `context_budget_threshold` (default 120k),
  `context_budget_overrun_pct` (default 10%),
  `context_budget_reprompt_margin` (default 10k)

Read `docs/architecture.md` and `docs/phases/phase-47.md` CER-027 enforcement sub-track
for the full implementation context.

## What broke (cite these real incidents)

- **Pre-INFRA-127 (all phases before 47):** The context budget threshold was a static
  constant (120k tokens). No learning. No per-phase variance. Sessions that ran fast
  (small stories, haiku builder) hit the threshold at a different real-cost point than
  sessions running slow (large stories, opus builder). The static threshold was
  simultaneously too aggressive (blocking early) for high-cost sessions and too
  permissive (missing the warning) for low-cost ones.
- **New project cold-start problem:** When flex was applied to a new project (e.g. cora,
  aab), the per-phase median had no data. The orchestrator had to guess or use an
  arbitrary fallback constant. The seed file solves this: even a brand-new project gets
  a defensible starting estimate from 524 observed attempts (261 builder, 263 reviewer).
- **CER-027 (2026-05-29):** The context budget check fired only when the orchestrator
  remembered to check. A static constant isn't self-enforcing. The per-phase median,
  combined with hook enforcement, makes the estimate dynamic and the check mechanical.

## Required catalog template sections

Fetch the template: `gh api repos/cloudnirvana/open-patterns/contents/PATTERN-TEMPLATE.md --jq '.content' | base64 -d`

Key sections:

**Pattern in 60 Seconds:** Problem = static token thresholds are wrong for every phase
that doesn't match the baseline assumption. Insight = observations from this project
(and sister projects) are better predictors than a fixed constant. Key structure = three-row
table (Phase <5 attempts: use seed prior | Phase ≥5 attempts: use per-phase median |
Between phases: export to seed for next project). What broke = cold-start guessing on
new projects + CER-027 enforcement gap.

**Classification:** Category: Cost & Operations. Difficulty: Intermediate.
Adjacent catalog patterns: `context-cost-control` (this is the estimation primitive
that cost-control patterns build on), `context-lifecycle-management` (decides when
checkpointing should happen — feeds from this pattern's estimate).

**Motivation:** Concrete scenario: a team applies the pairmode methodology to a new
project. First phase: 12 stories. The context budget threshold is set to 120k tokens
"because that's what we used on the last project." But this project uses opus for all
stories (the last project used sonnet). Opus burns ~3× the tokens per story. By story
7, the context is at 140k and compaction has already happened, dropping in-flight
orchestrator state. With the seeded prior: the 688-attempt baseline includes opus-heavy
sessions; the threshold for this new project would have been set to ~180k, preventing
the mid-phase compaction.

**Applicability — Use when:**
- Multi-story phases where context budget matters
- New projects that can benefit from sister-project observations
- You want the cost estimate to improve automatically over a phase

**Applicability — Do NOT use when:**
- Single-story phases (no meaningful per-phase median)
- Projects with wildly different token profiles than the seed corpus
  (e.g., embedding-only, no prose generation)

**Structure:** Mermaid flowchart:
`New phase starts` → `Load effort.db` → `N attempts?` →
  No: `Use seed prior from effort_baseline.json` →
  Yes: `Use per-phase median` →
`Compute context_budget_threshold` → `Pre-step: will next step exceed threshold?` →
  No: `Spawn builder/reviewer` →
  Yes: `Emit CONTEXT BUDGET prompt, wait for operator` →
`After step: record attempt in effort.db` → (loop)

**Participants:** effort.db (per-phase SQLite) / effort_baseline.json (cross-project
seed file) / context_budget.py (dynamic-median module) / pre_tool_use.py hook (enforcement)
/ state.json (configurable tunables) / Orchestrator.

**How It Works:**
(1) At phase start: load effort.db for current phase. Count attempts.
(2) If <N (default 5): use `expected_step_tokens` from state.json (bootstrapped from
    effort_baseline.json at project initialization).
(3) If ≥N: compute per-phase median of PASS-outcome attempts (excludes retries from
    denominator to avoid inflating cost estimate).
(4) Before each sub-agent spawn: compare `current_tokens + expected_step_tokens` against
    `context_budget_threshold * (1 + overrun_pct)`.
(5) If projected to exceed: emit CONTEXT BUDGET prompt; wait for operator to acknowledge
    or /clear.
(6) After each attempt: record `total_tokens`, `tool_uses`, `duration_ms`, `outcome`,
    `model`, `agent_role` in effort.db.
(7) At phase end: the seed file can be regenerated to include this phase's observations
    for downstream projects.

**Consequences — Benefits:** New projects get a defensible estimate instead of a guess.
Estimate improves automatically. The same code handles cold start and warm phase
transparently. Cost anomalies (guardrail fires at 3× median) surface automatically.

**Consequences — Liabilities:** Seed corpus must be maintained as projects diverge.
Per-phase median lags reality in the early attempts of a phase. SQLite adds disk I/O
(negligible in practice).

**Consequences — What Broke in Practice:** Static threshold + cold start guessing (above).

**Security Implications:** effort.db and effort_baseline.json contain token counts and
durations — no secrets, no user data. File paths are configurable via state.json (same
trust boundary as other state.json fields — user-owned, local-only). No network access.

**Known Uses:** flex project — effort.db used across Phases 22–47.
effort_baseline.json seeded from 688 attempts across 7 projects (generated 2026-05-31).

**Related Patterns:**
- `context-lifecycle-management`: decides when to checkpoint; feeds from this pattern's
  threshold estimate
- `context-cost-control`: budget enforcement strategy; this pattern is the estimation
  primitive underneath it
- `cer-backlog-living-phases` (NP-3): CER-027 was the finding that forced mechanical
  enforcement of the budget check — the two patterns are historically linked

**Metadata — Contributor:** David Hague, flex project (david@halfhorse.com)
**Metadata — Production Environment:** macOS/Linux, Python/uv, SQLite, Claude Code CLI
**Metadata — License:** CC BY 4.0

## Output

Create `docs/patterns/cost-operations/per-phase-effort-seeded-prior.md`
with the completed pattern doc. Create the directory if needed.
Do not modify any other file.
