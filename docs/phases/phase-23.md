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
| INFRA-044 | Flip reviewer-class templates to sonnet baseline (model rebalance — quick win) | planned |
| LESSON-004 | Capture sonnet-baseline-opus-on-demand rebalance rationale | planned |
| INFRA-043 | Auto-plumb `--phase`, `--rail`, and attempt counter into `record_attempt.py` (CER-015) | planned |
| INFRA-038 | Story frontmatter `source:` field + anchor-as-project for self-drift | planned |
| INFRA-039 | `.pairmode-overrides` integration in drift reports | planned |
| INFRA-031 | Project drift detection — `pairmode_drift_report.py` | planned |
| INFRA-032 | Drift promotion workflow — extend `/anchor:pairmode review` | planned |
| INFRA-037 | Token-evidence ranking in drift promotion | planned |

INFRA-044 + LESSON-004 land first as a token-budget rebalance, captured as a lesson
so the methodology survives compaction. They unblock the user's Sonnet-quota usage
before the rest of Phase 23 builds. Phase 24 (drafted separately) refines this with
data-defensible per-story-class triggers once Phase 22's effort data accrues. Then
INFRA-043 fixes the effort-tracking plumbing that INFRA-037 will rely on.

---

### Story INFRA-044 — Flip reviewer-class templates to sonnet baseline (model rebalance)

**Rail:** INFRA

**Acceptance criterion:** `reviewer.md.j2`, `intent-reviewer.md.j2`, and
`security-auditor.md.j2` carry `model: sonnet` (not `model: opus`). `loop-breaker.md.j2`
remains `model: opus` (loop-breaker fires only on hard cases by definition; the
default IS the upgrade for that role). Each affected template gains an
`# upgrade: opus  (when retry / pre-PR audit / mid-phase pivot)` comment immediately
after `model: sonnet`. `docs/architecture.md` "Model selection and fallback"
subsection is replaced with a "sonnet baseline, opus on demand" framing that
documents the upgrade triggers explicitly. Tests assert the new defaults. Tests pass.

**Background:** Phase 21 codified "judgment work → opus" as if every reviewer pass
were judgment work. In practice most reviews catch nothing (most builders produce
correct work) and the per-story reviewer task is mechanical: diff matches spec,
tests pass, checklist OK, commit. Sonnet handles that fine. Where Opus actually
earns its cost is the edge cases — a story on its second build attempt, a pre-PR
audit, a mid-phase spec pivot. Those should be explicit upgrade triggers, not
the default.

**Decision recorded here:** Flip the methodology to "sonnet baseline, opus on
demand." Loop-breaker stays opus because by the time it fires the case is already
hard. Builder stays sonnet (no change). The upgrade triggers documented below
are the contract; the orchestrator (or future tooling) is responsible for
enforcing them.

**Upgrade triggers (must be in the architecture doc):**

- **Story retry**: any story on its second or later build attempt — the
  reviewer missed something at sonnet last time, so use opus this time.
- **Pre-PR audit**: the final phase before a PR leaves the repo gets opus
  reviewers across the board (this is the cold-eyes check that costs the
  least to upgrade).
- **Mid-phase spec pivot**: when a story spec changes after the phase has
  begun (rare but real — INFRA-005 in Phase 18 was specced mid-phase to
  fix a security finding), the next intent-reviewer at the next checkpoint
  uses opus.
- **Production code touched in the phase**: if any Python code in `skills/`,
  `hooks/`, or other production paths changes, security-auditor uses opus.
  Doc-only / lesson-only / template-only phases use sonnet.

**Instructions:**

1. In each of the three templates, change the `model:` value:
   - `skills/pairmode/templates/agents/reviewer.md.j2`: `model: sonnet`
   - `skills/pairmode/templates/agents/intent-reviewer.md.j2`: `model: sonnet`
   - `skills/pairmode/templates/agents/security-auditor.md.j2`: `model: sonnet`
2. Add an inline upgrade comment after the model line in each. Format
   matching the existing fallback comment pattern from INFRA-033:
   `# upgrade: opus  (when retry / pre-PR audit / mid-phase pivot)`
   For `security-auditor`: `# upgrade: opus  (when phase touched production code)`
3. Do NOT modify `loop-breaker.md.j2` (stays opus) or `builder.md.j2`
   (stays sonnet) or `reconstruction-agent.md.j2` (separate role).
4. In `docs/architecture.md`, replace the existing "Model selection and
   fallback" subsection with the new "Model selection: sonnet baseline,
   opus on demand" framing. Document each upgrade trigger explicitly with
   the rationale ("most reviews catch nothing; opus is overhead for the
   common case"). Cross-reference Phase 24 as the proper data-defensible
   refinement.
5. In `tests/pairmode/test_templates.py`, update assertions to match the new
   defaults. The existing `TestReviewerClassAgentsPinnedToOpus` class needs
   to become `TestReviewerClassAgentsSonnetBaseline` (or similar) with
   inverted assertions.

**Tests:**

- `reviewer.md.j2` rendered/raw frontmatter has `model: sonnet`
- Same for `intent-reviewer.md.j2` and `security-auditor.md.j2`
- `loop-breaker.md.j2` retains `model: opus` (regression check — must not
  flip this one)
- `builder.md.j2` retains `model: sonnet`
- Each affected template contains the `# upgrade: opus` comment
- `docs/architecture.md` contains a section heading matching the new
  framing (e.g. "sonnet baseline" or "opus on demand")

---

### Story LESSON-004 — Capture sonnet-baseline-opus-on-demand rebalance rationale

**Rail:** LESSON

**Acceptance criterion:** A new lesson entry (id auto-assigned by lesson_utils)
captures the model-rebalance methodology so future audits and bootstraps inherit
the framing.

**Lesson content (all five fields):**

- **trigger**: User observed total opus:sonnet usage running at roughly 3:2,
  exceeding the Opus quota relative to the Sonnet quota. Methodology had Phase
  21 baseline of "reviewer-class agents → opus, builder → sonnet" applied
  uniformly across all reviews.
- **problem**: Treating every review as judgment work overcommits opus on
  routine cases. Most reviewer passes catch nothing (most builders produce
  correct work). Per-story reviewer work is mechanical (diff matches spec,
  tests pass, checklist OK, commit) and within Sonnet's capability.
  Intent-reviewer and security-auditor at routine checkpoints are similarly
  mechanical. The result: opus consumption disproportionate to the value
  it adds, leaving Sonnet quota underutilised.
- **learning**: Model selection should be **sonnet baseline, opus on demand**,
  not the inverse. Reserve opus for explicit upgrade triggers where the
  judgment edge actually matters: story retries (sonnet missed it the first
  time), pre-PR audits (last cold-eyes before code leaves the repo),
  mid-phase spec pivots (the spec itself moved), and production-code phases
  for security-auditor. Loop-breaker stays opus permanently because by the
  time it fires the case is by definition hard.
- **methodology_change**: Pairmode templates flip reviewer / intent-reviewer
  / security-auditor defaults from opus to sonnet, with inline upgrade
  comments documenting the triggers. INFRA-044 implements this in templates.
  Phase 24 refines the upgrade triggers into data-defensible per-story-class
  rules once Phase 22's effort tracking has produced enough data to validate
  the rebalance with actual token-and-PASS-rate per (model, role) numbers.
- **affects**: `pairmode-builder-reviewer-loop`, applies to any pairmode project.

---

### Story INFRA-043 — Auto-plumb `--phase`, `--rail`, and attempt counter into `record_attempt.py` (CER-015)

**Rail:** INFRA

**Acceptance criterion:** `record_attempt.py` accepts a `--story-file <path>` flag
that auto-extracts `phase` and `rail` from the story file's frontmatter (using
`schema_validator._parse_frontmatter`). A new `effort_db.next_attempt_number()`
helper queries the database for the highest existing `attempt_number` for a
given `(story_id, agent_role)` pair and returns the next value, eliminating the
orchestrator's need to remember per-story retry counts. CLAUDE.build.md and the
template are updated to use the new flags. Tests confirm both the helper and
the auto-extraction. CER-015 marked RESOLVED.

**Background (CER-015):** Phase 22 wired `record_attempt.py` into the build loop
but the orchestrator currently substitutes `--phase`, `--rail`, and
`--attempt-number` values by hand. That works as long as the orchestrator
remembers; one slip and rows land with NULL `phase`/`rail` (breaking rollup
reports) or `attempt_number=1` for what is really a retry (breaking the rework
signal — the entire spec-quality use case Phase 22 was built for). A small
helper closes the gap permanently.

**Instructions:**

1. **`--story-file` auto-extraction in `record_attempt.py`:**
   - Add a new Click option `--story-file <path>`. When present, parse the
     frontmatter with the canonical `schema_validator._parse_frontmatter`,
     read `phase`, `rail`, and `id` (use `id` as `--story-id` if not also
     given on the command line), populate the corresponding kwargs.
   - Existing `--phase`, `--rail`, `--story-id` flags still work and override
     anything pulled from the story file. The story-file path is the cheap
     default; explicit flags remain the escape hatch.
   - Error handling: if the story file can't be parsed or required fields
     are missing, fall back to the explicit-flag path with a stderr warning.

2. **`effort_db.next_attempt_number()` helper:**
   - Signature: `next_attempt_number(db_path: Path, *, story_id: str,
     agent_role: str) -> int`
   - Query: `SELECT MAX(attempt_number) FROM attempts WHERE story_id=? AND agent_role=?`.
     Return `1` if no rows; `max+1` otherwise.
   - Add a corresponding `--auto-attempt` flag to `record_attempt.py` that
     calls this helper and uses the result for `attempt_number`. Mutually
     exclusive with `--attempt-number`.

3. **Update `CLAUDE.build.md` and `skills/pairmode/templates/CLAUDE.build.md.j2`:**
   - Replace the hardcoded `--phase N --rail RAIL --attempt-number 1` literals
     in the example invocations with `--story-file docs/stories/<RAIL>/<RAIL>-NNN.md
     --auto-attempt`.
   - Add a one-line note: "The story file's frontmatter supplies phase and rail;
     `--auto-attempt` queries the effort database for the next retry count.
     The orchestrator no longer needs to track these by hand."

4. **Update `docs/cer/backlog.md`:**
   - Mark CER-015 row resolution as `**RESOLVED** Phase 23 INFRA-043`.

**Tests:** Extend `tests/pairmode/test_record_attempt.py`:
- `--story-file` populates phase, rail, story_id from a fixture story file
- Explicit `--phase` overrides story-file value
- Missing/malformed story file: stderr warning, falls back to explicit flags
- `--auto-attempt` returns 1 when no prior rows exist
- `--auto-attempt` returns max+1 when prior rows exist for same (story_id, agent_role)
- `--auto-attempt` and `--attempt-number` together: error (mutually exclusive)

Extend `tests/pairmode/test_effort_db.py`:
- `next_attempt_number` returns 1 for a fresh `(story_id, agent_role)`
- Returns max+1 across multiple existing rows
- Filters correctly by both `story_id` and `agent_role`

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
