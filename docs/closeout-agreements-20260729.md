# Closeout agreements — era 004 revision (2026-07-29)

**Inputs reconciled:**
- `/mnt/work/cora/docs/agreements/flex-upstream-candidates.md` (cora 0.1.0→0.3.0 hand-migration findings, items A#1–A#8)
- `docs/closeout-planning-cold-eyes-review_20260729.md` (external cold-eyes review, findings F1–F12, proposed CER-119..126)
- Cold synthesis + reconciliation against era-004 planning (phases 113–115, INFRA-296..310), this session.

**Process:** each point below was resolved as an explicit operator agreement, one at a
time. This document is the authority for the spec updates that follow; the era, phase,
and story specs are to be brought into conformance with it before build.

---

## Governing revision: containment principle

The cold-eyes review's sizing principle ("no new phase; ~2 stories + widened
INFRA-310") is **set aside by operator decision**. Era 004 was deliberately
scaffolded incomplete at inception, with stated intent that it would be reviewed
and revised based on external review — specifically the cold-eyes pass and the
cora hand-migration findings. The original scope was too narrow in spite of that
stated intent. The era is therefore **expanded**, not contained: two new stories
in existing phases, a widened INFRA-310, and a new phase 116.

---

## Agreements

### AG-1 — INFRA-311 (phase 113): sync canon-shrink + audit EXTRA finding
Covers F1 (CRITICAL) + F2 + F3's parity test.
- `sync.py` gains a canon-shrink path (`--prune-extra` or `retired_sections`
  mechanism — spec to choose and justify) so canon reductions propagate; today
  `sync_project` never modifies EXTRA items (`sync.py:344`) and structurally
  cannot deliver shrinkage (this is how the INFRA-241 thin-agent reduction
  stranded 6×–13× stale canon across all six fleet projects).
- `audit.py`: EXTRA-classified sections inside `CANONICAL_FILES` become a
  finding, not a `✓ project-specific` checkmark.
- Include the one-test `bootstrap.SCAFFOLD_FILES ⊆ audit-tracked` parity
  assertion (analog of `test_audit.py:2209`). Full seeded-doc body-tracking for
  `architecture.md` / `checkpoints.md` is NOT in scope — file as CER-121.
- Sequencing: gates phase-106 disposition (AG-3) and makes phase-116 canon
  rewrites (AG-6) propagatable.

### AG-2 — INFRA-312 (phase 115): observability UI functional validation
Covers F6.
- Manual dogfood checklist: SPA served against ≥2 registered repos, routes
  exercised, evidence pasted into the story.
- PLUS a TypeScript test runner (vitest or similar), deliberately beyond the
  review's minimal floor, so validation is repeatable. Scope the runner to the
  existing routes — smoke/route-level coverage, not a coverage crusade.

### AG-3 — INFRA-310 widened: era-003 closure
Covers F5 + T4. **Reverses INFRA-310's current `## Out of scope`** (which punts
era-003 transition to orphaned phase 108 / RELEASE-072).
- Fold in RELEASE-072's era transition and INFRA-279's exit criterion.
- Disposition phase 108: obligations folded into era 004; phase not revived.
- Disposition phase 106: complete-by-hand-migration, with the evidence
  limitation stated (hand-migration did not hold for agent shells — F1/T4);
  ordered **after INFRA-311 lands**.
- Exactly one era active at tag time.

### AG-4 — F4: check-index driven to true exit 0
- Widen INFRA-310 `touches:` with the enumerated ~25 violation files
  (48 violations: 21 orphan-story, 13 deferred-without-section in
  `phase-97.md`, 12 cross-link, 2 status-drift) and add explicit cleanup
  Ensures. No baselining; Ensures 14's exit-0 demand stands.
- Phase 97 gets its `## Deferred stories` section without being revived.

### AG-5 — Small folds (all five accepted)
1. **F7 → INFRA-304**: verify plugin-runtime resolution of the bare
   `skills/pairmode/skills/<role>/procedure.md` path in all six agent templates
   FIRST; fix (absolute render) only if it doesn't resolve.
2. **F8 → INFRA-305**: one added Ensures correcting README's pre-CER-074
   build-loop description (reviewer dispatch is orchestrator-held prose, not a
   resolver `spawn-reviewer` emission).
3. **F9 → INFRA-310**: Requires 2 restated predicate-only; no asserted counts.
4. **F10 → INFRA-310**: Requires 3's duplicate-ID map corrected against the
   live backlog (four duplicates, not five; two pairs span quadrants).
5. **F11 → INFRA-310**: flex's own `.companion/state.json` bumped to 0.3.1;
   file added to `touches:`.

### AG-6 — Phase 116: cora upstream (in era, pre-tag)
The six deferred cora items become a sequenced phase inside era 004, shipping in
0.3.1. New story IDs assigned at spec time (INFRA-313.. or as the spec-writer
rails them):
- **A#1** — CER backlog gate/groom: `cer.py gate` (nonzero on open Do Now,
  wired into `record-checkpoint-step`), `cer.py groom` (re-read Do Later /
  Do Much Later for arrived `gate:` conditions; operator decides pulls),
  `gate:` field in backlog schema. Promotion ledger already exists — not
  rebuilt.
- **A#2** — pre-build intent review: resolver emits `spawn-intent-reviewer` for
  an all-planned/draft phase before first `spawn-builder`, behind Build-standards
  opt-in (`intent_review: pre-build`).
- **A#4** — between-story context etiquette: `next-action` consults
  `context_budget_check.py` between story iterations against the 120k absolute
  threshold; `pause-context` handoff over threshold.
- **A#5** — covered-contracts gate: Build standards `covered_contracts:`
  (doc-section ↔ source-file pairs); builder procedure pre-build read gate on
  `primary_files`/`touches` intersection; doc wins on conflict.
- **A#6 + T5** — deferral/disposition gate in tooling, at BOTH boundaries:
  `record-checkpoint-step checkpoint-tag` refuses on planned/draft stories
  without a `## Deferred stories` entry (story→phase), and the era-transition
  path gets the analogous check (phase→era). `phase_new.py --parent-phase`.
- **A#7** — spec-time model review: story frontmatter `model:` /
  `reviewer_model:` honored by dispatch; spec-writer prompts the asymmetric
  raise/lower review (lower unilaterally with note; raise requires operator).

### AG-7 — INFRA-310 + 0.3.1 tag move to phase 116 (terminal story)
- Phase 116 = six cora stories, then the widened INFRA-310 as its terminal
  story; the 0.3.1 record and tag remain the era's last act.
- Phase 115 = observability closeout minus the record story (its remaining
  stories + INFRA-312).
- Numeric build order 113 → 114 → 115 → 116 preserved; no renumbering.
- INFRA-310 Requires 1 reworded to DERIVE its sibling set (all era-004 stories
  complete) rather than pinning "fourteen siblings INFRA-296..309".

### AG-8 — CER-127 (phase 114): portable hook-command paths
Filed after this document's original agreements, from a live operator report
(2026-07-29, fleet portability) rather than from either reconciled input.

- Registering a freshly-cloned consuming repo hard-blocked every prompt:
  `.claude/settings.json` carried
  `uv run python /mnt/work/flex-harness/hooks/user_prompt_submit.py` — a
  pre-rename path, and a machine-bound one, in a **committed** file.
- Pulled into phase 114 as **INFRA-319** (not phase 116): it is migration-tooling
  and audit surface, which is what phase 114 already owns, and it is a live
  fleet-blocking defect rather than 0.3.1 polish.
- Three deliverables per the CER row: portable registration, a repair path for
  already-migrated repos, an audit finding class.
- **Fix direction (a) is delivered differently than the row words it.**
  `${CLAUDE_PLUGIN_ROOT}` expands for a plugin's own `hooks/hooks.json`, not for
  a project's `.claude/settings.json`; the absolute-path construction stays and
  the *committed file* is what changes — hook registration moves to
  `.claude/settings.local.json`. The rejected direction is recorded in the story
  and must be recorded in the backlog annotation, so it is not re-proposed.
- Constrained by INFRA-303 (same phase, same file): no fifteenth
  `MigrationRule`; the repair lands as a `to-030` block.


### AG-9 — CER-128 (phase 113): mid-build scope relief
Filed after this document's original agreements and after AG-8, from a live
operator report (2026-07-29, scope friction) rather than from either reconciled
input.

- `scope_guard.check_path` matches `allowed_paths` by exact string membership and
  has **no path from a deny back to an allow that does not require a human**.
  Every mid-loop discovery of an undeclared file costs an operator round-trip:
  hand-edit `touches:` + `permissions-create`, toggle auto-mode off for the
  prompt, or fall back to shell writes.
- The downstream harm is over-declaration: on a fresh 0.3.0-bootstrapped repo,
  teams widen `touches:` at spec time to pre-empt prompts, which turns the guard
  into a fiction and produces per-build-loop CER churn. Same-session evidence in
  flex: INFRA-297 and INFRA-298 both edited `docs/cer/backlog.md` undeclared
  (reviewer MEDIUM), and the INFRA-319 spec-writer used the CER-087 shell-write
  workaround.
- Pulled into **phase 113** as **INFRA-320**, not 114/116: it is a build-loop
  blocker of the same class as the rest of 113 ("nothing in 114–116 is
  trustworthy until these land"), and 113 is the phase currently building.
- Three deliverables per the CER row: a central standing allowance for shared
  documentation/record surfaces (A), an audited `permissions-widen` command that
  writes the declaration back into the story frontmatter (B), and spec-time
  prediction of scope gaps wired into the spec-writer's Step 7 self-check (C),
  plus builder/reviewer procedure wiring (D).
- **The hard block is preserved, and the story must say so.** Protected paths
  stay unreachable by any standing or widening mechanism, out-of-root stays
  denied, and no code file is ever granted implicitly. Four directions are
  rejected on the record rather than deferred: auto-widen on deny,
  `permissionDecision: "ask"` in place of the block, routing the audit trail
  through the sidebar-only `spec_exception.py`, and glob/prefix matching in
  `allowed_paths`.
- Constrained by INFRA-299 (same phase, unmerged): it owns `hooks/pre_tool_use.py`
  and backlog rows CER-105/106/113; INFRA-320 touches neither.

---

## Unambiguous dispositions (no decision was needed)

- **A#3** (spec-surface discipline): largely already live in flex 0.3.0.
  Remaining polish (forbidden-proxy template stub, `phase_new.py --proposed`)
  folds into phase 116's A#6 story or CER row at spec-writer's discretion.
- **A#8**: already upstreamed; no action.
- **F12**: file CER-125 (phase-64 stale statuses); no story.
- **F3** (beyond the parity test): file CER-121.
- **CER filings**: CER-119..126 do not yet exist. The spec update files all of
  them: rows absorbed by in-era stories (F1→INFRA-311, etc.) are filed with a
  disposition pointer to their story; deferred rows (CER-121, CER-125) carry
  explicit `gate:` conditions. Closures are never deletions.

## Preserved do-not-dos (from the source documents)

- No pre-release suffix on the version string; beta status signaled in
  README § Status and the 0.3.1 CHANGELOG.
- Phase 97 stays `deferred` — cleaned (AG-4), not revived.
- Phase 108 not revived — folded (AG-3).
- Phase 106 not dispositioned before INFRA-311 (F1) lands.
- F7: verify runtime resolution before changing anything.
- CER grooming pull-forwards are operator decisions — never automated.
- Backlog closures are pointers, never deletions.
