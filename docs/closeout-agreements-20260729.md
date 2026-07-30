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


### AG-10 — CER-129 (phase 114): two-track context accounting
Filed after this document's original agreements and after AG-8/AG-9, from a live
operator report (2026-07-29, context accounting) rather than from either
reconciled input.

- The context-health/budget prompt fires on the wrong quantity, in **both**
  directions. Story/subagent spend is attributed to the orchestrator's window by
  three live consumers — `context_health.check_context_health`'s `/clear`
  recommendation (computed from reviewer-FAIL `effort.db` tokens),
  `context_budget_check.py`'s phase-spend sum compared against the *same*
  `context_budget_threshold` key the orchestrator gate uses, and the
  observability `/context` waypoints/misses queries, whose rows the SPA renders
  as "Near-miss blocks" that never occurred. Meanwhile the orchestrator's own
  accumulation between spawns (poll output, merge output, task notifications,
  spec-writer coordination) has no writer at all: `context_current_tokens` is
  refreshed only by `hooks/post_tool_use.py`'s Task/Agent branch.
- The DP7 invariant and the standing repo lesson already forbid exactly this, and
  the architecture's own § *Codified comingling* note flagged only
  `CLAUDE.build.md:320-326` — which no longer exists — and missed all three live
  sites. The rule was correct and unenforced; that is the finding.
- Pulled into **phase 114** as **INFRA-321**, not 116: phase 116's INFRA-316
  (between-story context etiquette) plans to wire `context_budget_check.py` into
  `next-action`'s pause decision, which would promote the mis-attribution from an
  unwired CLI into the resolver's live cadence. The track boundary must land
  first, and 114 already owns build-loop truth-restoration work.
- Five deliverables: a single definition of the two tracks and their state/db keys
  in `context_model.py` (A); the health/pause verdict re-based onto the
  orchestrator track with story spend demoted to informational retry-churn
  wording (B); between-spawn orchestrator coverage via the measurement that
  already exists — `read_current_tokens` called from `user_turn_seq.record_user_turn`,
  with `hooks/user_prompt_submit.py` left unedited because it is protected and
  already delegates (C); classification of the existing per-story numbers, with
  the explicit finding that `flex_factor` is an orchestrator ceiling multiplier
  and **no gate protects a subagent's own window today** (D); and distinctly
  labeled operator surfaces, including removing the false `tokens_at_block` /
  "Near-miss blocks" claim (E).
- **No gate is weakened and no gate is added.** `context_budget.decide()`'s
  decision logic is untouched; its only diff is a call-site extraction of the
  ceiling formula, which today exists in three divergent copies.
- Six directions are rejected on the record rather than deferred: deriving
  orchestrator headroom from `effort.db` totals (already a recorded lesson, and
  reinvented three times anyway — which is why the rule moves into the code's own
  constants); heuristically estimating poll/merge/notification sizes when a real
  JSONL measurement exists (the `expected_step_tokens` `111` failure, CER-053 /
  INFRA-254, is the precedent); summing subagent sidechain usage into the
  orchestrator count (INFRA-251's `isSidechain` filter exists for this);
  deleting `context_health.py` / `context_budget_check.py`; a single unified
  blended "context" number; and a TTL or turn-count staleness *block* between
  spawns (CER-041 → CER-047 showed a TTL cannot answer the cross-session
  question, and CER-067 showed agents forge state to defeat an un-clearable
  gate — coverage beats a new block).
- Constrained by INFRA-299 (unmerged): backlog rows CER-105/106/113 and
  `hooks/pre_tool_use.py` are untouched. CER-106 —
  `context_budget_acknowledged_at` stores a token count despite the `_at` suffix
  — is adjacent in subject and deliberately left to that branch. Constrained by
  INFRA-303 (same phase): no orchestrator-track state key is renamed; the new
  `story_spend_threshold` is additive.


### AG-11 — CER-130 (phase 114): anchored CER resolution-marker grammar
Filed after this document's original agreements and after AG-8/AG-9/AG-10, from
a live operator report (2026-07-29, a consuming repo's phase-35 checkpoint)
rather than from either reconciled input.

- The `cer-do-now` checkpoint guard decides whether a project may enter its
  checkpoint sequence using a bare, case-sensitive substring membership test on
  the whole Do Now row line —
  `if "RESOLVED" not in stripped and "SUPERSEDED" not in stripped`
  (`next_action.py:437`, left verbatim by INFRA-297 when the row splitting moved
  to `table_utils.split_table_row`). That one expression is wrong in **both**
  directions.
- **Direction 1 (observed):** a consuming repo whose convention is title-case
  (`Resolved cp-34 — …`) never matches, so every resolved row reads unresolved
  and the guard blocks every checkpoint forever. The operator's remedy was a
  manual `record-checkpoint-step checkpoint-tag` bypass — the CER-067 failure
  class (an un-clearable gate that operators learn to route around, after which
  it protects nothing), and the same shape as CER-072 and CER-094/INFRA-294.
- **Direction 2 (the more dangerous one):** with no boundaries, `UNRESOLVED`
  contains `RESOLVED`, and uppercased aspirational prose
  (`… SHOULD BE RESOLVED before the tag`) reads as an accomplished closure — so
  a genuinely open Do Now item passes a checkpoint silently.
- Pulled into phase 114 as **INFRA-322**: 114 already owns build-loop
  truth-restoration and doc-currency work, and this is a live fleet-blocking
  defect rather than 0.3.1 polish.
- **A lowercase-only fix is rejected on the record.** Case-folding alone repairs
  direction 1 and *widens* direction 2 (`unresolved`, `should be resolved`,
  `to be resolved` all begin matching). The check must be case-insensitive
  **and** anchored.
- The grammar is defined once as a shared public predicate in `cer.py` beside
  `is_placeholder_row` — the INFRA-294 two-reader precedent — and the guard's
  diff is one boolean expression plus its docstring. The accepted grammar:
  `RESOLVED` or `SUPERSEDED`, any case, **beginning an annotation segment**
  (start of text, a newline, a sentence/cell boundary such as `.` `;` `:`
  em-dash or `\|` followed by whitespace, or an emphasis/bracket opener `*`
  `(` `[`), and not followed by a word character. Mid-clause occurrences are not
  markers. `` ` ``, `"`, `'` and `_` are deliberately **not** openers, because
  each collides with prose that quotes the keyword — including CER-130's own row
  text. Where the grammar is uncertain it **fails closed**: a visible block an
  operator can correct beats a silent pass.
- **The root cause is that the grammar was never written down.** Nothing in the
  codebase writes a marker; `checkpoint-docs/procedure.md` says only that items
  "must be marked `RESOLVED`", and the bootstrap template preamble says only
  "resolved findings remain in place with a resolution note". Publishing the
  grammar in `docs/architecture.md`, that procedure, and — highest value — the
  `docs/cer/backlog.md.j2` preamble every consuming repo receives on disk, is
  half the story.
- The scaffolded empty-state placeholder exemption (INFRA-294) is preserved
  byte-identically and *ahead* of the resolution test, with a test asserting the
  placeholder row is not itself resolution-marked, so a future grammar change
  cannot silently start blocking freshly bootstrapped repos again.
- Four further directions are rejected rather than deferred: narrowing the
  scanned text from the whole row line to the finding cell (a second behavior
  change, dependent on INFRA-297's index-shifted `cols` shape, with no observed
  harm); admitting backtick/quote/underscore openers; widening the keyword set
  (`OBSOLETE`/`REJECTED`/`AMENDED`) — a policy change about what closes a Do Now
  row, not a defect fix; and treating a partial-resolution note (BUILD-006) as a
  closure. A `cer.py` subcommand that *writes* correctly-formed markers is named
  as future work rather than half-built.
- Constrained by INFRA-299 (phase 113, unmerged): backlog rows CER-105/106/113
  and `docs/stories/INFRA/INFRA-299.md` are untouched; the only `backlog.md`
  edits are CER-130's own row and the preamble paragraph.

### AG-12 — CER-134 (phase 114): session-lifecycle notices for agent-registration writes
Filed after this document's original agreements and after AG-8/AG-9/AG-10/AG-11,
from a live operator report (2026-07-29, bootstrap session lifecycle) rather than
from either reconciled input.

- Claude Code loads `.claude/agents/*.md` agent definitions, plugin/skill
  registrations, and the `hooks` blocks of `.claude/settings*.json` **at session
  start only**. Every pairmode path that installs or updates those surfaces
  writes them **mid-session**: `bootstrap` renders all seven agent shells and
  registers four hook events; `pairmode_sync sync-agents` rewrites shell
  frontmatter in place, `sync-all` runs it as chain step 2, and
  `audit-hooks --apply` rewrites both settings files' hook blocks;
  `pairmode_migrate` rule 2 delegates to `sync-agents`, rule 3 substitutes shell
  bodies, and `to-030`'s B7 deletes or flags shells. In the session that just
  bootstrapped or migrated a repo, none of it is in effect — spawns fall back to
  `general-purpose` or fail, and the operator concludes the bootstrap failed.
- **Nothing in the codebase says a restart is required.** A grep for `restart` /
  `new session` / `exit the session` across the four scripts,
  `hooks/session_start.py`, `SKILL.md`, the cutover runbook and `PAIRMODE.md`
  returns one unrelated hit. `bootstrap._print_next_steps` routes the operator
  into `story_new` → `story_context` → `audit`, none of which exercise the
  registry, so the scaffold looks healthy until the first spawn.
- **`/clear` is the trap, and it is what makes the hook-side check worth having.**
  A `/clear` or `/compact` resets the context window inside the *same* process;
  the registry is untouched, while `hooks/session_start.py` prints a reassuring
  `Pairmode v… is active` block that is true about `state.json` and silent about
  registration. `startup` and `resume` are fresh CLI processes and are therefore
  excluded from the advisory on the record — warning there would be false and
  would train operators to dismiss the true warning.
- Pulled into **phase 114** as **INFRA-323**: this phase already owns build-loop
  friction removal and doc currency, and the forcing function is immediate —
  RELEASE-068's canon-only pokus migration creates `gate-worker.md` and rewrites
  seven agent shells via `sync-all --apply`, then verifies only that the *files*
  are on disk, which passes in a stale session.
- Three deliverables: (a) one `session_lifecycle.py` module defining the
  `RESTART REQUIRED` notice **once** — enumerating the changed surfaces, naming
  the action, stating that `/clear` is not sufficient, printed **last** by
  bootstrap, migrate, `to-030`, `sync-agents`, `sync-all` and `audit-hooks`, and
  **only when something actually changed**; (b) the restart step written into
  `SKILL.md`'s four command flows, the cutover runbook's 6-step mechanic
  (positioned before any step that verifies agents) and one architecture
  subsection; (c) a SessionStart staleness advisory — a pure-read comparison of
  two additive `state.json` keys (`agent_surfaces_written_at` /
  `_written_by`, stamped by the tooling that already writes that file) against
  the pre-mutation session view, emitting one context line and **no additional
  state write**, inside the hook's existing best-effort discipline.
- **No gate is added.** The precondition is unverifiable from inside the process
  — the tooling cannot read Claude Code's loaded registry — so a block would fire
  on a guess, and CER-067's lesson is that an un-clearable mechanical gate gets
  routed around and then protects nothing. Advisory, fail-open, unmissable.
- Nine directions are rejected on the record rather than deferred: making the
  tooling restart the session itself (a child process cannot reload its parent's
  registry, and faking it violates the hook/state boundary in
  `docs/ideology.md:113-130`); relying on operators reading the docs as the
  primary mechanism; a blocking gate; mtime-only staleness detection as the
  authoritative signal (`git checkout`, worktree creation and the CER-090
  `rsync` workaround all rewrite mtimes without changing content); warning on
  `startup`/`resume`; a new state file or persisted notice log; a notice on
  every run regardless of changes (notice fatigue is CER-067's lesson applied to
  output); parsing child stdout in `sync_all` to detect changes (children
  inherit stdout by design — a stamp is the cleaner contract); and treating
  `CLAUDE.build.md`/`CLAUDE.md` as restart surfaces (read per invocation, not at
  session start).
- Sibling-constrained inside phase 114: **INFRA-319** holds `bootstrap.py` and
  `pairmode_migrate.py` as `primary_files` and rewrites hook registration
  itself — INFRA-323 adds only terminal output and one state stamp to the same
  commands, and where INFRA-319 changes *which* settings file is written the
  notice follows it; **INFRA-303** also holds `pairmode_migrate.py` (no rule
  added or renumbered); **INFRA-305** holds `docs/architecture.md` (the new
  subsection is additive); **INFRA-321** must not also edit
  `hooks/session_start.py`; **INFRA-304** owns the agent templates, which this
  story does not touch. `hooks/session_start.py` is a **protected** path
  (`scope_guard.PROTECTED_GLOBS`) and is declared explicitly in `touches:`.
- RELEASE-068 (phase 106) received a dated one-line **post-spec operator
  addendum** at INFRA-323's spec time adding the exit-and-restart step before
  agent verification, so the pokus migration is not blocked on this story
  landing. `RELEASE-068.md` is deliberately **not** in INFRA-323's `touches:`.


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
