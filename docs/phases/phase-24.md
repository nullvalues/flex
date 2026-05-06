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
| LESSON-005 | Capture data-defensible methodology pattern as a lesson | planned |

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

**Instructions:**

1. Add `validate-rebalance` subcommand to `pairmode_effort.py`. Output is
   plain-text columns by default; `--json` for machine-parseable.
2. Document the recommendation logic in architecture.md.
3. The report does NOT auto-update model selection — it surfaces evidence
   for the developer to revise the helpers from INFRA-047/048. Methodology
   changes still require story specs.

**Tests:** `tests/pairmode/test_validate_rebalance.py` with fixture databases
covering each recommendation category.

---

### Story LESSON-005 — Capture data-defensible methodology pattern

**Rail:** LESSON

**Acceptance criterion:** A lesson entry captures the broader pattern this
phase exemplifies — methodology decisions ship as intuition first, then
become falsifiable once instrumentation accrues data, then formalize once
data either confirms or revises the original intuition.

**Lesson content:**

- **trigger**: Phase 23 INFRA-044 / LESSON-004 documented model upgrade
  triggers in prose. Phase 24 made them structural and data-defensible.
- **problem**: Methodology decisions in prose are unauditable in either
  direction. "Most reviews catch nothing" was either true or false — no
  way to know without measurement. Without measurement, the next person
  to question the methodology has only the same intuitions to argue with.
- **learning**: A methodology lifecycle worth codifying:
  1. Ship the change under intuition (Phase 23 INFRA-044)
  2. Capture the rationale as a lesson (LESSON-004)
  3. Instrument the relevant signal (Phase 22 effort tracking)
  4. Wait for data to accrue (≥ 2 phases of post-change builds)
  5. Validate the methodology against the data (Phase 24 INFRA-049)
  6. Formalize, refine, or reverse based on findings (Phase 24
     INFRA-045-048; future phases revise as data demands)
- **methodology_change**: Pairmode adopts this lifecycle for any future
  intuition-driven methodology changes. The lesson template gets a new
  optional `validation_phase` field pointing at the phase that confirms or
  revises the lesson.
- **affects**: pairmode-methodology-evolution, applies broadly.

---

Tag: `cp24-data-defensible-methodology`
