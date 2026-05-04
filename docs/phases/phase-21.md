# anchor — Phase 21: Methodology refinement and companion/pairmode positioning

← [Phase 20: PR readiness — documentation, pipe clarity, contribution packaging](phase-20.md)
→ [Phase 22: Effort tracking](phase-22.md)

## Goal

Phase 21 reflects the methodology improvements that surfaced during cross-project dogfooding
(cora, radar, forqsite) into the canonical pairmode templates so future bootstraps inherit
them, and lands a README/PAIRMODE.md update that makes the companion-vs-pairmode boundary
explicit. This is a documentation- and template-heavy phase — fast, low-risk, no new
runtime surfaces. Effort tracking (Phase 22) and drift detection (Phase 23) build on this
foundation.

Prerequisites: Phase 20 complete and tagged cp20-pr-ready (pr-candidate-v0.1-squashed).
Branched from era2 onto `era3-methodology` so this work does not compound the
already-submitted PR (nraychaudhuri/anchor#3).

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-040 | Companion-vs-pairmode positioning in README and PAIRMODE.md | planned |
| INFRA-026 | Pin reviewer agents to `model: opus` in pairmode templates | planned |
| INFRA-027 | Default reviewer agents to read-only tools `[Read, Grep, Glob, Bash]` | planned |
| INFRA-033 | Document model fallback policy in agent templates | planned |
| LESSON-002 | Capture model upgrade/downgrade pattern as a lesson | planned |
| LESSON-003 | Capture reviewer-as-read-only-Bash pattern as a lesson | planned |

---

### Story INFRA-040 — Companion-vs-pairmode positioning in README and PAIRMODE.md

**Rail:** INFRA (doc story)

**Acceptance criterion:** `README.md` and `docs/pairmode/PAIRMODE.md` make the boundary
between companion and pairmode explicit using the reactive-vs-proactive framing.
Specifically:

1. `README.md` line 14 ("Anchor makes intent persistent") is reframed to acknowledge the
   two layers: "Anchor makes intent persistent in two ways: by recording it as you decide
   (reactive memory) and by requiring it before you build (proactive process)."
2. After the existing "What anchor does" section (around line 34), a new H3 section
   "Reactive memory vs proactive process" is inserted with a comparison table covering:
   when each acts, posture, primary artefact, who writes it, what it prevents, what it
   cannot prevent, and how the two compose.
3. After the table, a "Use companion when / use pairmode when / use both when" guidance
   block answers the implicit reader question.
4. `README.md`'s three-skill table gains a "Posture" column distinguishing
   bootstrap-once vs reactive vs proactive.
5. The build-loop section adds one line: "Pairmode owns this loop. Companion is not
   required to use it; if companion is running, the sidebar will surface the active
   story but does not gate the build."
6. `docs/pairmode/PAIRMODE.md` gains a one-paragraph "Pairmode in relation to companion"
   section after "What pairmode is", so an upstream maintainer doesn't conflate the two.
7. `docs/architecture.md` line ~231 ("Pairmode is a feature being built in this repo")
   is replaced with a fresh "Pairmode and companion: separation of concerns" preamble in
   the Pairmode design section.

**Background (CER finding):** README and PAIRMODE.md frame the two skills as "two layers"
without articulating that they are two *temporal postures* on the same concern (intent
integrity). A reader cannot answer "when do I run which?" from current docs. The
reactive-vs-proactive table this story restores was drafted during the CER and is
reproduced verbatim in the body below for reference.

**Reference table to land in README.md:**

| Dimension | Companion (`/anchor:seed`, `/anchor:companion`) | Pairmode (`/anchor:pairmode`) |
|-----------|-------------------------------------------------|--------------------------------|
| **When it acts** | During the session, reacting to what just happened | Before code is written, and at every commit gate |
| **Posture** | Reactive — observes decisions and drift live | Proactive — fixes intent in writing first, prevents drift |
| **Primary artefact** | `spec.json` per module | `docs/stories/<RAIL>/<RAIL>-NNN.md` and `docs/phases/phase-N.md` |
| **Actor that writes** | Sidebar, after the fact, from the transcript | Developer (story spec) and builder/reviewer subagents |
| **Failure it prevents** | Decision evaporation across sessions; silent contradiction of an earlier choice | Builder hallucinating scope; reviewer-less commits; phase drift |
| **Failure it cannot prevent** | A story that was never specced — companion can only record what was discussed | A decision made mid-story that nobody captures into spec.json |
| **Composition** | Feeds pairmode: spec.json non-negotiables generate the deny list at bootstrap | Feeds companion: `current_story` written into `state.json` so the sidebar surfaces story context |
| **Use it when** | You want institutional memory across sessions and projects | You want a structured build loop and want to specify intent before code |
| **Use both when** | You want intent both *captured live* (companion) and *enforced at the build gate* (pairmode) — the default for serious projects |

**Tests:** `tests/pairmode/test_docs.py` extended:
- README.md contains "reactive" and "proactive" both at least once (positioning is
  present)
- README.md contains a "Posture" column header in the skills table
- README.md remains under 400 lines (previous cap)
- PAIRMODE.md contains "in relation to companion"

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
across **all four** reviewer templates to still work via Bash. A doc note in
`docs/architecture.md` records the two-layer rationale (read-only tools +
pre-reviewer commit discipline).

**Background:** Forqsite (only) restricts reviewer tools. The pattern hasn't
propagated, but the rationale is sound: removing Edit/Write prevents the
reviewer from "fixing" code instead of reverting (a real failure mode), while
preserving Bash keeps git revert/checkout/commit available so the
commit-or-revert contract is unaffected.

**Verification step (must run before commit, expanded per CER finding):**

For each of `reviewer.md.j2`, `intent-reviewer.md.j2`, `loop-breaker.md.j2`,
and `security-auditor.md.j2`:

1. Confirm any commit path uses Bash only (`git add`, `git commit`).
2. Confirm any revert path uses Bash only (`git checkout -- <path>`,
   `git reset --hard HEAD`).
3. Confirm any test invocation uses Bash only.
4. Grep the template prose for any instruction that requires Edit or Write.
   If any: rewrite to use Bash equivalents or surface to the user.
5. For intent-reviewer specifically: confirm it produces *recommendations* the
   orchestrator applies, not edits the agent applies directly.

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

### Story INFRA-033 — Document model fallback policy in agent templates

**Rail:** INFRA

**Acceptance criterion:** Pairmode templates encode a documented fallback policy
for when the preferred model is rate-limited. The policy lives as inline comments
in the agent templates and as a section in `docs/architecture.md`. Bootstrap
renders the policy comments into the project's `.claude/agents/*.md` files so
they're visible to the developer at runtime.

**Background (CER finding):** During the era2 build, the Sonnet-pinned builder hit
an org-level rate limit mid-phase. The session's working response was to *strip*
the model pin from the local agent file (so it would inherit Opus), then continue.
That was an ad-hoc rescue; it left the project in a state where the methodology
intent (Sonnet for compute efficiency) was silently undone with no audit trail.
A documented fallback closes this hole: when Opus is rate-limited, reviewers fall
back to Sonnet (still better than the pre-pin baseline of inheriting); when
Sonnet is rate-limited, builder falls back to Haiku. Never below Haiku — the
reasoning quality cliff is too steep.

**Instructions:**

1. In each agent template, add a YAML comment after the `model:` line:
   - `builder.md.j2`: `# fallback: haiku  (never below)`
   - `reviewer.md.j2`, `intent-reviewer.md.j2`, `loop-breaker.md.j2`,
     `security-auditor.md.j2`: `# fallback: sonnet  (never below)`
2. In `docs/architecture.md`, add a "Model selection and fallback" subsection in
   the Pairmode design section. Document:
   - The role-based pinning rationale (volume → cheap, judgment → opus)
   - The fallback policy (one tier down, never below Haiku)
   - **The procedure when rate-limited:** override the agent's model at call time
     via the Agent tool's `model` parameter rather than editing the template
     file. The template intent stays clean; the override is per-invocation.
3. In `CLAUDE.build.md`, add a one-line note in the build-loop section pointing
   readers at the architecture doc subsection.

**Tests:** Extend `test_templates.py` with assertions that the fallback comment
is present in each affected template and that the architecture doc contains the
"Model selection and fallback" subsection heading.

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
  reviewers=opus, with fallback comments. INFRA-026, INFRA-033 implement this
  in templates; future bootstraps inherit it. Validation comes from Phase 22's
  `pairmode_effort.py models` report — once token-and-PASS-rate data accrues
  per (model, role), the methodology is data-defensible rather than aesthetic.
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

Tag: `cp21-template-methodology`
