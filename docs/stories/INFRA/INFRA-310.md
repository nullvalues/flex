---
id: INFRA-310
rail: INFRA
title: Backlog truth pass, phase-107 supersession, era-003 closure, zero-open audit, and the 0.3.1 version record
status: draft
phase: "116"
auth_gated: false
schema_introduces: false
primary_files:
  - docs/cer/backlog.md
  - CHANGELOG.md
  - skills/pairmode/scripts/_version.py
touches:
  - docs/phases/index.md
  - docs/phases/phase-107.md
  - docs/phases/phase-106.md
  - docs/phases/phase-108.md
  - docs/phases/phase-97.md
  - docs/eras/001-initial.md
  - docs/eras/003-flex-orchestrator-as-harness.md
  - docs/eras/004-flex-operational-closeout-and-0-3-1.md
  - docs/stories/INFRA/INFRA-273.md
  - docs/stories/INFRA/INFRA-274.md
  - docs/stories/INFRA/INFRA-275.md
  - docs/stories/INFRA/INFRA-276.md
  - docs/stories/INFRA/INFRA-277.md
  - docs/stories/INFRA/INFRA-278.md
  - docs/stories/INFRA/INFRA-279.md
  - docs/stories/RELEASE/RELEASE-072.md
  - docs/stories/INFRA/INFRA-310.md
  - docs/stories/OBS/OBS-006.md
  - docs/stories/RELEASE/RELEASE-058.md
  - docs/stories/INFRA/INFRA-001.md
  - docs/stories/INFRA/INFRA-002.md
  - docs/stories/INFRA/INFRA-003.md
  - docs/stories/INFRA/INFRA-004.md
  - docs/stories/INFRA/INFRA-022.md
  - docs/stories/INFRA/INFRA-023.md
  - docs/stories/INFRA/INFRA-024.md
  - docs/stories/INFRA/INFRA-025.md
  - docs/stories/INFRA/INFRA-110.md
  - docs/stories/INFRA/INFRA-111.md
  - docs/stories/INFRA/INFRA-114.md
  - docs/stories/INFRA/INFRA-115.md
  - docs/stories/INFRA/INFRA-116.md
  - docs/stories/INFRA/INFRA-117.md
  - docs/stories/INFRA/INFRA-118.md
  - docs/stories/INFRA/INFRA-119.md
  - docs/stories/INFRA/INFRA-120.md
  - docs/stories/INFRA/INFRA-121.md
  - docs/stories/INFRA/INFRA-122.md
  - docs/stories/INFRA/INFRA-123.md
  - docs/stories/INFRA/INFRA-133.md
  - .companion/state.json
  - .claude-plugin/plugin.json
  - .claude-plugin/marketplace.json
  - skills/pairmode/SKILL.md
  - tests/pairmode/test_fold_preparation.py
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

This is the closing story of era 004 and the last story built across phases
113, 114, 115 and 116 (moved from phase 115 to phase 116 as its terminal
story — AG-7, `docs/closeout-agreements-20260729.md`). Its job is to make the
record true and then stamp it.

**Widened 2026-07-29 per the closeout agreements:** the 2026-07-29 cold-eyes
review found the original scope would have tagged 0.3.1 with two eras active,
an orphaned phase 108 holding the era transition, phase 106 undispositioned,
and `check-index` red with 48 known violations its own `touches:` list barred
it from fixing. AG-3 folds era-003 closure in (reversing this story's earlier
`## Out of scope` bullet on that point); AG-4 drives `check-index` to a true
exit 0; AG-5 items 3–5 correct two Requires against the live backlog and bump
flex's own `.companion/state.json`.

Seven things happen here, in one story because they are one act — declaring
the era finished:

1. **The obsolete tail of `docs/cer/backlog.md` gets an honest disposition.**
   Nineteen rows (CER-001..012, 014, 017, 018, 019, 035, 044, 063) describe
   defects that were fixed years-of-phases ago by unrelated work and never
   annotated. They are not "open findings" in any meaningful sense — they are
   bookkeeping debt that makes the backlog unreadable and makes every
   "how many open rows are there?" question unanswerable. Each gets an
   `OBSOLETE` annotation quoting the file:line that proves it.

2. **CER-031 gets a retain-with-reason, not a resolution.** It is blocked on
   the timing of an external pull request in a repository this project does
   not own. It has zero code surface here. Closing it would be a lie;
   leaving it bare would make the zero-open audit unpassable. It gets an
   explicit `BACKLOG-RETAIN` disposition with a dated trigger.

3. **Phase 107 is formally superseded.** `docs/phases/phase-107.md` already
   exists as "CER backlog drain to zero" with five never-specced stubs
   (INFRA-273..277) whose scope this era re-did on merits — the era-004
   classification put CER-069 in the shared-blocker group rather than
   phase-107's "legacy quick-fix" bundle, and split the doc sweep from the
   code sweeps. Two live plans for the same backlog is exactly the
   silently-passed contradiction this project exists to prevent. Phase 107
   is marked `deferred` with a `## Superseded` note; nothing is deleted.

4. **Era 003 is formally closed (AG-3).** Phase 108's obligations fold in:
   RELEASE-072's era transition runs here (close era 003 **by ID** — two
   eras are active, and `era_transition._find_active_eras` returns a list;
   INFRA-314's by-ID targeting is the tool), INFRA-279's exit criterion is
   written into the era-003 doc, and INFRA-278's validation obligation is
   discharged by pointing at **both** INFRA-312's evidence (SPA/UI half) and
   INFRA-329's evidence (effort-db integrity half — added by the 2026-07-30
   reconciliation sweep to phase 115 as a sibling of INFRA-312, since
   INFRA-312 alone is UI/route-shaped and never touches effort.db; see
   phase-108.md's `## Superseded` note, Ensures 24). Phase 108 itself is
   dispositioned like phase 107 — superseded, not revived. Exactly one era
   (004) is active at tag time.

5. **Phase 106 is dispositioned (AG-3, after INFRA-311).** Marked complete-
   by-hand-migration per operator instruction, with the evidence limitation
   stated in the phase doc: hand-migration did **not** hold for the agent
   shells (the F1 stale-canon finding); the fleet receives the corrected
   canon via the post-0.3.1 sync campaign that INFRA-311 makes possible.
   This disposition is only honest because INFRA-311 is complete — verify it
   before writing.

6. **`check-index` is driven to a true exit 0 (AG-4).** The 48 pre-existing
   violations (21 orphan-story, 13 deferred-without-section in `phase-97.md`,
   12 cross-link, 2 status-drift — inventory in Requires 17) are fixed, not
   baselined. Phase 97 gets its `## Deferred stories` section without being
   revived.

7. **Version 0.3.1 is recorded.** A `CHANGELOG` entry covering phases
   113–116 and a coordinated bump across every version-bearing surface,
   including flex's own `.companion/state.json` (AG-5 item 5) so flex does
   not report itself behind canon.

**The zero-open target is editorial, not mechanical — state this plainly and
do not pretend otherwise.** `next_action._check_cer_do_now`
(`skills/pairmode/scripts/next_action.py:394`) guards **only** the `## Do Now`
quadrant, and it already passes today because Do Now holds nothing but
resolved rows. No tool anywhere reads `## Do Later` or `## Do Much Later` for
open findings. "Zero open rows" after this story is a claim this story makes
by enumeration and pastes the evidence for — it is not a gate a future
regression will trip. Ensures 6 exists to make the claim checkable by a human
running one command, not to imply CI enforcement.

## Requires

Every anchor below was re-verified against the working tree on 2026-07-29.
Where the closeout plan's line number had drifted, the live anchor is given
and the drift is called out. Line numbers in `docs/cer/backlog.md` will shift
as siblings annotate rows — **locate rows by their `| CER-NNN |` cell, never
by line number.**

1. **Every other era-004 story is complete and merged — derive the set, do
   not pin it (AG-7).** The sibling set is *derived* at build time: the
   union of every story ID in the Stories tables of
   `docs/phases/phase-113.md`, `phase-114.md`, `phase-115.md` and
   `phase-116.md`, minus INFRA-310 itself. Every derived row must read
   `complete`. (A pinned "fourteen siblings INFRA-296..309" list is exactly
   the asserted-count decay F9 flagged; the phase manifests are the truth
   source.) Each sibling annotates the CER rows it drains; this story's
   backlog edits are applied on top of theirs. If any derived sibling is not
   `complete`, **stop and report** — this is a hard precondition, not a
   preference. INFRA-311's completion additionally gates the phase-106
   disposition (Context item 5).

2. **Row-disposition formats in `docs/cer/backlog.md` are inconsistent —
   three variants exist.** This matters because Ensures 6's enumeration needs
   one predicate:
   - **Variant A (dominant):** a bold uppercase token inline in the Finding
     cell — `**RESOLVED Phase 94 (cp94) — INFRA-207 …**`,
     `**SUPERSEDED by CER-054 (D2) — …**`.
   - **Variant B (two rows):** bold *title-case* — `CER-083`
     (`**Resolved by INFRA-260 (Phase 102):**`) and `CER-091`
     (`**Resolved by INFRA-264 (Phase 104):**`). A case-sensitive scan
     reports both as open; they are not.
   - **Variant C (one row):** `CER-060` carries
     `RESOLVED cp-HARNESS002-main — RESOLVER-006 implemented the fix: …`
     unbolded, in the **last table column** (the `Phase` column position),
     not in the Finding cell. A scan for `**RESOLVED` misses it entirely.

   **No asserted count (AG-5 item 3).** Earlier drafts asserted row counts
   ("49", "50"); every such number had decayed within days as siblings and
   new filings landed. This Requires states the *predicate problem* only:
   three disposition-format variants exist, so no single scan is honest
   until Ensures 2 normalizes them. Whatever the count is on build day, the
   Ensures-6 enumeration derives it live — no number from this spec may be
   quoted as expected output.

3. **Duplicate CER IDs exist — corrected against the live backlog
   2026-07-29 (AG-5 item 4).** **Four** IDs are duplicated, not five:
   `CER-063`, `CER-064`, `CER-065`, `CER-066` each appear twice, products of
   the two fold renumberings; `CER-062` appears **once** (Do Later only).
   Three of the pairs **span quadrants** — `CER-064`, `CER-065` and
   `CER-066` each have their first occurrence in `## Do Now` (resolved rows)
   and their second in `## Do Later`; only `CER-063`'s pair sits wholly in
   `## Do Later`. Any enumeration or annotation loop keyed on the bare ID
   will hit the wrong row, and a scan scoped to one quadrant will miss a
   twin. The pairs, as they stand today:
   - `CER-063` — first occurrence: the `fold-prep` `INFRA-203` rail-collision
     row (**open; this story's target**). Second occurrence:
     `parse_worker_verdict_text` removal (already
     `**RESOLVED cp-HARNESS009-post1 (RESOLVER-016)**`).
   - `CER-064` — first: `story_update.py` cross-phase status leak (Do Now,
     resolved). Second: `spec_preflight` containment (**INFRA-304's row, not
     this story's**).
   - `CER-065` — first: PreToolUse matcher gap (Do Now, resolved). Second:
     reviewer-template `git clean -fd` residue (**INFRA-304's row**).
   - `CER-066` — likewise paired (Do Now resolved / Do Later); dispositioned
     or owned by INFRA-301.
   - `CER-062` — **not** duplicated; its single Do Later row stands alone
     (the earlier five-pair map was wrong on this — F10).

   Every edit this story makes must be applied to a row identified by its
   **surrounding text**, not by an ID match alone.

4. **The nineteen obsolete rows and their proving evidence — all
   re-verified 2026-07-29.** These are this story's annotation set. Plan drift
   is noted where found.

   | CER | Row claims | Live proving evidence (verified) |
   |---|---|---|
   | 001 | `reconstruct.py parse_ideology()` uses a `NamedTemporaryFile` round-trip | `skills/pairmode/scripts/ideology_parser.py:106` defines `parse_ideology_text(text)`; `reconstruct.py:39` is `return _ideology_parser.parse_ideology_text(text)`; no temp file remains |
   | 002 | `bootstrap.py` has no `--yes`/`--no-input` flag | `bootstrap.py:1047` — `"--yes", "-y",` |
   | 003 | `cer.py` lacks the depth guard | `cer.py:371` — `if not proj.is_dir() or len(proj.parts) < 3:` |
   | 004 | `lesson_review.py` uses `str.startswith()` for containment | `lesson_review.py:180` — `template_path.relative_to(boundary)` |
   | 005 | `phase_new.py` lacks the depth guard | `phase_new.py:314` — `if not project_path.is_dir() or len(project_path.parts) < 3:` |
   | 006 | validator rejects the empty `primary_files` `story_new.py` writes | `story_new.py:71` — `# primary_files is deliberately omitted for new (draft) stories (CER-006);`; `schema_validator.py:202-212` is the status-aware block (`status in ("draft", "backlog")`). **Drift:** plan cited `schema_validator.py:204-211` |
   | 007 | `era_new.py` writes an unquoted `id` | `era_new.py:49` — `f'id: "{era_id}"\n'` |
   | 008 | `permission_scope.py` `_read_json` returns non-dict JSON as-is | `permission_scope.py:163` — `if not isinstance(data, dict):` |
   | 009 | hooks default `PIPE_PATH` then override it from `state.json["pipe_path"]` | All five pipe-writing hooks use the flat path and none reads the key: `stop.py:18`, `session_end.py:19`, `exit_plan_mode.py:16`, `post_tool_use.py:50` (`os.path.join(tempfile.gettempdir(), "companion.pipe")`), `session_start.py:35` (`Path` form). Each carries an INFRA-238 comment (`stop.py:15-16`, `session_end.py:16-17`, `exit_plan_mode.py:13-14`, `session_start.py:32-33`) stating the key was deleted. `grep -n 'pipe_path' hooks/*.py` returns **only** those comment lines |
   | 010 | `story_new.py --rail` is `.upper()`'d but unvalidated | `story_new.py:305-306` — `_RAIL_RE = re.compile(r"[A-Z][A-Z0-9_]*")` + `fullmatch`; `:318` and `:228` — `rail_dir.resolve().relative_to(stories_root)` |
   | 011 | `era_new.py` has only informal `_slugify` traversal prevention | `era_new.py:119-121` — `eras_root = eras_dir.resolve()` then `era_path.resolve().relative_to(eras_root)`. **Drift:** plan cited `era_new.py:118+` |
   | 012 | `pairmode_status.py` `FLEX_ROOT` is one level short; `start_sidebar.sh` path does not exist | `pairmode_status.py:39` — `_REPO_ROOT = Path(__file__).resolve().parents[3]` with the level map documented at `:37-38`; `:129` builds `_REPO_ROOT / "skills" / "companion" / "scripts" / "start_sidebar.sh"`, which **exists on disk** |
   | 014 | architecture.md asserts a "pre-reviewer commit discipline" that no `CLAUDE.build.md` encodes | The subsection is now `docs/architecture.md:1049` ("Reviewer-class agent tool restriction (build-loop safety)"); `grep -rn 'pre-reviewer commit discipline\|git checkout -- lessons' docs/architecture.md CLAUDE.build.md skills/pairmode/templates/CLAUDE.build.md.j2` returns **zero hits** — the aspirational claim was removed, so the contradiction is gone |
   | 017 | `effort_tracking: true` is auto-enabled and never surfaced at bootstrap | `bootstrap.py:1473-1474` — `effort_newly_enabled = _record_state(...)` then `if effort_newly_enabled:` surfaces it |
   | 018 | `lesson.py` CLI cannot write `value_framing` / `validation_phase` | `lesson.py:41-42` (signature), `:79-82` (writes), `:130-131` (`--value-framing` option); `--validation-phase` present in the same option block |
   | 019 | `pairmode_sync._get_project_name` allows YAML injection via newlines | `pairmode_sync.py:106-113` — docstring at `:108` names CER-019; both return paths apply `.replace("\n", "").replace("\r", "")` |
   | 035 | architecture.md says `security-auditor` has no `Bash` | `docs/architecture.md:1051` — "all four reviewer-class agents declare `[Read, Bash, Glob, Grep]`". **Drift:** plan cited `:1052` |
   | 044 | `phaseIndex.ts` builds `docs/phases/${href}` with no containment check | `skills/observability/api/src/parsers/phaseIndex.ts:54` `resolveFileFromHref`, `:57` `const safeRoot = path.resolve(projectDir);`, `:59` `if (!candidatePath.startsWith(safeRoot + path.sep) && candidatePath !== safeRoot)`. **Drift:** the row cites `:44-46` |
   | 063 | `fold-prep`'s `INFRA-203` will collide with main's `INFRA-203` at merge | Commit `3367750e` — "merge(fold-prep): … renumber colliding fold-prep INFRA-192..199 to INFRA-203..210 (RELEASE-014)". The harness story is now `INFRA-215`, recorded at `docs/phases/phase-HARNESS011-main.md:18` |

5. **CER-031 is not in that set and must not be annotated `OBSOLETE`.** Its
   row records that the NP-6 pattern doc
   (`docs/patterns/agentic-architecture/source-of-truth-over-recall.md`) is
   catalog-ready but held from submission while `cloudnirvana/open-patterns`
   PR #3 is open. The row already names its own trigger command
   (`gh pr view 3 --repo cloudnirvana/open-patterns`). There is no flex code
   surface. It is a dated trigger, not a defect.

6. **CER-118 will exist and will be a survivor.** INFRA-305 (Phase 114,
   Ensures 14) **files** a new `## Do Later` row `CER-118` recording that
   `hooks/*` write `tempfile.gettempdir()/companion.pipe` while
   `skills/companion/scripts/sidebar.py:1677-1710` `mkfifo`s and reads
   `/tmp/companion-<md5[:8]>.pipe` and writes that path back to
   `state.json["pipe_path"]` (`:1692`) — a real cross-surface defect
   deliberately **not** fixed in the doc sweep. CER-118 will therefore be
   un-dispositioned when this story runs. **That is expected input, not an
   audit failure.** Ensures 5 gives it an explicit disposition.

7. **The Do Never placeholder row must not be deleted.**
   `docs/cer/backlog.md`'s `## Do Never` section (heading at `:221`) holds a
   single scaffold row `| — | *(none)* | — | — | — | — |`.
   `cer.is_placeholder_row` (`skills/pairmode/scripts/cer.py:144`) is the
   shared, column-count-agnostic predicate that tolerates it, consumed by both
   `cer._parse_entries_from_backlog` (`:124`) and
   `next_action._check_cer_do_now` (`next_action.py:432`) — INFRA-294. Deleting
   the row would remove the empty-state marker the predicate exists to
   recognise. Leave it exactly as it is.

8. **Phase-107 supersession requires FOUR coordinated edits, not two.**
   `check-index` check 2c (`index_integrity.py:280-305`) compares each era
   doc's Phases-table status against `docs/phases/index.md` **for exact
   string equality** and fails on any mismatch. Phase 107 belongs to
   **era 003**:
   - `docs/phases/index.md:135` — `| 107 | CER backlog drain to zero | planned | [phase-107.md](phase-107.md) |`
   - `docs/eras/003-flex-orchestrator-as-harness.md:198` — `| 107 | CER backlog drain to zero | planned |`

   **Both must change to `deferred` together.**

   **Correction 2026-07-30 (reconciliation sweep):** this Requires previously
   stated that `_mark_phase_complete_in_era_ledger` only writes the
   highest-numbered active era and therefore never touches era 003's ledger —
   that premise is now false. INFRA-326 (phase 114, builds before this story)
   fixes the dual-active-era tie-break: the function now locates whichever
   era doc actually **contains** the phase's row, rather than picking the
   highest-ID active era unconditionally. Re-verify `_mark_phase_complete_in_era_ledger`'s
   live behavior at build time — do not assume either the old or the new
   tie-break rule without checking. In any case, **both edits below were
   already applied by hand as part of the 2026-07-30 reconciliation sweep**
   (see this story's Ensures 9/10), so this Requires is now a verification
   step, not a manual-edit instruction: confirm the index and era-003 ledger
   rows already read `deferred` in lockstep before proceeding. This is a
   correction to the plan's §C.1, which named only the index row, and to this
   story's own earlier text, which assumed the tooling could never help.

   `deferred` is an established phase status in both surfaces
   (`index.md:30`, `:70`, `:119`, `:121`;
   `docs/eras/002-*.md:29`; `docs/eras/003-*.md:187`) and
   `index_integrity.is_phase_inactive` (`:72-78`) already treats it as
   inactive.

9. **INFRA-273..277 must go to `status: backlog`, not `deferred`.**
   `schema_validator.VALID_STORY_STATUSES` (`schema_validator.py:142`) is
   `{"draft", "planned", "in-progress", "complete", "backlog"}` — **`deferred`
   is not a valid story status.** Separately, `check-index` check 4
   (`index_integrity.py:340-375`) requires any `deferred` story's phase doc to
   carry a `## Deferred stories` section naming it. `backlog` avoids both
   problems and is semantically right: these stubs are not paused work to be
   resumed under new IDs, they are superseded plans. All five are
   `status: draft`, `phase: "107"` today; INFRA-273, 276 and 277 also carry
   `story_class: doc`.

10. **Version-bearing surfaces — there are FOUR, not three.** The plan named
    `_version.py`, `plugin.json` and `marketplace.json`. `test_version_match.py`
    asserts a fourth:
    - `skills/pairmode/scripts/_version.py:3` — `PAIRMODE_VERSION: str = "0.3.0"`
    - `.claude-plugin/plugin.json:4` — `"version": "0.3.0"`
    - `.claude-plugin/marketplace.json:14` — `"version": "0.3.0"`
    - `skills/pairmode/SKILL.md:5` — `pairmode_version: "0.3.0"`
      (`test_version_match.test_skill_frontmatter_mirrors_pairmode_version`
      asserts this equals `PAIRMODE_VERSION` **exactly**, with no
      release-core stripping)

11. **A hard version pin will break on the bump.**
    `tests/pairmode/test_fold_preparation.py:28-32`
    (`TestVersionFinalize::test_pairmode_version_is_0_3_0`) asserts
    `PAIRMODE_VERSION == "0.3.0"` by string equality. It was written as a
    RELEASE-007 fold-preparation invariant ("version finalized", docstring
    line 4) and will **fail** the moment `_version.py` reads `0.3.1`. This is
    the one test edit this story must make, and the plan did not anticipate
    it. The dated intent it protects — "the dev-line `-dev` suffix has been
    dropped" — is worth preserving in a form that survives future bumps.

12. **`pairmode_migrate.py`'s `0.3.0` literal is a migration target, not a
    version surface.** `pairmode_migrate.py:938` seeds
    `{"pairmode_version": "0.3.0", …}` inside the **`to-030`** step, and
    `tests/pairmode/test_pairmode_migrate.py:929` pins it. It names the schema
    generation the step migrates *to*. It must **not** be bumped.

13. **CHANGELOG shape and line budget.** `CHANGELOG.md` is **136 lines**;
    `tests/pairmode/test_docs.py:25-29`
    (`test_changelog_exists_and_under_200_lines`) caps it at 200. `## [Unreleased]`
    is at `:7`; the only other `## ` release heading is
    `## [pairmode v0.0.x] — Phases 1-16 (flex era2 branch)` at `:109`. Phase
    entries are `### ` headings in reverse-chronological *merge* order (112,
    111, 110, 105, 109, 104, 103, 102, 101, 100, 98, 96, 95). Git tags
    `v0.2.0` (2026-06-26), `v0.3.0` (2026-07-24, commit
    "feat(RELEASE-059): fold fold-prep into main as pairmode v0.3.0") and
    `v1.0` exist. **INFRA-305 will have added a Phase 99 entry (~6 lines)
    before this story runs**, so budget from ~142, not 136.

14. **Era-004 ledger.** `docs/eras/004-flex-operational-closeout-and-0-3-1.md`
    is `status: active` and its Phases table lists 113/114/115/116 (locate by
    row, not line — the doc gained a scope-revision paragraph 2026-07-29).
    `_mark_phase_complete_in_era_ledger` **does** advance these rows
    automatically as each phase is checkpointed, because era 004's own
    ledger contains the 113/114/115/116 rows — so 113, 114 and 115 should
    already read `complete` when this story runs. **Correction 2026-07-30:**
    the reason stated here previously ("because era 004 is the highest
    active era") is no longer the operative rule — INFRA-326 (phase 114)
    replaces the highest-ID tie-break with contains-the-row targeting, so the
    conclusion for 113/114/115 survives (era 004's ledger does contain those
    rows) but for a different reason than originally written. Do not rely on
    "highest active era wins" for any other phase — re-verify
    `_mark_phase_complete_in_era_ledger`'s live behavior at build time (see
    Requires 8's correction). Verify rather than assume; the phase-116 row is
    still `planned` and stays that way until cp-116.

15. **`check-index` invocation.**
    `PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py check-index --project-dir .`
    Exits 0 silently when clean; exits 1 printing one line per violation.

16. **Baseline.** `main`'s suite is green at **4116 passed / 211 skipped**
    (plus whatever the era-004 siblings added; the invariant is
    zero-failures, not the absolute count).

17. **The check-index violation inventory (AG-4) — re-verified 2026-07-29,
    48 violations.** Re-run the Requires-15 command at build time; the live
    output wins over this table. As inventoried:
    - **2 status-drift:** `docs/stories/OBS/OBS-006.md` (commit
      `feat(story-OBS-006)` exists, status `draft`) and
      `docs/stories/RELEASE/RELEASE-058.md` (commit exists, status
      `backlog`). Fix: set each to the status its history proves (complete)
      with a one-line note, or `deferred` named in its phase doc if the work
      was in fact abandoned — read the commits before choosing.
    - **12 cross-link:** 7 story-frontmatter references to nonexistent phase
      files — `INFRA-001.md`/`INFRA-003.md` → `phase-backlog.md`,
      `INFRA-022..025.md` → `phase-[].md`, `INFRA-133.md` → `phase-49.md`;
      plus 5 era-001 ledger rows disagreeing with the index (phase 23
      complete-vs-deferred; phases 53/54/56/57 planned-vs-complete). Fix:
      point story frontmatter at the real phase (or a valid legacy anchor)
      and correct `docs/eras/001-initial.md`'s five rows to match the index
      (the index is the truth source, Requires 8's 2c framing).
    - **21 orphan-story:** `INFRA-001..004`, `INFRA-022..025`,
      `INFRA-110/111`, `INFRA-114..123`, `INFRA-133` — story files no phase
      doc's Stories table references. Fix: reference each from the phase doc
      its frontmatter names once corrected, or flip to `status: backlog`
      with a body note when the story predates the manifest convention —
      the same treatment INFRA-273..277 get (Requires 9's
      `deferred`-is-invalid rule applies here too).
    - **13 deferred-without-section:** `RELEASE-044..056` in
      `docs/phases/phase-97.md`. **`phase-97.md` already has a
      `## Deferred stories` section** — it covers RELEASE-043..057 as a
      prose *range*, which is exactly why the per-ID check still fails.
      Fix: **extend the existing section** (do not add a second heading),
      naming all thirteen IDs individually with one-line reasons and
      "resumes post-0.3.1 at the fold" — the phase stays `deferred`, not
      revived (preserved do-not-do).

18. **Era-003 closure preconditions (AG-3).** Live state 2026-07-29:
    `docs/eras/003-flex-orchestrator-as-harness.md` is `status: active`
    alongside active era 004; index rows `106 | planned`, `107 | planned`,
    `108 | planned`; phase-108 holds INFRA-278/INFRA-279 (draft) and
    RELEASE-072 (draft). INFRA-314 (phase 116) provides the by-ID,
    gate-checked era-close path this story must use — its
    undispositioned-phase refusal means every era-003 phase row must read
    `complete` or `deferred` *before* the close runs. The ordering inside
    this story is therefore: phase dispositions (106/107/108) → check-index
    → era-003 close → version record.

19. **CER-119..126 were filed at spec time (2026-07-29)** in
    `docs/cer/backlog.md`: CER-119/120 (absorbed by INFRA-311), CER-121
    (open, `gate:`), CER-122 (absorbed by INFRA-304), CER-123 (absorbed by
    INFRA-305), CER-124/126 (absorbed by this story), CER-125 (open,
    `gate:`). The absorbed rows carry "Absorbed at spec time by …" pointers
    and are annotated `RESOLVED` by their owning stories at build time; the
    Ensures-6 enumeration treats CER-121 and CER-125 as expected survivors
    (each needs its retain reason restated in `## Evidence`, or its `gate:`
    condition cited as the reason).

## Ensures

Every command below is run from the repo root and is stated with its expected
result so the reviewer can execute it verbatim.

1. **Nineteen obsolete rows annotated with quoted evidence.** Each of
   CER-001, 002, 003, 004, 005, 006, 007, 008, 009, 010, 011, 012, 014, 017,
   018, 019, 035, 044 and 063 (the **first** CER-063 occurrence — the
   `fold-prep` `INFRA-203` rail-collision row, Requires 3) gains a clause of
   the form:

   > `**OBSOLETE — verified Phase 115 / INFRA-310. <one sentence naming what
   > fixed it>. Evidence: <path>:<line> — <quoted code or text fragment>.**`

   The evidence cited must be the **live** anchor from the Requires-4 table,
   re-verified at build time (Instructions step 2), not the row's original
   line number. Rows are annotated **in place**; none is deleted, re-worded
   beyond the appended clause, or moved between quadrants.
   - `for c in 001 002 003 004 005 006 007 008 009 010 011 012 014 017 018 019 035 044; do grep "| CER-$c |" docs/cer/backlog.md | grep -q 'OBSOLETE — verified Phase 115 / INFRA-310' || echo "UNANNOTATED CER-$c"; done`
     → no output.
   - CER-063: `grep -c 'OBSOLETE — verified Phase 115 / INFRA-310' docs/cer/backlog.md`
     → exactly **19** (the eighteen above plus the one CER-063 row; the second
     CER-063 row is untouched).
   - `grep -c 'Evidence:' docs/cer/backlog.md` → ≥ 19.

2. **The three off-format dispositions are normalized (Requires 2).**
   `CER-083` and `CER-091`'s `**Resolved by INFRA-NNN (Phase NN):**` become
   `**RESOLVED Phase NN — INFRA-NNN:**` (same wording otherwise, same
   position, no content change). `CER-060`'s last-column
   `RESOLVED cp-HARNESS002-main — …` text is left in place **and** a bold
   `**RESOLVED cp-HARNESS002-main — RESOLVER-006; see the resolution column.**`
   clause is appended to its Finding cell, so the row is discoverable by the
   same predicate as every other row without moving its historical text.
   - `grep -c '\*\*Resolved by' docs/cer/backlog.md` → 0.
   - `grep '| CER-060 |' docs/cer/backlog.md | grep -c '\*\*RESOLVED'` → 1.
   - `grep '| CER-083 |' docs/cer/backlog.md | grep -c '\*\*RESOLVED Phase 102'` → 1.
   - `grep '| CER-091 |' docs/cer/backlog.md | grep -c '\*\*RESOLVED Phase 104'` → 1.

3. **CER-091's sub-item (1) disposition is present and not re-opened.**
   INFRA-298 (Phase 113) closes the repeat-spawn-produces-no-row sub-item.
   CER-091's row carries INFRA-298's disposition sentence (either root cause
   + fix, or an explicit "no repeat-spawn drop observed since INFRA-264
   instrumentation" with a log-line count). This story **verifies its
   presence and does not author it**.
   - `grep '| CER-091 |' docs/cer/backlog.md | grep -c 'INFRA-298'` → ≥ 1.
   - If the clause is absent, **stop and report** — INFRA-298 is incomplete.

4. **CER-031 retained with a dated reason.** Its row gains:

   > `**BACKLOG-RETAIN — Phase 115 / INFRA-310. Not a defect and not
   > deferrable work: NP-6 is drafted and catalog-ready with zero flex code
   > surface. The only blocker is editorial timing in a repository this
   > project does not own — cloudnirvana/open-patterns PR #3. Trigger:
   > re-check `gh pr view 3 --repo cloudnirvana/open-patterns`; submit NP-6
   > as a follow-on PR once PR #3 merges or closes. Re-check date: <date
   > checked>, status: <observed status, or "not checked — no network
   > access from the build environment">.**`

   The builder **attempts** the `gh pr view` call and records the literal
   outcome, including a failure. A fabricated status is a CRITICAL finding.
   - `grep '| CER-031 |' docs/cer/backlog.md | grep -c 'BACKLOG-RETAIN'` → 1.
   - `grep '| CER-031 |' docs/cer/backlog.md | grep -c 'OBSOLETE\|RESOLVED'` → 0.

5. **CER-118 dispositioned as a survivor, not swept.** CER-118 (filed by
   INFRA-305) gains an explicit `**BACKLOG-RETAIN — Phase 115 / INFRA-310**`
   clause stating in one sentence that it is a **real, open, code-side
   defect** deliberately carried past the 0.3.1 line: hooks and sidebar are
   pointed at different pipes, the fix is a code story with a runtime
   behaviour change, and era 004 was scoped to doc/record closeout after the
   sibling code stories. It names INFRA-305 as the filer and CER-079 as the
   doc-side row that closed around it. **It must not be marked RESOLVED or
   OBSOLETE.**
   - `grep '| CER-118 |' docs/cer/backlog.md | grep -c 'BACKLOG-RETAIN — Phase 115 / INFRA-310'` → 1.
   - `grep '| CER-118 |' docs/cer/backlog.md | grep -c 'INFRA-305'` → ≥ 1.
   - `grep '| CER-118 |' docs/cer/backlog.md | grep -ci 'resolved\|obsolete'` → 0.

6. **Zero-open audit: enumeration command recorded and its output pasted.**
   A `## Evidence` section in this story file contains the verbatim command
   below and its complete verbatim output.

   ```bash
   python3 - <<'PY'
   import re, pathlib
   MARK = re.compile(r'\*\*(RESOLVED|SUPERSEDED|OBSOLETE|REJECTED|AMENDED|BACKLOG-RETAIN)\b')
   ROW  = re.compile(r'^\|\s*(CER-\d+[a-z]?)\s*\|')
   sec = None
   undispositioned = []
   for n, line in enumerate(pathlib.Path('docs/cer/backlog.md').read_text().splitlines(), 1):
       if line.startswith('## '):
           sec = line[3:].strip()
       m = ROW.match(line)
       if m and not MARK.search(line):
           undispositioned.append((n, sec, m.group(1)))
   print(f"undispositioned rows: {len(undispositioned)}")
   for row in undispositioned:
       print("  ", row)
   PY
   ```

   **Acceptance:** the printed count is **0**, *or* every listed row is named
   in the `## Evidence` block with an explicit one-sentence retain reason and
   an owner. A row appearing in this output with no accompanying reason is a
   FAIL. The single-predicate form is only valid because Ensures 2 normalized
   the three off-format rows — do not weaken the predicate to make the count
   pass.

   The enumeration is keyed on `(line number, section, ID)` because
   `CER-062..066` each appear twice (Requires 3); a set of bare IDs would
   silently under-count.

   **This assertion is editorial.** `## Evidence` must carry a one-line note
   stating that `next_action._check_cer_do_now` guards only `## Do Now`, that
   nothing mechanically enforces the Do Later / Do Much Later count, and that
   this enumeration is therefore a point-in-time record rather than a
   regression gate.

7. **`Last updated:` refreshed.** `docs/cer/backlog.md:3`'s `*Last updated: …*`
   line carries the build date.
   - `sed -n '3p' docs/cer/backlog.md` → matches `^\*Last updated: 2026-`
     and is a date **later than or equal to** the one INFRA-305 wrote.

8. **The Do Never placeholder row survives untouched (Requires 7).**
   - `awk '/^## Do Never/,0' docs/cer/backlog.md | grep -c '| — | \*(none)\* |'` → 1.
   - `git diff docs/cer/backlog.md` shows no deletion inside the
     `## Do Never` section.
   - `PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py next-action --project-dir .`
     does not report a CER Do Now block.

9. **Phase-107 index row deferred with a pointer.**
   **Already applied by the 2026-07-30 reconciliation sweep — this Ensures is
   now a verification, not an edit.** `docs/phases/index.md`'s phase-107 row
   status cell reads `deferred` and its Tag/notes cell names the superseding
   phases.
   - `grep '^| 107 |' docs/phases/index.md` → contains `deferred` and
     `113–116` / `INFRA-310`.

10. **Phase-107 era-003 ledger row deferred, in lockstep (Requires 8).**
    **Already applied by the 2026-07-30 reconciliation sweep — verify only.**
    - `grep '^| 107 |' docs/eras/003-flex-orchestrator-as-harness.md` →
      contains `deferred`.
    - The status strings in the two files are **byte-identical** for
      phase 107.

11. **`phase-107.md` gains a `## Superseded` note.**
    `docs/phases/phase-107.md` gains a `## Superseded` section that names
    era 004 and phases 113/114/115/116, states that the classification was re-done
    on merits (naming at least one concrete divergence — e.g. CER-069 was
    reclassified from phase-107's "legacy quick-fix" bundle to era-004's
    shared-blocker group and drained by INFRA-297), lists all five stubs
    INFRA-273..277 with the story that absorbed each one's scope, and states
    that **nothing was deleted**. The Goal, Stories table and Ordering
    sections are left intact as the historical record; the Stories table's
    five status cells are updated to `backlog` to match the story files.
    - `grep -c '^## Superseded' docs/phases/phase-107.md` → 1.
    - `for s in INFRA-273 INFRA-274 INFRA-275 INFRA-276 INFRA-277; do awk '/^## Superseded/,0' docs/phases/phase-107.md | grep -q "$s" || echo "MISSING $s"; done`
      → no output.
    - `grep -c 'phase-113\|113' docs/phases/phase-107.md` → ≥ 1.

12. **INFRA-273..277 flipped to `status: backlog` with a superseded-by note
    each (Requires 9).** **Already applied by the 2026-07-30 reconciliation
    sweep — verify only.** Each of the five story files has frontmatter
    `status: backlog` (**not** `deferred` — it is not a valid story status)
    and a body note naming the era-004 story or stories that absorbed its
    scope. The files are **not deleted** and their `phase: "107"` frontmatter
    is unchanged.
    - `for s in 273 274 275 276 277; do grep -q '^status: backlog' docs/stories/INFRA/INFRA-$s.md || echo "BAD STATUS INFRA-$s"; done`
      → no output.
    - `for s in 273 274 275 276 277; do grep -q 'INFRA-310' docs/stories/INFRA/INFRA-$s.md || echo "NO SUPERSESSION NOTE INFRA-$s"; done`
      → no output.
    - `grep -c '^phase: "107"' docs/stories/INFRA/INFRA-273.md` → 1.

13. **The index's backlog-promotions note is reconciled.**
    `docs/phases/index.md`'s `## backlog promotions` section (heading at
    `:152`) carries a line reading
    `- CER-078/079/084/085/086/035/014/065b, CER-012/006/010/069, CER-093/094/075, CER-070/062a/009/031 → Phase 107 …`
    (live anchor `:157`; **plan drift** — §C.1 cited `:154`). That line is
    **amended in place, not deleted** — it records a real operator decision
    dated 2026-07-25 — with a trailing clause noting the promotion was
    re-routed to phases 113/114/115/116 (the era-004 phase set) by INFRA-310 and that phase 107 is
    superseded.
    - `grep -n 'Phase 107' docs/phases/index.md` → the matching line contains
      `superseded` and `INFRA-310`.
    - The original promotion text before the amendment is still present
      (`git diff` shows an append, not a rewrite).

14. **`check-index` is clean — a true exit 0, not a baseline (AG-4).**
    - `PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py check-index --project-dir .`
      → exit code 0, no output. Run it and paste the exit code into
      `## Evidence`.
    - This now covers **both** the graph edits this story makes (phase
      106/107/108 dispositions, era rows) **and** the 48 pre-existing
      violations (Requires 17), all fixed per-category by Ensures 23. No
      suppression, allow-list, or check weakening anywhere in
      `index_integrity.py` — `git diff --name-only` must not contain it.
    - **Correct signal: exit 0 with every violation's underlying record made
      true. Forbidden proxy: exit 0 achieved by editing the checker or
      deleting the offending files.**

15. **Era-004 ledger matches the index (Requires 14).**
    `docs/eras/004-flex-operational-closeout-and-0-3-1.md`'s Phases table
    status for 113, 114 and 115 equals `docs/phases/index.md`'s status for the
    same phases. If `_mark_phase_complete_in_era_ledger` already advanced them,
    this is a verification with no edit; if a row drifted, correct the era doc
    to match the index (the index is the truth source per `index_integrity.py`'s
    2c framing).
    - Covered mechanically by Ensures 14; additionally record both files'
      113/114/115/116 rows verbatim in `## Evidence`.

16. **CHANGELOG 0.3.1 release section.** `CHANGELOG.md` gains, in this order
    from the top: a fresh empty `## [Unreleased]` heading, then
    `## [0.3.1] — <build date>`, and immediately under it four `### `
    entries for Phases 113, 114, 115 and 116 in reverse-merge order (116,
    115, 114, 113), each naming its stories by ID in the established voice
    (past tense, story ID in parentheses at the end of each bullet). The
    0.3.1 note also signals **beta status in prose** here and in
    `README.md` § Status — never via a version-string suffix (preserved
    do-not-do).

    Because the pre-existing entries below the new `## [0.3.1]` heading now
    fall under it and **three of them (Phases 95, 96, 98) landed on `main`
    before the `v0.3.0` fold tag** (Requires 13), `## [0.3.1]` carries one
    italic note line stating exactly that: the Phase 95/96/98 entries predate
    `v0.3.0` and appear here only because they were never given a release
    heading of their own. Do not re-section or move them — an honest note is
    correct; silently re-attributing dated work to 0.3.1 is not.
    - `grep -n '^## \[Unreleased\]' CHANGELOG.md` → line < the
      `## [0.3.1]` line.
    - `grep -c '^## \[0.3.1\]' CHANGELOG.md` → 1.
    - `for p in 113 114 115 116; do grep -q "Phase $p" CHANGELOG.md || echo "MISSING Phase $p"; done`
      → no output.
    - `for s in 296 297 298 299 300 301 302 303 304 305 306 307 308 309 310 311 312 313 314 315 316 317 318; do grep -q "INFRA-$s" CHANGELOG.md || echo "MISSING INFRA-$s"; done`
      → no output.
    - `wc -l < CHANGELOG.md` → **< 200** (`test_docs.py:25-29`'s cap). The
      pre-0.3.1 entry set grew with the era; if the four new phase entries
      cannot fit the cap, compress the *new* entries' bullet granularity —
      never delete historical entries.

17. **Version bumped to `0.3.1` across all four surfaces (Requires 10).**
    `0.3.1` is a **real release version with no pre-release suffix** — not
    `0.3.1-beta`, not `0.3.1-dev`.
    - `grep -c 'PAIRMODE_VERSION: str = "0.3.1"' skills/pairmode/scripts/_version.py` → 1.
    - `python3 -c "import json; print(json.load(open('.claude-plugin/plugin.json'))['version'])"` → `0.3.1`.
    - `python3 -c "import json; d=json.load(open('.claude-plugin/marketplace.json')); print([p['version'] for p in d['plugins'] if p['name']=='flex'])"` → `['0.3.1']`.
    - `grep -c '^pairmode_version: "0.3.1"$' skills/pairmode/SKILL.md` → 1.
    - `grep -rn '0\.3\.1-' skills/pairmode/scripts/_version.py .claude-plugin/ skills/pairmode/SKILL.md` → 0 matches.

18. **`test_version_match.py` green, unmodified.** All three of its tests pass
    against the bumped surfaces **without any edit to the test file** — the
    guard is doing its job, so touching it would be a tell that the bump is
    wrong.
    - `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_version_match.py -q` → 3 passed.
    - `git diff --name-only | grep -c 'test_version_match.py'` → 0.

19. **The fold-preparation version pin is re-anchored, not deleted
    (Requires 11).** `tests/pairmode/test_fold_preparation.py`'s
    `TestVersionFinalize::test_pairmode_version_is_0_3_0` is rewritten to
    assert the invariant it was actually protecting — that the dev-line
    pre-release suffix was dropped at the fold and never came back — in a form
    that survives future patch bumps:
    - the test is renamed (e.g. `test_pairmode_version_is_finalized`) and
      asserts (a) `PAIRMODE_VERSION` matches `^\d+\.\d+\.\d+$` — no `-dev` /
      `-beta` / any suffix; and (b) the version is `>= (0, 3, 0)` compared as
      a parsed integer tuple, so the fold floor still holds;
    - the module docstring's line 4 (`(a) _version.py == "0.3.0" (version
      finalized)`) is updated to describe the new assertion;
    - a one-line comment names INFRA-310 and states why the equality pin was
      replaced rather than bumped to `"0.3.1"` (a bare bump would re-break at
      0.3.2 — the intent is "finalized", not "0.3.0").
    - `grep -c 'test_pairmode_version_is_0_3_0' tests/pairmode/test_fold_preparation.py` → 0.
    - `grep -c 'INFRA-310' tests/pairmode/test_fold_preparation.py` → ≥ 1.
    - `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_fold_preparation.py -q` → all pass.
    - The other three test classes in the file (Signal-1 detection, runbook
      step, RELEASE-002 reconciliation) are **unchanged**:
      `git diff tests/pairmode/test_fold_preparation.py` touches only the
      docstring and `TestVersionFinalize`.

20. **`pairmode_migrate.py`'s `to-030` seed is NOT bumped (Requires 12).**
    - `grep -c '"pairmode_version": "0.3.0"' skills/pairmode/scripts/pairmode_migrate.py` → 1.
    - `git diff --name-only | grep -c 'pairmode_migrate.py'` → 0.

21. **No runtime behaviour change.** The only non-`docs/` files this story
    touches are `_version.py`, `.claude-plugin/plugin.json`,
    `.claude-plugin/marketplace.json`, `skills/pairmode/SKILL.md`,
    `CHANGELOG.md`, `.companion/state.json` (Ensures 27's one-key bump) and
    `tests/pairmode/test_fold_preparation.py`.
    - `git diff --name-only` intersected with `hooks/` → empty.
    - `git diff --name-only` intersected with `skills/companion/scripts/` and
      `skills/observability/` → empty.
    - Within `skills/pairmode/scripts/`, the only changed file is
      `_version.py`, and its only changed line is the `PAIRMODE_VERSION`
      literal.

22. **Full suite green.** Run **without `-x`**. No failures beyond `main`'s
    baseline of 4116 passed / 211 skipped. The passed count may change by at
    most the delta introduced by siblings; this story adds no new tests and
    removes none (Ensures 19 renames one in place).

23. **The 48 check-index violations are fixed per category (AG-4,
    Requires 17).** Each category's fix follows its Requires-17 rule; the
    per-category verification:
    - status-drift: `grep '^status:' docs/stories/OBS/OBS-006.md
      docs/stories/RELEASE/RELEASE-058.md` → neither reads `draft`/`backlog`
      unless its phase doc formally defers it; the chosen disposition and
      the commit evidence read are stated in `## Evidence`.
    - cross-link: the seven story files' `phase:` frontmatter each name an
      existing `docs/phases/phase-*.md`; `docs/eras/001-initial.md`'s five
      drifted rows equal the index's status strings byte-for-byte.
    - orphan-story: each of the 21 stories is referenced from the phase doc
      its frontmatter names, or reads `status: backlog` with a one-line
      body note; no story file is deleted.
    - deferred-without-section: the **existing** `## Deferred stories`
      section in `phase-97.md` is extended in place —
      `grep -c '^## Deferred stories' docs/phases/phase-97.md` → **exactly
      1** (a second heading is a FAIL), and
      `for s in 044 045 046 047 048 049 050 051 052 053 054 055 056; do awk '/^## Deferred stories/,0' docs/phases/phase-97.md | grep -q "RELEASE-$s" || echo "MISSING RELEASE-$s"; done`
      → no output. Phase-97's status everywhere stays `deferred`.

24. **Phase 108 superseded, mirroring phase 107 (AG-3).**
    **Partially applied by the 2026-07-30 reconciliation sweep.** The index
    and era-003 ledger rows for 108 already flip to `deferred` in lockstep
    (byte-identical status strings, same Requires-8 rule as phase 107), and
    INFRA-278/279 and RELEASE-072 story files already flip to `status:
    backlog` (**not** `deferred` — Requires 9's rule) with a superseded-by
    note each — verify these, do not re-edit. **Still this story's job:**
    `phase-108.md` gains a `## Superseded` section stating: INFRA-278's
    validation obligation splits in two — the SPA/UI half was discharged by
    INFRA-312 (name its evidence section), the effort-db integrity half was
    never discharged by INFRA-312 and was rescued as new story INFRA-329
    (phase 115, added by the 2026-07-30 reconciliation sweep as a sibling of
    INFRA-312 — name it here); INFRA-279's exit criterion was folded into the
    era-003 doc (Ensures 26); RELEASE-072's transition was executed by this
    story; nothing deleted.
    - `grep -c '^## Superseded' docs/phases/phase-108.md` → 1.
    - `grep -q 'INFRA-329' docs/phases/phase-108.md` → hit.
    - `for f in docs/stories/INFRA/INFRA-278.md docs/stories/INFRA/INFRA-279.md docs/stories/RELEASE/RELEASE-072.md; do grep -q '^status: backlog' $f || echo "BAD $f"; done`
      → no output.

25. **Phase 106 dispositioned complete-by-hand-migration, with the
    limitation written down (AG-3).** Index and era-003 rows for 106 read
    `complete` in lockstep; `phase-106.md` gains a closing note: completed
    by hand-migration per operator instruction (2026-07-28 hold-lift
    lineage), **with the stated evidence limitation** that hand-migration
    did not hold for the agent shells (F1) and that canon parity for the
    fleet arrives via the post-0.3.1 sync campaign enabled by INFRA-311.
    Precondition verified in `## Evidence`: INFRA-311 reads `complete` in
    phase-113's manifest **before** this edit is made.
    - `grep -qi 'hand-migration' docs/phases/phase-106.md` → hit.
    - `grep -qi 'INFRA-311' docs/phases/phase-106.md` → hit.

26. **Era 003 closed by ID; exactly one era active at tag time (AG-3).**
    After Ensures 23-25 and the phase-107 edits: the era-003 doc carries
    INFRA-279's exit criterion (a short `## Exit criterion` statement of
    what the era delivered, with the INFRA-312 evidence pointer), then the
    era is closed **by ID** via INFRA-314's gate-checked path —
    `status: complete` plus `closed_at: <build date>` in
    `docs/eras/003-flex-orchestrator-as-harness.md`'s frontmatter. No new
    era is scaffolded (004 exists).
    - `grep -c '^status: complete' docs/eras/003-flex-orchestrator-as-harness.md` → 1.
    - `grep -c '^closed_at:' docs/eras/003-flex-orchestrator-as-harness.md` → 1.
    - `grep -l '^status: active' docs/eras/*.md` → exactly
      `docs/eras/004-flex-operational-closeout-and-0-3-1.md`.
    - **Correct signal: the frontmatter state above via the gated path;
      forbidden proxy: hand-editing the frontmatter to dodge INFRA-314's
      undispositioned-phase refusal — if the gate refuses, a phase
      disposition above is wrong; fix it, don't bypass.**

27. **Flex's own `.companion/state.json` bumped (AG-5 item 5).** Its
    `pairmode_version` key reads `0.3.1`; no other key in the file changes
    (`git diff .companion/state.json` shows exactly one changed line).
    - `grep -o '"pairmode_version"[^,]*' .companion/state.json` →
      `"pairmode_version": "0.3.1"`.

28. **CER-124 and CER-126 annotated as this story's own rows.** Both gain
    `**RESOLVED Phase 116 — INFRA-310: <one sentence>.**` in place
    (CER-124: check-index driven to zero; CER-126: state.json bump). The
    spec-time "Absorbed at spec time by INFRA-310" pointer text is left in
    place; the bold token is appended.

## Instructions

**Ordering — this story is strictly the last story built across phases 113,
114, 115 and 116.** Before touching anything, derive the sibling set from the
Stories tables of all four phase docs (Requires 1) and confirm every derived
sibling reads `complete`. If any does not, **stop and report**. Every sibling annotates its own CER rows; running this
story early would either conflict with those edits or silently rebase them
away, and the Ensures-6 enumeration would be measuring an unfinished backlog.

**Note A — the plan's annotation set is corrected from 21 rows to 19.** The
closeout plan's INFRA-310 sketch lists `CER-065` and `CER-070` in this story's
annotate-only set. Both are already owned by siblings: `CER-070`'s residual
(the tracked `tsconfig.tsbuildinfo`) is drained by **INFRA-302**, and
`CER-065`'s residual (the `test_templates.py:612` `git clean -fd` assertion) is
drained by **INFRA-304** — and both of those specs already require their own
row annotation. Annotating them again here would double-annotate. **Do not
touch CER-065 or CER-070.** Verify instead: both must already carry a sibling
annotation when the Ensures-6 enumeration runs; if either is bare, that is an
incomplete sibling and grounds to stop and report, not to annotate it here.

**Note B — sibling-descoped rows.** If any sibling's `## Out of scope` or
`## Evidence` records that it *descoped* a row it was assigned, that row is
this story's to disposition: annotate it with the sibling's story ID, one
sentence naming what was descoped and why, and either `BACKLOG-RETAIN` (still
a real open finding) or `OBSOLETE` (no longer applicable). Read each sibling's
`## Out of scope` before running the enumeration — the enumeration will
surface such a row as un-dispositioned, but the *reason* only exists in the
sibling's spec.

**Note C — CER-118 is expected, not a failure.** INFRA-305 deliberately files
a real defect it does not fix (Requires 6). The correct response is Ensures 5:
give it an honest retain disposition and let it live past the 0.3.1 line. Do
not "close the audit" by resolving it, and do not treat its presence as a
reason to widen this story into a code fix.

**Spec-preflight note.** The preflight scan reports three constant warnings —
`OBSOLETE`, `AMENDED`, `RETAIN` "referenced in story but no definition found in
source tree". They are **intentional and correct**: these are markdown
disposition tokens in `docs/cer/backlog.md`'s prose vocabulary, not Python or
TypeScript constants. `RESOLVED` and `SUPERSEDED` are the same class and are
already in live use in the backlog today. Do not create code constants to
satisfy the scan — see the `## Out of scope` note on the rejected format
assertion for where a real vocabulary constant would belong if one is ever
built.

**Suggested build order** — verify first, edit second, stamp last:

1. **Verify preconditions.** Sibling statuses (Ordering, above); era-004
   ledger vs index for 113/114/115/116 (Ensures 15); CER-118 present (Requires 6);
   CER-091 carries INFRA-298's clause (Ensures 3). Record all four in
   `## Evidence`.

2. **Re-verify every Requires-4 anchor before quoting it.** Run each grep
   yourself. Sibling stories in phases 113 and 114 edited
   `schema_validator.py`, `story_new.py`, `flex_build.py`,
   `next_story.py` and `docs/architecture.md`, so several of these line
   numbers **will** have moved again since 2026-07-29. The live output wins
   over the table; record any discrepancy in `## Evidence`. Quoting a stale
   line number in a permanent backlog annotation is the exact failure this
   story exists to end.

3. **Annotate the nineteen obsolete rows** (Ensures 1), locating each by its
   `| CER-NNN |` cell and — for CER-063 — by the surrounding
   `fold-prep`/`INFRA-203` text (Requires 3).

4. **Normalize the three off-format dispositions** (Ensures 2), then
   **CER-031** (Ensures 4) and **CER-118** (Ensures 5), then `Last updated:`
   (Ensures 7).

5. **Run the Ensures-6 enumeration.** Paste command and output into
   `## Evidence`. Resolve any survivor by giving it a reason and an owner —
   never by loosening the predicate.

6. **Phase-107 supersession** (Ensures 9–13). Do all four edits together:
   index row, era-003 ledger row, `phase-107.md` `## Superseded` section +
   Stories-table statuses, and the five story files. Then the index
   promotions-note amendment.

7. **Run `check-index`** (Ensures 14). It is the mechanical proof that step 6
   left the index, era-003 ledger and era-004 ledger consistent. If it exits
   1, fix the desync before continuing — do not proceed to the version bump
   with a red graph.

8. **CHANGELOG** (Ensures 16), then the **four-surface version bump**
   (Ensures 17), then the **`test_fold_preparation.py` re-anchor**
   (Ensures 19). Run `test_version_match.py` and `test_fold_preparation.py`
   immediately after the bump — before the full suite — so a version-surface
   miss is diagnosed in seconds rather than in a 4000-test run.

9. **Full suite without `-x`** (Ensures 22).

**Do not:**
- annotate `CER-065` or `CER-070` (Note A — sibling-owned);
- annotate any row a sibling already annotated (re-annotation is
  double-annotation; verify presence instead);
- delete, re-word beyond the appended clause, or re-quadrant any CER row;
- delete the `## Do Never` placeholder row (Requires 7);
- delete `docs/phases/phase-107.md` or any of `INFRA-273..277` (Ensures 11/12);
- set any of INFRA-273..277 to `status: deferred` (not a valid story status,
  Requires 9);
- edit `tests/pairmode/test_version_match.py` (Ensures 18);
- bump `pairmode_migrate.py`'s `to-030` seed literal (Ensures 20);
- edit `docs/fleet-snapshot.md`'s recorded `0.3.0` values — they are a dated
  observation of downstream projects, not a version surface;
- edit any file under `hooks/`, `skills/companion/scripts/` or
  `skills/observability/` (Ensures 21);
- weaken the Ensures-6 predicate, or add an ID allow-list to it, to make the
  count reach zero.

**Ideology alignment note (Step 4a).** The draft was checked against
`docs/ideology.md`. Two adjustments were made to route around conflicts rather
than through them: (i) *"Never silently pass contradictions"* — an audit that
reached zero by resolving CER-118 or by exempting it from the predicate would
be precisely the false confidence the conviction names as worse than no
system, so Ensures 5 and 6 require the survivor to be named with a reason and
an owner, and Ensures 6 additionally requires the story to state in writing
that the target is editorial and mechanically unenforced; the same conviction
drives Note A's refusal to double-annotate and Ensures 2's normalization
(three disposition formats meant the "49 open rows" figure was only accidentally
correct). (ii) The `## Accepted constraints` entries *"Hooks are thin relays
only"* and *"Sidebar owns all state writes"* carry **no override path** — and
CER-118 is a live divergence between those two surfaces. This story deliberately
does **not** touch either (Ensures 21); it records the divergence as an open
finding carried past the release rather than papering over it, which preserves
the constraints' rationale rather than merely their letter. No conviction is
contradicted by anything drafted here.

## Tests

Immediately after the version bump (before the full run):

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_version_match.py \
  tests/pairmode/test_fold_preparation.py \
  tests/pairmode/test_plugin_manifest.py \
  -q 2>&1 | tail -20
```

Documentation and index-integrity surfaces this story edits:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_docs.py \
  tests/pairmode/test_index_integrity.py \
  tests/pairmode/test_cer.py \
  tests/pairmode/test_next_action.py \
  -q 2>&1 | tail -20
```

Full suite, run **without `-x`** so a pre-existing failure cannot mask a new
one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -20
```

Graph integrity (not a pytest — run it directly and record the exit code):

```bash
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py \
  check-index --project-dir .
echo "check-index exit: $?"
```

**Acceptance:**
- Both targeted runs: 0 failures.
- `check-index`: exit 0, no output.
- Full run: no failures beyond `main`'s baseline of 4116 passed / 211 skipped.
- The Ensures-6 enumeration prints `undispositioned rows: 0`, or every listed
  row is named in `## Evidence` with a retain reason and an owner.

**New tests this story authors: none.** It renames and re-anchors exactly one
existing test (`test_pairmode_version_is_0_3_0` →
`test_pairmode_version_is_finalized`, Ensures 19) and adds no test file. The
`story_class: doc` "no test file expected" exemption does **not** apply — the
reviewer must run both targeted commands and the full suite and report the
results, because the version bump's blast radius is every test that reads a
version surface.

**Negative checks the reviewer must perform:**
1. **The audit was not made to pass by weakening it.** Re-run the Ensures-6
   snippet verbatim from this spec (not from the builder's `## Evidence`) and
   confirm the count matches what was pasted.
2. **Annotations are not fabricated.** Spot-check at least five of the
   nineteen `OBSOLETE` annotations by opening the cited `file:line` and
   confirming the quoted fragment is actually there. A quoted line number that
   does not contain the quoted text is a CRITICAL finding.
3. **CER-118 and CER-031 are still open.** Confirm neither carries a
   `RESOLVED` or `OBSOLETE` token.
4. **CER-065 and CER-070 were not touched by this story.** `git diff` for
   those two rows should show a sibling's annotation already in the base, not
   an INFRA-310 clause.
5. **The version pin was re-anchored, not merely bumped.** Confirm
   `test_fold_preparation.py` no longer contains any hardcoded three-part
   version string equality — a `== "0.3.1"` pin would re-break at 0.3.2 and
   is a HIGH finding.

## Out of scope

- **Fixing CER-118 (the hook↔sidebar pipe divergence).** It is a runtime code
  change with a real behaviour delta and needs its own story with tests and a
  security review. This story gives it an honest retain disposition and
  carries it past the 0.3.1 line (Ensures 5). `docs/pipe-architecture.md`
  likewise stays unrewritten — it is bound to CER-118's resolution.

- **Submitting NP-6 to `cloudnirvana/open-patterns` (CER-031).** The trigger
  is an external repository's PR timing. This story records the trigger and
  the observed status; it does not open a PR.

- **A durable `tests/pairmode/test_cer.py` assertion that the backlog holds
  zero un-dispositioned rows.** The closeout plan suggests one. **Evaluated
  and rejected as not feasible today, honestly:** such a test would fail the
  moment anyone files a new CER row, which is the *intended* workflow —
  `docs/cer/backlog.md` is a live intake surface, and every future cold-eyes
  review is supposed to add bare rows to it. A zero-open assertion would
  therefore have to be either (a) dated/snapshotted, which is a
  hand-maintained list with the same drift surface it is meant to police, or
  (b) scoped to "rows older than N days", which encodes an arbitrary SLA
  nobody has agreed to. A genuinely useful mechanical guard here would be a
  **format** assertion, not a **count** assertion — e.g. "every row whose
  Finding cell contains a bold disposition token uses one of the six
  vocabulary words" — which Ensures 2's normalization makes possible for the
  first time. That is a small, real follow-on and is named here rather than
  built, because it is a new guard rather than a closeout record, and adding
  a new guard in the story that stamps the release is the wrong order.

- **Re-sectioning the pre-`v0.3.0` CHANGELOG entries** (Phases 95, 96, 98).
  They are noted as predating the tag (Ensures 16), not moved. Rewriting dated
  release history to be tidy is a different and riskier job.

- **Any CHANGELOG backfill other than Phases 113/114/115/116.** The Phase 99
  backfill belongs to INFRA-305.

- **Closing era 004.** ~~Closing era 003~~ — **reversed by AG-3
  (2026-07-29):** era-003 closure is now IN scope (Ensures 24-26 fold in
  RELEASE-072's transition, INFRA-279's exit criterion and the phase-106/108
  dispositions; the close runs by ID through INFRA-314's gated path). Era
  004's own close remains a later act — this story ships 0.3.1 with era 004
  still `active`.

- **Tagging the release.** `git tag`, pushes and the checkpoint sequence are
  the operator's and the checkpoint gate's job, not the builder's. This story
  writes files only.

- **Bumping any downstream project's `state.json["pairmode_version"]`.** The
  fleet reads `0.3.0` today (`docs/fleet-snapshot.md`); rolling 0.3.1 out is
  a `sync-all` campaign, not a version-record story.
