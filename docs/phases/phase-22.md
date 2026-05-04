# anchor — Phase 22: Per-story compute-effort tracking

← [Phase 21: Methodology refinement and companion/pairmode positioning](phase-21.md)
→ [Phase 23: Drift detection and promotion workflow](phase-23.md)

## Goal

Phase 22 introduces per-story compute-effort tracking so that model selection,
spec quality, and rework patterns become visible. The unit of measurement is
**tokens**, not dollars. Tokens are the unit of compute effort; dollars are an
ephemeral projection of tokens through whatever pricing snapshot is current.
Anchor stores tokens permanently and treats pricing as optional report-time
decoration. The user can drop a `pricing.json` next to the database for a dollar
projection, but anchor doesn't ship rates, maintain rates, or promise rates.

The phase covers three layers: a sqlite recorder (INFRA-028), a reporting CLI
(INFRA-029), and orchestrator wiring (INFRA-030). It then extends the recorder
to companion and seed (INFRA-035) so the cost picture isn't artificially
narrow, and lands a real-time guardrail (INFRA-034) so a story that's running
3× the median tokens for its rail pauses for user review rather than burning
through quietly.

**Why tokens, not dollars (recap):** the data layer stays correct forever even
as model rates change; the pricing-maintenance burden collapses to zero;
optimisation targets compute effort directly rather than a market-determined
projection.

**Why the recording cost is negligible:** the `<usage>` block already exists in
every agent response. Capturing it is parsing text the user already paid for.
A single sqlite INSERT is ~10ms with no LLM call. A single avoided rework
(10k–100k tokens) pays for thousands of inserts. The economics aren't close.

Prerequisites: Phase 21 complete and tagged cp21-template-methodology.

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-028 | Effort tracking — sqlite schema and `record_attempt.py` recorder | planned |
| INFRA-029 | Effort tracking — `pairmode_effort.py` reporting CLI | planned |
| INFRA-030 | Effort tracking — wire recording into the build loop (CLAUDE.build.md) | planned |
| INFRA-035 | Effort recording for seed and companion subagent calls | planned |
| INFRA-034 | Real-time effort guardrail in build loop | planned |

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
- Default: bootstrap auto-enables for pairmode-bootstrapped projects (since
  `.companion/pairmode_context.json` is present), opt-out for plain anchor
  projects. The `.companion/state.json["effort_tracking"]` flag controls
  recording at runtime.
- Capture mechanism: the orchestrator parses the `<usage>` block returned by
  every Agent tool call (`total_tokens`, `tool_uses`, `duration_ms`) and
  invokes `record_attempt.py` after each spawn. Token-level breakdown
  (input vs output vs cache) is captured when surfaced by Claude Code; left
  NULL when not available.

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
  agent_role TEXT NOT NULL,         -- "builder" | "reviewer" | "intent-reviewer" |
                                    -- "security-auditor" | "loop-breaker" |
                                    -- "seed-miner" | "seed-reconcile" |
                                    -- "sidebar-extractor" (see INFRA-035)
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

### Story INFRA-035 — Effort recording for seed and companion subagent calls

**Rail:** INFRA

**Acceptance criterion:** Effort tracking captures invocations made by
`skills/seed/` (during initial spec mining and reconcile) and by
`skills/companion/scripts/sidebar.py` (per pipe message that triggers an
LLM call). New `agent_role` values (`seed-miner`, `seed-reconcile`,
`sidebar-extractor`) are recorded alongside pairmode loop entries. A user
running `pairmode_effort.py rollup` after a seed + bootstrap + build sees
all three skills' compute effort, not just pairmode's.

**Background (CER finding):** without this story, a project enabling effort
tracking sees only pairmode loop costs. The companion sidebar makes API
calls per pipe message — every `stop` hook, every `post_tool_use`, every
plan-mode exit. Seed mines sessions and reconciles, both LLM-heavy. None of
that surfaces in the cost picture today, so a user concludes the data is
complete when it's missing the most expensive layer.

**Instructions:**

1. Add wrapper invocations of `record_attempt.py` to:
   - `skills/seed/scripts/mine_sessions.py`: after each session-mining LLM
     call, record an `agent_role: seed-miner` row with `story_id` set to the
     synthetic value `"seed:<session-id>"`.
   - `skills/seed/scripts/reconcile.py`: after each reconcile LLM call,
     record an `agent_role: seed-reconcile` row with `story_id: "seed:reconcile"`.
   - `skills/companion/scripts/sidebar.py`: after each pipe-message-triggered
     LLM extraction, record an `agent_role: sidebar-extractor` row. The
     `story_id` field is the active `current_story` from state.json (or
     `"sidebar:no-story"` when no story is active).

2. The `attempts` schema already supports these via the open-ended
   `agent_role` field — no migration needed.

3. **Cross-skill leverage to flag in architecture.md:** the
   `disable-model-invocation: true` flag on companion and seed (per their
   SKILL.md) means the orchestrator can't tool-call into them. INFRA-035's
   wrapper invocations therefore live *inside* those skills' Python code,
   not in the orchestrator. Document this constraint clearly.

4. Bootstrap (`bootstrap.py`): when `effort_tracking: true` and companion or
   seed scripts are present, ensure the wrappers are active (no-op if
   missing — the scripts handle their own conditional).

**Tests:** `tests/pairmode/test_record_attempt_seed.py` and
`test_record_attempt_companion.py` — fixture invocations of each skill's
recording path, assert the row lands with the correct `agent_role` and a
plausible `story_id`.

---

### Story INFRA-034 — Real-time effort guardrail in build loop

**Rail:** INFRA

**Acceptance criterion:** After each builder attempt, the orchestrator queries
the effort database for the median tokens-per-attempt for the current rail and
compares against the just-completed attempt's tokens. If the attempt exceeds
N× the median (default 3.0, configurable via
`state["effort_guardrail_multiplier"]`), the orchestrator pauses and surfaces
a structured prompt to the user before spawning the reviewer.

**Background (CER finding):** today an out-of-control story burns tokens
quietly until a phase ends and we run a retrospective `pairmode_effort.py
rework` query. A real-time guardrail catches the runaway *while it's
happening*, when intervention is cheap. The query is one line of SQL given
INFRA-028's schema; the guardrail is a four-line addition to the build loop.

**Instructions:**

1. In `CLAUDE.build.md`, after the builder-record step from INFRA-030, add a
   guardrail step:
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python -c "
   import sys
   sys.path.insert(0, 'skills/pairmode/scripts')
   from effort_db import check_guardrail
   check_guardrail(story_id='<id>', rail='<rail>', latest_tokens=<n>)
   "
   ```
2. Implement `effort_db.check_guardrail()`:
   - Query: median tokens for `agent_role='builder'` AND `rail=<rail>` AND
     `outcome='PASS'`, last 30 days.
   - If sample < 3 (insufficient data), return early — no guardrail fires
     until baseline exists.
   - If `latest_tokens > multiplier × median`, print a multi-line warning
     to stderr including the rail's median, the multiplier, the actual
     tokens, and a suggestion: "Consider pausing to review the spec, the
     builder's output, or both, before spawning the reviewer."
   - Exit code 0 always — the guardrail is informational; the orchestrator
     decides whether to pause based on the warning text.
3. Document the guardrail in `docs/architecture.md` as a Phase 22 capability
   that activates automatically once enough history accumulates.

**Why not block automatically?** The first time a new rail is added, every
attempt looks like an outlier. A blocking guardrail produces false positives
that erode trust. An informational guardrail surfaces the signal and lets
the orchestrator (with full context) decide. If informational proves too
weak, a future story can promote to blocking with a `--strict` flag.

**Tests:** `tests/pairmode/test_effort_guardrail.py` — fixture DB with
seeded attempts at varying token counts, assert the guardrail fires above
threshold and stays silent below. Test the insufficient-sample case.

---

Tag: `cp22-effort-tracking`
