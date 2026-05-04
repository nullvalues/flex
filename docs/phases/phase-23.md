# anchor — Phase 23: Project drift detection and promotion workflow

← [Phase 22: Per-story compute-effort tracking](phase-22.md)

## Goal

Phase 23 builds the feedback loop that closes the dogfooding cycle: pairmode-bootstrapped
projects report their drift back to anchor; anchor identifies cross-project convergence and
promotes it from project-side improvement to canonical methodology. The unifying observation:
convergent change across multiple pairmode projects is a methodology signal. Today there is
no mechanism to surface that signal, so improvements stay trapped in the projects that
discovered them.

This phase intentionally lands after Phase 22 so it can use Phase 22's effort-tracking data
as one of the inputs for "is this divergence worth promoting?" — a methodology candidate
that demonstrably reduces tokens or rework across projects is a stronger signal than one
that's just prettier. INFRA-037 implements that wiring directly so the cost data isn't
decorative.

Two foundational stories (INFRA-038 frontmatter discipline + anchor-as-self-drift, and
INFRA-039 `.pairmode-overrides` integration) land before the main detector and promoter to
prevent infinite-recursion and re-prompting issues identified by the CER.

Prerequisites: Phase 22 complete and tagged cp22-effort-tracking, with effort-tracking data
accruing in at least one project.

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-038 | Story frontmatter `source:` field + anchor-as-project for self-drift | planned |
| INFRA-039 | `.pairmode-overrides` integration in drift reports | planned |
| INFRA-031 | Project drift detection — `pairmode_drift_report.py` | planned |
| INFRA-032 | Drift promotion workflow — extend `/anchor:pairmode review` | planned |
| INFRA-037 | Token-evidence ranking in drift promotion | planned |

---

### Story INFRA-038 — Story frontmatter `source:` field + anchor-as-project for self-drift

**Rail:** INFRA

**Acceptance criterion:** All story spec frontmatter supports a new optional `source:`
field that distinguishes human-written stories (default, absent) from drift-promotion
generated stories (`source: drift-promotion`). `pairmode_drift_report.py` (built in
INFRA-031) is documented and tested to run from `/mnt/work/anchor` itself, treating
anchor as a project for drift purposes. Stories tagged `source: drift-promotion` are
suppressed from subsequent drift reports to prevent infinite recursion.

**Background (CER finding):** anchor dogfoods its own pairmode templates — `.claude/agents/`,
`CLAUDE.build.md`, `docs/architecture.md` are anchor's *own use* of templates the same
templates apply to. Without a marker, drift detection generates a story for promotion;
that story file then becomes part of anchor's diff against templates next time; rinse,
repeat. The fix is one frontmatter field plus a documented suppression rule.

**Instructions:**

1. Update `skills/pairmode/scripts/schema_validator.py` to accept and validate the
   optional `source:` field (string, allowed values: `drift-promotion`). Story files
   without the field are valid (default human-authored).
2. Update `skills/pairmode/scripts/story_resolver.py` and any drift-related script
   to filter out `source: drift-promotion` entries when scanning for divergence.
3. Document anchor-as-project explicitly in `docs/architecture.md` — running
   `pairmode_drift_report.py` from `/mnt/work/anchor` is supported and surfaces
   the same signal a downstream project would.
4. Add a verification test that runs the future drift-report against anchor itself
   and confirms the output is meaningful (no infinite recursion, no spurious
   re-flagging of `source: drift-promotion` stories).

**Tests:** `tests/pairmode/test_schema_validator.py` extended with `source:` field
acceptance; `tests/pairmode/test_drift_self.py` — fixture run against a synthesized
anchor-shaped tree, assert recursion-suppression works.

---

### Story INFRA-039 — `.pairmode-overrides` integration in drift reports

**Rail:** INFRA

**Acceptance criterion:** `pairmode_drift_report.py` (INFRA-031) and the
promotion-workflow review (INFRA-032) honor the existing `.pairmode-overrides`
file format. Sections declared in `.pairmode-overrides` are suppressed from
drift reports the same way `audit.py` already suppresses INCONSISTENT findings.
A user who has marked `.claude/settings.json:permissions.deny` as a
project-specific override doesn't get re-prompted on every drift pass.

**Background (CER finding):** `.pairmode-overrides` was introduced in Phase 18 to
suppress audit noise on intentional divergence. Drift detection without override
support would re-classify the same intentional divergence on every run, training
the user to ignore the prompts. That's the opposite of what we want.

**Instructions:**

1. Extract the `.pairmode-overrides` parser from `skills/pairmode/scripts/audit.py`
   (currently the `_load_overrides()` helper) into `skills/pairmode/scripts/overrides.py`
   as a shared utility.
2. Update `audit.py` to import from the shared module (no behaviour change).
3. Drift report (INFRA-031) and promotion review (INFRA-032) consume the same parser
   and apply the same suppression logic to deltas keyed by `(file, section)`.
4. Document the override format and behaviour in the drift detection section of
   `docs/architecture.md`.

**Tests:** `tests/pairmode/test_overrides.py` — extracted parser unit tests;
`tests/pairmode/test_audit.py` regression check (audit behaviour unchanged after the
extraction).

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

Sections declared in `.pairmode-overrides` are filtered out (per INFRA-039). Stories
with `source: drift-promotion` frontmatter are filtered out (per INFRA-038). The
report is JSON-serializable so it can be ingested by the anchor-side review flow
(INFRA-032).

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
3. Apply override suppression and `source: drift-promotion` suppression.
4. Emit a structured report:
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
5. The `classification` field is left null — the user fills it during review.

**Tests:** `tests/pairmode/test_drift_report.py` with fixture project trees
covering MISSING / EXTRA / DIFFERENT cases, override-suppression, and
drift-promotion-suppression.

---

### Story INFRA-032 — Drift promotion workflow

**Rail:** INFRA

**Acceptance criterion:** `/anchor:pairmode review` is extended to read drift
reports from one or more projects, group similar deltas across projects, and
prompt the user to classify each cluster as one of:

- **PROJECT_INTENT** — divergence is intentional and project-specific. Recorded
  in `.pairmode-overrides` of the affected project (or pointed at) so future
  drift reports suppress it.
- **POLICY_DRIFT** — project is out of date. Recommend running
  `/anchor:pairmode sync` in that project.
- **METHODOLOGY_CANDIDATE** — convergent improvement across projects. Promotes
  to a pairmode template change. Generates a story spec in the anchor repo
  (or appends to an existing phase) tagged with `source: drift-promotion`
  (per INFRA-038), plus a lesson entry.

**Instructions:**

1. Add a `--from-drift-reports <dir>` flag to `/anchor:pairmode review`.
2. Cluster deltas by `(file, section)` across reports.
3. If a delta appears in N projects with the same value, surface it as a
   strong candidate for METHODOLOGY_CANDIDATE.
4. Walk the user through each cluster with AskUserQuestion-style prompts.
5. For PROJECT_INTENT: append to `.pairmode-overrides` of each affected
   project (or print recommended additions if the project is read-only from
   the anchor side).
6. For POLICY_DRIFT: print a recommended `pairmode sync` command per project.
7. For METHODOLOGY_CANDIDATE: draft a story spec in
   `docs/stories/INFRA/INFRA-NNN.md` (assigned by phase_new helpers, with
   `source: drift-promotion` frontmatter) plus a lesson entry, ready for the
   user to incorporate into the next phase.

**Tests:** `tests/pairmode/test_drift_promotion.py` with fixture drift
reports, mocked AskUserQuestion responses, assertions on output files
written and `source:` frontmatter present.

---

### Story INFRA-037 — Token-evidence ranking in drift promotion

**Rail:** INFRA

**Acceptance criterion:** Drift promotion (INFRA-032) consumes effort-tracking
data when ranking METHODOLOGY_CANDIDATE clusters. A divergence that demonstrably
reduces tokens or rework across projects ranks above a cosmetic divergence. The
ranking is visible to the user in the AskUserQuestion prompt.

**Background (CER finding):** Phase 22 sells itself on effort data being a
tiebreaker for "is this divergence worth promoting?" but INFRA-032 doesn't
actually query the data. Without this story, the cost data is decorative in
this phase. Adding the ranking is small (one query per cluster) and high-impact
(it's the entire reason Phase 22 lands first).

**Instructions:**

1. For each METHODOLOGY_CANDIDATE cluster, query each affected project's
   effort database for the average tokens-per-attempt over the last N days
   (configurable, default 30).
2. Compute a `cost_evidence` score per cluster: positive if projects with the
   divergence show lower median tokens, negative if higher, neutral if no
   data. The score is a normalised difference, not a raw token count.
3. In the user prompt, show the score and a one-line justification ("Projects
   with this divergence have ~12% lower median builder tokens over the last
   30 days") above each cluster.
4. Document the methodology in `docs/architecture.md` so the user understands
   what the score means and what its limits are (small samples, confounds).

**Tests:** `tests/pairmode/test_drift_evidence.py` with synthesized effort
databases across multiple fixture projects, assert the ranking matches the
seeded data and that absent data degrades gracefully (no crash, neutral score).

---

Tag: `cp23-drift-detection`
