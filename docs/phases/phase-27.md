# anchor — Phase 27: Auth check per-story placement fix

← [Phase 26: Build loop retry automation + auth policy canonization](phase-26.md)

## Goal

INFRA-055 placed the auth check (Step 8) in "Before the first build loop" — a
phase-level section that fires once at session start. This means a phase with
mixed auth and non-auth stories only checks auth classification on the first
story; subsequent auth-gated stories later in the same phase are not gated.

Move the auth check to the per-story pre-flight — between "Model evaluation" and
"Step 1 — Spawn the builder" — so every story gets the check independently.
Remove Step 8 from "Before the first build loop" and update the architecture.md
reference accordingly.

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-056 | Move auth check from phase pre-flight to per-story pre-flight | planned |

---

### Story INFRA-056 — Move auth check from phase pre-flight to per-story pre-flight

**Rail:** INFRA
**story_class:** methodology

**Acceptance criterion:** The auth check in `CLAUDE.build.md` (and its `.j2` template)
moves from "Before the first build loop" (phase-level, runs once) to a new section
between "Model evaluation" and "Step 1 — Spawn the builder" (per-story, runs on every
story). The check text is otherwise unchanged. `docs/architecture.md` is updated to
reflect the new placement.

**Instructions:**

1. In `CLAUDE.build.md`, remove step 8 from the "Before the first build loop" section
   (currently the last step in that section, lines referencing "Auth check (conditional)").
   The section should end at step 7 (the DEVELOPER ACTION gate check) as before.

2. Between the "## Model evaluation" section and "## Build loop (repeat for each story)",
   add a new section:

   ```
   ## Auth check (conditional — per story)

   Run this check **once per story**, after model evaluation, before spawning the builder.

   If this story is auth-gated (touches user authentication, session handling, permission
   checks, role validation, or access-controlled resources):

   a. Load `~/.claude/policies/auth-coexistence.md`.
   b. Surface the classification question to the user: RBAC / ABAC / both?
   c. Record the answer in the phase doc or `docs/architecture.md` before building.
      Do not build this story until the classification is recorded.

   If the story is not auth-gated, skip this section.
   ```

3. Apply the same changes to `skills/pairmode/templates/CLAUDE.build.md.j2`.

4. In `docs/architecture.md`, update the "Auth policy integration" subsection's
   **Build loop integration** bullet to say "between the Model evaluation section and
   Step 1" rather than "Step 8 of 'Before the first build loop'":

   Change:
   > **Build loop integration:** Step 8 of "Before the first build loop" in
   > `CLAUDE.build.md` gates any auth-gated story on an answered classification question.

   To:
   > **Build loop integration:** A dedicated per-story auth check section between
   > "Model evaluation" and "Step 1 — Spawn the builder" in `CLAUDE.build.md` gates
   > every auth-gated story on an answered classification question, regardless of
   > where it falls in the phase.

**Tests:** Methodology story — no test file. Verify the auth check no longer appears
in "Before the first build loop" and does appear between model evaluation and the
build loop. Confirm that a test in `tests/pairmode/test_templates.py` referencing
the auth check text (if any) still passes.

---

Tag: `cp27-auth-check-per-story-placement`
