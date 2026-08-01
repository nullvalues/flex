# Cold-Eyes Review — Build-Loop Harness Integrity (post Phase 116 / cp-116)

**Date:** 2026-08-01
**Reviewed at:** `main` @ `e112fb9a` (pre-checkpoint-tag), promoted as `cp-116`
**Reviewers:** two independent, blind cold-eyes passes — one on the `fable` model, one on `opus` —
each given an identical prompt and no visibility into the other's findings or this session's prior
conversation. Coordinated and cross-checked by the operator's orchestrator session.
**Subject:** the pairmode build-loop harness itself — `skills/pairmode/scripts/next_action.py`
(resolver), `flex_build.py` (worktree/checkpoint CLI), `CLAUDE.build.md` +
`skills/pairmode/templates/CLAUDE.build.md.j2` (orchestrator contract), the attempt-recording
pipeline (`subagent_transcript.py`, `effort_db.py`), `model_selector.py`, and the
checkpoint-adjacent gates (`cer.py`, `era_transition.py`, `phase_new.py`, `index_integrity.py`).
Observability (`skills/observability/`) was explicitly out of scope this pass.

**Trigger:** three real bugs surfaced only by live builds during Phase 116 (INFRA-316's forbidden
context-track wiring, INFRA-318's twice-rejected orphaned dispatch, INFRA-329's miscounted audit
evidence) raised the concern that the harness's own test suite verifies each build stage in
isolation but never the hand-offs between stages — i.e. that "PASS" from the reviewer loop this
session might not mean what it claims. This review was commissioned to check that concern before
formally closing era 004.

---

## 1. Method

Each reviewer was given the same scope, the same six-category hunting lens (written-never-read,
required-never-written, duplicate state, half-implementation, loop-transition flaws, and — the
core question — whether the test suite actually exercises stage-to-stage sequences or only
per-function units), and told to read source directly rather than trust docstrings, trace multiple
field lifecycles end to end, and rate their own confidence per finding. Neither reviewer was shown
the other's output. The operator then cross-checked the two independently, kept findings verbatim
where they agreed (treated as high-confidence corroboration), and flagged single-source findings
by which reviewer produced them and how well evidenced they were (live-log/live-repro vs. static
trace).

---

## 2. Corroborated findings (found independently by both reviewers)

### CRITICAL

**F1 — The FAIL escalation ladder does not reliably advance.**
Both reviewers traced this to the same root cause via different entry points: `discard-story-worktree`
(`flex_build.py:4783`) clears the `current_stories` stamp before the next poll (per
`CLAUDE.build.md:25`'s prescribed order), and the SubagentStop sweep's late-bump guard
(`_story_accepts_late_bump`, `subagent_transcript.py`) requires that stamp — or an already-recorded
counter entry — to authorize a FAIL bump. Since the PostToolUse bump path is itself acknowledged in
the codebase's own comment as structurally unreachable for the live async spawn shape, and
`reconcile_one` (the primary SubagentStop path since INFRA-298) deliberately never bumps, the sweep
is the only remaining writer — and it's gated shut in exactly the story-just-discarded case.
**Opus found live evidence in this repo's own `.companion/effort_recording.log`: 8
`bump:late-fail` vs 8 `skip:late-bump-blocked` — roughly a 50% ladder-advance failure rate**, most
recently on INFRA-330 (2026-07-31T05:52).
Failure scenario: a story whose builder/reviewer cycle FAILs on its first attempt can loop at
attempt 1 forever — never reaching Row 5 (retry-upgrade), Row 6 (loop-breaker), or Row 7 (operator
pause).

### HIGH

**F2 — INFRA-316's `pause-context` feature (built and reviewer-PASSed this session) is
structurally unreachable.**
Both reviewers found the identical bug via the identical trace: `infer_position` can only produce
the `OUTCOME_PASS` state Row 8 requires when `_has_story_commit(next_story_id, git_log)` is true —
but `next_story_id` comes from `find_next_story`, which unconditionally *skips* any story for which
that same function already returned true. The two calls use the same git log, microseconds apart.
`OUTCOME_PASS` cannot occur from a live `infer_position` call; only hand-constructed test fixtures
produce it. Everything downstream — `PAUSE_CONTEXT`, `_check_context_pause`, the schema-version
bump — is dead code that shipped past review.

**F3 — INFRA-333's model-selector wiring is incomplete for 2 of 3 newly-added roles.**
Both reviewers independently found: Row 9 (`next_action.py`) hardcodes `model=None` for
`checkpoint-security` and `checkpoint-intent` — only `checkpoint-docs` actually got the INFRA-333
wiring. `select_security_auditor_model`/`select_intent_reviewer_model` are reachable only via CLI
subcommands `CLAUDE.build.md` never calls. Both `.claude/agents/security-auditor.md` and
`intent-reviewer.md` document a model-override contract that does not exist in the live dispatch
path.

**F4 — `meta["gate_worker_model"]` is written and never read.**
Both reviewers found this at the identical file/line (`next_action.py`, INFRA-333's Row 4b). The
selector result is computed and stored in advisory `meta`, but `CLAUDE.build.md`'s dispatch line
reads only `a.model` (contractually `None` for this action) — no code path anywhere consumes the
advisory field. Same orphaned-producer shape as F2/F3 and as this session's twice-rejected
INFRA-318 attempts. Opus's own framing of this finding: "the honest conclusion is that the
selector shouldn't have been called at all, not that its result should be parked in advisory
meta" — the review takes no position between removing the call and giving it a real consumer;
either is a legitimate fix direction, and the choice is left to whichever story addresses it.

**F5 — `CLAUDE.build.md` and its `.j2` template have drifted in both directions.**
Both reviewers found: the live file has three `ACTION_SUBAGENT_TYPE` dispatch entries
(`checkpoint-docs`, `spawn-gate-worker`, `spawn-spec-writer`, from INFRA-325/331) that the template
lacks; the template has an `intent_review=` Build-standards key and `pause-context`/
`record-intent-review` handling prose that the live file lacks entirely. Each Phase 116 story
edited exactly one copy. Consequence: a project bootstrapped fresh today cannot dispatch three
actions the resolver already emits live; and if flex's own `CLAUDE.build.md` ever opts into
`intent_review=`, nothing in it explains what to do with the resulting action.

**F6 — `parse_worker_outcome`'s JSON-extraction regex cannot match a result containing braces.**
Both reviewers independently found the identical line: `subagent_transcript.py`'s non-nesting
`\{[^{}]*\}` pattern. A BUILD-RESULT/REVIEW-RESULT whose `reason`/`findings`/`fail_cause` string
quotes a code snippet containing `{...}` (routine reviewer prose in this codebase) fails to parse
as a single object — outcome stays `None`, feeding directly into F1.

### Confirmed test-coverage gap (the reviewers' own core question)

Both reviewers, independently, concluded the same thing in detail: **every build stage
(worktree creation, builder dispatch, reviewer dispatch, checkpoint steps) has solid isolated test
coverage, but no test drives a realistic multi-stage sequence with real state evolving between
calls.** Concretely:
- Attempt-counter test fixtures write a shape (`{"story_id":…, "attempt_count":…}`) the real
  writer (`flex_build.py`'s keyed `{"stories": {...}}` map) cannot produce — most resolver tests
  exercise only a legacy read branch the live loop never writes.
- Story-frontmatter test fixtures omit `title:`/`touches:` and use `status: planned` where the
  real scaffolder (`story_new.py`) writes `status: draft` — so no test exercises a realistic
  permissions artifact or `current_stories` entry shape.
- The checkpoint chain (writer → `infer_position` → `resolve_next_action`) is covered by three
  separate test files, each exercising a different two-of-three link — no test spans all three.
- `test_e2e_roundtrip.py`'s name is misleading — it covers bootstrap→audit→sync doc drift only,
  never a story, a worktree, an attempt counter, or `next-action`.
- **F1 above is the concrete proof this gap is load-bearing**: a real integration test driving
  `next-action → create-story-worktree → (FAIL) → discard-story-worktree → next-action` and
  asserting the second poll returns attempt 2 does not exist today, and would fail if it did.

---

## 3. Opus-only findings (not raised by fable, but well evidenced)

### CRITICAL

**F7 — `cer.py`'s backlog-append path can corrupt unrelated rows; reproduced against a live copy.**
`append_finding`'s writer does a full parse → re-render → whole-file overwrite using a naive
`\|`-split regex, while the reader half (`_scan_rows_in_sections`) correctly uses
`table_utils.split_table_row`. Opus reproduced a real corruption: one append truncated several
unrelated rows' `**RESOLVED …**` annotations at their first escaped pipe (routine in this file —
`Task\|Agent` appears verbatim in resolved rows), flipping the CER Do-Now gate from clear to
blocked with no way to see what the destroyed annotation used to say. The 5-line/0-entry parse
warning only catches total failure, not partial corruption.

**F8 — `spawn-gate-worker`'s verdict has no consumer anywhere; a livelock shipped in Phase 116
(INFRA-331).**
`CLAUDE.build.md`'s dispatch branch spawns the gate-worker and re-polls, with no instruction to
route its stdout anywhere. `parse_worker_verdict_json`/`route_gate_verdict` have zero non-test
callers. The gate-worker's own procedure document asserts the orchestrator feeds its output to the
parser — it does not. Since the gate's inputs (frontmatter, phase manifest) don't change between
polls, the same action re-emits indefinitely.

### HIGH

**F9 — The checkpoint build gate is decorative; measured empirically.**
`_run_build_gate_subprocess` runs with a 60-second timeout and returns `True` (green) on any
timeout or exception. Opus measured the actual suite at 175 seconds — nearly 3× the timeout — so
the gate always "passes" without the suite ever completing. The only real test-verification
happening at checkpoint time is the reviewer's own manual run.

**F10 — Spec-writer's elaborated output is never committed before the story worktree branches off
`HEAD`.** This matches a pre-existing operator-memory item ("commit spec before worktree —
worktree snapshots git HEAD, not the working tree"), confirming the harness itself still has no
enforcement for a gap the operator already had to learn about live. Row 2 dispatches the
spec-writer to the main worktree; nothing commits its output; `create-story-worktree` branches from
`HEAD`; the builder's worktree contains the pre-elaboration stub.

**F11 — Duplicate attempt rows from two independent live writers, with contradictory data.**
A legacy CLI path (`record_attempt.py`) and the hook-driven path
(`subagent_transcript.record_attempt_from_transcript`) both write rows for what should be the same
spawn. Opus found concrete live examples (e.g. row 473 vs 475 for the same
story/role/attempt-number triple: 33,380 tokens/PASS vs. 117,347 tokens/FAIL) — 12 such duplicate
triples exist in flex's own `effort.db`.

**F12 — Context-session scoping mismatch.** INFRA-316's Row-8 context check hand-assembles
arguments from the flat top-level `state.json` mirror, not the session-scoped values the
equivalent PreToolUse hook check uses — moot today only because F2 makes Row 8 unreachable, but
latent if F2 is fixed without also fixing this.

**F13 — Two disagreeing definitions of "phase complete," and the checkpoint's own step ordering
lets the weaker one decide.** The resolver's phase-completion guard reads only the phase doc's
Stories table; the deferral gate at `checkpoint-tag` reads story-file frontmatter and requires a
formal `## Deferred stories` section — but `CLAUDE.build.md`'s mandated order calls
`checkpoint-tag` directly after the checkpoint-report, without re-polling `next-action`, so the
weaker table-only check is what actually let three checkpoint workers run before the stronger gate
has a chance to refuse.

---

## 4. Fable-only findings

**F14 (MEDIUM–HIGH, split rating between reviewers) — `attempt_counter.json`'s writers are
unlocked read-modify-write, unlike every `state.json` writer.** Both reviewers flagged this; fable
rated it HIGH given the declared parallel-build model (Phase 109), opus rated it MEDIUM as a known,
documented limitation. Two concurrent bumps (or a merge-clear racing a sibling story's bump) can
silently lose an update.

**F15 (MEDIUM) — A double-FAIL-in-one-cycle (builder self-reports FAIL, reviewer then also FAILs
the same worktree) can double-bump the counter**, collapsing the 3-strike ladder to effectively 1.5
cycles. Fable rated this medium confidence, dependent on whether the orchestrator always spawns the
reviewer even after a builder FAIL (the documented pseudocode does).

---

## 5. Medium/Low findings (both reviewers, various severities — routed to backlog, not this phase)

- `check-index`'s four graph-invariant checks have zero automated callers anywhere in the loop —
  corroborates the already-open CER-136 (`merge-story-worktree` never flips story status), which
  this session hit live twice (Phase 115 and Phase 116 checkpoints both required a manual status
  sync before `checkpoint-tag` would proceed).
- `cer.py gate`/`groom` CLI subcommands are dead surfaces whose own docstrings claim they're wired
  into the checkpoint sequence — they are not; the live gate imports the shared function directly.
- Several effort.db columns (`tool_uses`, `duration_ms` on the primary path, `story_class`/
  `model_selection_reason` outside the legacy CLI writer) have no live writer or no live reader.
- Era-ledger flip failures are silently swallowed (`_flip_era_ledger_row`'s "not_found" return is
  computed and discarded); the era-transition disposition gate fails open on any unparseable
  ledger.
- The `docs/phases/index.md` `Tag` column is never mechanically written — hand-maintained since
  phase 106, silently absent for phases 106–116 despite `cp-106`…`cp-116` all existing.
- Multiple docstrings actively misdescribe current wiring (e.g. `cmd_next_action`'s own docstring
  still says "not wired into the live CLAUDE.build.md loop" — it is the loop driver).
- Test-suite environment coupling to git commit-signing config (137 tests fail headless without
  `commit.gpgsign=false`) — same class of finding as the just-filed CER-146 (a different
  environment-coupled test, `flex-harness` directory-name substring matching).
- A parallel-build resolution ambiguity in `record-checkpoint-step` without `--phase-key` degrades
  to a silent no-op key rather than a real gate.

---

## 6. Where the reviewers disagreed with themselves (self-correction, noted for transparency)

Opus's own sub-audits initially rated a permissions-artifact/worktree-shadowing risk as HIGH; on
tracing further, opus downgraded it to LOW after confirming the artifact is written only to the
main checkout and never reaches a builder's worktree — noted here so the downgrade isn't lost.
Opus also explicitly confirmed the `/mnt/work/flex` → `/mnt/work/flex-harness` `pairmode_scripts_dir`
indirection is intentional design (the release-channel dogfood pattern), not a finding — ruling out
a plausible-looking false positive before it reached this document.

---

## 7. The through-line

Four of the five most serious findings (F1, F2, F3/F4, F8) share one shape: **a mechanism gets
built, unit-tested in isolation, documented as wired, reviewer-PASSed, and merged — with no
consumer at the exact seam where it would matter in the live loop.** This is not a one-off; it
recurred at least three times in this session alone before this review even started (INFRA-316,
INFRA-318 ×2). The reviewers agree on why it keeps recurring: nothing in the test suite spans a
real stage transition, so "wired" has only ever been asserted by a comment or an isolated unit
test, never verified by a test that watches the actual hand-off happen. Per both reviewers, the
single highest-leverage remediation is one integration test driving
`next-action → create-story-worktree → (FAIL) → discard-story-worktree → next-action` and asserting
the second poll returns attempt 2 — a test that fails today and would independently have caught
F1, F2, F8, and F10.

---

## 8. Disposition

CRITICAL and HIGH findings (F1–F13) are scoped into a new phase (Phase 117 — see
`docs/phases/phase-117.md`) rather than the backlog, on the reasoning that the harness's core
promise — reliable attempt escalation — is measurably broken in this repo's own live log, two of
the broken features were built and reviewer-PASSed in the session immediately preceding this
review, and a data-corrupting bug exists in the tooling this same checkpoint sequence depends on.
MEDIUM/LOW findings (§5) are routed to the CER Do Later / Do Much Later backlog per the project's
living-backlog policy.

*End of review.*
