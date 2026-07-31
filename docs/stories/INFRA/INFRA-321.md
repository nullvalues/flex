---
id: INFRA-321
rail: INFRA
title: "Two-track context accounting: orchestrator-window occupancy vs story/subagent spend — the pause decision fires on the orchestrator track only"
status: complete
phase: "114"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/context_health.py
  - skills/pairmode/scripts/context_model.py
touches:
  - skills/pairmode/scripts/context_budget.py
  - skills/pairmode/scripts/context_budget_check.py
  - skills/pairmode/scripts/user_turn_seq.py
  - skills/pairmode/scripts/flex_build.py
  - skills/observability/api/src/readers/effortDb.ts
  - skills/observability/api/src/routes/context.ts
  - skills/observability/ui/src/api/client.ts
  - skills/observability/ui/src/components/ContextMetrics.tsx
  - tests/pairmode/test_context_health.py
  - tests/pairmode/test_context_budget.py
  - tests/pairmode/test_context_budget_check.py
  - tests/pairmode/test_user_turn_seq.py
  - tests/pairmode/test_flex_build.py
  - tests/pairmode/test_next_action.py
  - docs/architecture.md
  - docs/cer/backlog.md
  - docs/phases/phase-114.md
  - docs/stories/INFRA/INFRA-321.md
  - tests/pairmode/test_context_model.py
  - tests/pairmode/test_flex_build_story_cost_estimate.py
  - tests/pairmode/test_observability_context_api.py
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

**Pulled from CER-129** (`docs/cer/backlog.md`, operator report 2026-07-29,
"context accounting"), a mid-phase addition to Phase 114 by operator direction
rather than from the era-004 closeout reconciliation.

flex has two token quantities and one vocabulary for them. The word "context
budget" names both, the state key `context_budget_threshold` is compared against
both, and three separate consumers pick whichever one is nearest to hand. The
result is a pause/`/clear` prompt that fires on the wrong quantity in both
directions.

**The two quantities.**

- **Orchestrator-window occupancy** — how full the orchestrator's own context
  window is right now. Measured by
  `context_budget.compute_context_tokens()` (`context_budget.py:174-252`), which
  reverse-scans the session JSONL for the last **non-sidechain** assistant turn's
  `usage` block and sums `input_tokens + cache_read_input_tokens +
  cache_creation_input_tokens`. Stored as `context_current_tokens`. This is the
  only quantity that can overflow a window, and therefore the only one a pause
  decision may be computed from.
- **Story / subagent spend** — what a story cost to build: `effort.db`'s
  `attempts.tokens_total` / `tokens_out`, recorded per builder/reviewer/auditor
  spawn. Those tokens were burned in **subagent** context windows. They never
  entered the orchestrator's window at all — INFRA-251 added the `isSidechain`
  filter at `context_budget.py:210-231` precisely to keep them out of
  `context_current_tokens`.

`docs/architecture.md` § *(c) effort.db ≠ context-control invariant (DP7)*
(`:2005-2029`) already states the rule: subagent cost is "**Never an input to a
context-headroom or clear-seam decision.**" The repo's own recorded lesson says
the same thing (effort.db cost totals must never be used to estimate orchestrator
context headroom — they measure different things). `context_budget.decide()` obeys
it. **Three other live consumers do not.**

**Mis-attribution 1 — `context_health.py` recommends `/clear` from effort.db.**
`phase_retry_burden` (`context_health.py:77-111`) sums
`COALESCE(tokens_out, CAST(tokens_total * 0.15 AS INTEGER))` over
`agent_role = 'reviewer' AND outcome = 'FAIL'` rows — pure subagent spend.
`check_context_health` (`:141-227`) divides that by a rolling median of prior
phases and emits `recommendation` ∈ `normal` / `elevated` / `high`, whose messages
read "consider /clear before next phase" (`:211`) and "recommend /clear before
next phase" (`:216`), and whose CLI exits 1 on the latter two (`:273-275`). A
`/clear` advisory is an orchestrator-headroom verdict. It is computed here with
zero reference to `context_current_tokens`. A phase with many reviewer FAILs and a
freshly-`/clear`ed orchestrator reports `HIGH — recommend /clear`; a phase with
one clean story and a nearly-full orchestrator reports `normal`.

**Mis-attribution 2 — `context_budget_check.py` compares phase spend against the
orchestrator ceiling.** It sums `attempts.tokens_total` for a phase
(`context_budget_check.py:64-77`) and compares it against
`context_budget_threshold` read from `state.json` (`:46-62`, `:118-123`) — the
*same state key* `context_budget.decide()` uses as the orchestrator window
ceiling (`context_budget.py:882`). Over threshold it prints `CONTEXT BUDGET
EXCEEDED — phase N has accumulated M tokens of recorded subagent work` and
`Orchestrator MUST surface a proceed-vs-pause prompt to the user before spawning
the next builder` (`:140-147`) and exits 1. That is the whole defect in one
message: it names the quantity correctly ("recorded subagent work"), compares it
to a window ceiling, and then instructs an orchestrator pause. Because story
budgets accumulate monotonically across a phase, this verdict trips on any
multi-story phase regardless of orchestrator state.

**Mis-attribution 3 — the observability `/context` surface labels subagent spend
as orchestrator block events.** `queryWaypoints(db, threshold)`
(`effortDb.ts:123-177`) and `queryMisses(db, threshold)` (`:246-303`) both take
`context_budget_threshold` (`routes/context.ts:280-283`) and apply it to
`attempts.tokens_total`: `near_miss = tokens > threshold * 0.85`,
`delta_above_threshold`, and `count`/`entries` for `tokens_total > threshold *
1.1` — the ceiling formula from `should_block` (`context_budget.py:558`). The miss
rows are exposed as `tokens_at_block` and rendered by the SPA under the heading
**"Near-miss blocks (N)"** (`ContextMetrics.tsx:428-437`). No block ever occurred
at any of those numbers. They are subagent costs measured against an orchestrator
ceiling and then narrated as gate history.

**The other half: the orchestrator track is undercounted between spawns.**
`context_current_tokens` has exactly one automatic writer —
`hooks/post_tool_use.py`'s `Task`/`Agent` branch (`:63`, `:100-135`). It refreshes
only *after an agent spawn completes*. Everything else that enters the
orchestrator's window between spawns — `next-action` poll output, merge and git
output, task-completion notifications, spec-writer coordination, the orchestrator's
own reasoning — is never observed. The gate's staleness authority (`_is_stale`,
`:641-666`) only compares `context_current_tokens_recorded_at` against
`context_session_reset_at`, so a value that is many turns behind is not "stale"; it
is silently believed. The only additive path, `bump-context-tokens`
(`flex_build.py:1929-1990`), is documented as having zero live callers, precisely
because its historical caller fed it subagent cost (a DP7 violation the docstring
spells out). So the orchestrator track can read far below the truth, and the gate
that is supposed to pause a nearly-full orchestrator does not fire.

**Net effect, and why this is HIGH.** The prompt an operator actually sees is
driven by story-budget accumulation, while the number that determines whether the
window survives the next step is under-measured. The loop can be paused when the
orchestrator is nearly empty and allowed to continue when it is nearly full — the
two failure modes CER-129 reports, from opposite ends of the same conflation.

**Forcing function.** Phase 116's `INFRA-316` (draft) plans to have `next-action`
consult `context_budget_check.py` between story iterations against the 120k
absolute threshold and emit a `pause-context` handoff. That would promote
mis-attribution 2 from an unwired CLI into the resolver's live cadence decision.
`next_action.py:1017` already reserves the advisory string
(`_ADVISORY_CONTEXT = "context-budget-exceeded"`) with no producer. This story
must land before that one, and must leave behind a named, tested track boundary
for INFRA-316 to wire against. This story does **not** edit `docs/phases/phase-116.md`
or `INFRA-316`'s spec — see § Out of scope.

**The shape of the fix.** Not a new gate. A named two-track model, one definition
of which keys belong to which track, the pause/health verdict re-based onto the
orchestrator track, coverage for the orchestrator track's between-spawn blind
spot using the measurement that already exists, and every operator-facing surface
labeled so the two numbers can never again be read as one.

## Requires

Re-verified against the working tree at spec time (2026-07-29, `main` @
`2e6fc7db`). A builder finding an anchor moved should re-locate by symbol name,
not line number, and note the drift in its report.

**Orchestrator track — the correct mechanism, to be preserved.**

- `context_budget.compute_context_tokens` (`:174-252`) — bounded reverse scan of
  the last 500 JSONL lines; skips `isSidechain` entries (`:210-231`) with a long
  comment explaining that a subagent's usage is not the orchestrator's window.
  This is the repo's **real measurement path** for orchestrator occupancy.
- `context_budget.read_current_tokens` (`:255-281`) — JSONL-only wrapper; returns
  `None` without a `session_id` or a resolvable transcript. No state fallback.
- `context_budget.derive_expected_step_tokens` (`:400-445`) and
  `record_step_growth` (`:448-498`) — the DP7-clean live estimate: median of the
  `context_step_growth_samples` ring buffer (cap 20, min 5 for live —
  `context_model.py:28-29`), else the stored seed, else
  `THIN_HARNESS_STEP_TOKENS` (5000, `context_model.py:20`). Returns
  `(value, provenance)`.
- `context_budget.should_block` (`:506-577`) — the ceiling is
  `threshold * (1.0 + overrun_pct)` (`:558`); `decide()` pre-multiplies
  `threshold * flex_factor` (`:920`) and `render_alert_prompt` recomputes
  `int(threshold * (1 + overrun_pct) * flex_factor)` independently (`:603`).
  **Three sites, one formula, no shared helper** — § A4.
- `context_budget.decide` (`:736-949`) — reads `context_current_tokens`
  (`:844-852`), applies `_is_stale` (`:864-870`), reads
  `context_budget_threshold` / `context_budget_overrun_pct` /
  `context_budget_reprompt_margin` (`:882-890`), and is **strictly read-only
  (D11)**. It never opens effort.db: `estimate_next_step_tokens(None, None,
  seeded_default)` at `:909-913` passes `db_path=None` deliberately, and
  CER-053's regression test `test_expected_step_tokens_source.py` pins that
  literal call site. **This function is already correct and its DP7 posture must
  not be disturbed.**
- `hooks/post_tool_use.py:63` — branch matcher is `("Task", "Agent",
  "SendMessage")`; `SendMessage` exits early at `:81` as observed-only. The
  `context_current_tokens` write happens inside one
  `state_utils.update_state_json` read-modify-write (`:96-145`) through
  `session_state.session_view(state, session_id)` (INFRA-285 session keying).
  **This is the only automatic writer of the orchestrator track.**
- `hooks/user_prompt_submit.py` is a **protected path** (`scope_guard.PROTECTED_GLOBS`
  includes `hooks/**`) and is a thin dispatcher: stdin parse → one delegated call
  `record_user_turn(project_dir, data)` → `sys.exit(0)` (`:28-40`). Its domain
  logic lives entirely in `skills/pairmode/scripts/user_turn_seq.py`
  (`record_user_turn`, `:89-...`), which owns the full read-modify-write via
  `state_utils.update_state_json` and has an INFRA-248 sha256 fingerprint
  idempotency guard keyed on `session_id` + `prompt`. **§ C lands in
  `user_turn_seq.py`; the hook file is not edited.**

**Story-spend track — the three mis-attributing consumers.**

- `context_health.py` — `phase_retry_burden` (`:77-111`), `rolling_phase_median`
  (`:114-138`), `check_context_health` (`:141-227`) returning
  `{phase, retry_burden, phase_median, ratio, recommendation, sample_size,
  message}`; `_cli_main` (`:230-278`) exits 1 for `elevated`/`high`. Tested by
  `tests/pairmode/test_context_health.py`.
- `flex_build.py:785-799` — `context-health` command; prints
  `json.dumps(result)`. Imported at `flex_build.py:64`.
- `context_budget_check.py` — `_load_threshold_from_state` (`:46-62`),
  `_sum_tokens_for_phase` (`:64-77`), `main` (`:79-152`); `_DEFAULT_THRESHOLD =
  120000` (`:26`). Tested by `tests/pairmode/test_context_budget_check.py`.
  `context_budget.py:37-38` asserts this CLI "is unrelated and remains
  untouched" — that claim is what § B falsifies: it shares
  `context_budget_threshold`.
- `skills/observability/api/src/readers/effortDb.ts` — `queryWaypoints`
  (`:123-177`), `queryMisses` (`:246-303`).
  `skills/observability/api/src/routes/context.ts` — `THRESHOLD_DEFS`
  (`:28-60`), `buildContextPayload` (`:262-316`), threshold resolution at
  `:280-283`, effort queries at `:296-300`.
- `skills/observability/ui/src/components/ContextMetrics.tsx` — thresholds table
  (`:309-345`), "Waypoints (last 10)" (`:346-400`), "Effort totals" (`:405-425`),
  "Near-miss blocks" (`:428-441`). Types in
  `skills/observability/ui/src/api/client.ts`.

**Existing per-story numbers, to be classified not changed.**

- `flex_factor` — story frontmatter, resolved by
  `hooks/pre_tool_use.py::_resolve_flex_factor` and multiplied into the
  orchestrator ceiling (`context_budget.decide` `:920`). It is an
  **orchestrator-track** ceiling multiplier, not a subagent gate.
- `story-cost-estimate` (`flex_build.py:1833-1876`) — median PASS
  `tokens_total` for `(rail, story_class)` from effort.db. **Story-spend track**,
  informational, no threshold comparison. Leave its arithmetic alone.
- `next_action.py:1016-1017` — `_ADVISORY_GUARDRAIL` and `_ADVISORY_CONTEXT` are
  defined and surfaced in the docstring's `warnings` contract but **no code in
  the module produces either**. `next_action.py` contains no effort.db read on
  the advisory path today.

**Documentation anchors.**

- `docs/architecture.md:2005-2029` — § *(c) effort.db ≠ context-control
  invariant (DP7)*. The rule text is correct; what it lacks is the track names
  and the consumer inventory.
- `docs/architecture.md:2031-2043` — § *Codified comingling — FLAGGED FOR REMOVAL
  AT HARNESS006*. It names `CLAUDE.build.md:320-326` as the comingled advisory to
  delete. `CLAUDE.build.md` is now **52 lines**; that advisory is gone. The
  section is stale and describes the comingling as a single remaining site, which
  is false — three others survived in code.
- `docs/architecture.md:525-620` — § *Context budget check*, including the
  INFRA-254 live-derivation narrative. `:2192`, `:2218`, `:2574`, `:3258` are the
  other DP7 cross-references.

**Baseline.** `main`'s suite is green — 4116 passed, 211 skipped. A
`test_observability_ui` failure inside a story worktree is the known CER-090
vendored-payload gap: fix by `rsync`-ing the payload from the main checkout,
**never** by `pnpm install`.

**Sibling-story coordination.**

- **INFRA-299** (Phase 113, unmerged at spec time) owns `hooks/pre_tool_use.py`
  and `docs/cer/backlog.md` rows **CER-105, CER-106 and CER-113**. This story
  edits neither the hook nor those rows. CER-106 is directly adjacent in subject
  (`context_budget_acknowledged_at` stores a token count despite the `_at`
  suffix) and stays untouched — see § Out of scope.
- **INFRA-320** (Phase 113) introduces `scope_guard.STANDING_SURFACES` covering
  `docs/cer/backlog.md` and `docs/architecture.md`. This story declares both in
  `touches:` explicitly and does not depend on INFRA-320 having merged.
- **INFRA-303** (same phase) owns `pairmode_migrate.py`'s
  `expected_step_tokens` opt-out. This story changes no migration rule and does
  not rename `expected_step_tokens`.
- **INFRA-316** (Phase 116, draft) is the downstream consumer this story
  constrains; nothing in phase 116 is edited here.


## Scope widenings

| path | reason | widened_at |
| --- | --- | --- |
| tests/pairmode/test_context_model.py | new test file for context_model.py's INFRA-321 track constants, not in the story's touches: list | 2026-07-31T00:31:58Z |

| tests/pairmode/test_flex_build_story_cost_estimate.py | retarget the pinned 'estimate:' stdout string for § D2's track_label caption | 2026-07-31T00:45:24Z |
| tests/pairmode/test_observability_context_api.py | retarget queryMisses export-name pin for the § E3 querySpendOutliers rename | 2026-07-31T00:55:24Z |
## Ensures

### A — one definition of the two tracks

**A1.** `context_model.py` — already the DP7-clean constants home — gains the
track vocabulary as module-level constants:

- `TRACK_ORCHESTRATOR: str = "orchestrator-window"` — live occupancy of the
  orchestrator's own context window.
- `TRACK_STORY_SPEND: str = "story-spend"` — retrospective cost of subagent work.
- `ORCHESTRATOR_TRACK_KEYS: tuple[str, ...]` — the `state.json` keys that belong
  to the orchestrator track: `context_current_tokens`,
  `context_current_tokens_recorded_at`, `context_step_growth_samples`,
  `expected_step_tokens`, `context_budget_threshold`,
  `context_budget_overrun_pct`, `context_budget_reprompt_margin`,
  `context_budget_acknowledged_at`, `context_budget_user_turn_seq`,
  `context_budget_acknowledged_user_turn_seq`, `context_session_reset_at`.
- `STORY_SPEND_SOURCES: tuple[str, ...]` — the effort.db columns that belong to
  the story-spend track: `attempts.tokens_total`, `attempts.tokens_out`,
  `attempts.tokens_in`.

Each carries a docstring stating the boundary rule verbatim: **a story-spend
quantity may never be compared against an orchestrator-track threshold, and may
never be summed into an orchestrator-track key.** `context_model.py` stays
stdlib-only and import-cheap (it is on the PreToolUse hook path).

**A2.** `context_model.py` gains a pure labeling helper —
`track_label(track: str) -> str` (name indicative) — returning the operator-facing
string for each track (e.g. `"orchestrator window"` /
`"story spend (subagent cost — not headroom)"`). Every Python surface that prints
either number labels it through this helper rather than hand-writing a caption, so
the two captions cannot drift apart. Unknown track values return a safe
`"unlabelled"` rather than raising.

**A3.** A **dedicated story-spend threshold key** is introduced —
`story_spend_threshold` — so that no consumer needs to reach for
`context_budget_threshold` to answer a spend question. Resolution order for
story-spend consumers is: explicit CLI `--threshold` → `state["story_spend_threshold"]`
→ the module default. When `story_spend_threshold` is absent, the default is used
and the surface says the threshold is **unconfigured** — it does **not** fall back
to `context_budget_threshold`. A test asserts that a `state.json` carrying only
`context_budget_threshold` produces the unconfigured-default path and that the
orchestrator threshold value never appears in the spend verdict.

**A4.** The ceiling formula is extracted once. `context_budget` gains a pure
`effective_ceiling(threshold, overrun_pct, flex_factor=1.0) -> int` and the three
existing sites — `should_block` (`:558`), `decide`'s `threshold * flex_factor`
pre-multiplication (`:920`), and `render_alert_prompt` (`:603`) — all route
through it. Arithmetic is byte-identical for every existing input (a test pins a
table of `(threshold, overrun_pct, flex_factor)` triples against the values the
current code produces, including the `int()` truncation in `render_alert_prompt`).
This is the duplicate-state fix that makes § B2's re-based verdict impossible to
compute from a fourth, divergent copy.

### B — the health/pause verdict fires on the orchestrator track only

**B1.** `context_health.py` gains a pure orchestrator-track function —
`orchestrator_headroom(state, flex_factor=1.0)` (name indicative) — that reads
**only** `state.json` keys from `ORCHESTRATOR_TRACK_KEYS`, opens no database, and
returns:

| key | meaning |
|---|---|
| `track` | `TRACK_ORCHESTRATOR` |
| `tokens` | `context_current_tokens`, or `None` when absent/non-positive |
| `ceiling` | `context_budget.effective_ceiling(...)` (§ A4) |
| `expected_step_tokens` | value from `context_budget.derive_expected_step_tokens` |
| `expected_step_provenance` | that function's provenance string |
| `headroom` | `ceiling - tokens`, or `None` when `tokens` is `None` |
| `steps_remaining` | `headroom // expected_step_tokens`, or `None` |
| `stale` | `context_budget._is_stale(state)`'s verdict |
| `recommendation` | see B2 |
| `message` | human-readable, captioned via `track_label` |

It **reuses** `context_budget.derive_expected_step_tokens`,
`context_budget.effective_ceiling` and `context_budget._is_stale` rather than
re-deriving any of them. It never writes. It never raises — a malformed or empty
`state` yields `tokens=None`, `recommendation="insufficient_data"`.

**B2.** `recommendation` is computed from `steps_remaining` and `stale` only:
`stale` or `tokens is None` → `"insufficient_data"`; `steps_remaining >= 3` →
`"normal"`; `1 <= steps_remaining < 3` → `"elevated"`; `steps_remaining < 1` →
`"high"`. The `/clear` advice appears **only** in the `elevated` and `high`
messages of this function. No effort.db value participates in this computation,
and a test asserts the function under a monkeypatched `sqlite3.connect` that
raises on any call.

**B3.** `phase_retry_burden` and `rolling_phase_median` keep their exact current
signatures, SQL and return values — the measurement is fine, only its framing was
wrong. What changes is that `check_context_health`'s returned dict is restructured
into two explicitly-tracked sub-objects:

```
{
  "phase": "<phase>",
  "orchestrator": { ...orchestrator_headroom(...) },
  "story_spend": { "track": TRACK_STORY_SPEND, "retry_burden": N,
                   "phase_median": M, "ratio": R, "sample_size": K,
                   "informational": true, "message": "<captioned>" },
  "recommendation": "<orchestrator.recommendation>",
  "message": "<orchestrator.message>; story spend: <story_spend.message>"
}
```

The top-level `recommendation` **is** `orchestrator["recommendation"]` — asserted
by identity in a test, not by re-derivation. `check_context_health` gains an
optional `state` parameter (default `None` → read `.companion/state.json` via the
same reader pattern the module already uses for the DB path) so it can be called
purely in tests.

**B4.** `story_spend.message` contains **no** `/clear` advice and no pause
instruction. The strings `"consider /clear"` and `"recommend /clear"` appear
nowhere in any story-spend code path — a test greps the rendered `story_spend`
message across `normal`/`elevated`/`high` retry-burden fixtures and asserts
`"/clear"` is absent. The retry-burden ratio bands (`< 2.0`, `2.0-4.0`, `>= 4.0`)
survive as a *retry-churn* signal with churn wording (`"retry churn: normal /
ELEVATED / HIGH"`), which is what the number actually measures.

**B5.** The `context-health` CLI (`context_health._cli_main`, `:230-278`) and
`flex_build.py context-health` (`:785-799`) exit **1** when
`orchestrator["recommendation"]` is `elevated` or `high`, and **0** otherwise —
including when story-spend retry churn is `HIGH` with a healthy orchestrator. Two
tests pin both directions: high churn + empty orchestrator → exit 0; low churn +
`steps_remaining < 1` → exit 1. `flex_build.py context-health` gains
`--project-dir`-relative state reading and continues to print the JSON object.

**B6.** `context_budget_check.py` keeps summing phase spend but stops rendering an
orchestrator verdict:

- the threshold resolves per § A3 (`--threshold` → `story_spend_threshold` →
  `_DEFAULT_THRESHOLD`), and **never** from `context_budget_threshold`;
- the machine-parseable stdout line gains `track=story-spend` and the resolved
  threshold's provenance, e.g.
  `story_spend phase=114 tokens=N threshold=M threshold_source=default status=over`;
- the over-threshold stderr block is rewritten: it names the quantity as
  recorded subagent work, states that it is **not** a context-headroom signal,
  and points at `context-health` for the orchestrator track. The strings
  `"CONTEXT BUDGET EXCEEDED"` and `"Orchestrator MUST surface a proceed-vs-pause
  prompt"` are removed;
- exit codes are unchanged (0 ok / 1 over / 2 usage-IO), so any existing caller's
  control flow still works. A test asserts the exit-code table is byte-identical
  to today's for the same inputs.

**B7.** `context_budget.decide()` is **not** re-based, re-scoped or otherwise
altered in its decision logic. Its only diff is the § A4 call-site extraction.
`test_expected_step_tokens_source.py`'s pinned
`estimate_next_step_tokens(None, ...)` literal survives verbatim, and a test
asserts `decide()` still returns byte-identical dicts for a matrix of pre-existing
fixtures.

### C — orchestrator-track coverage between spawns

**C1.** `user_turn_seq.record_user_turn` gains a second delegated
responsibility, performed **inside the read-modify-write it already does** (one
state write per invocation, unchanged): refresh the orchestrator track from the
real measurement. It calls `context_budget.read_current_tokens(project_dir,
session_id)` — the same JSONL, `isSidechain`-filtered path `post_tool_use.py`
uses — and, when it returns a positive int, writes `context_current_tokens` and
`context_current_tokens_recorded_at` through
`session_state.session_view(state, session_id)`, mirroring
`post_tool_use.py:113-133`.

**C2.** `hooks/user_prompt_submit.py` is **not modified.** It already delegates
everything to `record_user_turn`; the protected-path contract
(`scope_guard.PROTECTED_GLOBS` → `hooks/**`) and the thin-hook boundary (D11)
both hold with no edit. A test asserts the hook file's byte content is unchanged
by this story (or, equivalently, that the hook's only call remains
`record_user_turn`).

**C3.** The refresh is **measurement-only and fail-open**. `read_current_tokens`
returning `None` (no `session_id`, transcript not on disk, no non-sidechain
assistant entry, unreadable file) leaves `context_current_tokens` and its stamp
**untouched** — it is never zeroed, never lowered by fiat, and never estimated.
Any exception in the refresh leaves the turn-counter increment intact: the two
responsibilities are independently wrapped, mirroring `post_tool_use.py`'s
two-delegated-calls contract. A test asserts a raising `read_current_tokens` still
advances `context_budget_user_turn_seq`.

**C4.** `record_step_growth` is **not** called from this path. The ring buffer's
samples must remain *per-build-step* growth deltas (the quantity
`expected_step_tokens` is supposed to estimate); mixing per-user-turn deltas into
it would corrupt the median that the gate's ceiling arithmetic depends on. A test
asserts `context_step_growth_samples` is unchanged in length after a
`record_user_turn` refresh that moved `context_current_tokens`.

**C5.** The INFRA-248 fingerprint idempotency guard governs the **turn counter
only**. A duplicate `UserPromptSubmit` firing for the same prompt still skips the
increment, and the token refresh is idempotent by construction (it writes the same
measured value). A test covers duplicate-firing: counter advances once, token
value ends at the measured number.

**C6.** Provenance is recorded. Every writer of `context_current_tokens` also
writes `context_current_tokens_source` ∈ `{"post-tool-use", "user-prompt-submit",
"manual"}`:

- `post_tool_use.py`'s Task/Agent branch → `"post-tool-use"`;
- `record_user_turn`'s refresh → `"user-prompt-submit"`;
- `flex_build.py set-context-tokens` and `bump-context-tokens` → `"manual"`.

The key is additive and every reader tolerates its absence (legacy state) by
treating the source as unknown. `context_budget.decide()` does **not** gate on it —
it is an observability and audit field only, asserted by a test that `decide()`'s
verdict is identical with the key present, absent, and set to garbage.

**C7.** `bump-context-tokens` stays dormant by design. No new caller is wired in
this story. Its docstring is amended to state the two-track rule in the new
vocabulary — the `--cost` argument must be a **measured orchestrator-window
delta** (`TRACK_ORCHESTRATOR`), never a story-spend figure — and to record that
§ C1's measured refresh is the reason no caller is needed. The command's
arithmetic and exit codes are unchanged.

### D — per-story gates: classify, preserve, and do not invent

**D1.** `flex_factor` is documented and tested as an **orchestrator-track
ceiling multiplier**, not a subagent gate: it scales the orchestrator's own
ceiling for a story known to need a longer run. `_resolve_flex_factor`'s
fail-open-to-`1.0` behaviour and its resolution path are unchanged. A test
asserts a story `flex_factor` still reaches `effective_ceiling` after § A4's
extraction, with the same product.

**D2.** `story-cost-estimate` is documented and tested as a **story-spend
informational** surface. Its output line is captioned via `track_label` so it
reads as cost, not headroom, and it acquires **no** threshold comparison. A test
asserts its stdout contains no threshold and no pause language.

**D3.** The story states on the record that **no gate protecting a subagent's own
context window exists today**, and does not invent one. The distinction is
recorded in the architecture note (§ E): a story too large for one builder
context is a real risk, but the only per-story number in the system today
(`flex_factor`) protects the *orchestrator's* ceiling, and the only per-story cost
number (`story-cost-estimate`) is retrospective. A subagent-window gate would need
a pre-spawn estimate of a builder's own input size, which nothing measures — it is
named as future work with its track (`TRACK_ORCHESTRATOR` is **not** its track)
rather than half-built here.

**D4.** `next_action.py`'s `_ADVISORY_CONTEXT` (`:1017`) is documented in place as
an **orchestrator-track** advisory: its producer, whenever one is wired, must read
the orchestrator track. No producer is added by this story. A test asserts
`next_action.py` contains no `effort.db` / `sqlite3` read on any advisory path and
that `resolve_next_action` still ignores `warnings` for action selection (DP2
unchanged).

### E — operator-facing surfaces label the two numbers distinctly

**E1.** `routes/context.ts`'s `THRESHOLD_DEFS` entries each gain a `track` field
(`"orchestrator-window"` or `"story-spend"`), surfaced in the `/context` payload
and rendered as a column in the SPA Thresholds table. `context_budget_threshold`,
`context_budget_overrun_pct`, `expected_step_tokens`,
`context_budget_reprompt_margin` and `flex_factor` are all
`"orchestrator-window"`; `story_spend_threshold` is added as `"story-spend"`.

**E2.** `context_budget_threshold`'s `editable_via` is corrected. It currently
reads `'flex_build.py set-context-tokens'` (`routes/context.ts:33`), which is
false — `set-context-tokens` writes the *current count*, not the threshold. It
becomes `null` (or the actual edit path if one exists), and a test asserts no
threshold def claims an `editable_via` command that does not write that key.

**E3.** `queryWaypoints` and `queryMisses` stop taking the orchestrator threshold.
They take the **story-spend** threshold (§ A3) resolved in
`buildContextPayload`, and their derived fields are renamed to say what they are:

- `waypoints[].near_miss` → `waypoints[].over_spend_band` (or the field is
  dropped if the SPA does not use it — a written-never-read check);
- `waypoints[].delta_above_threshold` → `delta_above_spend_threshold`;
- `misses` → `spend_outliers`, and `entries[].tokens_at_block` →
  `entries[].tokens_total`. **No field in the payload asserts that a block
  occurred**, because none did.

The `threshold * 1.1` ceiling formula is removed from `effortDb.ts` entirely — the
orchestrator overrun ceiling has no meaning applied to subagent cost. Outliers use
a plainly-named spend multiple.

**E4.** `ContextMetrics.tsx` is reorganised into two labeled groups with a visible
caption on each:

- **Orchestrator window** — current tokens / ceiling / progress bar / stale
  badge / thresholds where `track === 'orchestrator-window'`. This group is the
  only place a headroom judgment appears.
- **Story spend (subagent cost — not headroom)** — waypoints, effort totals,
  spend outliers, and thresholds where `track === 'story-spend'`.

The heading `"Near-miss blocks (N)"` is replaced with `"Spend outliers (N)"`. The
progress bar and its `ratio >= 0.85` / `>= 1.0` tone thresholds
(`ContextMetrics.tsx:255-257`) stay bound to `current.tokens` — orchestrator track
— and are asserted not to be fed by any effort.db value.

**E5.** `ui/src/api/client.ts`'s types are updated to match the renamed payload
fields, and the API's own test suite is updated so a stale field name fails a test
rather than silently rendering `undefined`. Any Python-side consumer of the
`/context` shape (if one exists) is updated in the same commit.

**E6.** `flex-build context-health`'s printed JSON is the two-sub-object shape
from § B3, and the sub-object captions come from `track_label` (§ A2). No operator
surface prints an unlabelled token number.

### F — documentation

**F1.** `docs/architecture.md` § *(c) effort.db ≠ context-control invariant
(DP7)* (`:2005-2029`) is extended with the **two-track model**: the track names
and their constants (`TRACK_ORCHESTRATOR` / `TRACK_STORY_SPEND`,
`ORCHESTRATOR_TRACK_KEYS`, `STORY_SPEND_SOURCES`), the boundary rule in both
directions (no story-spend quantity against an orchestrator threshold; no
subagent token summed into an orchestrator key), and the separate
`story_spend_threshold` key with its no-fallback rule (§ A3).

**F2.** The § *Codified comingling — FLAGGED FOR REMOVAL AT HARNESS006*
section (`:2031-2043`) is replaced by a resolved record. It must state: the
`CLAUDE.build.md:320-326` advisory it named is gone (that file is now 52 lines);
the comingling actually survived in **three other consumers** —
`context_health.py`'s `/clear` recommendation, `context_budget_check.py`'s shared
threshold, and the `/context` waypoints/misses queries — none of which the
original note anticipated; and this story is where each was re-based. A
"flagged for removal" note that outlived its target and missed three live sites
is itself a documentation defect.

**F3.** § *Context budget check* (`:525-620`) records the § C coverage change: the
orchestrator track now has **two** measurement writers — PostToolUse after each
spawn, and `record_user_turn` on each human turn — both reading the same
`isSidechain`-filtered JSONL measurement; the between-spawn blind spot (poll
output, merge output, task notifications, spec-writer coordination) and why it
mattered; the `context_current_tokens_source` provenance field; and the explicit
statement that `record_step_growth` is **not** invoked from the user-turn path
(§ C4) with the reason.

**F4.** The § D3 finding is recorded: no gate protects a subagent's own context
window today, `flex_factor` is an orchestrator ceiling multiplier and not that
gate, and a genuine subagent-window gate is named as future work with what it
would require. This closes the "which gate protects what" ambiguity rather than
leaving a reader to assume the per-story knob is a per-builder guard.

**F5.** The rejected directions (§ Out of scope R1–R6) are recorded in the
architecture note with their reasons — R1 especially, because deriving
orchestrator headroom from effort.db totals is an already-recorded lesson that
three separate consumers reinvented anyway, and R2, because inventing numbers for
un-measured turns is the exact failure CER-053/INFRA-254 already corrected once
for `expected_step_tokens`.

**F6.** A forward constraint is recorded for **INFRA-316** (Phase 116, draft,
between-story context etiquette): its `next-action` pause decision must consult
the **orchestrator** track — `orchestrator_headroom` / `context-health`'s
`orchestrator` sub-object — and must not consult `context_budget_check.py`, whose
verdict is story-spend by construction. `_ADVISORY_CONTEXT` is named as the
orchestrator-track advisory string its producer should emit. This story does not
edit `docs/phases/phase-116.md` or `INFRA-316`'s spec.

**F7.** No new persistent schema object is introduced. `schema_introduces` stays
`false` and Phase 114's § Schema delivery table owes this story no row. Both new
`state.json` keys (`story_spend_threshold`, `context_current_tokens_source`) live
in an existing file whose human management surface is already the observability
`/context` thresholds view plus direct edit; `story_spend_threshold` is surfaced
there by § E1 in this same story.

### G — backlog

**G1.** The CER-129 row in `docs/cer/backlog.md` is annotated
`**RESOLVED INFRA-321 (Phase 114)**` with a short statement of what landed: the
two-track model and its constants (A), the health/pause verdict re-based onto the
orchestrator track (B), between-spawn orchestrator coverage via the existing JSONL
measurement (C), per-story number classification (D), and distinctly-labeled
operator surfaces (E).

**G2.** The annotation states plainly that **no gate was weakened and no new gate
was added** — `decide()`'s logic is untouched — and names the rejected
effort.db-derived-headroom direction so the record cannot be read as licensing it.

**G3.** No other backlog row is edited and no row is deleted. `git diff
docs/cer/backlog.md` touches exactly one row. Rows **CER-105, CER-106 and
CER-113** are owned by the unmerged INFRA-299 branch and must be left
byte-identical.

### H — tests and suite

**H1.** New tests exist for each of: A1/A2 (constants present, boundary docstring,
`track_label` total), A3 (spend threshold never falls back to
`context_budget_threshold`), A4 (ceiling parity table across all three former
sites, including `int()` truncation), B1 (headroom fields, reuse of
`derive_expected_step_tokens`), B2 (each recommendation band; no sqlite3 call —
monkeypatched to raise), B3 (top-level `recommendation` is identically
`orchestrator["recommendation"]`), B4 (`"/clear"` absent from every story-spend
message), B5 (both exit-code directions), B6 (renamed stdout line, removed
strings, unchanged exit-code table), B7 (`decide()` output parity matrix),
C1 (refresh writes the measured value through the session view), C3 (`None`
measurement leaves the value untouched; raising measurement still increments the
counter), C4 (ring buffer length unchanged), C5 (duplicate firing: one increment,
correct token value), C6 (source stamped by each writer; `decide()` indifferent to
it), D1 (`flex_factor` still multiplies the ceiling), D2 (no threshold/pause
language in `story-cost-estimate`), D4 (no sqlite read on `next_action.py`'s
advisory path).

**H2.** The observability API test suite gains cases asserting: every threshold
def carries a `track`; `spend_outliers` entries expose `tokens_total` and no
`tokens_at_block`; and `queryWaypoints`/`queryMisses` are never called with the
orchestrator threshold value. The SPA test/build gate must pass with the renamed
fields — a stale field name fails, it does not render `undefined`.

**H3.** Existing tests are **retargeted, not deleted**. In particular
`tests/pairmode/test_context_health.py`'s assertions on the flat
`{retry_burden, ratio, recommendation, message}` shape and on the `/clear`
message text move to the `story_spend` sub-object with churn wording, each with a
docstring line naming INFRA-321; `tests/pairmode/test_context_budget_check.py`'s
assertions on the `CONTEXT BUDGET EXCEEDED` string and the
`context_budget_threshold` read move to the story-spend equivalents.

**H4.** Full suite green, run **once without `-x`** so a pre-existing failure
cannot mask a new one, against the `main` baseline of 4116 passed / 211 skipped
plus this story's additions.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Build in order **A → B → C → D → E → F → G**, running the focused suites after
each of A, B, C and E, then the full suite without `-x` at the end.

**A — vocabulary first, and only once.** Put the track constants and
`track_label` in `context_model.py`, not in `context_budget.py` — `context_model`
already exists as the DP7-clean constants module, is imported by
`context_budget` under both import styles (`context_budget.py:50-64`), and is the
one place a reader looking for "what is a token here" will land. Keep it
stdlib-only and side-effect-free; it is on the PreToolUse hook path. Extract
`effective_ceiling` into `context_budget.py` (the module that owns the gate
arithmetic) and rewire all three call sites in the same commit — do **not** leave
one site computing the ceiling inline, because the whole point of § A4 is that
§ B1 adds a fourth reader.

**B — re-base the verdict, keep the measurement.** Do not touch
`phase_retry_burden`'s SQL. The retry-burden number is a legitimate measurement
of reviewer churn; it was only ever wearing the wrong hat. Write
`orchestrator_headroom` as a pure function over a `state` dict so it is testable
without a filesystem, and have `check_context_health` acquire the state (existing
reader pattern, `.companion/state.json`) and pass it in. When wiring the top-level
`recommendation`, assign `orchestrator["recommendation"]` by reference — do not
re-run the band logic, or the two can drift. In `context_budget_check.py`, resolve
the threshold through the § A3 order and make the absence of
`story_spend_threshold` visible in the output (`threshold_source=default`); a
silent default is how the original conflation stayed invisible for this long.

**C — coverage in `user_turn_seq.py`, never in the hook.**
`hooks/user_prompt_submit.py` is a protected path and needs no edit: it already
calls `record_user_turn(project_dir, data)` and passes the full payload, which
carries `session_id`. Add the refresh inside the existing
`state_utils.update_state_json` mutation so the hook still performs exactly one
state write per invocation. Wrap the `read_current_tokens` call and the counter
increment independently — copy the posture from `post_tool_use.py`'s
"two delegated calls, each independently wrapped" comment (`:82-84`). Resist the
temptation to call `record_step_growth` here (§ C4): the ring buffer must stay a
per-build-step series or `expected_step_tokens` stops meaning what the ceiling
arithmetic assumes.

**D — classify, do not build.** § D is mostly assertions and documentation over
existing behaviour. The one thing to be careful about is § D3: write the "no
subagent-window gate exists" finding plainly. A reader who assumes `flex_factor`
guards a builder's window will size stories wrongly, and the current docs do not
disabuse them.

**E — surfaces.** Do the TypeScript renames as renames, not additive aliases;
leaving `tokens_at_block` in place "for compatibility" preserves the exact false
claim this story exists to remove. Update `client.ts` types and the API tests in
the same change so the compiler and the suite catch every reference. If the SPA
build needs the vendored payload, `rsync` it from the main checkout — never
`pnpm install` (CER-090).

**F/G — docs and backlog.** Rewrite the stale § *Codified comingling* section
rather than appending to it; a note that says "one remaining site, flagged for
removal" next to a paragraph listing three others is worse than either alone.
Annotate exactly the CER-129 row, appending to the existing Finding cell as
sibling rows do; do not reword the original finding text. Do not touch rows
CER-105/106/113 (§ Requires, INFRA-299 coordination).

**Ideology-alignment note (Step 4a, resolved inline).** `docs/ideology.md`
§ Accepted constraints — *"Never silently pass contradictions"* — reads directly
on § A3's `threshold_source` output and § B6's rewritten message: a verdict whose
input provenance is invisible is how three consumers came to share one threshold
key without anyone noticing. § Core convictions — *rationale-bearing decisions
over bare rules* — is why § A1 ships the boundary rule in the constants'
docstrings rather than a bare tuple of key names, and why § F5 records the
rejected directions: R1 is already a recorded lesson and was still reinvented
three times, which is the strongest possible evidence that the rule must live next
to the code and not only in a lessons file.

## Tests

```bash
# Focused — track vocabulary, ceiling parity, gate parity
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_context_budget.py \
  tests/pairmode/test_expected_step_tokens_source.py -q

# Focused — the re-based health verdict and the spend CLI
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_context_health.py \
  tests/pairmode/test_context_budget_check.py -q

# Focused — orchestrator-track coverage on the user-turn path
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_user_turn_seq.py \
  tests/pairmode/test_user_prompt_submit_hook.py \
  tests/pairmode/test_post_tool_use.py -q

# Focused — CLI surfaces and resolver advisory posture
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_flex_build.py \
  tests/pairmode/test_next_action.py -q

# Observability API + SPA gate (renamed payload fields)
cd skills/observability/api && pnpm test
cd skills/observability/ui && pnpm build

# Full suite — once, WITHOUT -x, so a pre-existing failure cannot mask a new one
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

**Acceptance:**

- All four focused runs green, including every new test named in H1.
- Observability API suite green with the renamed fields; SPA build clean.
- Full suite green against the `main` baseline of 4116 passed / 211 skipped plus
  this story's new tests. No new failures.
- A `test_observability_ui` failure is worktree-only (CER-090). Fix by `rsync`-ing
  the vendored payload from the main checkout; never `pnpm install`. State in the
  build report that it does not reproduce on a clean `main` checkout.

**New tests required** (names indicative):

- `test_track_constants_and_label_are_total`
- `test_story_spend_threshold_never_falls_back_to_context_budget_threshold`
- `test_effective_ceiling_parity_across_former_call_sites`
- `test_orchestrator_headroom_opens_no_database`
- `test_orchestrator_headroom_recommendation_bands`
- `test_orchestrator_headroom_stale_is_insufficient_data`
- `test_check_context_health_recommendation_is_orchestrator_recommendation`
- `test_story_spend_message_contains_no_clear_advice`
- `test_context_health_exit_zero_on_high_churn_with_healthy_orchestrator`
- `test_context_health_exit_one_on_low_churn_with_no_steps_remaining`
- `test_context_budget_check_stdout_declares_story_spend_track`
- `test_context_budget_check_exit_codes_unchanged`
- `test_decide_output_parity_after_ceiling_extraction`
- `test_record_user_turn_refreshes_orchestrator_tokens_from_measurement`
- `test_record_user_turn_leaves_tokens_untouched_when_measurement_is_none`
- `test_record_user_turn_increments_counter_when_measurement_raises`
- `test_record_user_turn_does_not_append_step_growth_sample`
- `test_duplicate_user_prompt_increments_once_and_refreshes_tokens`
- `test_user_prompt_submit_hook_still_only_delegates`
- `test_context_current_tokens_source_stamped_by_each_writer`
- `test_decide_ignores_context_current_tokens_source`
- `test_flex_factor_still_multiplies_effective_ceiling`
- `test_story_cost_estimate_prints_no_threshold_or_pause_language`
- `test_next_action_advisory_path_reads_no_effort_db`

## Out of scope

- **R1 — deriving orchestrator headroom (or a `/clear` recommendation) from
  effort.db totals. Rejected, not deferred.** This is already a recorded repo
  lesson and an architecture invariant (`docs/architecture.md` § *(c) effort.db ≠
  context-control invariant (DP7)*): subagent tokens never entered the
  orchestrator's window, so summing them to estimate headroom counts tokens that
  were never there. Three live consumers reinvented it anyway, which is why § F1
  puts the rule in the code's own constants and § F5 records the rejection where a
  future reader of `context_health.py` will see it.
- **R2 — heuristically estimating the size of poll output, merge output or task
  notifications to grow the orchestrator track. Rejected.**
  `compute_context_tokens()` is a **real measurement** of the orchestrator's live
  window, available on any hook event, and § C uses it. A per-event constant or a
  character-count ratio would re-create exactly the invented-number failure
  CER-053/INFRA-254 already corrected once for `expected_step_tokens` (a
  hand-edited `111` persisted through multiple builds and distorted the ceiling).
  Measure, or do not write.
- **R3 — summing subagent sidechain `usage` into `context_current_tokens` to
  "account for" spawned work. Rejected.** INFRA-251 added the `isSidechain` filter
  (`context_budget.py:210-231`) for this precise reason, and
  `subagent_transcript.py` already reads the sidechain side of the same transcript
  for its own (correct, story-spend) purpose. The two readers share a file and
  must keep extracting disjoint data.
- **R4 — deleting `context_health.py` or `context_budget_check.py`. Rejected.**
  Phase spend and reviewer-retry churn are legitimate story-spend products. The
  defect is the label, the shared threshold key and the pause instruction — not
  the measurement. Both modules survive with their SQL intact.
- **R5 — a single unified "context" number blending occupancy and spend.
  Rejected.** That is the bug, restated as a feature. Two tracks, two captions,
  one verdict source.
- **R6 — a TTL or turn-count staleness *block* on the orchestrator track between
  spawns. Rejected.** CER-041 → CER-047 already demonstrated in production that a
  TTL cannot answer the cross-session question, and a hard block on every
  un-refreshed turn would re-arm the CER-067 class of un-clearable gate that
  agents were observed forging state to defeat. Coverage (a second measurement
  writer, § C) beats a new block.
- **Editing `hooks/user_prompt_submit.py`, `hooks/pre_tool_use.py`, or any file
  under `hooks/`.** All are protected paths; none needs a change (§ C2). The
  PostToolUse writer's `context_current_tokens_source` stamp in § C6 is the one
  exception that would require a hook edit — if the builder finds it cannot be
  delivered from `context_budget`/`session_state` without touching
  `hooks/post_tool_use.py`, it must report `BUILDER BLOCKED` per
  `builder/procedure.md` rather than editing a protected file, and the PostToolUse
  arm of § C6 defers to a follow-up row.
- **Renaming `context_budget_threshold`, `expected_step_tokens`, or any existing
  orchestrator-track state key.** INFRA-303 (same phase) owns the
  `expected_step_tokens` migration opt-out; a rename here would collide and would
  strand every downstream `state.json`. The new key `story_spend_threshold` is
  additive.
- **CER-106's `context_budget_acknowledged_at` naming defect** (the key stores a
  token count despite the `_at` suffix). Adjacent in subject, but that row is
  owned by the unmerged INFRA-299 branch (§ Requires) and is not touched.
- **Wiring `next-action` to pause between stories.** That is INFRA-316 (Phase 116);
  this story only establishes and documents the track it must consult (§ D4, § F6)
  and edits nothing in phase 116.
- **Building a subagent-window gate.** Named as future work with its requirement
  (a pre-spawn estimate of a builder's own input size, which nothing measures
  today) rather than half-built (§ D3).
- **Wiring a caller for `bump-context-tokens`.** It stays dormant by design
  (§ C7); § C1's measured refresh removes the need.
