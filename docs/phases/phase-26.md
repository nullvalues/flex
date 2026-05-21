# flex — Phase 26: Build loop retry automation + auth policy canonization

← [Phase 25: Backlog remediation and cross-project agent sync](phase-25.md)

## Goal

Two methodology fixes with no interdependency — either can be built independently.

**Build loop auto-retry (INFRA-054):** The Step 3 FAIL branch currently stops the loop
and asks the user on the first reviewer failure. The correct flow is:
attempt 1 FAIL → auto-retry builder; attempt 2 FAIL → auto-invoke loop-breaker;
loop-breaker proposal → single user confirmation point. User is only interrupted
after two automated recovery attempts have been exhausted.

**Auth policy canonization (INFRA-055):** The global `~/.claude/CLAUDE.md` now requires
loading auth policies before speccing any permission-gated feature. Pairmode's
`CLAUDE.build.md` and its template don't encode *when* in the build process to surface
the classification question, and the `spec.json non-negotiables` language in the policies
doesn't map to pairmode's story-file + architecture.md convention. INFRA-055 closes both
gaps so the auth pattern propagates correctly to any pairmode-bootstrapped project.

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-054 | Build loop reviewer-FAIL auto-retry flow | complete |
| INFRA-055 | Auth policy integration in CLAUDE.build.md and pairmode template | complete |

---

### Story INFRA-054 — Build loop reviewer-FAIL auto-retry flow

**Rail:** INFRA
**story_class:** methodology

**Acceptance criterion:** The "If reviewer reports FAIL" branch in CLAUDE.build.md
(and its `.j2` template) is replaced with a three-tier escalation that requires no
user input for the first two failures:

1. **Attempt 1 FAIL** → automatically re-spawn the builder (attempt 2) with the
   original story text plus reviewer findings appended as a `PREVIOUS ATTEMPT FAILED`
   section. No user pause. Increment the per-story attempt counter to 2.
2. **Attempt 2 FAIL** → automatically invoke the loop-breaker (no user pause). Present
   the loop-breaker's proposal to the user with a single binary prompt:
   "proceed" (spawn builder attempt 3 with loop-breaker guidance) or
   "pause" (stop and await user investigation).
3. **Attempt 3 FAIL, or user says "pause" after loop-breaker** → BUILD PAUSED report.
   Stop the build loop.

The standalone `## Loop-breaker` section at the bottom of CLAUDE.build.md is folded into
the Step 3 escalation and removed as a separate section (its content is now embedded).

**Instructions:**

1. In CLAUDE.build.md Step 3 "Handle the result", replace the entire "If reviewer reports
   FAIL (reverted)" block (currently: stop immediately + report + "do not spawn the builder
   again" + "Fix/retry flow" paragraph) with the three-tier escalation below:

   ```
   **If reviewer reports FAIL (reverted):**

   Check the current attempt number for this story.

   **Attempt 1 FAIL — auto-retry:**
   Append the reviewer's findings as a `## PREVIOUS ATTEMPT FAILED` section to the
   original story prompt. Re-spawn the builder (attempt 2) immediately — no user pause.
   Increment the per-story attempt counter to 2.
   After the builder returns, record the attempt and run the guardrail as in Step 1,
   then re-spawn the reviewer (Step 2). The reviewer model re-selects based on the
   updated attempt_number (attempt 2 → opus for code stories).

   **Attempt 2 FAIL — auto loop-breaker:**
   Spawn the `loop-breaker` subagent immediately — no user pause:
     LOOP-BREAKER: [reviewer finding verbatim]
     FILE: [file:line if known, or "unknown"]
     TRIED: [description of attempt 1 and attempt 2 approaches]
   After the loop-breaker responds, present its proposal to the user:

     LOOP-BREAKER — Story [RAIL-NNN]
     Two attempts failed. Proposed alternative:
     [loop-breaker output verbatim]
     Say "proceed" to attempt a third build with this guidance,
     or "pause" to investigate manually.

   Wait for user response.
   - "proceed": spawn the builder (attempt 3) with original story text PLUS loop-breaker
     guidance appended as a `## LOOP-BREAKER GUIDANCE` section.
   - "pause": go to BUILD PAUSED below.

   **Attempt 3 FAIL or user "pause":**

     BUILD PAUSED — Story [RAIL-NNN]
     Reason: [last reviewer's top findings]
     Working tree reverted to HEAD.
     When resolved, say: "Continue building"

   Stop the build loop.
   ```

2. Remove the standalone `## Loop-breaker` section at the bottom of CLAUDE.build.md
   entirely — its content is now embedded in the Step 3 escalation above.

3. Apply the identical changes to `skills/pairmode/templates/CLAUDE.build.md.j2`.

**Tests:** Methodology story — no test file. Verify the revised Step 3 reads coherently
from PASS path through all three FAIL tiers without gaps or contradictions.

---

### Story INFRA-055 — Auth policy integration in pairmode build process

**Rail:** INFRA
**story_class:** methodology

**Acceptance criterion:** `CLAUDE.build.md`, its `.j2` template, and `docs/architecture.md`
explicitly encode the auth policy integration point:

1. CLAUDE.build.md "Before the first build loop" gains a new conditional step (after the
   existing step 7) that states: if the story being built touches authentication, session
   handling, permission checks, or access-controlled resources, answer the classification
   question from `~/.claude/policies/auth-coexistence.md` before proceeding. The answer
   (RBAC / ABAC / both) must be recorded in the phase doc or `docs/architecture.md`.
   Do not build the story until the answer is recorded.

2. `CLAUDE.build.md.j2` receives the same step.

3. `docs/architecture.md` gains a "Auth policy integration" subsection (under Pairmode
   non-negotiables or methodology) that:
   - Points to the three policy files at `~/.claude/policies/`.
   - Maps the policies' `spec.json non-negotiables` language to pairmode's equivalent:
     a `## Non-negotiables` or `## Auth model` section in `architecture.md` or the
     phase doc, naming the auth model and the enforcement layer module before the first
     auth-gated story is built.
   - States that the classification question in `auth-coexistence.md` is the required
     pre-spec gate, not an implementation detail.

**Instructions:**

1. In CLAUDE.build.md "Before the first build loop" section, add after step 7 (the
   DEVELOPER ACTION gate check):

   ```
   8. **Auth check (conditional)** — if this story is auth-gated (touches user
      authentication, session handling, permission checks, role validation, or
      access-controlled resources):
      a. Load `~/.claude/policies/auth-coexistence.md`.
      b. Surface the classification question to the user: RBAC / ABAC / both?
      c. Record the answer in the phase doc or `docs/architecture.md` before building.
         Do not build this story until the classification is recorded.
      If the story is not auth-gated, skip this step.
   ```

2. Apply the same step 8 to `skills/pairmode/templates/CLAUDE.build.md.j2`.

3. In `docs/architecture.md`, add a subsection "Auth policy integration" in the
   Pairmode section. Content:

   - **Policy files:** `~/.claude/policies/auth-rbac.md` (role-based system controls),
     `~/.claude/policies/auth-abac.md` (ownership and content-level access),
     `~/.claude/policies/auth-coexistence.md` (classification question + coexistence
     patterns).
   - **Build loop integration:** Step 8 of "Before the first build loop" in
     `CLAUDE.build.md` gates any auth-gated story on an answered classification question.
   - **Pairmode equivalent of `spec.json non-negotiables`:** The policies require a
     `non_negotiables` entry in the relevant module `spec.json` before the first
     auth-gated story is built. In pairmode-based projects (which use story files +
     `architecture.md` rather than `spec.json`), the equivalent is a dedicated
     `## Auth model` or `## Non-negotiables` section in `architecture.md` or the
     phase doc that names: (a) the chosen auth model (RBAC / ABAC / both),
     (b) the enforcement layer module, and (c) which resource types map to which model
     (for coexistence cases). This section serves as the spec contract that reviewers
     check before accepting any auth-gated story.

**Tests:** Methodology story — no test file. Verify the step 8 reads correctly in context
and the architecture.md subsection is findable and cross-referenced from the right location.

---

Tag: `cp26-build-loop-retry-and-auth-canonization`
