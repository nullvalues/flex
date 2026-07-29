---
id: INFRA-305
rail: INFRA
title: Build-loop doc and procedure currency sweep
status: draft
phase: "114"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/security-auditor/procedure.md
  - docs/architecture.md
  - CHANGELOG.md
touches:
  - README.md
  - docs/brief.md
  - docs/reconstruction.md
  - docs/cer/backlog.md
  - tests/pairmode/test_docs.py
  - tests/pairmode/test_procedure_skills.py
  - docs/stories/INFRA/INFRA-305.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase 114's four sibling stories fix build-loop *code*. This one fixes the
build-loop *contract* — the documents a cold-starting agent reads before it is
allowed to judge that code. Seven CER rows (CER-078, 079, 084, 085, 086, 100,
112) are all the same defect class: a document that described the system
correctly when it was written and has silently diverged since.

Three of them — **CER-078, CER-084, CER-100** — are not cosmetic. They sit in
`skills/pairmode/skills/security-auditor/procedure.md`, which is the
**grading contract** the checkpoint security auditor is dispatched with. That
worker reads the procedure cold, with no repo history, and returns CRITICAL /
HIGH / MEDIUM / LOW verdicts that gate a phase tag. Its "Documented
thin-delegation exceptions" list is the whitelist of hook behaviour that is
*authorized*; its PIPE CONTRACT check is the description of the pipe path
hooks are *required* to use. Both are stale:

- the exception list names `session_reset` for `session_start.py` but not the
  `reconcile_pending_attempts` sweep that hook has imported since INFRA-258
  (CER-100), and names only the context-token writes for `post_tool_use.py`
  but not `record_step_growth` (CER-084);
- the PIPE CONTRACT check still instructs the auditor to verify hooks read
  their pipe path from `state.json["pipe_path"]`, a key INFRA-238 retired
  (CER-078).

A stale grading contract is therefore an **operational defect, not a doc
nicety**: the next auditor reading it literally will either flag compliant
code CRITICAL (false positive that blocks a checkpoint) or pass
non-compliant code (false negative). Phase 100's auditor already had to
re-derive `record_step_growth`'s authorization from `docs/architecture.md`
because the procedure did not carry it — the cost has been paid once already.

The remaining four rows are the surrounding truth-set: `docs/architecture.md`
§ Data flow still describes an md5-hashed project-scoped pipe no hook writes
to (CER-079); the deny-list passages present a protection surface that
INFRA-253's doctrine retired (CER-085); `CHANGELOG.md` skipped its Phase 99
entry (CER-086); and `docs/brief.md` / `docs/reconstruction.md` still say the
plugin has three skills when it has four (CER-112).

The whole class exists because **nothing tests any of it**. This story
therefore does not only correct text — it lands a durable mechanical parity
assertion between the hook sources and the procedure's exception list, so the
CER-078/084/100 shape fails a test the next time it recurs instead of being
found by a cold-eyes review two phases later.

This story runs **last in Phase 114**: it annotates the backlog rows that
INFRA-301..304 close, so it must observe their completed state.

## Requires

Anchors below were re-verified against the working tree on 2026-07-29. Several
CER rows cite line numbers that have since drifted; the corrected anchor is
given, and the drift is called out.

1. **INFRA-301, INFRA-302, INFRA-303, INFRA-304 are complete and merged.**
   Each annotates its own CER rows in `docs/cer/backlog.md`; this story's
   backlog edits must be applied on top of theirs, not concurrently with
   them. If any sibling is incomplete, stop and report — do not annotate a
   row a sibling still owns.

2. **`skills/pairmode/skills/security-auditor/procedure.md`**
   - Check 1's "Documented thin-delegation exceptions — do NOT flag these
     (BUILD-041)" block spans lines 80-108 and contains exactly four hook
     bullets: `hooks/pre_tool_use.py`, `hooks/post_tool_use.py`,
     `hooks/session_start.py`, `hooks/user_prompt_submit.py`.
   - The `session_start.py` bullet names only `session_reset.py` and three
     state.json writes (token baseline, recorded-at, session-reset stamp).
   - The `post_tool_use.py` bullet names only `context_budget.py` and "the
     live context-token count and its recorded-at timestamp".
   - The `pre_tool_use.py` bullet names only `context_budget.py` and
     `scope_guard.py`, and only `context_budget_acknowledged_at`.
   - `### 2. PIPE CONTRACT (CRITICAL if violated)` begins at line 111; line
     113 reads
     `(read from \`.companion/state.json["pipe_path"]\`, fallback \`/tmp/companion.pipe\`)?`

3. **`skills/pairmode/skills/reviewer/procedure.md:235-243`** carries the
   correct post-INFRA-238 text and is the copy source for Ensures 1:

   > Do all hook scripts write only to the single hardcoded pipe path
   > (`os.path.join(tempfile.gettempdir(), "companion.pipe")`, the same
   > convention `post_tool_use.py` established)? (INFRA-238) The `pipe_path`
   > state.json key was retired by `pairmode_migrate.py`'s `to-030` step and
   > no hook script reads it any longer.

4. **Hook → scripts import facts** (the ground truth Ensures 2/3/12 assert
   against; produced by AST walk of `hooks/*.py` against the module basenames
   in `skills/pairmode/scripts/`):

   | Hook | Imported from `skills/pairmode/scripts/` |
   |---|---|
   | `post_tool_use.py` | `context_budget`, `session_state`, `state_utils`, `subagent_transcript` |
   | `pre_tool_use.py` | `cold_read_guard`, `context_budget`, `scope_guard`, `scope_guard.resolve_call_story`, `state_utils.update_state_json`, `flex_build._read_story_frontmatter`, `flex_build._story_path` |
   | `session_start.py` | `session_reset`, `session_state`, `state_utils`, `subagent_transcript.reconcile_pending_attempts` |
   | `user_prompt_submit.py` | `user_turn_seq.record_user_turn` |

   `hooks/stop.py`, `hooks/session_end.py` and `hooks/exit_plan_mode.py`
   import nothing from `skills/` — consistent with
   `docs/architecture.md:2573` ("plain pipe relays … do not require
   thin-delegation exception documentation").

   **Anchor drift:** CER-100 cites `hooks/session_start.py:104` for the
   `reconcile_pending_attempts` import. The live line is
   **`hooks/session_start.py:157`**. `record_step_growth` (CER-084) is called
   at `hooks/post_tool_use.py:124`.

5. **Pipe-path ground truth.**
   - Every hook that writes the pipe uses a flat path:
     `hooks/stop.py:18`, `hooks/session_end.py:19`,
     `hooks/exit_plan_mode.py:16`, `hooks/post_tool_use.py:50` —
     `os.path.join(tempfile.gettempdir(), "companion.pipe")`;
     `hooks/session_start.py:35` — the `Path`/`str` form of the same.
   - `docs/architecture.md:168-169` (§ Data flow) claims
     `stop.py hook → writes to /tmp/companion-<hash>.pipe` with
     "(pipe path is project-scoped; hash is first 8 chars of md5 of project
     dir)". **This is false for every hook.**
   - **Newly discovered, not in any CER row:**
     `skills/companion/scripts/sidebar.py:1677-1679` still computes
     `_hash = hashlib.md5(...)` and sets
     `PIPE_PATH = f"/tmp/companion-{_hash}.pipe"`, then `mkfifo`s and reads
     *that* path (`:1709-1710`, `:1753`) and writes it back to
     `state.json["pipe_path"]` (`:1692`). So the md5 claim is not merely
     stale prose — hooks and sidebar are pointed at **different pipes**. This
     story documents the divergence and files it; it does **not** fix the
     code (see Ensures 14 and Out of scope).
   - `docs/architecture.md:2299` says hooks "Write a JSON message to
     `/tmp/companion.pipe`" — right shape, hardcoded `/tmp` rather than
     `tempfile.gettempdir()`.
   - `docs/architecture.md:2578` points at `docs/pipe-architecture.md` "for
     the project-scoped pipe design", which is the same retired design.

6. **Deny-list passages (CER-085).** The row cites
   `docs/architecture.md:583,605` and `README.md:162`. **All three anchors
   have drifted.** Live anchors:
   - `docs/architecture.md:1045` — "pairmode functions without the sidebar
     (the deny list still blocks protected-file writes; …)"
   - `docs/architecture.md:1067` — "**Spec-derived protections:** The deny
     list in a pairmode project's `.claude/settings.json` is generated from
     the project's `spec.json` non-negotiables…"
   - `docs/architecture.md:1416` — "`protected_files` is derived from the
     deny list in `CLAUDE.md` § Protected…"
   - `docs/architecture.md:1789` — "The deny list generator must include an
     inline comment on each generated rule…"
   - `README.md:68` (composition table) and `README.md:161` (skills table
     "Key output" cell) and `README.md:178` (Scenario A step 2).
   - The doctrine to reconcile against is
     `docs/architecture.md:759-777`, "**`.claude/settings.json` end-state
     doctrine (INFRA-253)**" inside § 9.5 (§ 9.5 heading at
     `docs/architecture.md:616`).

7. **CHANGELOG (CER-086).** `## [Unreleased]` at `CHANGELOG.md:7`. Phase
   entries are `### ` headings in reverse-chronological *merge* order (112,
   111, 110, 105, 109, 104, 103, 102, 101, 100, 98, 96, 95, …) — not strict
   numeric order. `### Added [pairmode] — Phase 100` is at line 54 and
   `### Added [pairmode] — Phase 98` at line 59; the Phase 99 entry belongs
   between them. There is no Phase 99 heading today. The backfill source is
   `docs/phases/phase-99.md`, whose Stories table (lines 71-76) lists
   INFRA-247..252, all `complete`. `CHANGELOG.md` is 136 lines and
   `tests/pairmode/test_docs.py:25-29` caps it at 200.

8. **Skill count (CER-112).** `docs/brief.md:10` and
   `docs/reconstruction.md:12` both read
   `Flex is a Claude Code plugin with three skills:` and each enumerate only
   `pairmode`, `companion`, `seed`. `skills/*/SKILL.md` is exactly four:
   `companion`, `observability`, `pairmode`, `seed`. `README.md:157` already
   says "## The four skills" and `README.md:165` carries the
   `/flex:observability` row — README is the corrected exemplar.
   `skills/pairmode/templates/docs/reconstruction.md.j2` is project-neutral
   and contains no skill count — the template is **not** a fix target.

9. **Test homes.** `tests/pairmode/test_docs.py` (repo-doc assertions,
   `REPO_ROOT` via `Path(__file__).resolve().parent.parent.parent`) and
   `tests/pairmode/test_procedure_skills.py` (procedure-text assertions;
   already defines `SECURITY_AUDITOR_PROCEDURE` at line 72 and
   `REVIEWER_PROCEDURE` at line 17) both exist and are green.

10. **Baseline.** `main`'s suite is green at 4116 passed / 211 skipped.

## Ensures

Every grep below is run from the repo root and is stated with its expected
result so the reviewer can execute it verbatim.

1. **CER-078 — PIPE CONTRACT text corrected.**
   `skills/pairmode/skills/security-auditor/procedure.md`'s `### 2. PIPE
   CONTRACT` body no longer instructs reading the pipe path from state.json.
   Its replacement text is semantically equivalent to
   `skills/pairmode/skills/reviewer/procedure.md`'s current § 2 (Requires 3),
   naming `os.path.join(tempfile.gettempdir(), "companion.pipe")`, the
   INFRA-238 reference, and the fact that the `pipe_path` key was retired by
   `pairmode_migrate.py`'s `to-030` step. The check's CRITICAL severity and
   its second question (hooks writing directly to spec files or
   `.companion/`) are preserved.
   - `grep -c 'pipe_path' skills/pairmode/skills/security-auditor/procedure.md`
     → the only surviving occurrences (if any) are inside a retired-key
     sentence of the form "the `pipe_path` state.json key was retired"; there
     is **no** occurrence instructing the auditor to *read* it. Concretely:
     `grep -n 'read from .*pipe_path' skills/pairmode/skills/security-auditor/procedure.md`
     → 0 matches.
   - `grep -c 'tempfile.gettempdir' skills/pairmode/skills/security-auditor/procedure.md`
     → ≥ 1.
   - `grep -c 'INFRA-238' skills/pairmode/skills/security-auditor/procedure.md`
     → ≥ 1.
   - Repo-wide `pipe_path` occurrences elsewhere (`sidebar.py`,
     `pairmode_migrate.py`, `pairmode_status.py`, `docs/pipe-architecture.md`,
     historical phase docs) are **out of scope and must not be edited** — the
     plan's "grep `pipe_path` → 0" is corrected to this file-scoped form
     (see Instructions, note A).

2. **CER-100 — `session_start.py` exception bullet made current.**
   The `hooks/session_start.py` bullet in the exception list names, verbatim:
   `subagent_transcript.reconcile_pending_attempts` (with the INFRA-258
   reference) and `session_state` (the INFRA-285 per-session keyed
   `state.json` view), in addition to the existing `session_reset.py`
   dispatch and its three state writes.
   - `awk '/Documented thin-delegation exceptions/,/### 2\. PIPE CONTRACT/'
     skills/pairmode/skills/security-auditor/procedure.md | grep -c
     'reconcile_pending_attempts'` → ≥ 1.
   - Same extraction `| grep -c 'session_state'` → ≥ 1.

3. **CER-084 — `post_tool_use.py` exception bullet made current.**
   That bullet names `record_step_growth` and the two state.json keys it
   writes (`context_step_growth_samples`, `expected_step_tokens`) with the
   INFRA-254 reference, and names `subagent_transcript` (the INFRA-236
   effort-recording delegation) and `session_state`.
   - Exception-block extraction `| grep -c 'record_step_growth'` → ≥ 1
   - `| grep -c 'context_step_growth_samples'` → ≥ 1
   - `| grep -c 'expected_step_tokens'` → ≥ 1
   - `| grep -c 'subagent_transcript'` → ≥ 2 (session_start + post_tool_use
     bullets).

4. **Exception-list completeness beyond the filed rows.** The
   `hooks/pre_tool_use.py` bullet additionally names `cold_read_guard`
   (INFRA-196 `Read` dispatch), `scope_guard.resolve_call_story` (INFRA-281),
   `state_utils`, `flex_build` (the `_story_path` /
   `_read_story_frontmatter` helpers), and the second authorized state key
   `context_budget_acknowledged_user_turn_seq` (INFRA-193). Every module
   basename in the Requires-4 table appears in its hook's bullet.
   - Exception-block extraction `| grep -c 'cold_read_guard'` → ≥ 1
   - `| grep -c 'context_budget_acknowledged_user_turn_seq'` → ≥ 1
   - `| grep -c 'state_utils'` → ≥ 1
   - `| grep -c 'flex_build'` → ≥ 1
   - This item exists because Ensures 12's parity test fails without it; it
     is the same defect class as CER-084/100 with no filed row.

5. **CER-079 — § Data flow pipe description corrected.**
   `docs/architecture.md` § Data flow (the fenced block at ~:163-179) is
   corrected so the hook write target is the single flat
   `tempfile.gettempdir()/companion.pipe` path, and the parenthetical
   claiming the path is project-scoped by an md5 hash of the project dir is
   removed.
   - `sed -n '/^## Data flow/,/^---/p' docs/architecture.md | grep -ci 'md5'`
     → 0.
   - `sed -n '/^## Data flow/,/^---/p' docs/architecture.md | grep -c
     'companion-<hash>.pipe'` → 0.
   - `sed -n '/^## Data flow/,/^---/p' docs/architecture.md | grep -c
     'tempfile.gettempdir'` → ≥ 1.

6. **CER-079 — the two downstream architecture claims reconciled.**
   `docs/architecture.md:2299`'s "Write a JSON message to
   `/tmp/companion.pipe`" is corrected to the `tempfile.gettempdir()` form,
   and `docs/architecture.md:2578`'s "See `docs/pipe-architecture.md` for the
   project-scoped pipe design…" is rewritten so it no longer asserts the
   retired project-scoped design is current — it must label
   `docs/pipe-architecture.md` as a historical record of the superseded
   design and point at the INFRA-238 flat-path convention as current.
   - `grep -c '/tmp/companion.pipe' docs/architecture.md` → 0.
   - `grep -n 'pipe-architecture.md' docs/architecture.md` → the matching
     line contains `historical` or `superseded`.

7. **CER-085 — deny-list doctrine reconciled.**
   Each live deny-list passage (`docs/architecture.md:1045`, `:1067`,
   `:1416`, `:1789`; `README.md:68`, `:161`, `:178` — re-locate by text, the
   line numbers will have shifted) is amended so it states which surface is
   authoritative: `scope_guard` + the per-story permissions artifacts are the
   enforcement surface (INFRA-253, § 9.5), and the spec-derived
   `.claude/settings.json` deny list is a **bootstrap-era convenience**
   retained for downstream projects, not a protection surface flex itself
   relies on. Passages are amended in place, not deleted — the downstream
   mechanism still exists.
   - `grep -c 'INFRA-253' docs/architecture.md` → strictly greater than its
     pre-change count (record both numbers in `## Evidence`).
   - `grep -n 'deny list' docs/architecture.md README.md` → every hit sits
     within three lines of the words `scope_guard` **or** `bootstrap-era`
     **or** `INFRA-253`.
   - `docs/architecture.md:759-777`'s INFRA-253 doctrine block is unchanged
     (it is already correct): `git diff` shows no edit inside § 9.5's
     end-state-doctrine paragraph.

8. **CER-086 — Phase 99 CHANGELOG entry backfilled.**
   A `### Fixed [pairmode] — Phase 99 (Post-fold self-sync remediation)`
   heading exists in `CHANGELOG.md`, positioned strictly between the
   `Phase 100` heading and the `Phase 98` heading, with one bullet per
   INFRA-247..252 (or a small number of merged bullets that name all six
   story IDs), sourced from `docs/phases/phase-99.md`'s Stories table.
   - `grep -c 'Phase 99' CHANGELOG.md` → ≥ 1.
   - `python3 -c "import re,pathlib; t=pathlib.Path('CHANGELOG.md').read_text().splitlines();
     i=lambda s:[n for n,l in enumerate(t) if l.startswith('### ') and s in l][0];
     assert i('Phase 100') < i('Phase 99') < i('Phase 98')"` → exits 0.
   - `for s in INFRA-247 INFRA-248 INFRA-249 INFRA-250 INFRA-251 INFRA-252;
     do grep -q "$s" CHANGELOG.md || echo "MISSING $s"; done` → no output.
   - `wc -l < CHANGELOG.md` → < 200 (`test_docs.py`'s existing cap).

9. **CER-112 — skill count corrected in both documents.**
   `docs/brief.md:10` and `docs/reconstruction.md:12` read
   `Flex is a Claude Code plugin with four skills:` and each gains a
   `/flex:observability` bullet describing the local browser dashboard,
   consistent with `README.md:165`'s row.
   - `grep -c 'three skills' docs/brief.md docs/reconstruction.md` → 0 for
     both files.
   - `grep -c 'four skills' docs/brief.md docs/reconstruction.md` → ≥ 1 for
     both files.
   - `grep -c 'flex:observability' docs/brief.md docs/reconstruction.md` →
     ≥ 1 for both files.
   - Historical phase docs containing "three skills"
     (`docs/phases/phase-20.md`, `-22`, `-41`, `-111`) are **not** edited —
     they are dated records.

10. **Skill-count parity test.** `tests/pairmode/test_docs.py` gains
    `test_skill_count_prose_matches_skill_dirs`, which computes
    `n = len(list((REPO_ROOT / "skills").glob("*/SKILL.md")))`, maps it
    through a small number-word table (`{3: "three", 4: "four", 5: "five",
    6: "six"}`), and asserts the phrase
    `f"plugin with {word} skills"` appears in **both** `docs/brief.md` and
    `docs/reconstruction.md`. It additionally asserts `n >= 4` as an
    anti-vacuity floor (a glob that matches nothing must fail, not pass), and
    asserts each skill directory basename appears at least once in each of
    the two documents.

11. **`pipe_path`-absence test.** `tests/pairmode/test_procedure_skills.py`
    gains an assertion that
    `skills/pairmode/skills/security-auditor/procedure.md` contains no line
    matching `read from .*pipe_path` and does contain the literal
    `tempfile.gettempdir()`. The same two assertions are applied to
    `skills/pairmode/skills/reviewer/procedure.md` (already true today — this
    pins the copy source so the two procedures cannot drift apart again).

12. **Durable procedure-vs-architecture parity test (the reason this class
    exists).** `tests/pairmode/test_procedure_skills.py` gains
    `test_hook_delegations_are_documented_exceptions`, which:
    - builds `mods = {p.stem for p in (REPO_ROOT/"skills"/"pairmode"/"scripts").glob("*.py")}`;
    - for each `hooks/*.py`, walks its `ast` for `Import` / `ImportFrom`
      nodes (module-level **and** function-local — every real delegation in
      these hooks is a lazy import) whose module basename is in `mods`,
      producing a set of delegate module names plus, for `ImportFrom`, the
      imported symbol names;
    - extracts the exception block from
      `skills/pairmode/skills/security-auditor/procedure.md` between the
      literal `Documented thin-delegation exceptions` and the literal
      `### 2. PIPE CONTRACT`;
    - asserts, for every hook with a non-empty delegate set, that the hook's
      filename **and** every delegate module name **and** every imported
      symbol name appear in that extracted block;
    - asserts hooks with an empty delegate set (`stop.py`, `session_end.py`,
      `exit_plan_mode.py`) are correctly absent from the block, matching
      `docs/architecture.md:2573`;
    - carries a failure message naming CER-078/084/100 and the hook that
      drifted.

    The test must fail on the pre-change procedure text (prove this in
    `## Evidence` by running it once before applying Ensures 2/3/4) and pass
    after. No allow-list is permitted: if a delegate is genuinely not worth
    documenting, the right move is to remove the import, not to except it.

13. **Feasibility record for the state-key half of the parity check.** The
    story body records — in a short `## Evidence` note and mirrored as a
    one-line comment above `test_hook_delegations_are_documented_exceptions`
    — that the *import* half of the exception list is mechanically checkable
    (Ensures 12) but the *state.json key* half is not, because the keys are
    written inside the delegate modules (`session_reset.decide_reset` returns
    a dict the hook splats; `context_budget.record_step_growth` writes its
    own keys) and never appear as literals in the hook source. A key-level
    parity test would require either a hand-maintained hook→key map (the same
    drift surface it is meant to police) or a call-graph analysis of the
    delegate modules. It is therefore **not built here** and is named in
    `## Out of scope`.

14. **Pipe divergence filed, not fixed.** A new row `CER-118` is appended to
    `docs/cer/backlog.md` § Do Later recording the Requires-5 finding: hooks
    write `tempfile.gettempdir()/companion.pipe` while
    `skills/companion/scripts/sidebar.py:1677-1710` `mkfifo`s and reads
    `/tmp/companion-<md5[:8]>.pipe` and writes that path back to
    `state.json["pipe_path"]:1692`, so on any project the sidebar reads a
    pipe no hook writes to. Row cites this story as its source, the
    file:line evidence above, and states `docs/pipe-architecture.md` is stale
    for the same reason. CER-118 is **not** resolved by this story.
    - `grep -c 'CER-118' docs/cer/backlog.md` → ≥ 1.
    - `grep -c 'CER-118' docs/cer/backlog.md` inside the `## Do Later`
      section (`awk '/^## Do Later/,/^## Do Much Later/'`) → ≥ 1.

15. **RESOLVED annotations on all seven rows.** Each of CER-078, CER-079,
    CER-084, CER-085, CER-086, CER-100, CER-112 in `docs/cer/backlog.md`
    gains a bold `**RESOLVED Phase 114 — INFRA-305 …**` clause naming this
    story ID and, in one sentence, what changed and where. CER-079's
    annotation must additionally name CER-118 as the code-side residue it
    does *not* close.
    - `for c in 078 079 084 085 086 100 112; do
        grep "| CER-$c |" docs/cer/backlog.md | grep -q 'RESOLVED Phase 114 — INFRA-305'
        || echo "UNANNOTATED CER-$c"; done` → no output.
    - `grep '| CER-079 |' docs/cer/backlog.md | grep -c 'CER-118'` → 1.
    - Rows are annotated in place; no row is deleted or moved between
      quadrants.

16. **Backlog `Last updated:` refreshed.** `docs/cer/backlog.md:3`'s
    `*Last updated: …*` line carries the build date.
    (Note: INFRA-310 refreshes it again at era close; both are correct.)

17. **No code behaviour change.** `git diff --name-only` for this story
    intersected with `hooks/`, `skills/pairmode/scripts/`, and
    `skills/companion/scripts/` is empty. The only non-`docs/` non-`.md`
    files touched are the two test files.

18. **Targeted suites and full suite green.**
    `uv run pytest tests/pairmode/test_docs.py tests/pairmode/test_architecture_policy.py
    tests/pairmode/test_skill_md.py tests/pairmode/test_procedure_skills.py
    tests/pairmode/test_plugin_manifest.py -q` → all pass.
    Full suite run **without `-x`** matches the 4116 passed / 211 skipped
    baseline (or exceeds it by the tests this story adds), with no new
    failures.

19. **(F8, AG-5 item 2) README's build-loop description matches the shipped
    loop.** `README.md`'s description of the build loop predates CER-074: it
    states the resolver emits `spawn-reviewer`. In the shipped loop the
    resolver's builder iteration carries the reviewer dispatch and the
    PASS/FAIL branch as orchestrator-held prose — the reviewer is dispatched
    by the orchestrator inside the same `spawn-builder` iteration
    (`next_action.py:163` comment is the code-side anchor). The README
    section is corrected to describe that shape (resolver actions vs
    orchestrator-held steps, in ≤ 15 changed lines), and the CER-123 row
    filed 2026-07-29 gains
    `**RESOLVED Phase 114 — INFRA-305: README build-loop description
    corrected to the post-CER-074 orchestrator-held reviewer dispatch.**`
    in place.
    - `grep -n 'spawn-reviewer' README.md` → no hit that describes the
      resolver *emitting* it (a historical-note mention is acceptable if
      clearly marked as pre-CER-074 history).
    - **Correct signal: the corrected description names who dispatches the
      reviewer (the orchestrator) and where the branch lives; forbidden
      proxy: deleting the loop description instead of correcting it —
      removing the contract is not making it true.**

## Instructions

**Ordering.** This story is strictly the **last** story built in Phase 114.
INFRA-301, INFRA-302, INFRA-303 and INFRA-304 each annotate their own CER
rows in `docs/cer/backlog.md`; if this story ran first or in parallel, its
backlog edits would either conflict with theirs or be silently rebased away.
Before touching `docs/cer/backlog.md`, verify all four sibling rows in
`docs/phases/phase-114.md`'s Stories table read `complete`. If any does not,
stop and report rather than proceeding — this is a hard precondition, not a
preference.

**Note A — the plan's `pipe_path` grep is corrected.** The closeout plan's
sketch item 1 asks for repo-wide `grep 'pipe_path' → 0`. That is not
achievable and must not be attempted: `pipe_path` is live in
`skills/companion/scripts/sidebar.py` (writer), `pairmode_migrate.py` (the
`to-030` remover), `pairmode_status.py` (a comment recording the removal),
`docs/pipe-architecture.md`, and several historical phase docs. Ensures 1
scopes the assertion to the security-auditor procedure file only.

**Note B — the plan's CER-079 scope is widened, honestly.** The plan assumed
"grep md5 → no pipe hit" was purely a doc correction. Re-verification found
`sidebar.py` genuinely still computes the md5 pipe path and reads it, so the
doc's md5 claim is half-true in a way that hides a real code divergence.
Correcting § Data flow to describe only the flat path is right (hooks are the
writers, and they are all flat), but doing it silently would bury the
divergence. Hence Ensures 14: file it as CER-118 and cross-reference it from
CER-079's annotation. Do **not** edit `sidebar.py`.

**Ideology alignment note (Step 4a).** The drafted work was checked against
`docs/ideology.md`. Two adjustments were made to route around conflicts
rather than through them: (i) *"Never silently pass contradictions"* — a
doc-only fix that quietly deleted the md5 claim would let the
hook↔sidebar pipe contradiction pass unrecorded, so Ensures 14 files it
instead; (ii) *"Hooks are thin relays only"* — the exception list this story
expands is precisely the enumeration that keeps that constraint enforceable,
so Ensures 4 and 12 widen and mechanize it rather than merely transcribing
today's imports. Nothing in this story alters hook behaviour
(Ensures 17), so the constraint's rationale is preserved, not just its
letter.

**Suggested build order:**

1. Read `skills/pairmode/skills/reviewer/procedure.md` § 2 and copy its pipe
   text into the security-auditor procedure's § 2 (Ensures 1), adapting only
   the surrounding CRITICAL framing that the security-auditor version carries
   and the reviewer version does not.
2. Rewrite the four exception bullets (Ensures 2, 3, 4). Work from the
   Requires-4 table, not from memory. Re-derive it yourself before editing —
   run the AST walk described in Ensures 12 as a throwaway script and diff
   its output against the table; if it disagrees, the table is stale and the
   live output wins (record the discrepancy in `## Evidence`).
3. Write `test_hook_delegations_are_documented_exceptions` (Ensures 12) and
   run it **against the not-yet-edited procedure** to prove it fails, then
   against the edited one. If it passes before the edit, the test is wrong.
4. `docs/architecture.md`: § Data flow (Ensures 5), then the two downstream
   claims (Ensures 6), then the deny-list reconciliation (Ensures 7). Locate
   all of these by text search, not by the line numbers in this spec — the
   earlier edits shift them.
5. `CHANGELOG.md` Phase 99 backfill (Ensures 8). Read
   `docs/phases/phase-99.md` for the story list and its § Goal for the
   four-symptom framing; write in the voice of the surrounding entries
   (past tense, story ID in parentheses at the end of each bullet). Keep it
   to four to six lines — the file has a 200-line cap and Phase 115's
   INFRA-310 still needs room for the 0.3.1 entry.
6. `docs/brief.md` / `docs/reconstruction.md` skill count + observability
   bullet (Ensures 9), then the parity test (Ensures 10).
7. `docs/cer/backlog.md` last: CER-118 filing (Ensures 14), the seven
   RESOLVED annotations (Ensures 15), `Last updated:` (Ensures 16).
8. Run the targeted suites, then the full suite without `-x`.

**Do not:**
- edit any file under `hooks/`, `skills/pairmode/scripts/`, or
  `skills/companion/scripts/` (Ensures 17);
- edit `docs/pipe-architecture.md` (it is the subject of CER-118, not a fix
  target here);
- edit historical phase docs to correct their "three skills" / `pipe_path`
  prose — they are dated records;
- add an allow-list escape hatch to the Ensures-12 parity test;
- delete or re-quadrant any CER row (annotate in place only);
- touch `docs/architecture.md:759-777`'s INFRA-253 doctrine block — it is
  already correct and is the reconciliation target, not the thing reconciled.

**Evidence block.** Add a `## Evidence` section to this story file recording:
the AST-walk output from step 2; the pre-edit failure and post-edit pass of
the Ensures-12 test; the `grep -c 'INFRA-253' docs/architecture.md` counts
before and after (Ensures 7); and the Ensures-13 feasibility note.

## Tests

Targeted run (must be green; these are the files this story's assertions live
in or could plausibly break):

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_docs.py \
  tests/pairmode/test_architecture_policy.py \
  tests/pairmode/test_skill_md.py \
  tests/pairmode/test_procedure_skills.py \
  tests/pairmode/test_plugin_manifest.py \
  -q 2>&1 | tail -20
```

Full suite, run **without `-x`** so a pre-existing failure cannot mask a new
one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -20
```

**Acceptance:**
- Targeted run: 0 failures.
- Full run: no failures beyond `main`'s baseline of 4116 passed / 211
  skipped; the passed count increases by exactly the number of tests added
  (three: Ensures 10, 11, 12 — 11 may be authored as one test with four
  assertions or as two parametrized cases; state which in `## Evidence`).

**New tests this story must author:**

| Test | File | Ensures |
|---|---|---|
| `test_skill_count_prose_matches_skill_dirs` | `tests/pairmode/test_docs.py` | 10 |
| `test_security_auditor_pipe_contract_has_no_pipe_path_read` | `tests/pairmode/test_procedure_skills.py` | 11 |
| `test_hook_delegations_are_documented_exceptions` | `tests/pairmode/test_procedure_skills.py` | 12 |

**TEST RUN note.** This is a `story_class: doc` story, but it is **not**
documentation-only: it authors three new test functions, so the
"documentation story — no test file expected" exemption does **not** apply.
The reviewer must run the targeted command above and report its result. The
five targeted files that must stay green are
`tests/pairmode/test_docs.py`, `tests/pairmode/test_architecture_policy.py`,
`tests/pairmode/test_skill_md.py`, `tests/pairmode/test_procedure_skills.py`,
and `tests/pairmode/test_plugin_manifest.py`.

**Negative check the reviewer must perform:** confirm
`test_hook_delegations_are_documented_exceptions` genuinely fails on the
pre-change procedure text — e.g.
`git stash` the procedure edit, run the test, expect failure, restore. A
parity test that passes against the stale contract is worthless.

## Out of scope

- **Fixing the hook↔sidebar pipe divergence.** `sidebar.py`'s md5 pipe path
  and its `state.json["pipe_path"]` write stay exactly as they are; the
  divergence is filed as CER-118 (Ensures 14) for a code story in a later
  phase. This story is doc-currency only and must not change runtime
  behaviour.
- **Rewriting `docs/pipe-architecture.md`.** It describes the superseded
  project-scoped design end to end; correcting it is a rewrite, not a sweep,
  and is bound to CER-118's resolution.
- **A state.json-key-level parity test.** Not mechanically feasible without a
  hand-maintained map or delegate call-graph analysis — reasoned out in
  Ensures 13 and deliberately deferred.
- **Retiring the downstream `.claude/settings.json` deny list.** CER-085 is
  closed by *stating which doctrine is authoritative*, not by removing the
  bootstrap-era generator. Any change to
  `permission_scope.py` / the deny-list generator is a separate code story.
- **Annotating the ~21 obsolete CER rows** (CER-001..019, 035, 044, 063,
  070) or CER-031's backlog-retain reason — that is INFRA-310's job in
  Phase 115.
- **The `docs/cer/backlog.md` zero-open editorial target.** This story
  annotates seven rows; it makes no claim about the total open count.
- **`README.md`'s skills table and "The four skills" heading** — already
  correct (Requires 8); README is touched only for the CER-085 deny-list
  sentences.
- **Backfilling any CHANGELOG entry other than Phase 99**, and the 0.3.1
  release entry (INFRA-310).
