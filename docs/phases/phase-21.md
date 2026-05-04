# anchor — Phase 21: Methodology refinement and cost visibility

← [Phase 20: PR readiness — documentation, pipe clarity, contribution packaging](phase-20.md)
→ [Phase 22: Project drift detection and promotion workflow](phase-22.md)

## Goal

Phase 21 reflects two classes of methodology improvement that surfaced during cross-project
dogfooding (cora, radar, forqsite) into the canonical pairmode templates so future bootstraps
inherit them, and opens a new methodology surface: per-story compute-effort tracking measured
in tokens. The intent is to land fast and concrete improvements first, while the more
speculative drift-detection work moves to Phase 22 where it can benefit from the effort data
this phase starts collecting.

**Why tokens, not dollars:** tokens are the unit of compute effort. Dollars are an ephemeral
projection of tokens through whatever pricing snapshot is current. We store tokens permanently
and treat pricing as optional report-time decoration — the user can drop a `pricing.json` next
to the database for a dollar projection if they want one, but anchor doesn't ship rates,
maintain rates, or promise rates. This decision collapses pricing-maintenance burden to zero
and keeps the data layer correct forever even as model rates change.

Prerequisites: Phase 20 complete and tagged cp20-pr-ready (pr-candidate-v0.1-squashed).
Branched from era2 onto `era3-methodology` so this work does not compound the
already-submitted PR (nraychaudhuri/anchor#3).

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-026 | Pin reviewer agents to `model: opus` in pairmode templates | planned |
| INFRA-027 | Default reviewer agents to read-only tools `[Read, Grep, Glob, Bash]` | planned |
| LESSON-002 | Capture model upgrade/downgrade pattern as a lesson | planned |
| LESSON-003 | Capture reviewer-as-read-only-Bash pattern as a lesson | planned |
| INFRA-028 | Effort tracking — sqlite schema and `record_attempt.py` recorder | planned |
| INFRA-029 | Effort tracking — `pairmode_effort.py` reporting CLI | planned |
| INFRA-030 | Effort tracking — wire recording into the build loop (CLAUDE.build.md) | planned |

Project drift detection and promotion (originally drafted as INFRA-031 and INFRA-032) moved to
[Phase 22](phase-22.md) so this phase ships the cost-tracking foundation first.

---

### Story INFRA-026 — Pin reviewer agents to `model: opus` in pairmode templates

**Rail:** INFRA

**Acceptance criterion:** All four reviewer-class agent templates carry an explicit
`model: opus` field. Builder remains pinned to `sonnet`. A bootstrap into a fresh
project produces agent files matching the cora/radar/forqsite convergence pattern.

**Background:** Cross-project audit (cora, radar, forqsite as of 2026-05-04) shows
all three converge on builder=sonnet, reviewer/intent-reviewer/loop-breaker/
security-auditor=opus. Pairmode templates currently only pin builder; reviewers
inherit the orchestrator's model. If the orchestrator runs sonnet, the entire
quality gate runs sonnet, losing the upgrade benefit.

**Instructions:**

In each of the following four templates, add `model: opus` to the YAML frontmatter
immediately after the `description:` line:

- `skills/pairmode/templates/agents/reviewer.md.j2`
- `skills/pairmode/templates/agents/intent-reviewer.md.j2`
- `skills/pairmode/templates/agents/loop-breaker.md.j2`
- `skills/pairmode/templates/agents/security-auditor.md.j2`

Do not modify `builder.md.j2` (already correct at `model: sonnet`) or
`reconstruction-agent.md.j2` (a different role, evaluate separately).

**Tests:** Extend `tests/pairmode/test_templates.py` (or create) with assertions:
- Each of the four reviewer templates contains `model: opus`
- `builder.md.j2` contains `model: sonnet`
- A render of each template still produces valid YAML frontmatter

---

### Story INFRA-027 — Default reviewer agents to read-only tools `[Read, Grep, Glob, Bash]`

**Rail:** INFRA

**Acceptance criterion:** All four reviewer-class agent templates restrict tools
to `[Read, Grep, Glob, Bash]` (security-auditor: `[Read, Grep, Glob]` — no Bash
since it never runs commands). Reviewer cleanup and revert paths are verified
to still work via Bash. A doc note in `docs/architecture.md` records the
two-layer rationale (read-only tools + pre-reviewer commit discipline).

**Background:** Forqsite (only) restricts reviewer tools. The pattern hasn't
propagated, but the rationale is sound: removing Edit/Write prevents the
reviewer from "fixing" code instead of reverting (a real failure mode), while
preserving Bash keeps git revert/checkout/commit available so the
commit-or-revert contract is unaffected.

**Verification step (must run before commit):**

1. Confirm reviewer's commit path uses Bash only (`git add`, `git commit`).
2. Confirm reviewer's revert path uses Bash only (`git checkout -- <path>`,
   `git reset --hard HEAD`).
3. Confirm reviewer's test invocation uses Bash only.
4. Grep all reviewer.md/.j2 prose for any instruction that requires Edit or
   Write. If any: rewrite to use Bash equivalents or surface to the user.

**Instructions:**

Add or update the `tools:` field in the YAML frontmatter:

- `skills/pairmode/templates/agents/reviewer.md.j2` → `tools: [Read, Grep, Glob, Bash]`
- `skills/pairmode/templates/agents/intent-reviewer.md.j2` → `tools: [Read, Grep, Glob, Bash]`
- `skills/pairmode/templates/agents/loop-breaker.md.j2` → `tools: [Read, Grep, Glob, Bash]`
- `skills/pairmode/templates/agents/security-auditor.md.j2` → `tools: [Read, Grep, Glob]`

Do not modify `builder.md.j2` (needs full write tools) or
`reconstruction-agent.md.j2` (evaluate separately).

In `docs/architecture.md`, in the section that describes the build loop, add a
short note: "Reviewer-class agents are restricted to read-only tools plus Bash.
This is one of two layers protecting the working tree: tool restriction prevents
the reviewer from backdooring a fix into the code instead of reverting it; the
orchestrator's pre-reviewer commit discipline (committing story files and
running `git checkout -- lessons/` before the reviewer fires) prevents
accidental erasure of uncommitted methodology files."

**Tests:** Same `test_templates.py` extended with tools-field assertions.

---

### Story LESSON-002 — Capture model upgrade/downgrade pattern as a lesson

**Rail:** LESSON

**Acceptance criterion:** A new lesson entry in `lessons/lessons.json` documents
the model-selection methodology with a concrete trigger, problem, learning, and
methodology change.

**Instructions:**

Append a new entry (id auto-assigned by lesson_utils):

- **trigger:** Cross-project audit (cora, radar, forqsite) of `.claude/agents/`
  configurations.
- **problem:** Pairmode templates pinned only the builder to sonnet, leaving
  reviewer-class agents to inherit the orchestrator's model. If the orchestrator
  ran on sonnet (efficiency reasons), the entire quality gate ran on sonnet,
  losing the judgment-quality benefit.
- **learning:** Model selection should be explicit per role, not inherited.
  Volume work (builder) → sonnet for compute efficiency. Judgment work
  (reviewer, intent-reviewer, loop-breaker, security-auditor) → opus for
  judgment quality. Inheritance from the orchestrator is a silent capability
  leak. Add a documented fallback policy: if the preferred model is rate-limited,
  fall back one tier (Opus → Sonnet on reviewers; Sonnet → Haiku on builder),
  never below Haiku.
- **methodology_change:** Pairmode templates pin model per agent: builder=sonnet,
  reviewers=opus. INFRA-026 implements this in templates; future bootstraps
  inherit it. Validation comes from INFRA-029's `pairmode_effort.py models`
  report — once token-and-PASS-rate data accrues per (model, role), the
  methodology is data-defensible rather than aesthetic.
- **affects:** `pairmode-builder-reviewer-loop`, applies to any pairmode project.

---

### Story LESSON-003 — Capture reviewer-as-read-only-Bash pattern as a lesson

**Rail:** LESSON

**Acceptance criterion:** A new lesson entry documents the reviewer tools
restriction methodology and its rationale.

**Instructions:**

- **trigger:** Forqsite restricted reviewer tools to `[Read, Grep, Glob, Bash]`;
  cora and radar did not. Cross-project audit surfaced the divergence.
- **problem:** Reviewers with full tool access can "fix" failing code (edit a
  test until it passes, edit production until the test passes) instead of
  reverting, hiding the real failure. Concrete example: a reviewer faced with
  a failing assertion can edit the assertion to match the (wrong) actual
  output and commit, presenting a green test that no longer tests the
  invariant. This compromises the commit-or-revert contract.
- **learning:** Reviewer-class agents should be limited to read-only tools plus
  Bash. Bash preserves the commit-or-revert capability via git; Edit/Write
  removal closes the "reviewer backdoor" failure mode. This is layered with
  the orchestrator's pre-reviewer commit discipline (which protects against
  accidental erasure of uncommitted methodology files) — neither layer alone
  is sufficient.
- **methodology_change:** Pairmode templates restrict reviewer tools.
  INFRA-027 implements this.
- **affects:** `pairmode-builder-reviewer-loop`.

---

### Story INFRA-028 — Effort tracking — sqlite schema and `record_attempt.py` recorder

**Rail:** INFRA

**Acceptance criterion:** A sqlite database at `.companion/effort.db` (path
configurable via `.companion/state.json["effort_db_path"]`) records one row per
agent invocation with story_id, phase, agent_role, model, token counts, tool_uses,
duration_ms, outcome, and timestamp. A `record_attempt.py` CLI lets the
orchestrator append a row in one command. **No pricing data is stored.**

**Design rationale:**

- Python stdlib `sqlite3` — no driver dependency.
- Single file at `.companion/effort.db` — no server, no plumbing.
- One table: `attempts` (one row per agent call). Pricing is **not** in the
  schema — see "Pricing as optional decoration" below.
- Default: opt-in. Set `.companion/state.json["effort_tracking"]: true` to
  enable. Bootstrap auto-enables for pairmode-bootstrapped projects (since
  `.companion/pairmode_context.json` is present), opt-out for plain anchor
  projects.
- Capture mechanism: the orchestrator parses the `<usage>` block returned by
  every Agent tool call (`total_tokens`, `tool_uses`, `duration_ms`) and
  invokes `record_attempt.py` after each spawn. Token-level breakdown
  (input vs output vs cache) is captured when surfaced by Claude Code; left
  NULL when not available.
- **Cost of capture is effectively zero.** The `<usage>` block already exists
  in every agent response. Recording is a single sqlite INSERT, ~10ms,
  no LLM call. A single avoided rework (10k–100k tokens) pays for thousands
  of inserts. The economics aren't close.

**Pricing as optional decoration:**

A user who wants dollar projections drops a `pricing.json` next to the database:

```json
{
  "claude-opus-4-7":   {"input": 15.00, "output": 75.00, "cache_read": 1.50, "cache_write": 18.75},
  "claude-sonnet-4-6": {"input":  3.00, "output": 15.00, "cache_read": 0.30, "cache_write":  3.75},
  "claude-haiku-4-5":  {"input":  1.00, "output":  5.00, "cache_read": 0.10, "cache_write":  1.25}
}
```

Reports project tokens × rates at query time. Anchor neither ships nor
maintains rates. Stale `pricing.json` produces stale dollar projections; the
underlying token data stays correct forever.

**Schema:**

```sql
CREATE TABLE attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  story_id TEXT NOT NULL,           -- "INFRA-014"
  phase TEXT,                        -- "20"
  rail TEXT,                         -- "INFRA"
  agent_role TEXT NOT NULL,         -- "builder" | "reviewer" | "intent-reviewer" | ...
  model TEXT,                        -- "claude-opus-4-7" | "claude-sonnet-4-6" | ...
  attempt_number INTEGER NOT NULL,  -- 1 for first try, 2 for retry, etc.
  tokens_total INTEGER,             -- always recorded when available
  tokens_in INTEGER,                 -- nullable; capture when surfaced
  tokens_out INTEGER,                -- nullable
  cache_read_tokens INTEGER,         -- nullable
  cache_write_tokens INTEGER,        -- nullable
  tool_uses INTEGER,
  duration_ms INTEGER,
  outcome TEXT,                      -- "PASS" | "FAIL" | "PARTIAL" | NULL
  notes TEXT,
  ts TEXT NOT NULL                   -- ISO-8601 UTC
);

CREATE INDEX idx_attempts_story ON attempts(story_id);
CREATE INDEX idx_attempts_phase ON attempts(phase);
CREATE INDEX idx_attempts_rail ON attempts(rail);
```

No `pricing` table. No pricing migration to maintain.

**Instructions:**

1. Create `skills/pairmode/scripts/effort_db.py` — schema initialization and
   helper functions: `init_db(path)`, `insert_attempt(...)`, `query_*`.
   Idempotent init.
2. Create `skills/pairmode/scripts/record_attempt.py` — Click CLI with flags
   for every column. Resolves DB path from `.companion/state.json` (or
   `--db-path` override). Calls `effort_db.insert_attempt(...)`. No-op if
   `effort_tracking` is not enabled in state.json.
3. Bootstrap (`bootstrap.py`): when invoked in pairmode mode, set
   `effort_tracking: true` in the generated `.companion/state.json` by
   default. Plain anchor (non-pairmode) bootstraps leave the flag unset.

**Tests:** `tests/pairmode/test_effort_db.py` — schema init, insert,
idempotent re-init, query roundtrip; `tests/pairmode/test_record_attempt.py`
— CLI happy path, no-op when tracking disabled, error on missing required
fields.

---

### Story INFRA-029 — Effort tracking — `pairmode_effort.py` reporting CLI

**Rail:** INFRA

**Acceptance criterion:** A Click CLI at
`skills/pairmode/scripts/pairmode_effort.py` produces several useful reports
from `.companion/effort.db`. **Token counts are the primary metric in every
report.** Dollar projections are an optional `--dollars <pricing.json>` flag.

Reports:

- **Total effort rollup** (`rollup [--phase N | --rail RAIL]`): tokens per
  phase, per rail, per model. Output ranks rails by total tokens to show
  where compute effort concentrates.
- **Rework patterns** (`rework [--threshold N]`): stories with attempt_number > 1.
  Output: story_id, attempts, total tokens, builder tokens, reviewer tokens,
  ranked by total tokens. Treats any high-token rework as a spec quality
  candidate.
- **Most effort-intensive stories** (`expensive [--top N]`): top N by tokens,
  with token cost split by agent role (so it's visible whether the cost was
  builder retries or reviewer iteration).
- **Sonnet vs Opus comparison** (`models`): tokens and attempts per model,
  and **outcome rate per model** (PASS rate by role/model pair). This is the
  data that validates the upgrade/downgrade methodology — if builder-on-Opus
  has a higher PASS rate and lower retry token cost than builder-on-Sonnet,
  we want to know.

**Use it for:** identify stories that were built more than once and look for
spec quality patterns. After a phase, run `pairmode_effort.py rework` and treat
any story with >1 attempt as a candidate for spec review (was the spec
ambiguous? was the scope wrong? did the reviewer catch something the spec
should have called out?).

**Instructions:** Standard Click CLI. Output is plain text columns by default
(token counts), with `--json` for machine-parseable output and
`--dollars <pricing.json>` for an optional dollar projection column.

**Tests:** `tests/pairmode/test_pairmode_effort.py` — fixture DB with seeded
attempts, run each subcommand, assert expected output. Dollar projection test
uses a fixture pricing.json — confirms the projection is multiplicative and
the absence of pricing.json doesn't break any report.

---

### Story INFRA-030 — Effort tracking — wire recording into the build loop

**Rail:** INFRA

**Acceptance criterion:** `CLAUDE.build.md` orchestrator instructions include
explicit bash steps that call `record_attempt.py` after each builder and
reviewer spawn. The recording is conditional on `state["effort_tracking"]`. A
fresh pairmode project accumulates token rows across a phase by default.

**Instructions:**

In `CLAUDE.build.md`:

- After the builder spawn (Step 1), add a recording step that captures the
  agent's `<usage>` output and invokes `record_attempt.py --story <id>
  --agent builder --model <inferred> --attempt <n> --tokens-total <n>
  --tool-uses <n> --duration-ms <n>`.
- After the reviewer spawn (Step 2), same with `--agent reviewer --outcome
  PASS|FAIL`.
- Document that the orchestrator should look for `<usage>...</usage>` in
  the agent's final message and parse out `total_tokens`, `tool_uses`,
  `duration_ms`. If absent, record what's available with NULLs.

Also: add a section in `docs/architecture.md` documenting the effort-tracking
data model, the tokens-as-primary-metric framing, and how to enable/disable
it (one-line state.json edit).

**Tests:** Documentation-only test; no runtime behaviour to assert. Verify
`record_attempt.py` is referenced in CLAUDE.build.md with the right flags.

---

(The earlier "DEVELOPER ACTION — Verify cost tracking flag default" gate was
resolved during the pre-build CER: bootstrap auto-enables effort tracking when
the project is pairmode-bootstrapped, opt-out for plain anchor projects. INFRA-028
implements this directly; no separate gate needed.)

Tag: `cp21-methodology-refinement`
