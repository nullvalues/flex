# anchor — Phase 24: Data-defensible model rebalance refinement

← [Phase 23: Drift detection and promotion workflow](phase-23.md)

## Goal

Phase 24 refines the "sonnet baseline, opus on demand" methodology that Phase 23
landed (INFRA-044, LESSON-004) into a data-defensible per-story-class system.
The interim flip in Phase 23 was the right move under budget pressure, but
its upgrade triggers ("story retry", "pre-PR audit", etc.) are documented in
prose and enforced by the orchestrator's memory of them. Phase 24 makes the
triggers structural — readable from story frontmatter and phase declarations,
queryable from the effort database, and validated by the actual token-and-
PASS-rate data Phase 22 has been collecting.

The unifying observation: by the time Phase 24 builds, the effort database
will have months of (model, role, outcome, tokens) data. The methodology
intuition that motivated the rebalance ("most reviews catch nothing") becomes
a falsifiable claim. If the data shows builder-on-Sonnet has a higher retry
rate than builder-on-Opus would, the methodology adjusts. If sonnet reviewers
on doc-only stories have the same PASS rate as opus reviewers, the rebalance
is confirmed and the upgrade triggers can be tightened further.

This is the phase where the methodology stops being aesthetic and starts
being defensible.

Prerequisites: Phase 23 complete and tagged cp23-drift-detection. Effort
database accruing across at least 2 phases of post-INFRA-044 builds, ideally
including at least one mid-phase spec pivot (a triggering case that
exercises the upgrade path).

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-045 | `story_class` frontmatter field — code / doc / lesson / methodology | planned |
| INFRA-046 | `phase_class` field — production / docs-only / pre-pr | planned |
| INFRA-047 | Reviewer model selection by `story_class` (replaces hardcoded triggers) | planned |
| INFRA-048 | Checkpoint-agent model selection by `phase_class` | planned |
| INFRA-049 | Effort-data validation report — does the rebalance hold? | planned |
| INFRA-050 | Pre-story model evaluation step — auto-downgrade and prompted upgrade | planned |
| LESSON-005 | Capture data-defensible methodology pattern as a lesson | planned |
| INFRA-045 | story_class frontmatter field — code / doc / lesson / methodology | draft |
| INFRA-046 | phase_class field — production / docs-only / pre-pr | draft |
| INFRA-047 | Reviewer model selection by story_class (replaces hardcoded triggers) | draft |
| INFRA-048 | Checkpoint-agent model selection by phase_class | draft |
| INFRA-049 | Effort-data validation report — does the rebalance hold? | draft |
| INFRA-050 | Pre-story model evaluation step — auto-downgrade and prompted upgrade | draft |
| LESSON-005 | Capture data-defensible methodology pattern as a lesson | draft |

---

### Story INFRA-045 — `story_class` frontmatter field

**Rail:** INFRA

**Acceptance criterion:** Story spec frontmatter accepts an optional
`story_class` field with allowed values `code`, `doc`, `lesson`, `methodology`.
`schema_validator` validates the field. Stories without the field default to
`code` (the conservative choice — opus reviewer on retry). Existing stories
remain valid; the field is purely additive.

**Background:** Phase 23's INFRA-044 documented upgrade triggers like "doc-only
phases use sonnet" but had no structural way to mark a story as doc-only. The
orchestrator (or human) had to remember. `story_class` makes the distinction
machine-readable so reviewer-model selection (INFRA-047) can be deterministic.

**Field semantics:**

- `code`: production code in `skills/`, `hooks/`, etc. Reviewer pass at sonnet
  baseline; upgrade to opus on retry. Default if field absent.
- `doc`: documentation only — `README.md`, `docs/`, prose changes. Reviewer
  stays sonnet even on retry. Doc reviews don't get harder with retries.
- `lesson`: append-only lesson entries. Reviewer stays sonnet — lessons are
  high-structure JSON with a programmatic invariant check.
- `methodology`: template / scaffold / orchestrator-instruction changes.
  Reviewer stays sonnet baseline; upgrade if any other story in the same
  phase touches `code`.

**Instructions:**

1. Update `skills/pairmode/scripts/schema_validator.py` to accept and validate
   `story_class`. Allowed values listed above; default `code` if absent.
2. Update `story_new.py` to optionally accept `--story-class` and write it
   into generated story frontmatter.
3. Document the field in `docs/architecture.md` under a new "Story
   classification" subsection.

**Tests:** `tests/pairmode/test_schema_validator.py` extended for `story_class`
validation; `tests/pairmode/test_story_new.py` extended for the new flag.

---

### Story INFRA-046 — `phase_class` field

**Rail:** INFRA

**Acceptance criterion:** Phase doc frontmatter accepts an optional
`phase_class` field with allowed values `production`, `docs-only`, `pre-pr`.
Phases without the field default to `production`. Drift report and intent
review can read the field and adjust their checkpoint-agent model selection
accordingly (INFRA-048).

**Background:** Same logic as INFRA-045 but at phase scope. Phase 21 was
docs-only (templates + lessons); Phase 22 was production. The pre-PR audit
phase that Phase 20 served as is its own class. Marking these structurally
lets the checkpoint-agent model upgrade decisions be deterministic.

**Field semantics:**

- `production`: at least one story touched production code. Checkpoint
  security-auditor uses opus.
- `docs-only`: no story touched production code. Checkpoint security-auditor
  stays sonnet.
- `pre-pr`: the phase is a final-pass audit before code leaves the repo. All
  checkpoint agents (intent-reviewer, security-auditor) upgrade to opus.

**Instructions:**

1. Update `phase_new.py` to optionally accept `--phase-class`.
2. Add validation to whatever helper reads phase frontmatter today (likely
   `schema_validator` or `phase_resolver`).
3. Document in `docs/architecture.md` Story-classification subsection.

**Tests:** `tests/pairmode/test_phase_new.py` extended.

---

### Story INFRA-047 — Reviewer model selection by `story_class`

**Rail:** INFRA

**Acceptance criterion:** When the orchestrator spawns a reviewer for a story,
the reviewer's model is determined by `(story_class, attempt_number)` rather
than the prose-documented triggers from Phase 23. The selection is implemented
as a small helper that takes `(story_class, attempt_number)` and returns
`"sonnet"` or `"opus"`. The CLAUDE.build.md(.j2) example invocations call the
helper rather than hardcoding model values.

**Selection table:**

| story_class | attempt_number=1 | attempt_number≥2 |
|---|---|---|
| code | sonnet | opus |
| doc | sonnet | sonnet |
| lesson | sonnet | sonnet |
| methodology | sonnet | sonnet (upgrade if same-phase code story exists) |

The "same-phase code story" rule for methodology means the helper takes an
optional `phase_id` parameter and checks the phase's story manifest.

**Instructions:**

1. Add `select_reviewer_model(story_class, attempt_number, phase_id=None) -> str`
   helper to `skills/pairmode/scripts/effort_db.py` or a new
   `skills/pairmode/scripts/model_selector.py`.
2. Update `CLAUDE.build.md` and the template's reviewer-spawn step to call
   this helper and pass the result to the Agent tool's `model` parameter.
3. Replace the prose-documented upgrade triggers in `docs/architecture.md`
   "Model selection: sonnet baseline" subsection with a forward reference
   to the helper, plus the selection table above. Keep the rationale text;
   replace the implementation description.

**Tests:** `tests/pairmode/test_model_selector.py` covering every cell of
the selection table plus the same-phase-code-story rule.

---

### Story INFRA-048 — Checkpoint-agent model selection by `phase_class`

**Rail:** INFRA

**Acceptance criterion:** When the orchestrator runs the checkpoint sequence
(intent-reviewer + security-auditor + tag), the model for each checkpoint
agent is determined by `phase_class`. The selection table is part of the
same `select_*_model` helper family from INFRA-047.

**Selection table:**

| phase_class | intent-reviewer | security-auditor |
|---|---|---|
| production | sonnet | opus |
| docs-only | sonnet | sonnet |
| pre-pr | opus | opus |

**Instructions:**

1. Add `select_intent_reviewer_model(phase_class) -> str` and
   `select_security_auditor_model(phase_class) -> str` helpers.
2. Update `CLAUDE.build.md` checkpoint-sequence step to call them.
3. Document in architecture.md.

**Tests:** Extend `test_model_selector.py`.

---

### Story INFRA-049 — Effort-data validation report

**Rail:** INFRA

**Acceptance criterion:** A new `pairmode_effort.py validate-rebalance`
subcommand queries the effort database for evidence supporting (or refuting)
the sonnet-baseline-opus-on-demand methodology. Output: token cost and
PASS rate per (story_class, agent_role, model) cell, with a recommendation
column ("rebalance confirmed", "consider upgrading", "consider further
downgrade") based on configurable thresholds.

**Background:** This is the falsifiability story. The Phase 23 rebalance was
intuition-driven. Phase 24's whole rationale is making it data-defensible.
Without a report that surfaces the data, the methodology can't be revised
in either direction with confidence.

**Recommendation logic:**

For each (story_class, agent_role, model) cell:
- If sample size < 5: "insufficient data"
- If PASS rate ≥ 95% AND median tokens within 1.5× of opus equivalent (where
  applicable): "rebalance confirmed for this cell"
- If PASS rate < 80%: "consider upgrading this cell to opus"
- If sonnet PASS rate ≥ opus PASS rate AND tokens lower: "consider further
  downgrade" (e.g. sonnet reviewer on what was opus)

Thresholds configurable via flags or `state["effort_validation_thresholds"]`.

**Decision-quality section (requires INFRA-050 data):**

A second section of the report surfaces model selection decision quality — how
well the pre-story evaluation is performing over time. For each
`model_selection_reason` value (`auto-downgrade`, `auto-baseline`,
`prompted-upgrade`, `user-override`):

- Frequency count and percentage of total stories
- PASS-on-first-attempt rate per path
- Average cost per path (tokens × pricing)
- Efficiency ratio: PASS rate / avg cost (normalised to the `auto-baseline`
  cell as 1.0)

The efficiency ratio is the core metric for the value proposition: a path with
ratio > 1.0 is delivering better outcome per token than the baseline. A path
with ratio < 1.0 is either over-spending (upgrade too aggressive) or
under-spending (downgrade causing retries). This section is omitted if the
`model_selection_reason` column is absent from the database (pre-INFRA-050
builds).

**Instructions:**

1. Add `validate-rebalance` subcommand to `pairmode_effort.py`. Output is
   plain-text columns by default; `--json` for machine-parseable.
2. Document the recommendation logic and efficiency ratio in architecture.md.
3. The report does NOT auto-update model selection — it surfaces evidence
   for the developer to revise the helpers from INFRA-047/048/050. Methodology
   changes still require story specs.

**Tests:** `tests/pairmode/test_validate_rebalance.py` with fixture databases
covering each recommendation category, plus fixture databases that include
`model_selection_reason` data to exercise the decision-quality section.

---

### Story INFRA-050 — Pre-story model evaluation step

**Rail:** INFRA

**Acceptance criterion:** `CLAUDE.build.md` and its Jinja2 template gain a
"Model evaluation" step that the orchestrator runs before spawning the builder
for each story. The step reads `story_class` and `primary_files` from the
story spec and produces a model selection decision without spawning any agent.
Downgrades (haiku for doc/lesson stories) are applied automatically. Upgrades
(opus for code stories touching protected files or with ≥ 3 primary files) are
presented to the user as a prompt before the builder is spawned. The user can
accept or override. If the user overrides to a lower model, the decision is
recorded and the builder is spawned with that model.

**Motivation:** The sonnet rate limit is shared across all projects running
concurrently. Doc and lesson stories on any project are fully adequate on haiku,
so routing them there frees sonnet capacity for code stories. Opus builder
upgrades are high-cost and should require explicit user intent — but when a
story signals high risk (protected files, broad scope), surfacing the option
before spawning is better than reacting after a retry.

**Decision table:**

| story_class | complexity signal | builder model | selection reason | action |
|---|---|---|---|---|
| `doc` | any | haiku | `auto-downgrade` | auto (no prompt) |
| `lesson` | any | haiku | `auto-downgrade` | auto (no prompt) |
| `methodology` | any | sonnet | `auto-baseline` | auto |
| `code` | < 3 primary_files, no protected file | sonnet | `auto-baseline` | auto |
| `code` | ≥ 3 primary_files OR protected file in touches | opus | `prompted-upgrade` | **prompt user** |
| *(any)* | user overrides model downward | *(user choice)* | `user-override` | recorded |

Protected files are those listed in `CLAUDE.md` § Protected files and the
project-specific deny list in `.claude/settings.json`.

**Schema additions (effort DB):**

INFRA-050 owns the migration that adds two columns to the `attempts` table:

- `story_class TEXT` — copied from story frontmatter at record time; `NULL`
  for pre-INFRA-045 builds (defaulting to `code` in queries).
- `model_selection_reason TEXT` — one of `auto-downgrade`, `auto-baseline`,
  `prompted-upgrade`, `user-override`; `NULL` for pre-INFRA-050 builds.

These columns are the raw material for INFRA-049's decision-quality section.
Without them, the efficiency ratio cannot be computed.

**Instructions:**

1. Add migration to `effort_db.py`: `ALTER TABLE attempts ADD COLUMN
   story_class TEXT` and `ALTER TABLE attempts ADD COLUMN
   model_selection_reason TEXT`. Use `IF NOT EXISTS` guard for idempotency on
   existing databases.
2. Update `record_attempt.py` to accept `--story-class` and
   `--model-selection-reason` flags and write them to the DB.
3. Add `select_builder_model(story_class, primary_files, protected_files)
   -> (model: str, reason: str)` helper to `skills/pairmode/scripts/model_selector.py`
   (alongside the reviewer/checkpoint selectors from INFRA-047/048).
4. Add a `## Model evaluation` section to `CLAUDE.build.md` between "Before the
   first build loop" and "Build loop". The section documents the decision table,
   the prompt text for upgrades, and the instruction to pass `--story-class` and
   `--model-selection-reason` to `record_attempt.py` on each builder invocation.
5. Add the same section to `skills/pairmode/templates/CLAUDE.build.md.j2`.
6. Document the decision table and reason values in `docs/architecture.md` under
   the "Model selection: sonnet baseline, opus on demand" subsection.
7. The orchestrator prompt text when an upgrade is suggested:
   ```
   MODEL SUGGESTION — Story [ID]
   story_class: code
   Signal: [e.g. "touches protected file src/middleware.ts" or "4 primary_files"]
   Suggested builder model: opus (baseline: sonnet)
   Reason: high-scope code story; opus reduces rework risk
   Say "upgrade" to use opus, or "continue" to proceed with sonnet.
   ```

**Dependencies:** INFRA-045 (`story_class` frontmatter) must be built first so
the evaluation can read a machine-readable class. Before INFRA-045 is built,
the orchestrator infers class from story text (presence of `.py`/`.ts` file
paths in `primary_files` implies `code`; `docs/` paths only implies `doc`).

**Tests:** `tests/pairmode/test_model_selector.py` extended with cases covering
each row of the decision table, including the `user-override` reason path.
`tests/pairmode/test_effort_db.py` extended with migration idempotency test and
round-trip test for the two new columns via `record_attempt.py`.

---

### Story LESSON-005 — Capture data-defensible methodology pattern

**Rail:** LESSON

**Acceptance criterion:** A lesson entry captures the broader pattern this
phase exemplifies — methodology decisions ship as intuition first, then
become falsifiable once instrumentation accrues data, then formalize once
data either confirms or revises the original intuition.

**Lesson content:**

- **trigger**: Phase 23 INFRA-044 / LESSON-004 documented model upgrade
  triggers in prose. Phase 24 made them structural and data-defensible,
  adding per-story model evaluation (INFRA-050) and an efficiency-ratio
  report (INFRA-049) to close the feedback loop.
- **problem**: Methodology decisions in prose are unauditable in either
  direction. "Most reviews catch nothing" was either true or false — no
  way to know without measurement. Without measurement, the next person
  to question the methodology has only the same intuitions to argue with.
  The same applies to cost: "haiku is fine for doc stories" is a claim
  that needs a retry-rate check to validate, not just intuition.
- **value framing**: The goal is not minimum cost (that sacrifices quality
  and causes rework) and not maximum intelligence (that wastes budget on
  trivial work). It is best outcome per token — optimising the efficiency
  ratio: PASS rate / cost. This framing is stable even as model prices and
  capabilities shift; the thresholds in the decision table are the thing
  that changes, not the objective.
- **learning**: A methodology lifecycle worth codifying:
  1. Ship the change under intuition (Phase 23 INFRA-044)
  2. Capture the rationale as a lesson (LESSON-004)
  3. Instrument the relevant signal (Phase 22 effort tracking)
  4. Wait for data to accrue (≥ 2 phases of post-change builds)
  5. Validate the methodology against the data (Phase 24 INFRA-049)
  6. Formalize, refine, or reverse based on findings (Phase 24
     INFRA-045-050; future phases revise as data demands)
  The efficiency ratio is the durable metric: as models evolve and prices
  change, re-run the report; if the ratio for a decision path shifts,
  update the decision table thresholds in a new story.
- **methodology_change**: Pairmode adopts this lifecycle for any future
  intuition-driven methodology changes. The lesson template gets a new
  optional `validation_phase` field pointing at the phase that confirms or
  revises the lesson.
- **affects**: pairmode-methodology-evolution, applies broadly.

---

Tag: `cp24-data-defensible-methodology`
