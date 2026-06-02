---
era: "001"
---

# flex — Phase 29: Project drift detection and promotion workflow

← [Phase 28: CER backlog remediation (LOW items)](phase-28.md)

**Parent phase:** Phase 23 (deferred 2026-05-08 — picks up INFRA-038, -039, -031, -032, -037)

## Goal

Build the feedback loop that closes the dogfooding cycle: pairmode-bootstrapped
projects surface convergent improvements back to flex, which promotes them from
project-side discoveries into canonical methodology. Convergent change across
multiple projects is a methodology signal — this phase makes that signal actionable.

Phase 23 designed this arc but pivoted to Phase 24 after landing INFRA-044. The pivot
was correct: the model-rebalance result needed data-defensible backing before it could
be trusted, and that work (Phases 24–28) built the foundation these stories depend on:

- Effort tracking (Phase 22) is fully operational in `effort.db`
- `sync-agents` (Phase 25) propagates template changes to existing projects
- `record_attempt.py --story-file` (Phase 25) enriches effort rows with story context
- CER backlog clear (Phase 28), no security debt to carry forward

The original Phase 23 ordering stands: two foundational stories (INFRA-063 `source:`
field, INFRA-064 overrides integration) land before the main detector and promoter to
prevent infinite-recursion and re-prompting on flex's own promoted stories.

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-063 | Story frontmatter `source:` field — track drift-promoted vs flex-native stories | complete |
| INFRA-065 | Project drift detection — `pairmode_drift_report.py` | complete |
| INFRA-064 | `.pairmode-overrides` integration in drift reports | complete |
| INFRA-066 | Drift promotion workflow — extend `pairmode review` | complete |
| INFRA-067 | Token-evidence ranking in drift promotion | complete |

---

### Story INFRA-063 — Story frontmatter `source:` field

**Rail:** INFRA | **story_class:** code

**Acceptance criterion:** Story files may carry an optional `source: <string>` field in
frontmatter. `schema_validator.py` accepts (but does not require) the field. `story_new.py`
accepts an optional `--source` flag; when provided, `source:` is written to frontmatter
after `story_class`; when absent, the field is omitted entirely. When the drift promotion
workflow (INFRA-066) creates a story from a project-side discovery, it sets `source:
<project-slug>` automatically — this lets flex skip auditing promoted stories as
"canonical drift" against the project they came from.

**Instructions:**

1. In `schema_validator.py`, add `source` as an optional string field in the story
   frontmatter schema. No validation of the value beyond being a non-empty string when
   present.

2. In `story_new.py`, add `--source` as an optional string argument (default None). When
   provided, write `source: <value>` to the generated frontmatter after `story_class`.
   When absent, omit the field.

3. In `docs/architecture.md`, add `source` to the story frontmatter field table as
   optional, with a note: "set by drift promotion to record the originating project."

**Tests:** `tests/pairmode/test_schema_validator.py` — assert `source` is accepted when
present and that its absence is also valid. `tests/pairmode/test_story_new.py` — assert
`--source` writes the field; omitting it produces no `source:` key in the generated file.

---

### Story INFRA-064 — `.pairmode-overrides` integration in drift reports

**Rail:** INFRA | **story_class:** code

**Acceptance criterion:** `pairmode_drift_report.py` (INFRA-065) reads `.pairmode-overrides`
at the project root before classifying any section. Sections declared there are classified
as `INTENTIONAL` rather than `DRIFT` or `EXTRA` in the report output, and are excluded from
the convergence candidates list. The report shows: "Intentional (declared in
.pairmode-overrides): N sections."

**Note:** AUDIT-001 (Phase 18) added `.pairmode-overrides` support to `audit.py` and
`sync.py`. This story only wires the existing file format into the new drift report;
no changes to the override file format or audit/sync behaviour.

**Instructions:**

1. Read the existing `.pairmode-overrides` parsing logic in `audit.py` to understand the
   file format. Extract or reuse the parser rather than re-implementing it.

2. In `pairmode_drift_report.py`, after loading comparison data for a project, read
   `.pairmode-overrides` (if present). For each classified DRIFT or EXTRA section, check
   whether it appears in the declared overrides; if so, reclassify as INTENTIONAL and
   exclude from convergence candidates.

3. Include an INTENTIONAL count in both text and JSON output formats.

**Tests:** `tests/pairmode/test_drift_report.py` — fixture project with a `.pairmode-overrides`
file declaring one divergent section. Assert that section appears as INTENTIONAL, not DRIFT,
and does not appear in convergence candidates.

---

### Story INFRA-065 — Project drift detection — `pairmode_drift_report.py`

**Rail:** INFRA | **story_class:** code

**Acceptance criterion:** `skills/pairmode/scripts/pairmode_drift_report.py` exists as a
Click CLI. Running `pairmode drift-report --projects <path> [<path>...]` compares each
project's `CLAUDE.build.md` and `.claude/agents/` against flex's canonical templates and
reports per-project: `MISSING` (in template, not in project), `EXTRA` (in project, not in
template), `DRIFT` (present in both but diverged), `INTENTIONAL` (declared in
`.pairmode-overrides`). With `--convergent`, it surfaces patterns appearing as the same drift
in 2+ projects as convergence candidates. Supports `--output text|json`.

**Instructions:**

1. Create `skills/pairmode/scripts/pairmode_drift_report.py`. Structure:
   - `drift_report(project_dirs, convergent, output_format)` — core function
   - CLI entry point via Click: `pairmode drift-report --projects ... [--convergent] [--output text|json]`

2. For each project:
   - Load the project's `CLAUDE.build.md` and compare section-by-section against
     `skills/pairmode/templates/CLAUDE.build.md.j2` rendered with the project's state.
   - Load each agent file from `.claude/agents/` and compare against the matching template
     in `skills/pairmode/templates/agents/`.
   - Classify each difference. Apply `.pairmode-overrides` (INFRA-064 wires this in).

3. With `--convergent`: group DRIFT items across all projects. Any drift item appearing
   in 2+ projects with matching content is a convergence candidate. Surface it with a
   project list and count.

4. Text output: one block per project, then a convergence candidates section. JSON output:
   `{"projects": [...], "convergence_candidates": [...]}`.

5. Add `depth_guard` and `resolve().relative_to()` containment on all project dir arguments,
   consistent with the guard discipline applied in other pairmode entry points.

**Tests:** `tests/pairmode/test_drift_report.py` — fixture projects with known MISSING/EXTRA/
DRIFT/INTENTIONAL sections. Assert correct classification. Assert `--convergent` identifies
shared drift across 2 fixture projects but not unique drift.

---

### Story INFRA-066 — Drift promotion workflow — extend `pairmode review`

**Rail:** INFRA | **story_class:** code

**Acceptance criterion:** After its existing lesson review step, `pairmode review` runs
`pairmode_drift_report.py --convergent` against the list of paths in
`.companion/state.json["registered_projects"]` (if present). If convergence candidates are
found, it surfaces each one interactively:

```
CONVERGENCE CANDIDATE — [section/file]
Appears in: project-a, project-b, project-c
Drift:
  [diff excerpt]
Promote to canonical? [y/n/skip]
```

On `y`: calls `story_new.py --source <origin-project>` to create a draft story file with a
TODO acceptance criterion. Prints the story path. On `n` or `skip`: records the rejection
pattern so it is not re-prompted in future reviews.

**Instructions:**

1. In `.companion/state.json`, add support for a `registered_projects` key (list of absolute
   paths). `bootstrap.py` does not need to set it — it is opt-in. Document it in
   `docs/architecture.md`.

2. In `lesson_review.py` (the script behind `pairmode review`), add a drift-promotion step
   after the lesson review section. If `state.json["registered_projects"]` is absent or
   empty, skip with a note: "No registered projects — drift detection skipped."

3. Call `pairmode_drift_report.py --convergent --output json`. Parse the JSON. For each
   convergence candidate, present the interactive decision.

4. On promotion: call `story_new.py` with `--source <origin-project>`, title derived from
   the section/file name, story_class `code`. Print the story path for the user to complete.

5. On rejection: append the pattern identifier to a `.pairmode-drift-rejected` file at the
   flex root so it is excluded from future `--convergent` output.

**Tests:** `tests/pairmode/test_lesson_review.py` — mock `drift_report` JSON output; assert
promotion creates a story file with `source:` set; assert rejection writes to
`.pairmode-drift-rejected`. Assert empty registered_projects skips without error.

---

### Story INFRA-067 — Token-evidence ranking in drift promotion

**Rail:** INFRA | **story_class:** code

**Acceptance criterion:** When INFRA-066 displays convergence candidates, each is annotated
with a token-evidence score computed from `effort.db` across registered projects. The score
and a one-line justification (e.g., "Projects with this pattern show ~12% lower median
builder tokens") appear above each promotion prompt. If effort data is absent or insufficient
(fewer than 5 story attempts covering the pattern), the score shows as "insufficient data"
and the candidate is still surfaced. Score computation lives in
`skills/pairmode/scripts/drift_evidence.py`.

**Instructions:**

1. Create `skills/pairmode/scripts/drift_evidence.py` with:
   - `score_convergence_candidate(project_dirs, pattern_id)` — queries each project's
     `effort.db` for story attempts in sections matching the pattern; computes median builder
     tokens. Returns `(score: float | None, justification: str)`. Returns `(None, "insufficient
     data")` when fewer than 5 attempts are found.
   - Score is a normalised value (0–1) where higher = stronger token-efficiency evidence.
     Methodology: median builder tokens for stories *with* the pattern vs. *without*,
     normalised by total attempts. Document limits (small samples, confounds) in a docstring.

2. In `pairmode_drift_report.py`'s `--convergent` JSON output, call
   `score_convergence_candidate` for each candidate and include `score` and `justification`
   fields.

3. In INFRA-066's promotion display, show the score line above the diff excerpt.

4. In `docs/architecture.md`, document the scoring methodology and its limits under a
   "Drift evidence scoring" subsection.

**Tests:** `tests/pairmode/test_drift_evidence.py` — synthesized `effort.db` fixtures across
multiple projects; assert ranking matches seeded data; assert fewer than 5 attempts returns
`(None, "insufficient data")`; assert no crash on absent or empty databases.

---

Tag: `cp29-drift-detection-and-promotion`
