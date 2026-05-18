# Anchor Methodology Lessons

This file is auto-generated from `lessons.json`. Edit `lessons.json` directly
or use `/anchor:pairmode lesson` to capture a new lesson.

## L001 — Ran audit against cora — a project with pairmode scaffold but no pairmode_context.json
**Date:** 2026-04-20
**Status:** applied
**Learning:** When audit detects no pairmode_context.json, it should emit a prominent warning: 'No pairmode_context.json found — template body comparison will show false INCONSISTENT for all variable-bearing sections. Bootstrap this project with /anchor:pairmode to fix.' MISSING and EXTRA findings remain reliable; INCONSISTENT findings require a context file to be meaningful.

## L002 — Ran audit against radar and forqsite — projects with pairmode scaffold
**Date:** 2026-04-20
**Status:** applied
**Learning:** The _split_sections output uses '---' as section keys in audit output. These entries are hard to interpret. Either: (a) skip separator-keyed sections from INCONSISTENT comparison since --- separators carry no semantic content, or (b) display the surrounding context (what section comes before/after) when reporting --- inconsistencies.

## L003 — Bootstrap dogfood on anchor — re-running after bug fixes
**Date:** 2026-04-21
**Status:** applied
**Learning:** For mature projects, templates are a starting point, not a replacement. Files that already exist should be skipped by default (same as CLAUDE.md/CLAUDE.build.md), or bootstrap should warn before overwriting hand-authored content.

## L004 — Bootstrap dogfood — builder.md Python standards section
**Date:** 2026-04-21
**Status:** applied
**Learning:** Template variables should be scoped to their semantic slot. build_command belongs in the build-gate section only; the Python standards section should hardcode 'uv run'.

## L005 — Bootstrap dogfood — reviewer.md checklist from spec non-negotiables
**Date:** 2026-04-21
**Status:** applied
**Learning:** Non-negotiables are constraints, not checklist item names. The reviewer checklist needs human-authored label + short action question, not raw spec text. checklist_deriver should either produce module-scoped labels (e.g. 'companion-skill: spec write isolation') or not populate the reviewer checklist at all — leaving that to the human.

## L006 — Dogfood audit run on anchor after clean bootstrap
**Date:** 2026-04-21
**Status:** applied
**Learning:** Audit needs a way to mark sections as intentionally overridden. Without that signal, any project that customises its scaffold will permanently live in a noisy INCONSISTENT state, eroding trust in the tool.

## L007 — Dogfood pairmode on multiple projects simultaneously — anchor + ud running at same time
**Date:** 2026-04-21
**Status:** applied
**Learning:** The pipe path must be scoped to the project directory. Each project gets its own pipe derived from an 8-char md5 hash of the project dir. The sidebar reads its own pipe only. Hooks read the pipe_path from .companion/state.json at startup.

## L008 — Phase 21 spec written, CER agent run on spec before build, found 20 issues including compile-blockers
**Date:** 2026-04-24
**Status:** applied
**Learning:** Running a cold-eyes review on the phase spec itself (not just on built code) catches architectural and correctness errors before any builder time is spent. The CER agent reading actual source files alongside the spec finds mismatches the spec author missed. This is more valuable than a post-build reviewer alone.

## L009 — Cross-project audit (cora, radar, forqsite) of .claude/agents/ configurations
**Date:** 2026-05-04
**Status:** applied
**Learning:** Model selection should be explicit per role, not inherited. Volume work (builder) -> sonnet for compute efficiency. Judgment work (reviewer, intent-reviewer, loop-breaker, security-auditor) -> opus for judgment quality. Inheritance from the orchestrator is a silent capability leak. Add a documented fallback policy: if the preferred model is rate-limited, fall back one tier (Opus -> Sonnet on reviewers; Sonnet -> Haiku on builder), never below Haiku.

## L010 — Forqsite restricted reviewer tools to [Read, Grep, Glob, Bash]; cora and radar did not. Cross-project audit surfaced the divergence.
**Date:** 2026-05-04
**Status:** applied
**Learning:** Reviewer-class agents should be limited to read-only tools plus Bash. Bash preserves the commit-or-revert capability via git; Edit/Write removal closes the "reviewer backdoor" failure mode. This is layered with the orchestrator's pre-reviewer commit discipline (which protects against accidental erasure of uncommitted methodology files) — neither layer alone is sufficient.

## L011 — User observed total opus:sonnet usage running at roughly 3:2, exceeding the Opus quota relative to the Sonnet quota. Methodology had Phase 21 baseline of "reviewer-class agents -> opus, builder -> sonnet" applied uniformly across all reviews.
**Date:** 2026-05-05
**Status:** applied
**Learning:** Model selection should be sonnet baseline, opus on demand, not the inverse. Reserve opus for explicit upgrade triggers where the judgment edge actually matters: story retries (sonnet missed it the first time), pre-PR audits (last cold-eyes before code leaves the repo), mid-phase spec pivots (the spec itself moved), and production-code phases for security-auditor. Loop-breaker stays opus permanently because by the time it fires the case is by definition hard.

## L012 — Phase 23 INFRA-044 / LESSON-004 documented model upgrade triggers in prose. Phase 24 made them structural and data-defensible, adding per-story model evaluation (INFRA-050) and an efficiency-ratio report (INFRA-049) to close the feedback loop.
**Date:** 2026-05-07
**Status:** applied
**Learning:** A methodology lifecycle worth codifying: (1) Ship the change under intuition. (2) Capture the rationale as a lesson. (3) Instrument the relevant signal. (4) Wait for data to accrue (≥ 2 phases). (5) Validate the methodology against the data. (6) Formalize, refine, or reverse based on findings. The goal is not minimum cost (that sacrifices quality and causes rework) and not maximum intelligence (that wastes budget on trivial work). It is best outcome per token — optimising the efficiency ratio: PASS rate / cost. This framing is stable even as model prices and capabilities shift; the thresholds in the decision table are the thing that changes, not the objective.

## L013 — Phase 24 session start revealed that anchor's own `.claude/agents/` files had no `model:` frontmatter, and forqsite/radar still carried pre-INFRA-044 opus reviewer assignments — despite INFRA-044 having updated the templates.
**Date:** 2026-05-07
**Status:** applied
**Learning:** Two complementary patterns close the gap: (1) a sync command that re-renders template frontmatter into existing agent files on demand; (2) a note in the methodology that any template change affecting agent behaviour should be followed by a `pairmode sync-agents` run on all active projects. The sync command is idempotent — running it twice produces no further changes.

## L014 — INFRA-077 required updating lessons.json status fields and regenerating LESSONS.md. The builder ran lesson_utils.py as a script and assumed it worked because exit code was 0.
**Date:** 2026-05-13
**Status:** applied
**Learning:** When a utility module has no __main__ block, running it as a script is a no-op. To call generate_lessons_md and write LESSONS.md: import the function directly and write the output in the same Python invocation. Always use json.dumps(..., ensure_ascii=True) when writing lessons.json to preserve existing \uXXXX escape sequences byte-for-byte. Never confirm success with a shell echo after &&; verify by reading the output file.

## L015 — External CER on forqsite 2026-05-18 surfaced multiple doc/code mismatches accumulated over many phases: architecture.md claimed 58 role_permissions rows but actual seed produces 56 (migration 0050 was tightened by 0052 with no doc update); three additional backlog items pointed to docs that no longer matched code. None caught by per-story or checkpoint reviews. Pairmode's existing DOCUMENTATION CURRENCY check in reviewer.md.j2 covers only README.md; checkpoint Documentation review covers only README + brief.
**Date:** 2026-05-18
**Status:** applied
**Learning:** Documentation reliability across builds is what preserves project context across sessions and compactions. The reviewer's doc check should expand from README-only to any non-history doc in docs/ whose content references code the story touched. The fix is builder-remediable inline: the builder updates the relevant doc as part of the same story commit, not a doc-rebuild phase. The check is approximate but cheap — grep the doc surface for references to changed files/symbols, flag candidates, let the reviewer judge. Severity HIGH when the doc statement is now factually wrong, MEDIUM for missing README user-facing change.

## L016 — Reviewing L005 marker hygiene during forqsite session 2026-05-18. Found that L005's marker in CLAUDE.md.j2 points at the wrong file — the actual implementation correctly landed in agents/reviewer.md.j2. Also realized L015 was implemented directly (template edits written outside the /anchor:pairmode review flow), leaving its status as 'captured' despite the change being live in the canonical templates.
**Date:** 2026-05-18
**Status:** captured
**Learning:** Markers are 'pending work' signals and must be lifecycle-managed. When a lesson flips to 'applied' the marker should either be removed entirely or transformed into a brief breadcrumb ({# LESSON LNNN APPLIED YYYY-MM-DD in <file> #}). Affects keys should be granular enough that markers land near where the actual change is most likely to happen. And there must be a clean path to declare a lesson applied when the change was implemented directly without going through review's annotation step.
