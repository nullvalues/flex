# flex — Phase 47: Pair-mode methodology consolidation

← [Phase 46: Local model infrastructure](phase-46.md)

**Status:** drafting — three of seven tracks specced (T8, T3, T4) plus the
**CER-027 enforcement sub-track** specced 2026-05-29 (post-clear) as
INFRA-127, INFRA-128, INFRA-129. Context cleared mid-phase on
2026-05-29 at message-token 155k (above the 120k pairmode threshold,
instance of CER-027). Resume marker below; post-clear resume note follows.

## Resume marker (2026-05-29 — written before context clear)

**Where we are in the sequence:**
- T8 (sync defects) — spec'd: INFRA-124 + BOOTSTRAP-003 + runbook ✓
- T3 (override boilerplate) — spec'd: INFRA-125 + runbook ✓
- T4 (DOC CURRENCY pointer) — spec'd: INFRA-126 + runbook ✓
- CER-027 enforcement sub-track — spec'd 2026-05-29 post-clear:
  INFRA-127 + INFRA-128 + INFRA-129 + runbook ✓
- T1, T2, T5, T6, T7 — not yet spec'd

**Pattern observed across T8/T3/T4 recon:** each track's *literal* scope
from the original cross-repo evaluation turned out to be smaller than the
evaluation framing implied. T8 → variable-plumbing already existed;
T3 → flex-only checks already not in canonical; T4 → DOC CURRENCY already
at HIGH severity in canonical. The actual work in each track collapsed to
a small template defect plus an operator runbook. Expect the same pattern
for T1/T2/T5/T6/T7 — re-recon each before drafting.

**Decision pending before next spec:** the natural next track is T6
(auth-check classification cache), but a load-bearing question is open:
**CER-027** (between-story context-check enforcement) has been on the table
for two specs without discussion. The original memory rule (`How to apply`
in `flex-context-check-enforcement.md`) said raise it at the first natural
pause after T4. T4 just landed. The current context clear is itself an
instance of CER-027's failure mode and an explicit signal to address it.

**Two valid resume paths after clear:**
1. **(Recommended)** Address CER-027 first. Spec the enforcement hook
   (likely PostToolUse or stop-hook reading `/context` and comparing
   against `state.json["context_budget_threshold"]`). Investigate first:
   does `flex/hooks/` already have scaffolding for this?
2. Continue with T6 spec. Defer CER-027 to a later natural pause.

**State on disk at clear:**
- `/mnt/work/flex/docs/phases/phase-47.md` (this file) — all recon
  findings, all drafted stories, all runbooks, working principles, all
  seven track decisions.
- `/mnt/work/flex/docs/cer/backlog.md` — CER-026 (vestigial
  `checklist_items`), CER-027 (context-check enforcement), CER-028
  (BUILD GATE variable inconsistency) all recorded with full context.
- `/home/nullvalues/.claude/projects/-mnt-work/memory/flex_context_check_enforcement.md`
  — project memory with `How to apply` trigger.
- `/home/nullvalues/.claude/projects/-mnt-work/memory/MEMORY.md` — index.

**What's NOT on disk (recoverable from above but worth noting):**
- The harness task list (11 tasks; T8/T3/T4 marked completed). After
  clear, regenerate from the Stories table + the pending tracks list.
- The recommended track sequence for remaining work:
  T6 → T2 → T5 → T1 → T7 (smallest to largest, T7 last by design so
  T2/T5/T1 become real worked examples to validate the lift workflow).

## Post-clear resume note (2026-05-29)

Resumed from the post-clear state above. Chose **Path 1** (address CER-027
first) — the clear itself was an instance of CER-027's failure mode, and
the "How to apply" trigger in `flex-context-check-enforcement.md` named
the first natural pause after T4 as the moment to surface it. T4 landed
just before the clear; this is that moment.

Recon, decisions, and four stories for the enforcement sub-track follow
the existing T3/T4/T8 recon sections. The original
T6 → T2 → T5 → T1 → T7 sequence resumes after the CER-027 sub-track is
built. Per the methodology, this sub-track must be **built** before the
remaining track specs are drafted — speccing T6/T2/T5/T1/T7 under the
known-broken /context check would simply produce more sessions that fail
the same way.

## Goal

Synthesize the methodology lessons from five downstream projects (forqsite,
radar, asp, aab, cora) back into the canonical flex template. Two motivating
findings from the cross-repo evaluation:

1. **Convergent inventions** in downstream projects (rebuild-completeness
   vocabulary in CORA/AAB/ASP; phase-doc existence gate in forqsite; doc-currency
   review check in four of five projects) signal canonical gaps that should be
   filled now.
2. **Canonical bloat** has accumulated — CLAUDE.build.md is 728 lines and ~250
   of those are inline bash blocks every downstream project carries verbatim
   without ever reading. Zero-context reads pay this cost on every cold start.

The overall objective is to **minify** the canonical (cut prose that doesn't
bind agent behavior; collapse inline bash into helper-CLI calls) **and** to
**lift** proven downstream patterns into the canonical, with a first-class
sync-back workflow so future lifts are routine rather than archeological.

## Tracks

Seven tracks identified from the evaluation. Each will be specced as one or
more stories below; large tracks may be split into their own phase docs.

| # | Track | Type |
|---|-------|------|
| T1 | `flex-build` helper CLI — collapse inline bash blocks | refactor |
| T2 | Promote rebuild-completeness vocabulary into phase template | template |
| T3 | Move flex-only checks (SKILL ISOLATION, PYTHON STANDARDS) out of canonical | restructure |
| T4 | Promote DOC CURRENCY review check to canonical at HIGH severity | promote |
| T5 | Promote `build-queue.md` pattern | template / docs |
| T6 | Generalize auth check to read recorded RBAC/ABAC classification | feature |
| T7 | Sync-back / lift-to-canonical workflow | tooling |

Plus a cleanup track for the sync defects surfaced in the evaluation:

| # | Track | Type |
|---|-------|------|
| T8 | Fix sync defects: duplicated `## session modes` blocks; stale `pytest tests/pairmode/` in downstream. Variable plumbing already exists via `.companion/pairmode_context.json` — only the canonical template forgot to use it. See "T8 recon" below. | bugfix |

## Decisions recorded

Decisions are recorded here as they are made, so they survive context
compaction. Open decisions are below; resolved decisions move up to this
section.

### Settled

- **T1 — `flex-build` helper CLI refactor: APPROVED.** This unlocks the
  largest single line reduction in CLAUDE.build.md (~250 lines collapsing to
  one-line helper calls). It's a flex code change, not a doc-only edit, but
  the canonical clarity payoff justifies the refactor.

- **T2 — Bootstrap phase-doc behavior: CONDITIONAL SCAFFOLD.** Bootstrap
  auto-creates `docs/phases/phase-1.md` with the rebuild-completeness
  `## Schema delivery` section pre-filled, but only when no phase doc exists.
  New projects get the right shape on day one; existing projects with phases
  are untouched. Re-running bootstrap is safe.

- **T3 — Flex-only checks: INTERNAL REVIEWER ADDENDUM.** SKILL ISOLATION and
  PYTHON STANDARDS move into a flex-only file (likely `flex/.claude/agents/`
  or a `flex-only` addendum loaded by flex's own reviewer agent). The
  canonical CLAUDE.md template loses both checks entirely so downstream
  projects do not inherit them via sync.

- **T4 — DOC CURRENCY review check severity: HIGH.**
  Reason: stale docs that no longer match code actively mislead future
  agents — exactly the failure mode flex methodology exists to prevent.
  asp/aab/cora/forqsite already run it as HIGH; canonical adopts the same.

- **T5 — Phase queue lives in `docs/phases/index.md`: UPGRADE THE INDEX,
  NO NEW FILE.** The canonical `index.md` template is enriched from day zero
  to carry queue semantics: explicit "next to build" pointer, deferred-stories
  lineage column, backlog-promotion entries. forqsite's `build-queue.md`
  invention is recognised as the symptom of a too-thin index, not a need for
  a second file. One source of truth, one template.

- **T6 — Auth-check generalization: APPROVED.** The canonical auth check
  should learn to read a recorded RBAC/ABAC classification from
  `docs/architecture.md` and skip the per-story prompt when present.
  Forqsite already does this manually; canonical generalizes. Architectural
  constraints should manifest as automatic reflexes.

- **T7 — Sync-back / lift-to-canonical workflow: APPROVED.** Need a guided,
  surgical lift process. `drift-report --convergent` already detects 3+ project
  convergence; what's missing is the workflow step that turns convergent
  findings into proposed-template-changes. The `/flex:pairmode review`
  machinery is the likely vehicle.

### Open

*(All seven decisions settled. Story specs to be drafted next, one track at
a time.)*

## Working principles (binding for all tracks)

These are the minification rules distilled from the evaluation. They apply
when writing new canonical prose and when reviewing existing prose for cuts.

1. A rule earns its lines only if removing it would change agent behavior.
2. Bash blocks longer than 3 lines belong in a helper script.
3. Don't restate — second mention is a 1-line cross-reference.
4. Narrate the gate, not the rationale.
5. Deprecation-history sentences expire.
6. Project-specific narrative lives in `docs/`, not `CLAUDE.md`.
7. Conditional rules ("Phase N only") must self-destruct at checkpoint.
8. One source of truth per fact — `CLAUDE.md` references it, doesn't restate.
9. Templates must be variable-substituted at sync time.
10. Promote to canonical only when 3+ projects converge.
11. Stack-specific commands and paths are template variables, never literals.
    Bootstrap detects or asks once and stores in `state.json` (or equivalent);
    canonical templates reference the variable. This covers at minimum:
    test command (`pytest`, `npm test`, `pnpm test`, `cargo test`, ...);
    package-manager invocation (`uv run`, `npm run`, `pnpm exec`, ...);
    schema-migration discovery surface (Alembic, Prisma, raw SQL paths);
    auth-file discovery surface (Better Auth, Auth.js, NextAuth, custom).
    If a canonical line contains a literal that varies by stack, it is a bug.

## T4 recon (recorded 2026-05-29)

Findings from inspecting `templates/CLAUDE.md.j2` lines 43-51,
`templates/agents/reviewer.md.j2` lines 47-156, `bootstrap.py:64`, and
the rendered `CLAUDE.md` files of all five downstream projects:

- **DOC CURRENCY is canonical at item #4 in both templates.**
  `CLAUDE.md.j2:43-51` carries the brief overview: HIGH severity for
  "factually wrong" cases, MEDIUM for README-only changes, with the
  documentation-surface rule (every `*.md` under `docs/` excluding history
  paths, plus `README.md`) and a manifest override at
  `docs/documentation-surface.md`. `reviewer.md.j2:63-115` carries the
  full operational procedure: discovery surface bash, four per-file check
  steps, severity matrix, and resolution path ("DOC CURRENCY failures are
  builder-remediable inline; the builder updates the affected doc in the
  same story commit").
- **Two-tier structure is healthy.** `CLAUDE.md` is the brief overview
  pointing at `reviewer.md` for detail; downstream projects use both. The
  original evaluation finding (asp/aab/cora/forqsite have DOC CURRENCY at
  item #4) is partially correct — confirmed for asp, aab, forqsite; cora
  does not have it. radar also lacks it entirely.
- **Reference path is wrong.** `CLAUDE.md.j2:51` says
  `See \`agents/reviewer.md\` § 4 for the full discovery and judgement procedure.`
  but `bootstrap.py:64` ships the file to `.claude/agents/reviewer.md`.
  Agents following the pointer look in the wrong place. One-line fix.
- **Two downstream projects need re-sync.** radar (`last_sync: 2026-04-22`)
  and cora (`last_sync: 2026-05-07`) both bootstrapped before DOC CURRENCY
  was added to canonical (asp has no last_sync field but has the check;
  aab synced 2026-05-22 and has it). Sync re-render should propagate the
  check; verify on completion.
- **No "promote" work remains.** The user-approved decision (HIGH severity)
  matches what's already shipped.

## T3 recon (recorded 2026-05-29)

Findings from inspecting `templates/CLAUDE.md.j2`, `pairmode_drift_report.py`
(`_load_overrides`, `_normalise`, `_split_sections`, `_SECTION_RE`),
`sync.py` lines 275-459, and the `.pairmode-overrides` files of all five
downstream projects:

- **Canonical template never shipped SKILL ISOLATION or PYTHON STANDARDS.**
  `templates/CLAUDE.md.j2` is 87 lines with exactly 4 review items:
  PROTECTED FILES, STORY SCOPE, BUILD GATE, DOCUMENTATION CURRENCY. Three
  Jinja variables total: `{{ project_name }}`, `{{ stack }}`,
  `{{ build_command }}`. No iteration anywhere. The original evaluation's
  "flex-only checks in canonical that other projects inherit" was a misread
  of flex's own *rendered* `CLAUDE.md`, which has been manually extended.

- **flex does not bootstrap itself.** No `.companion/` directory, no
  `.pairmode-overrides`, no `pairmode_context.json`. flex's own `CLAUDE.md`
  is wholly hand-maintained; sync never touches it. This is fine but means
  there is no formal declaration of which items in flex's checklist are
  "flex-only extensions."

- **Override mechanism works correctly.** `sync.py:275-459` reads
  `.pairmode-overrides`, parses to `(file_path, section_key)` tuples via
  `_load_overrides`, and skips re-rendering any section declared as
  project-owned. The mechanism's behaviour is fine.

- **Override boilerplate ships in two incompatible formats.** The parser
  (`pairmode_drift_report.py:114-117`) keys sections by the full header
  line *including* the `##` markers, then lowercase-normalises. So
  `## review checklist` matches but `review checklist` does not.
  - forqsite's `.pairmode-overrides` (2332 bytes) shows examples *with*
    markers (`CLAUDE.md:## review checklist`) — correct.
  - radar/asp/aab/ (~582 bytes each) show examples *without* markers
    (`CLAUDE.md:review checklist`) — incorrect; entries following these
    examples would silently fail to match.
  - cora has no `.pairmode-overrides` file at all.
  Anyone following the boilerplate examples in the four projects with the
  shorter format would write entries that don't work and have no diagnostic.

- **`checklist_items` field in `pairmode_context.json` is vestigial.**
  Captured at bootstrap (or by reconstruction parsing), persisted in
  context, and never consumed by the template. forqsite's context.json has
  rich `checklist_items` with name/description/severity for each, but
  forqsite's *rendered* `CLAUDE.md` items (TENANT ISOLATION, VISIBILITY
  JOIN, ...) were added manually — they don't match the items in
  `checklist_items` semantically. The field is dead data.

## T8 recon (recorded 2026-05-29)

Findings from inspecting `flex/skills/pairmode/scripts/bootstrap.py`,
`sync.py`, `audit.py`, the `.companion/pairmode_context.json` of all five
downstream projects, and lesson L004:

- `.companion/pairmode_context.json` is the canonical persistence file for
  bootstrap context (`stack`, `build_command`, `test_command`,
  `migration_command`, `project_name`, `project_description`, etc.). It is
  distinct from `.companion/state.json` (runtime / operational state). Every
  downstream project has the file and uses it on sync.
- The variable plumbing exists; the template forgot to call it.
  `CLAUDE.md.j2:70` hardcodes `uv run pytest tests/pairmode/ -x -q`. That is
  the source of the stale text in cora/radar/asp/aab. The fix is a one-line
  template edit to reference `{{ test_command }}` (with the same wrapper
  shape — sync re-runs will then regenerate correctly per project).
- AAB has a data defect: `test_command` in `pairmode_context.json` is the
  flex literal even though the stack is Node/pnpm. Needs a one-shot value
  correction *and* a validator to prevent recurrence.
- Lesson L004 is not in conflict with variable substitution. L004 correctly
  identified a semantic-slot mismatch (variable in Python-standards prose).
  With T3 removing the Python-standards prose from the canonical template,
  the remaining slots (Story test verification, BUILD GATE) are generic and
  should use the variable.
- T1 dependency does not bind T8. `CLAUDE.build.md.j2`'s inline
  `uv run python -c "..."` blocks are T1's territory (the `flex-build` CLI
  refactor); T8 touches only `CLAUDE.md.j2`.

## Surprises surfaced during T8 recon (flagged for later tracks)

- **T4 is essentially satisfied; one template defect to fix.** See
  "T4 recon" below for full findings. Summary: DOC CURRENCY is fully
  canonical at item #4 in both `CLAUDE.md.j2` (brief overview) and
  `reviewer.md.j2` (full procedure with discovery, per-file checks, severity
  matrix, resolution). HIGH severity already. Only real defect: the pointer
  in CLAUDE.md.j2:51 says `agents/reviewer.md` but the file actually ships
  to `.claude/agents/reviewer.md`. Two downstream projects (radar, cora)
  also lack the check entirely — pre-DOC-CURRENCY syncs. Re-sync via runbook.
- **T3 is essentially satisfied; recon surfaced adjacent defects.** See
  "T3 recon" below for full findings. Summary: canonical template never
  shipped SKILL ISOLATION or PYTHON STANDARDS. The original concern was a
  misread of flex's own (manually maintained) `CLAUDE.md`. Recon did surface
  three real adjacent issues that need a decision before T3 closes.
- **BUILD GATE is not part of the T8 bug.** Canonical line 40 already uses
  `{{ build_command }}`. Only Story test verification (line 70) is broken.

Both T3 and T4 will be re-recon'd before specs are drafted. The 88-line
canonical template + override mechanism is healthier than the evaluation
implied — much of the "promote / restructure" work may collapse into
verification + documentation.

## CER-027 sub-track recon (recorded 2026-05-29)

Findings from inspecting `skills/pairmode/templates/CLAUDE.build.md.j2`
lines 453-498, `CLAUDE.build.md` (rendered, same range), `hooks/hooks.json`,
`hooks/stop.py`, `hooks/post_tool_use.py`, `hooks/exit_plan_mode.py`,
`hooks/session_start.py`, `hooks/session_end.py`,
`skills/pairmode/scripts/context_budget_check.py`,
`skills/pairmode/scripts/record_attempt.py` (`attempts` table schema),
`skills/companion/scripts/sidebar.py` (`handle_stop`),
`docs/architecture.md` step 9, the flex local `CLAUDE.md`
HOOK PERFORMANCE / PIPE CONTRACT review checks, and the union of
`.companion/effort.db` across forqsite/radar/asp/aab/cora/anchor/pokus.

- **The doc-stated rule is a four-step LLM ritual.** `CLAUDE.build.md.j2`
  lines 453-498 instruct the orchestrator, between every story, to read
  `state["context_budget_threshold"]` (default 120 000), compare its own
  context-window size via `/context`, and surface a verbatim
  proceed-vs-clear prompt at threshold. Every step depends on the LLM
  remembering to run it. The operator observed (cross-project session
  2026-05-29) that the ritual is reliably skipped: the prompt that
  should fire never fires, context bloats past threshold, and at 155k a
  manual `/clear` is the only recourse.

- **The existing `context_budget_check.py` measures a different signal.**
  `skills/pairmode/scripts/context_budget_check.py` sums
  `effort.db.attempts.tokens_total` for a phase — cumulative subagent
  spend. That is useful for phase-cost dashboards but is **not** the
  orchestrator's own context-window size. Both share the
  `context_budget_threshold` name and the 120 000 default but read
  different denominators. Reusing the existing CLI for enforcement
  would silently shift the semantic; the sub-track adds a sibling
  module instead.

- **Token totals for the orchestrator window are available in the
  transcript JSONL.** Each assistant turn carries a `message.usage`
  object with `input_tokens`, `output_tokens`,
  `cache_read_input_tokens`, `cache_creation_input_tokens`. The
  context-window estimate matching what `/context` reports is
  `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`
  on the **last** assistant message. No API call; one tail-read of the
  JSONL.

- **PreToolUse on `Task` is the right enforcement point — and large
  enough to carry the whole mechanism.** Claude Code's PreToolUse hook
  fires before each tool call and can return a deny/block decision that
  prevents the call and feeds the reason back as the next observation.
  Matching `Task` targets the exact "between stories" boundary (every
  builder and reviewer spawn). At this granularity a transcript
  tail-read + a single sqlite query is sub-millisecond — cheap enough
  to run on every Task call. **The producer (count + decide) and the
  consumer (block) collapse into one hook.** No marker file, no Stop-
  hook coupling, no sidebar dependency.

- **Sidebar deprecation context.** The sidebar is on a path to be
  retired in favor of a full-auto build mode driven by specs + rules,
  with a thin TypeScript SPA later providing observability/tuning.
  Putting CER-027 producer logic in the sidebar would push work *into*
  the component being retired — wrong direction. The skill module
  approach below survives sidebar retirement and the SPA can read its
  state.json fields when it lands.

- **Self-clear is not achievable from a hook today.** Claude Code's
  hook return contract supports `decision: block` with a `reason`,
  additional-context injection, and a few related shapes — none of
  which execute a slash command. The realistic enforcement ceiling for
  v1 is "force the prompt; user types `/clear` themselves." An
  external watcher that polls a `.companion/clear_requested` sentinel
  and resumes via Claude Code's session-resume CLI could close that
  gap later (separate phase, separate spec).

- **Real seed data exists.** Union of `attempts.tokens_total` across
  seven existing downstream `effort.db` files (cora, forqsite, pokus,
  radar, asp, anchor, aab — 688 attempts total):
  - builder (n=261): median 53 416, p75 77 498, p90 111 434, max 235 348
  - reviewer (n=263): median 49 499, p75 58 308, p90 75 349, max 124 376
  - sidebar/other (n=164): median 4 492, p90 7 865
  These numbers are the *subagent's* total tokens, not the orchestrator's
  per-step context delta — they overestimate the increment by a wide
  margin (the orchestrator only sees the Task result envelope, not the
  subagent's internal context). Used as a seed they bias toward earlier
  prompts, which is the safer failure mode. Bootstrap will seed
  `state["expected_step_tokens"]` from the builder median (~53 000) as a
  conservative prior; per-project medians refine over time.

- **150k Claude context hard ceiling (current).** Operator note:
  irrespective of nominal model context windows (200k, 1M), today's
  Claude Code session pushes past ~150k start to degrade severely. The
  default `context_budget_threshold` (120 000) + a default
  `context_budget_overrun_pct` (0.10) gives a 132 000 effective ceiling
  — well under 150k. Both fields are operator-tunable so the ceiling
  moves with the platform.

- **Architectural tension with the thin-relay rule.** The flex local
  `CLAUDE.md` review check #1 (HOOK PERFORMANCE) reads: "Hooks are thin
  relays only. Any blocking logic in a hook is CRITICAL." The rule's
  *spirit* is: don't slow hooks down with API calls or subprocess
  spawns, and don't put domain logic inline in a script that fires on
  every tool use. A PreToolUse hook that delegates all logic to a named
  pairmode skill module (`skills/pairmode/scripts/context_budget.py`)
  and returns either a `decision: block` or exit-0 stays within the
  spirit: the hook itself is a five-line caller; the logic is in a
  testable module. The rule must be amended to name this as the
  canonical thin-delegation exception.

- **`record_attempt.py` already writes the fields we need.** The
  `attempts` table schema (verified via sqlite):
  ```
  story_id, phase, rail, agent_role, model, attempt_number,
  tokens_total, tokens_in, tokens_out, cache_read_tokens,
  cache_write_tokens, tool_uses, duration_ms, outcome, notes, ts,
  story_class, model_selection_reason, backend
  ```
  Median by `phase` is one sqlite query. No schema change required.

## CER-027 sub-track decisions

These are settled before story specs are drafted, in the spirit of the
"Decisions recorded" section above. They bind INFRA-127 through
INFRA-129.

- **D1 — One PreToolUse-on-Task hook owns the whole mechanism.**
  No producer/consumer split, no marker file, no Stop-hook coupling.
  On each `Task` tool call, the hook delegates to
  `skills/pairmode/scripts/context_budget.py:should_block()` which
  reads transcript + state.json + effort.db, decides, and returns
  either the verbatim prompt as a block reason or pass-through.

- **D2 — All decision state lives in `.companion/state.json`.**
  New optional fields (no schema migration; absent fields use defaults):
  - `context_budget_threshold` — int — already canonical, default
    120 000. Operator-tunable upward; ceiling tracks platform headroom.
  - `context_budget_overrun_pct` — float — new, default 0.10. The
    effective block ceiling is `threshold * (1 + overrun_pct)`.
  - `expected_step_tokens` — int — new, default seeded at bootstrap
    from the flex-aggregated builder median (~53 000). Used as the
    cold-start estimate when the current phase has fewer than 5
    recorded attempts.
  - `context_budget_acknowledged_at` — int|null — written by the hook
    when it consumes-and-blocks. Suppresses re-block until tokens
    cross `acknowledged_at + context_budget_reprompt_margin`.
  - `context_budget_reprompt_margin` — int — new, default 10 000.

- **D3 — Token source is the transcript JSONL tail.** Read the last
  ~50 lines of `transcript_path`, find the last `type: "assistant"`
  message, compute
  `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`
  from `message.usage`. Missing values default to 0. Same accounting
  `/context` reports.

- **D4 — Estimate is dynamic from effort.db with a seeded fallback.**
  Logic in `context_budget.py:estimate_next_step_tokens(db_path, phase)`:
  1. If `attempts` table has ≥ 5 rows for `phase = ?`, return the
     median of `tokens_total` for those rows.
  2. Otherwise return `state["expected_step_tokens"]` (seeded prior).
  As the project accumulates attempts the estimate refines; until
  then the seeded prior applies. The seed itself is refreshable —
  see INFRA-127's `refresh_effort_baseline.py` CLI.

- **D5 — Block condition.** `current + estimate > threshold * (1 + overrun_pct)`.
  Strictly-greater so the threshold itself isn't a block; only the
  *next-step projection* crossing the overrun ceiling triggers.

- **D6 — Hook matcher is `Task` only.** PreToolUse fires on every
  tool call. Matching `Task` only (the subagent-spawn tool) targets
  the between-story boundary and lets other tools (Read, Bash, etc.)
  flow through unaffected — useful when the operator needs to inspect
  state after a block.

- **D7 — Verbatim prompt stays in the canonical template.** The
  CONTEXT BUDGET prompt body remains in `CLAUDE.build.md.j2` as the
  source of truth; `context_budget.py:render_alert_prompt()`
  templates from it via a small fixture file shared with the template
  tests so drift is impossible. The four-step LLM ritual prose around
  the prompt body is replaced with a mechanical-enforcement pointer.

- **D8 — Hook-thinness exception is documented inline.** The flex
  local `CLAUDE.md` HOOK PERFORMANCE check #1 is amended to name
  `pre_tool_use.py` as the canonical thin-delegation exception: the
  hook itself does one stdin parse, one tool_name check, one delegated
  call into `skills/pairmode/scripts/context_budget.py`, and emits the
  module's return value to stdout. All domain logic lives in the
  named module. Any added logic in the hook beyond delegation remains
  CRITICAL.

- **D9 — Build order is INFRA-127 → INFRA-128 → INFRA-129.**
  Pairmode skill module + seed CLI first (INFRA-127), so the hook
  (INFRA-128) has a stable, tested interface to call. Doc changes
  (INFRA-129 — template prose + CLAUDE.md carve-out + architecture.md
  step 9 update) last, after the mechanism they describe is shipped.
  All three stories share a single acceptance condition: a session
  whose projected next-step total would cross
  `threshold * (1 + overrun_pct)` produces the prompt without LLM
  attention.

- **D10 — Auto-clear is explicitly out of scope.** Not achievable
  from a hook in current Claude Code. Recorded as a follow-on in the
  CER backlog at the same time INFRA-129 ships.

- **D11 — Write boundary: `decide()` is read-only; the hook owns the
  one write.** `context_budget.decide()` reads `.companion/state.json`,
  `.companion/effort.db`, and the transcript JSONL; it MUST NOT write
  any of them. The hook (`hooks/pre_tool_use.py`) performs exactly one
  write — `context_budget_acknowledged_at` — and only when `decide()`
  returned `block=True`. Rationale: `.companion/state.json` is a plain
  JSON file with no in-process concurrency protection, so keeping the
  write surface to one code path on the block edge serializes access.
  Any future write-back from `decide()` (counters, learned overrides,
  last-check timestamps) is out of scope here and requires a new CER
  plus a concurrency-model pass before it lands. Catalog cross-reference:
  `files-over-databases` (cloudnirvana/open-patterns) → Common Pitfalls
  → "Not locking files during writes." Added 2026-05-29 after a
  pre-build pattern-catalog review surfaced the implicit assumption.

- **D12 — Single hard block; no soft-warning gradient.** The catalog
  pattern `context-lifecycle-management` (cloudnirvana/open-patterns)
  recommends tiered thresholds (40 / 60 / 75 / 85 %) with progressively
  aggressive actions. We use a single hard block at
  `threshold * (1 + overrun_pct)` instead. Rationale: every tier below
  a hard block is an LLM-attention prompt, and CER-027 *is* the failure
  of LLM-attention-based enforcement. Softer tiers would reproduce the
  failure mode this sub-track exists to fix. The single block is
  mechanical — the hook injects it; the LLM cannot skip it — which is
  the load-bearing property. If real-world telemetry later shows the
  block consistently fires "too late" (work lost before next-step
  projection had a chance to trigger), the correction is to lower
  `context_budget_threshold` or shrink `context_budget_overrun_pct`,
  not to re-introduce soft tiers. Recorded as a deliberate divergence
  from catalog guidance, not an oversight. Added 2026-05-29.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-124 | Use `{{ test_command }}` variable in CLAUDE.md.j2 Story test verification block | complete |
| BOOTSTRAP-003 | Validator: warn when test_command/stack disagree on toolchain | complete |
| INFRA-125 | Fix `.pairmode-overrides.j2` boilerplate to use parser-correct section-key format | complete |
| INFRA-126 | Fix `CLAUDE.md.j2` DOC CURRENCY pointer to use shipped path `.claude/agents/reviewer.md` | planned |
| INFRA-127 | New `skills/pairmode/scripts/context_budget.py` module + `refresh_effort_baseline.py` seed CLI + bootstrap seeding | planned |
| INFRA-128 | New thin `hooks/pre_tool_use.py` delegate + `hooks.json` `Task` wire-up | planned |
| INFRA-129 | Replace `CLAUDE.build.md.j2` § "Context budget check" prose; amend flex `CLAUDE.md` HOOK PERFORMANCE carve-out; update `docs/architecture.md` step 9 | planned |

### Story INFRA-124 — Use `{{ test_command }}` variable in CLAUDE.md.j2 Story test verification block

**Rail:** INFRA | **story_class:** code

#### Requires

- `skills/pairmode/templates/CLAUDE.md.j2:70` contains the literal
  `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q 2>&1 | tail -30`
  inside the `## Story test verification` fenced bash block. This is the
  source of the stale text in `cora/CLAUDE.md`, `radar/CLAUDE.md`,
  `asp/CLAUDE.md`, and `aab/CLAUDE.md`.
- `skills/pairmode/scripts/audit.py:218-247 _load_project_context` reads
  `.companion/pairmode_context.json` and exposes `test_command` as a Jinja
  variable. All five downstream projects already have `test_command`
  captured in their context file.
- `skills/pairmode/scripts/bootstrap.py:802` and `sync.py:431` both pass the
  loaded context into the render call.
- Lesson L004 (`lessons/lessons.json`) noted that placing `{{ build_command }}`
  inside Python-standards prose was a semantic-slot mismatch — the Python
  standards section is stack-specific narrative, not generic. The Story test
  verification block is the inverse case: it is a generic slot ("run the
  story's tests") and is the correct place for a variable.
- The audit fallback context (`_load_project_context` lines 232-246) returns
  `"test_command": ""` when `pairmode_context.json` is absent. A naive
  substitution `{{ test_command }}` against an empty value would render
  ` 2>&1 | tail -30` (leading space, no command) — silently broken bash.

#### Ensures

- **`skills/pairmode/templates/CLAUDE.md.j2`** — the fenced bash block under
  `## Story test verification` (currently line 70) becomes:
  ```jinja2
  {{ test_command | default('echo "TEST COMMAND NOT CONFIGURED — run flex bootstrap"; exit 1', true) }} 2>&1 | tail -30
  ```
  The `default(..., true)` flag ensures an empty string is treated as
  unset (Jinja `default` filter normally only fires on undefined, not empty).
  An unconfigured project renders a self-flagging command rather than silently
  broken bash.
- **`tests/pairmode/test_template_render.py`** (new file, or new test in an
  existing render test file if one exists) — three test cases:
  1. Python-shaped context (`test_command="PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q"`)
     → rendered output contains that exact command on its own line, followed
     by ` 2>&1 | tail -30`.
  2. Node-shaped context (`test_command="pnpm test"`) → rendered output
     contains `pnpm test 2>&1 | tail -30` and does not contain `pytest`.
  3. Empty context (`test_command=""`) → rendered output contains the
     `TEST COMMAND NOT CONFIGURED` placeholder and `exit 1`.
- **No other changes to CLAUDE.md.j2.** BUILD GATE (line 40) already uses
  `{{ build_command }}` correctly. Do not touch any other section.
- **No changes to `pairmode_context.json` schema.** The variable is already
  defined; this story only consumes it correctly.

#### Out of scope

- Re-rendering downstream projects' `CLAUDE.md` files. That is the operator's
  job after this story merges, covered by the "Downstream propagation" runbook
  in this phase doc.
- Fixing AAB's corrupted `test_command` value (it's a Python literal in a
  Node project's context.json). That is BOOTSTRAP-003's territory and the
  runbook.
- Touching `CLAUDE.build.md.j2`'s inline `uv run python -c "..."` blocks.
  Those are T1's territory (the `flex-build` helper CLI refactor).

---

### Story BOOTSTRAP-003 — Validator: warn when test_command/stack disagree on toolchain

**Rail:** BOOTSTRAP | **story_class:** code

#### Requires

- `aab/.companion/pairmode_context.json` has
  `test_command = "PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q"`
  despite `stack` being `"TypeScript / pnpm workspaces / Fastify v5 / Drizzle ORM / Postgres / Vite / React 19 / Tailwind v4 / better-auth / zod / vitest"`.
  This is a data defect introduced at bootstrap time — the operator
  presumably hit Enter on a prompt that defaulted to the flex literal, and
  nothing caught it.
- `skills/pairmode/scripts/bootstrap.py:697-698` derives `test_command` from
  `build_command` without any check that the result is consistent with the
  captured `stack`.
- No equivalent check exists at sync time, so the bad value survives every
  subsequent `pairmode_sync.py update` invocation.

#### Ensures

- **New function in `bootstrap.py`** (placement: near `_infer_build_command`
  at line 130):
  ```python
  def _validate_test_command(test_command: str, stack: str) -> list[str]:
      """Return a list of warning strings; empty list means no concerns."""
  ```
  Rules (only one for now, designed to grow):
  1. If `test_command` contains `"pytest"` or `"uv run"` and
     `"python"` not in `stack.lower()`: append warning
     `"test_command looks like a Python toolchain ({test_command!r}) but stack does not mention Python ({stack!r}) — likely a bootstrap default that should be overridden."`
- **bootstrap.py calls the validator** immediately before
  `pairmode_context.json` is written (around line 802 where the context dict
  is assembled). Warnings are printed via `click.echo(msg, err=True)`.
  Bootstrap continues; warnings are advisory, not blocking.
- **sync.py calls the validator** at the top of `update_project` (or
  equivalent entry point — likely around line 273 where `_load_project_context`
  is invoked). Same advisory behaviour; printed once per sync run.
- **`tests/pairmode/test_validators.py`** (new file, or appended to an
  existing validators test file): four test cases:
  1. Python stack + Python test_command → no warnings.
  2. Python stack + Node test_command (`pnpm test`) → no warnings. The
     inverse direction is not a defect we have evidence for; do not gate it.
  3. Node stack + Python test_command (the AAB case) → one warning.
  4. Node stack + Node test_command → no warnings.
- **No changes to `pairmode_context.json` schema.** No changes to any
  template. No changes to existing downstream context files (the AAB
  correction is the operator's job, covered by the runbook).

#### Out of scope

- Fixing AAB's existing bad value. The validator only warns going forward;
  the operator fixes the existing value as part of the runbook.
- Adding more rules. The framework is in place; future rules (e.g., Node
  stack + missing `pnpm`/`npm`/`yarn` in test_command) can be added later
  when evidence accumulates. One rule now satisfies the actual evidence.
- Gating sync or bootstrap on warnings. Warnings are advisory; the operator
  may have legitimate reasons (e.g., a polyglot repo) that we don't predict.

---

### Story INFRA-125 — Fix `.pairmode-overrides.j2` boilerplate to use parser-correct section-key format

**Rail:** INFRA | **story_class:** code

#### Requires

- `skills/pairmode/templates/.pairmode-overrides.j2` is 15 lines. Its
  example block (lines 10-12) shows:
  ```
  #   CLAUDE.md:review checklist
  #   .claude/agents/reviewer.md:checklist
  ```
  and its format description (line 9) reads:
  ```
  # The section key is the lowercased, stripped header text.
  ```
  Both are incorrect.
- `pairmode_drift_report.py:88-117` is the authoritative parser:
  - `_SECTION_RE = r"^(##+ .+|---)$"` matches the full header line including
    `##` markers.
  - `_split_sections` keys each section by `_normalise(header)` where the
    header *retains* its `##` markers.
  - `_normalise` lowercases and collapses whitespace; it does not strip
    markers.
  Therefore the correct example is `CLAUDE.md:## review checklist`, not
  `CLAUDE.md:review checklist`. Any override entry written by an operator
  following the current boilerplate will silently fail to match.
- forqsite's manually corrected `.pairmode-overrides` (2332 bytes) carries
  the parser-correct examples and an additional `sync-build` caveat that the
  canonical boilerplate lacks. It is the de-facto reference for what the
  canonical should ship.
- Four downstream projects (radar, asp, aab — and any other project that
  bootstrapped from the current template) carry the wrong boilerplate. cora
  has no `.pairmode-overrides` file. forqsite has the correct one (manual
  fix).

#### Ensures

- **`skills/pairmode/templates/.pairmode-overrides.j2`** is rewritten so the
  comment block:
  - Replaces the line "The section key is the lowercased, stripped header
    text" with: "The section key is the full header line — `##` markers
    included — lowercased and whitespace-collapsed. Examples below match
    this format."
  - Replaces the examples with:
    ```
    #   CLAUDE.md:## review checklist
    #   .claude/agents/reviewer.md:### checklist
    ```
  - Adds a short `sync-build` caveat at the bottom of the comment block:
    "Note: `.pairmode-overrides` is honored by `pairmode sync` (scaffold
    sync) and `audit`, but NOT by `pairmode sync-build`. `sync-build
    --apply` rewrites CLAUDE.build.md wholesale and ignores these
    declarations. Maintain CLAUDE.build.md via surgical merge, never via
    `sync-build --apply`."
  - Total length stays under 25 lines. The forqsite version (76 lines after
    expansion) is too verbose for canonical; preserve only the essential
    contract.
- **`tests/pairmode/test_overrides_boilerplate.py`** (new file, or appended
  to an existing test): two tests:
  1. Render `.pairmode-overrides.j2` against an empty context and assert
     the rendered text contains the substring `CLAUDE.md:## review checklist`.
  2. Parse the rendered text using `pairmode_drift_report._load_overrides`
     against a tempdir copy and assert that the example entries (with `#`
     prefix) are correctly ignored as comments — confirming the examples
     are well-formed comments.
- **No changes to the parser, to sync.py, to audit.py, or to existing
  downstream `.pairmode-overrides` files.** Those are operator-runbook
  territory.

#### Out of scope

- Fixing existing downstream boilerplate. Covered by the runbook.
- Promoting forqsite's longer version verbatim. The canonical stays terse;
  the runbook can point operators to forqsite if they want a fuller
  reference.
- Adding new override capabilities (per-line patterns, regex matching,
  etc.). The mechanism's behaviour is unchanged.
- Writing a separate `docs/overrides.md`. The boilerplate IS the developer
  documentation; restating it elsewhere violates minification principle 8
  ("one source of truth per fact").
- Fixing CER-026 (vestigial `checklist_items`). Recorded in CER backlog
  with full context; will be addressed in a future track when forcing
  function arrives (likely T2 phase-template work).

---

### Story INFRA-126 — Fix `CLAUDE.md.j2` DOC CURRENCY pointer to use shipped path `.claude/agents/reviewer.md`

**Rail:** INFRA | **story_class:** code

#### Requires

- `skills/pairmode/templates/CLAUDE.md.j2:51` reads:
  `See \`agents/reviewer.md\` § 4 for the full discovery and judgement procedure.`
- `skills/pairmode/scripts/bootstrap.py:64` registers the destination
  mapping: `(".claude/agents/reviewer.md", "agents/reviewer.md.j2")`. The
  rendered file ships to `.claude/agents/reviewer.md`, not `agents/reviewer.md`.
- Every downstream project verified shows the file at
  `.claude/agents/reviewer.md` (forqsite/radar/asp/aab/cora — confirmed by
  `find` listing). Agents following the pointer in the current canonical
  text look in a nonexistent directory.

#### Ensures

- **`skills/pairmode/templates/CLAUDE.md.j2`** line 51 (the trailing
  reference line of the DOCUMENTATION CURRENCY item) is updated to read:
  `See \`.claude/agents/reviewer.md\` § 4 for the full discovery and judgement procedure.`
  No other content in CLAUDE.md.j2 changes.
- **`tests/pairmode/test_template_render.py`** (the file introduced by
  INFRA-124, or appended to it if INFRA-124 already created it): one new
  test. Render `CLAUDE.md.j2` against an empty context and assert the
  rendered text contains the substring `.claude/agents/reviewer.md` and does
  NOT contain the bare `agents/reviewer.md` outside that substring. (Use a
  precise check — e.g., split on lines, find the DOC CURRENCY pointer line,
  assert it contains the dot prefix.)

#### Out of scope

- Re-rendering downstream projects' `CLAUDE.md` files to propagate the
  fix. Covered by the runbook.
- Re-syncing radar and cora to add DOC CURRENCY in the first place.
  Same runbook handles both fixes in one sync pass.
- The BUILD GATE variable inconsistency (CER-028). Recorded in the CER
  backlog; needs a semantic decision (`build_command` vs `test_command`)
  before any template change. Out of T4 scope.
- Removing or renaming `agents/reviewer.md.j2` itself — the template path
  is correct; only the rendered consumer's reference text is wrong.

---

### Story INFRA-127 — New `skills/pairmode/scripts/context_budget.py` module + `refresh_effort_baseline.py` seed CLI + bootstrap seeding

**Rail:** INFRA | **story_class:** code

#### Requires

- The `attempts` table schema (verified via sqlite on
  `cora/.companion/effort.db`):
  ```
  story_id, phase, rail, agent_role, model, attempt_number,
  tokens_total, tokens_in, tokens_out, cache_read_tokens,
  cache_write_tokens, tool_uses, duration_ms, outcome, notes, ts,
  story_class, model_selection_reason, backend
  ```
  No schema change required; the median query is `SELECT tokens_total
  FROM attempts WHERE phase = ? AND tokens_total IS NOT NULL`.
- Claude Code transcript JSONL lines of `type: "assistant"` carry a
  `message.usage` object with `input_tokens`, `output_tokens`,
  `cache_read_input_tokens`, `cache_creation_input_tokens`. The
  context-window-size estimate matching what `/context` reports is
  `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`
  on the **last** assistant message in the file. The transcript may be
  large (multi-MB); a tail read of the last ~50 lines is sufficient
  and avoids full-file parse cost.
- `.companion/state.json` already carries `context_budget_threshold`
  (default 120 000) and `pipe_path`. New optional fields owned by this
  story: `context_budget_overrun_pct` (float, default 0.10),
  `expected_step_tokens` (int, default 53000 — flex builder median),
  `context_budget_acknowledged_at` (int|null, set by INFRA-128 hook),
  `context_budget_reprompt_margin` (int, default 10000).
- The verbatim CONTEXT BUDGET prompt body lives in
  `skills/pairmode/templates/CLAUDE.build.md.j2` lines 487-496. The
  module's `render_alert_prompt()` must template from a fixture file
  shared with INFRA-129's template tests so drift between prompt
  source and rendered prompt is impossible.
- `skills/pairmode/scripts/bootstrap.py:802` is the canonical write
  point for new `.companion/state.json` files. INFRA-127 adds seed
  defaults to the dict assembled there.
- The seed source is `skills/pairmode/seed/effort_baseline.json`
  (new file), populated by `refresh_effort_baseline.py` from the
  union of downstream `effort.db` files. Verified aggregate as of
  2026-05-29 across seven projects (688 attempts): builder median
  53 416, reviewer median 49 499, sidebar/other median 4 492. The
  seed file *ships in the repo* so a fresh clone with no `.companion/`
  directories anywhere still bootstraps with sensible priors.
- The existing `skills/pairmode/scripts/context_budget_check.py`
  (phase-spend CLI) is unrelated and stays as-is. The new module is
  named `context_budget.py` (no `_check` suffix) to distinguish.

#### Ensures

- **New module `skills/pairmode/scripts/context_budget.py`** carrying
  pure functions, no side effects on import:
  ```python
  def compute_context_tokens(transcript_path: str) -> int | None:
      """Return the orchestrator context-window estimate at the last
      assistant turn (input + cache_read + cache_creation), or None if
      the transcript is missing/malformed or has no assistant turns
      yet. Implementation tail-reads ~50 lines to avoid full-file parse."""

  def estimate_next_step_tokens(
      db_path: Path | None,
      phase: str | None,
      seeded_default: int,
  ) -> int:
      """If db_path exists AND phase is set AND attempts table has >=5
      rows for that phase with non-null tokens_total: return the
      median. Otherwise return seeded_default."""

  def should_block(
      current_tokens: int,
      expected_next: int,
      threshold: int,
      overrun_pct: float,
      acknowledged_at: int | None,
      reprompt_margin: int,
  ) -> bool:
      """Pure decision. Block iff:
        current + expected > threshold * (1 + overrun_pct)
      AND (acknowledged_at is None OR
           current_tokens >= acknowledged_at + reprompt_margin)."""

  def render_alert_prompt(
      story_id: str | None,
      tokens: int,
      threshold: int,
      overrun_pct: float,
  ) -> str:
      """Template the canonical verbatim prompt body from
      tests/pairmode/fixtures/context_budget_prompt.txt with
      [story RAIL-NNN], [N], [T], and [O] substituted. Story_id falls
      back to 'current' when None."""

  def decide(project_dir: Path, transcript_path: str) -> dict | None:
      """End-to-end glue. Reads state.json + effort.db + transcript,
      calls should_block, returns
        {"block": True, "reason": "<prompt>", "tokens": N, "acknowledged_at": N}
      when the next step would exceed the overrun ceiling, else None.
      Caller (the hook) is responsible for writing
      acknowledged_at back to state.json after consuming."""
  ```
  All logic lives here. The hook (INFRA-128) is a six-line caller.
- **New module `skills/pairmode/scripts/refresh_effort_baseline.py`**
  — operator CLI:
  ```bash
  uv run python skills/pairmode/scripts/refresh_effort_baseline.py \
      --project-dirs /mnt/work/forqsite /mnt/work/radar /mnt/work/asp \
                     /mnt/work/aab /mnt/work/cora /mnt/work/anchor \
                     /mnt/work/pokus \
      --output skills/pairmode/seed/effort_baseline.json
  ```
  Reads `.companion/effort.db` from each path, aggregates
  `tokens_total` grouped by `agent_role`, computes median + p75 + p90
  + n, writes a JSON file:
  ```json
  {
    "generated_at": "2026-05-29T00:00:00Z",
    "source_projects": ["forqsite", "radar", "..."],
    "by_role": {
      "builder":  {"n": 261, "median": 53416, "p75": 77498, "p90": 111434},
      "reviewer": {"n": 263, "median": 49499, "p75": 58308, "p90": 75349}
    }
  }
  ```
  Missing or empty effort.dbs are skipped silently. Output is
  idempotent — running twice with the same input produces byte-equal
  output (sort source_projects alphabetically; round floats; etc.).
- **New seed file `skills/pairmode/seed/effort_baseline.json`** —
  shipped in the repo with the current snapshot of aggregate values
  (builder median 53416, reviewer median 49499 per recon). Generated
  by the refresh CLI; committed alongside this story. The file is
  data, not code; future operators refresh it whenever they want a
  fresher baseline.
- **`bootstrap.py` reads the seed file at write time** (around
  line 802 where the state.json dict is assembled) and writes the
  following defaults into new projects:
  - `context_budget_threshold`: 120000 (existing default, unchanged)
  - `context_budget_overrun_pct`: 0.10
  - `expected_step_tokens`: seed_file["by_role"]["builder"]["median"]
  - `context_budget_reprompt_margin`: 10000
  Existing projects' state.json files are not modified — absent
  fields use code-level defaults, matching the prior bootstrap pattern.
- **Fixture file `tests/pairmode/fixtures/context_budget_prompt.txt`**
  — the verbatim prompt body extracted from `CLAUDE.build.md.j2` lines
  487-496. Tests for both `context_budget.py` AND the template render
  in INFRA-129 assert against this fixture so source-of-truth drift
  is mechanically caught.
- **Tests `tests/pairmode/test_context_budget.py`** (new file):
  1. `compute_context_tokens` single assistant message → sum of three
     input-side fields.
  2. `compute_context_tokens` multiple assistant turns → last turn's
     sum, not running total.
  3. `compute_context_tokens` missing/empty/malformed file → None.
  4. `compute_context_tokens` assistant turns with no `usage` → None.
  5. `compute_context_tokens` against a large (>1MB) synthetic
     transcript → returns in under 100ms. Asserts the tail-read path.
  6. `estimate_next_step_tokens` with <5 attempts in phase → returns
     seeded_default.
  7. `estimate_next_step_tokens` with ≥5 attempts in phase → returns
     median(tokens_total).
  8. `estimate_next_step_tokens` with missing db_path → returns
     seeded_default.
  9. `should_block(current=110_000, expected=15_000, threshold=120_000,
     overrun=0.10, ack=None)` → False
     (125k ≤ 120k*1.10 = 132k).
  10. `should_block(current=120_000, expected=15_000, threshold=120_000,
      overrun=0.10, ack=None)` → True
      (135k > 132k).
  11. `should_block(current=140_000, expected=15_000, ack=140_000, margin=10_000)`
      → False (acknowledged at current value, not yet +10k).
  12. `should_block(current=150_000, expected=15_000, ack=140_000, margin=10_000)`
      → True (crossed +10k beyond ack).
  13. `render_alert_prompt(story_id="HOOKS-001", tokens=140_000,
      threshold=120_000, overrun_pct=0.10)` matches
      `fixtures/context_budget_prompt.txt` byte-for-byte except for
      placeholder substitutions.
  14. End-to-end `decide()` on tempdir with synthetic state.json +
      effort.db + transcript JSONL → returns expected dict.
  15. `decide()` with `acknowledged_at` within margin → returns None.
  16. `decide()` malformed state.json → returns None (degrade safely).
- **Tests `tests/pairmode/test_refresh_effort_baseline.py`** (new
  file):
  1. Run CLI against a single tempdir effort.db with 10 builder
     attempts → output JSON has `by_role["builder"]["n"] == 10` and
     median equals statistics.median of the input values.
  2. Run CLI against two tempdir effort.dbs → aggregate `n` is the
     sum; median is computed across the union.
  3. Run CLI against a missing path → that path is silently skipped;
     the run succeeds.
  4. Run CLI twice with the same input → byte-identical output
     (sorted source_projects, deterministic field order).
- **No changes to `hooks/stop.py`, `hooks/post_tool_use.py`,
  `hooks/hooks.json`, `hooks/exit_plan_mode.py`,
  `hooks/session_start.py`, `hooks/session_end.py`.** This story is
  module + bootstrap only.
- **No changes to `context_budget_check.py`, `record_attempt.py`,
  `effort.db` schema, `sync.py`, `audit.py`.**

#### Out of scope

- The PreToolUse hook that calls `decide()`. That is INFRA-128.
- The CLAUDE.build.md.j2 prose change, the CLAUDE.md HOOK PERFORMANCE
  carve-out, the architecture.md step 9 update. All INFRA-129.
- Backfilling new state.json fields into existing downstream projects.
  Absent fields fall back to code-level defaults from this module;
  the runbook documents how operators can opt-in per project.
- Showing budget state in the sidebar TUI panel. Useful, but the
  sidebar is on a deprecation path; observability moves to the thin
  TypeScript SPA later. INFRA-127's state.json fields are what that
  SPA will read.
- A scheduled-refresh path for `effort_baseline.json`. The CLI is
  operator-invoked; automation is a follow-on if the cadence becomes
  burdensome.
- Distinguishing builder-spawn from reviewer-spawn in the estimate.
  The hook fires on both via the Task matcher; we use builder median
  (the larger of the two) as the seeded default for safety.

---

### Story INFRA-128 — New thin `hooks/pre_tool_use.py` delegate + `hooks.json` `Task` wire-up

**Rail:** INFRA | **story_class:** code

#### Requires

- INFRA-127 has landed `skills/pairmode/scripts/context_budget.py`
  with the public function `decide(project_dir, transcript_path) -> dict | None`
  returning either `{"block": True, "reason": "...", "tokens": N,
  "acknowledged_at": N}` or `None`. The hook's sole job is to call
  this function and translate the return value to Claude Code's hook
  contract.
- `hooks/hooks.json` currently has no `PreToolUse` entry. The existing
  `PostToolUse` entry (lines 26-37) matches `Write|Edit|MultiEdit` and
  routes to a thin relay. PreToolUse follows the same JSON shape.
- Claude Code's PreToolUse contract: a hook that emits
  `{"decision": "block", "reason": "<text>"}` to stdout prevents the
  matched tool call from running and feeds the reason back as the
  next observation. An exit-0 with empty stdout is the pass-through.
  Hook receives `tool_name`, `tool_input`, `transcript_path`,
  `session_id`, `cwd` via stdin JSON.
- The matched tool name for orchestrator subagent spawns is `Task`.
  `CLAUDE.build.md:206` ("Spawn the `builder` subagent…") and
  `docs/architecture.md:424` (`Agent({..., subagent_type: "reviewer", ...})`)
  both route through the Claude Code Task tool. Matching `Task` only
  catches the exact between-story boundary.
- The flex local `CLAUDE.md` review check #1 (HOOK PERFORMANCE)
  presently forbids blocking logic in hooks. INFRA-129 amends it to
  carve a documented thin-delegation exception; INFRA-128 ships the
  code that the exception will name. Build order is enforced by D9.

#### Ensures

- **New file `hooks/pre_tool_use.py`** — strictly a thin delegate to
  the named pairmode skill module. Cap at 40 lines including
  docstring:
  ```python
  #!/usr/bin/env python3
  """
  PreToolUse hook — context budget enforcement (CER-027).

  Thin delegate. All decision logic lives in
  skills/pairmode/scripts/context_budget.py. This script:
    1. Parses stdin
    2. Skips if tool_name != "Task"
    3. Delegates to context_budget.decide(cwd, transcript_path)
    4. Emits the module's return value as a Claude Code hook response
  No logic beyond delegation. See CLAUDE.md HOOK PERFORMANCE check #1
  for the documented exception.
  """
  import json
  import sys
  from pathlib import Path

  # Add the plugin's pairmode scripts to the import path
  PLUGIN_ROOT = Path(__file__).resolve().parent.parent
  sys.path.insert(0, str(PLUGIN_ROOT / "skills" / "pairmode" / "scripts"))

  def main():
      try:
          data = json.load(sys.stdin)
      except Exception:
          sys.exit(0)
      if data.get("tool_name") != "Task":
          sys.exit(0)

      try:
          import context_budget
          result = context_budget.decide(
              project_dir=Path(data.get("cwd") or "."),
              transcript_path=data.get("transcript_path") or "",
          )
      except Exception:
          sys.exit(0)

      if result and result.get("block"):
          # context_budget.decide() has already written acknowledged_at
          # to state.json; we just emit the block decision.
          print(json.dumps({
              "decision": "block",
              "reason": result["reason"],
          }))
      sys.exit(0)

  if __name__ == "__main__":
      main()
  ```
  Line budget cap: ≤ 40 lines including docstring. Any logic added
  in the hook beyond stdin parse / tool-name check / delegate / emit
  signals the carve-out has been violated.
- **`hooks/hooks.json` gains a `PreToolUse` entry** identical in
  shape to the existing `PostToolUse` entry: matcher `"Task"`,
  command `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/pre_tool_use.py`,
  timeout 5. No change to any other hook entry.
- **Note on acknowledged_at write location.** The state.json write
  that records `context_budget_acknowledged_at` lives inside
  `context_budget.decide()` (INFRA-127), NOT inside the hook. The
  hook is a pure delegate. This keeps the carve-out exception narrow:
  the hook does *not* write to state.json itself.
- **Tests `tests/pairmode/test_pre_tool_use_hook.py`** (new file):
  1. `tool_name != "Task"` → exit 0, empty stdout. (Run via
     `subprocess.run` with stdin JSON; check returncode + stdout.)
  2. `tool_name == "Task"` + `context_budget.decide` returns None →
     exit 0, empty stdout.
  3. `tool_name == "Task"` + `decide` returns block payload → stdout
     is JSON with `decision == "block"` and `reason` equals the
     `reason` field of `decide`'s return, returncode 0.
  4. `context_budget` import failure (simulated by monkeypatching
     sys.path) → exit 0, empty stdout (degrade safely; do not
     prevent tool use because the module has a bug).
  5. `decide` raises → exit 0, empty stdout (same degrade rationale).
  6. Run the hook 1000 times against a tempdir where `decide` returns
     None in a tight loop; total wall time under 5 seconds.
     This is the thin-delegate assertion in code.
- **No changes to `hooks/stop.py`, `hooks/post_tool_use.py`,
  `hooks/exit_plan_mode.py`, `hooks/session_start.py`,
  `hooks/session_end.py`.** Existing hooks are untouched.
- **No changes to the sidebar.** INFRA-128 is hook + wire-up only.

#### Out of scope

- Matching tools other than `Task`. The architecture deliberately
  scopes enforcement to the subagent-spawn boundary; expanding to
  other tools is a follow-on if evidence accumulates that the prompt
  arrives too late.
- Implementing decision logic inside the hook. By design, the hook
  is the dumbest possible delegate. All token math, threshold
  comparison, and state mutation live in `context_budget.py`.
- Handling the "Clear and resume" path. That's a user-initiated
  `/clear`; the fresh session has a fresh transcript and the next
  Task call passes through naturally.
- Auto-clear. Out of scope per D10; recorded as a follow-on CER on
  ship.
- Logging hook fires. Stop/post-tool hooks don't log; pre-tool
  follows suit. If observability is ever needed, the SPA reads
  state.json fields written by `decide()`.

---

### Story INFRA-129 — Replace `CLAUDE.build.md.j2` § "Context budget check" prose; amend flex `CLAUDE.md` HOOK PERFORMANCE carve-out; update `docs/architecture.md` step 9

**Rail:** INFRA | **story_class:** code

This story bundles three doc-only changes. They share a single
acceptance condition: every doc that describes the context-budget
check now describes the mechanical enforcement, and the hook-thinness
carve-out is documented where the reviewer will read it. Combining
them avoids three small stories whose only differences are file paths.

#### Requires

- `skills/pairmode/templates/CLAUDE.build.md.j2:453-498` currently
  carries a four-step LLM ritual instructing the orchestrator to run
  `/context` between stories, compare against
  `state["context_budget_threshold"]`, and surface a verbatim prompt.
  Operator observation (CER-027) confirms the ritual is reliably
  skipped.
- After INFRA-127 + INFRA-128 ship, the same prompt fires
  mechanically via the PreToolUse hook on every Task spawn. The LLM
  no longer needs to remember to run `/context`; the hook injects the
  prompt as a block reason when the projected next-step total
  exceeds `threshold * (1 + overrun_pct)`.
- The verbatim CONTEXT BUDGET prompt body (the 11-line block from
  `CONTEXT BUDGET — [story RAIL-NNN] just completed.` through
  `Say: "Continue building Phase X from story RAIL-NNN"`) lives in
  `tests/pairmode/fixtures/context_budget_prompt.txt` after INFRA-127
  ships. The template should reference the fixture as the canonical
  prompt source, not duplicate it.
- The flex local `CLAUDE.build.md:473-498` is a hand-maintained copy;
  it is NOT regenerated by sync (flex does not bootstrap itself).
  Same substitution applies to that file.
- `/mnt/work/flex/CLAUDE.md` review checklist item #1 (HOOK
  PERFORMANCE) currently reads:
  ```
  1. HOOK PERFORMANCE
     Do any hook scripts in `hooks/` make API calls, spawn subprocesses that block,
     or take more than a few milliseconds to exit?
     Hooks are thin relays only. Any blocking logic in a hook is CRITICAL.
  ```
  INFRA-128 ships `hooks/pre_tool_use.py` which emits
  `{"decision": "block", ...}` when `context_budget.decide()` returns
  a block payload. Without an explicit carve-out, every future
  reviewer run would flag this as CRITICAL.
- `docs/architecture.md:158-160` (step 9 of the build loop) currently
  describes the LLM-attention check:
  ```
  9. **Context budget check** — after every story, the orchestrator compares its current Claude
     Code `/context` token count against `state["context_budget_threshold"]` (default 120 000).
     When at or above threshold, it surfaces a proceed-vs-clear prompt before the next story.
  ```
  Same rewrite-needed.
- Working principles 1 ("a rule earns its lines only if removing it
  would change agent behavior") and 8 ("one source of truth per
  fact") both bind: the old prose earns no lines once the mechanism
  is in place; the fixture file becomes the one source of truth for
  the prompt body.

#### Ensures

- **`skills/pairmode/templates/CLAUDE.build.md.j2`** — replace lines
  453-498 with:
  ```markdown
  ## Context budget check (between stories)

  Enforced mechanically by `hooks/pre_tool_use.py` (matcher `Task`),
  which delegates to `skills/pairmode/scripts/context_budget.py`.
  On every subagent spawn, the hook checks whether the projected
  next-step total would exceed
  `state["context_budget_threshold"] * (1 + state["context_budget_overrun_pct"])`
  (defaults: 120 000 × 1.10 = 132 000). When it would, the spawn is
  blocked and the verbatim prompt below is fed back as the block
  reason. The orchestrator surfaces it to the user **verbatim** — no
  commentary, no recommendation — and waits for a response.

  Canonical prompt body (source of truth:
  `tests/pairmode/fixtures/context_budget_prompt.txt`, reproduced
  here for in-doc readability):

  ```
  CONTEXT BUDGET — [story RAIL-NNN] just completed.
  Context is at approximately [N] tokens (threshold: [T], overrun: [O]).

  Continuing risks context compaction mid-story. Options:

  1. **Proceed** — continue building in this session; budget acknowledged.
     Say: "Continue building"

  2. **Clear and resume** — run /clear, then in the fresh session:
     Say: "Continue building Phase X from story RAIL-NNN"
  ```

  Response handling:
  - "Continue building" → `context_budget.decide()` has already
    written `state["context_budget_acknowledged_at"]`. Re-prompt is
    suppressed until tokens cross
    `acknowledged_at + state["context_budget_reprompt_margin"]`
    (default 10 000).
  - "Clear and resume" → user types `/clear`; the fresh session
    starts with empty transcript and the hook passes through.

  Tunables (all in `.companion/state.json`):
  `context_budget_threshold`, `context_budget_overrun_pct`,
  `expected_step_tokens` (seeded prior; replaced by the per-phase
  effort.db median once ≥5 attempts accumulate),
  `context_budget_reprompt_margin`.
  ```
  Total length target: 40-45 lines (was 46), with the prompt body
  preserved verbatim. Format the `[O]` placeholder as a percent (e.g.
  `10%`) at render time.
- **`/mnt/work/flex/CLAUDE.build.md`** — same substitution applied to
  the rendered flex local copy (currently lines 473-518). flex's own
  build loop must run the new mechanism, not the old ritual.
- **`/mnt/work/flex/CLAUDE.md` HOOK PERFORMANCE check** is rewritten
  to:
  ```
  1. HOOK PERFORMANCE
     Do any hook scripts in `hooks/` make API calls, spawn subprocesses that block,
     or take more than a few milliseconds to exit?
     Hooks are thin relays only. Any blocking logic in a hook is CRITICAL.

     **Documented thin-delegation exception:** `hooks/pre_tool_use.py`
     is the canonical thin delegate (CER-027 enforcement). It is
     allowed: one stdin parse, one `tool_name == "Task"` check, one
     delegated call into `skills/pairmode/scripts/context_budget.py`,
     and one stdout emit of the module's return value. All domain
     logic — transcript read, effort.db query, threshold math, state
     mutation — lives in the named module, NOT in the hook.

     Any *additional* logic added inside `pre_tool_use.py` beyond
     stdin-parse + tool-name-check + delegate + emit remains CRITICAL.
     Any *other* hook that emits a decision-block response remains
     CRITICAL.
  ```
- **`docs/architecture.md` step 9** is rewritten to:
  ```
  9. **Context budget check** — `hooks/pre_tool_use.py` fires on every
     Task spawn and delegates to
     `skills/pairmode/scripts/context_budget.py`. The module reads the
     transcript's last assistant `usage` block, estimates the next
     step's tokens (median of recent effort.db attempts for the
     current phase, or `state["expected_step_tokens"]` as a seeded
     fallback), and blocks the spawn when the projected total would
     exceed `threshold * (1 + overrun_pct)`. The block reason carries
     a verbatim prompt; the operator picks Proceed (acknowledged) or
     `/clear` and resume. CER-027 documents the failure mode this
     replaces.
  ```
- **Fixture file `tests/pairmode/fixtures/context_budget_prompt.txt`**
  is updated by INFRA-127 (since both stories share it). INFRA-129
  ensures the template's prompt body and the fixture stay
  byte-identical:
- **`tests/pairmode/test_template_render.py`** (the file introduced
  by INFRA-124 — append, do not create twice) gains four new tests:
  1. Render `CLAUDE.build.md.j2` against an empty context and assert
     the rendered text contains `Enforced mechanically`, the paths
     `hooks/pre_tool_use.py` AND
     `skills/pairmode/scripts/context_budget.py`, and the field
     names `context_budget_threshold`, `context_budget_overrun_pct`,
     `expected_step_tokens`, `context_budget_reprompt_margin`. (The
     new pointer must name the hook, the module, and every tunable.)
  2. Render the same template and assert the rendered text does NOT
     contain any of the old ritual phrases:
     `Read \`context_budget_threshold\` from`,
     `Compare your current context window`,
     `Your context token count is visible`.
  3. Extract the prompt-body block from the rendered template
     (between the two ` ``` ` fences) and assert it equals the
     contents of `tests/pairmode/fixtures/context_budget_prompt.txt`
     byte-for-byte. (Drift fail-fast.)
  4. Read `/mnt/work/flex/CLAUDE.md` HOOK PERFORMANCE section and
     assert it contains `Documented thin-delegation exception:`,
     `hooks/pre_tool_use.py`,
     `skills/pairmode/scripts/context_budget.py`, and
     `remains CRITICAL`.
- **`docs/architecture.md` test.** A new tiny test reads
  architecture.md, finds step 9, and asserts it contains
  `hooks/pre_tool_use.py` and `skills/pairmode/scripts/context_budget.py`.
  Append to `test_template_render.py` since the file is already
  the "doc consistency" home; rename the file later if it grows.
- **No changes to** `CLAUDE.md.j2` (canonical for downstream — never
  carried HOOK PERFORMANCE), `agents/reviewer.md.j2`, `bootstrap.py`
  (its INFRA-127 changes are independent), `sync.py`,
  `record_attempt.py`, `context_budget_check.py`, `effort.db` schema.

#### Out of scope

- Re-rendering downstream projects' `CLAUDE.build.md`. Covered by the
  CER-027 sub-track runbook below.
- Removing `context_budget_check.py` or its phase-spend semantics.
  Still earns its lines as a separate phase-cost signal.
- Renaming `context_budget_threshold`. Existing field continues to
  do double duty (phase-spend CLI + orchestrator-window check); the
  operator sets one number and both honor it.
- Promoting the HOOK PERFORMANCE check (or its exception) into the
  canonical template. T3's settled decision is "INTERNAL REVIEWER
  ADDENDUM" — flex-only.
- Listing every other hook in the exception note. Only the named
  exception case is documented; all other hooks remain governed by
  the unmodified thin-relay rule.
- Auto-clear. Recorded as a follow-on CER on ship (D10).

---

## Downstream propagation runbook (T4)

Operator-executed after INFRA-126 is merged. One pass handles both the
pointer fix and the radar/cora missing-DOC-CURRENCY backfill.

1. **Re-sync every downstream project** so `CLAUDE.md` picks up the corrected
   reference path *and* (for radar and cora) gains the missing DOC CURRENCY
   item:
   ```bash
   for p in forqsite radar asp aab cora; do
     uv run python skills/pairmode/scripts/pairmode_sync.py update \
       --project-dir /mnt/work/$p
   done
   ```

2. **Verify** in each project:
   ```bash
   grep -c "DOCUMENTATION CURRENCY" CLAUDE.md   # expect 1
   grep ".claude/agents/reviewer.md" CLAUDE.md  # expect the pointer line
   ! grep -E " agents/reviewer\.md" CLAUDE.md   # bare path should NOT match
   ```
   (Note: `! grep` will fail the shell command if the bare path is found —
   that's the intent; flip to a positive grep if scripting.)

3. **Spot-check radar and cora's checklist position.** DOC CURRENCY should
   land at item #4 in radar and cora (the canonical position), since
   neither carries project-specific extensions ahead of the canonical
   items. If sync places it later, inspect the rendered output before
   committing.

---

## Downstream propagation runbook (T3)

Operator-executed after INFRA-125 is merged. These steps update existing
downstream projects to the corrected boilerplate.

1. **Re-render `.pairmode-overrides` in each downstream project that
   currently ships the broken boilerplate** (radar, asp, aab — verify before
   acting):
   ```bash
   for p in radar asp aab; do
     test -f /mnt/work/$p/.pairmode-overrides || continue
     # Only re-render if the file currently has no real (non-comment, non-blank) entries.
     if ! grep -v '^#' /mnt/work/$p/.pairmode-overrides | grep -q '\S'; then
       uv run python skills/pairmode/scripts/pairmode_sync.py update \
         --project-dir /mnt/work/$p
     else
       echo "$p has real entries — convert by hand: prepend '## ' to each section key"
     fi
   done
   ```
   aab has real override entries (5 lines under CLAUDE.build.md, none under
   CLAUDE.md); inspect manually and rewrite the keys to include the
   correct `##`/`###` markers.

2. **Leave forqsite alone.** Its `.pairmode-overrides` is already correct
   and includes additional project-specific extension content the canonical
   doesn't carry.

3. **Optionally scaffold for cora.** cora has no `.pairmode-overrides` file.
   If cora has any project-owned section divergences (none currently known),
   run `pairmode sync` against cora to scaffold the file.

4. **Verify.** In each touched project:
   ```bash
   head -20 .pairmode-overrides | grep -E "## review checklist|markers"
   ```
   should show the corrected example and the markers-included note.

---

## Downstream propagation runbook (T8)

Operator-executed after INFRA-124 and BOOTSTRAP-003 are merged. These steps
are *not* a story — they happen across five different repositories that
flex's builder/reviewer loop doesn't touch.

1. **Fix AAB's `test_command` value.**
   Edit `/mnt/work/aab/.companion/pairmode_context.json` — set
   `test_command` to a Node value appropriate for the AAB project (likely
   `pnpm test`, but operator confirms by checking `package.json`).

2. **Re-render `CLAUDE.md` in every downstream project** so the Story test
   verification block picks up the corrected variable. From flex's repo:
   ```bash
   for p in forqsite radar asp aab cora; do
     uv run python skills/pairmode/scripts/pairmode_sync.py update \
       --project-dir /mnt/work/$p
   done
   ```
   Expect each project's `CLAUDE.md` Story test verification block to now
   contain that project's actual `test_command`.

3. **Manually delete duplicated `## session modes` blocks.**
   Sync renders the canonical position; the duplicate sits below the
   canonical section and looks like manual content to sync. Operator
   deletes by hand:
   - `forqsite/CLAUDE.md`: the second `## session modes` block (around
     line 178 — the first occurrence at line 5 is canonical and stays).
   - `radar/CLAUDE.md`: the second `## session modes` block (around
     line 121 — the first occurrence at line 5 stays).

4. **Verify.** In each downstream project:
   ```bash
   grep -c "^## session modes" CLAUDE.md  # expect 1
   grep "tail -30" CLAUDE.md              # expect the project's real test_command
   ```
   And run `audit.py` against each project to confirm no DRIFT findings on
   CLAUDE.md.

5. **Commit downstream changes** with a short message referencing
   `flex/docs/phases/phase-47.md § T8`.

---

## Downstream propagation runbook (CER-027 sub-track)

Operator-executed after INFRA-127, INFRA-128, and INFRA-129 are all
merged. These steps push the mechanical enforcement out to every
downstream project that pairmode-bootstrapped before the sub-track
shipped.

The hook + module propagate automatically — `hooks/` and `skills/`
are flex plugin directories shared by every project running the flex
plugin, not duplicated per-project. The per-project work is template
re-render + optional state.json field opt-in + seed file refresh.

1. **(Optional) Refresh `effort_baseline.json` before propagation.**
   The seed file shipped by INFRA-127 was generated from the
   2026-05-29 snapshot of effort.db data. If significant build
   activity has occurred since, regenerate:
   ```bash
   uv run python skills/pairmode/scripts/refresh_effort_baseline.py \
       --project-dirs /mnt/work/forqsite /mnt/work/radar \
                      /mnt/work/asp /mnt/work/aab /mnt/work/cora \
                      /mnt/work/anchor /mnt/work/pokus \
       --output skills/pairmode/seed/effort_baseline.json
   ```
   Commit the regenerated file if values changed materially.

2. **Re-sync every downstream project so `CLAUDE.build.md` picks up
   the new mechanical-enforcement pointer** (replaces the dead
   four-step ritual):
   ```bash
   for p in forqsite radar asp aab cora; do
     uv run python skills/pairmode/scripts/pairmode_sync.py update \
       --project-dir /mnt/work/$p
   done
   ```
   This sync run also propagates INFRA-124's `{{ test_command }}`
   variable fix and INFRA-126's DOC CURRENCY pointer fix (if they
   have landed by this point). One sync pass, three fixes.

3. **Verify the new pointer is present** in each project's
   `CLAUDE.build.md`:
   ```bash
   for p in forqsite radar asp aab cora; do
     echo "== $p =="
     grep "Enforced mechanically" /mnt/work/$p/CLAUDE.build.md | head -1
     grep -c "hooks/pre_tool_use.py" /mnt/work/$p/CLAUDE.build.md
     # expect 1+
     grep -c "Read \`context_budget_threshold\` from" /mnt/work/$p/CLAUDE.build.md
     # expect 0 — old ritual gone
   done
   ```

4. **Inspect tunable fields in each project's state.json.** New
   fields (`context_budget_overrun_pct`, `expected_step_tokens`,
   `context_budget_reprompt_margin`) are absent on existing projects
   and code-level defaults apply. Operators who want per-project
   overrides edit the file directly:
   ```bash
   for p in forqsite radar asp aab cora; do
     echo "== $p =="
     test -f /mnt/work/$p/.companion/state.json && \
       python3 -c "
   import json
   s = json.load(open('/mnt/work/$p/.companion/state.json'))
   print(f'  threshold:        {s.get(\"context_budget_threshold\", \"unset (default 120000)\")}')
   print(f'  overrun_pct:      {s.get(\"context_budget_overrun_pct\", \"unset (default 0.10)\")}')
   print(f'  expected_step:    {s.get(\"expected_step_tokens\", \"unset (default 53000)\")}')
   print(f'  reprompt_margin:  {s.get(\"context_budget_reprompt_margin\", \"unset (default 10000)\")}')
   print(f'  ack_at:           {s.get(\"context_budget_acknowledged_at\", \"unset\")}')
   "
   done
   ```
   Common operator adjustments: raise `context_budget_threshold` to
   140 000 on a project with mostly small stories; lower
   `expected_step_tokens` to 30 000 once the project has its own
   effort.db median; widen `overrun_pct` to 0.15 on a 1M-context
   model when the platform allows.

5. **Confirm the plugin's `hooks/hooks.json` is the version with the
   PreToolUse entry.** In a downstream project session, after
   pulling the latest flex plugin:
   ```bash
   grep -c "pre_tool_use.py" $CLAUDE_PLUGIN_ROOT/hooks/hooks.json
   # expect 1
   ```
   If 0, the project is running an older plugin checkout; update.

6. **End-to-end smoke test per project.** Start a session, force
   context past threshold (e.g., dump a large file via Read), then
   try to spawn a builder. The CONTEXT BUDGET prompt should appear
   as a block reason without the operator typing `/context`. This
   is the load-bearing acceptance check.

7. **No downstream commits required for the mechanism itself.** All
   five projects share the flex plugin via the same hook + skill
   directory; the template re-render in step 2 is the only
   per-project file change. Downstream commit only if the re-render
   produced project-specific diffs worth recording.
