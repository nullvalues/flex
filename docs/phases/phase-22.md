# anchor — Phase 22: Project drift detection and promotion workflow

← [Phase 21: Methodology refinement and cost visibility](phase-21.md)

## Goal

Phase 22 builds the feedback loop that closes the dogfooding cycle: pairmode-bootstrapped
projects report their drift back to anchor; anchor identifies cross-project convergence and
promotes it from project-side improvement to canonical methodology. The unifying observation:
convergent change across multiple pairmode projects is a methodology signal. Today there is
no mechanism to surface that signal, so improvements stay trapped in the projects that
discovered them.

This phase intentionally lands after Phase 21 so it can use Phase 21's cost-tracking data as
one of the inputs for "is this divergence worth promoting?" — a methodology candidate that
demonstrably reduces cost or rework across projects is a stronger signal than one that's just
prettier.

Prerequisites: Phase 21 complete and tagged cp21-methodology-refinement, with cost-tracking
data accruing in at least one project.

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-031 | Project drift detection — `pairmode_drift_report.py` | planned |
| INFRA-032 | Drift promotion workflow — extend `/anchor:pairmode review` to ingest drift reports | planned |

---

### Story INFRA-031 — Project drift detection — `pairmode_drift_report.py`

**Rail:** INFRA

**Acceptance criterion:** A CLI at
`skills/pairmode/scripts/pairmode_drift_report.py` runs in any pairmode-bootstrapped
project, compares its current state to the canonical pairmode templates, and
produces a structured report classifying each delta as one of:

- **MISSING** — file/section in canonical, absent in project.
- **EXTRA** — file/section in project, absent in canonical.
- **DIFFERENT** — file/section present on both sides but content differs.

The report is JSON-serializable so it can be ingested by the anchor-side review
flow (INFRA-032).

**Differences from existing `audit.py`:** `audit.py` audits drift *into* a
project (canon → project: what should sync change). `drift_report.py` audits
drift *out of* a project (project → canon: what divergence exists, with the
question "is this a bug, an intentional pivot, or a candidate improvement?").
The same comparator code can power both directions; the framing and output
format differ.

**Instructions:**

1. Walk a configurable set of canonical artefacts: `.claude/agents/*.md`,
   `.claude/settings.json` (deny rules), `CLAUDE.md`, `CLAUDE.build.md`,
   `docs/architecture.md` template-derived sections.
2. For each, render the canonical template against the project's context and
   diff against what's actually in the project.
3. Emit a structured report:
   ```json
   {
     "project": "...",
     "pairmode_version": "...",
     "deltas": [
       {"file": ".claude/agents/reviewer.md", "kind": "DIFFERENT",
        "section": "frontmatter.tools", "canonical": "...", "actual": "...",
        "classification": null}
     ]
   }
   ```
4. The `classification` field is left null — the user fills it during review.

**Tests:** `tests/pairmode/test_drift_report.py` with fixture project trees
covering MISSING / EXTRA / DIFFERENT cases.

---

### Story INFRA-032 — Drift promotion workflow

**Rail:** INFRA

**Acceptance criterion:** `/anchor:pairmode review` is extended to read drift
reports from one or more projects, group similar deltas across projects, and
prompt the user to classify each cluster as one of:

- **PROJECT_INTENT** — divergence is intentional and project-specific. No
  action; recorded for future audits to suppress.
- **POLICY_DRIFT** — project is out of date. Recommend running
  `/anchor:pairmode sync` in that project.
- **METHODOLOGY_CANDIDATE** — convergent improvement across projects. Promote
  to a pairmode template change. Generates a story spec
  in the anchor repo (or appends to an existing phase) and a lesson entry.

**Instructions:**

1. Add a `--from-drift-reports <dir>` flag to `/anchor:pairmode review`.
2. Cluster deltas by file+section across reports.
3. If a delta appears in N projects with the same value, surface it as a
   strong candidate for METHODOLOGY_CANDIDATE.
4. Walk the user through each cluster with AskUserQuestion-style prompts.
5. For PROJECT_INTENT: write to `lessons/drift_overrides.json` (new file,
   project-keyed, suppresses re-prompting).
6. For POLICY_DRIFT: print a recommended `pairmode sync` command per project.
7. For METHODOLOGY_CANDIDATE: draft a story spec in
   `docs/stories/INFRA/INFRA-NNN.md` (assigned by phase_new helpers) plus a
   lesson entry, ready for the user to incorporate into the next phase.

**Note:** This is a meta-tooling story. The drift-promotion flow itself
becomes evidence for future drift reports — recursion is intentional.

**Tests:** `tests/pairmode/test_drift_promotion.py` with fixture drift
reports, mocked AskUserQuestion responses, assertions on output files
written.

---

Tag: `cp22-drift-detection`
