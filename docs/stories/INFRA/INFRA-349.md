---
id: INFRA-349
rail: INFRA
title: Docstring-currency sweep: fix harness docstrings/comments that misdescribe live wiring
status: draft
phase: "117"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/scripts/next_action.py
  - .claude/agents/spec-writer.md
  - .claude/agents/docs-reviewer.md
touches:
  - tests/pairmode/test_docs.py
  - docs/cer/backlog.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

CER-156 (LOW), filed from `docs/build-loop-cold-eyes-review-20260801.md`'s §5: multiple docstrings
and comments in the harness actively misdescribe current wiring rather than describing it
accurately — the same class of drift CER-078/CER-085 already flagged elsewhere in this project.
Known instances found by the review (grep for the current text first — other stories in this phase
may have already fixed some of these as a side effect; don't duplicate):

- `flex_build.cmd_next_action`'s own docstring still says "Advisory only — not wired into the live
  CLAUDE.build.md loop (DP7)" when it is the live loop driver.
- `cmd_record_intent_review`'s docstring references a nonexistent `_is_fresh_phase`.
- A `next_action.py` Row-PBI comment claims `checkpoint-intent` carries a model override — it does
  not (see INFRA-340 in this same phase, which may fix the underlying behavior rather than just the
  comment — check its landed shape first).
- `.claude/agents/spec-writer.md` claims `select_spec_writer_model` doesn't exist when it's wired
  (from INFRA-333, Phase 116).

This should build after INFRA-336/338/339/340/341/342/346/347 land, since several of those stories
will change the actual wiring these comments describe — sweep for currency against the *final*
state of this phase, not a mid-phase snapshot.

### Spec-time verification (2026-08-02) — read this before building

Every claim above was re-verified at spec time against the **committed** tree (`git show HEAD:...`),
not the working tree, because a story worktree branches from `HEAD` and will therefore see exactly
the state recorded here. Result — three of the four named instances are still present, one has been
overtaken by events, and the bounded sweep the CER asked for turned up a fifth:

1. **Still present.** `flex_build.py:3551-3552` (`cmd_next_action`) reads
   `Pure-read: no file is written.  Advisory only — not wired into the live / CLAUDE.build.md loop
   (DP7).` It is the live loop driver.
2. **Still present.** `flex_build.py:4519` (`cmd_record_intent_review`) reads
   ``...evidence ``next_action._is_fresh_phase``/`` — `_is_fresh_phase` does not exist in
   `next_action.py` at all (`git grep -n "_is_fresh_phase" HEAD -- skills/pairmode/scripts/next_action.py`
   returns nothing). The real symbol is `_phase_is_fresh` (`next_action.py:1021`), which produces the
   `phase_is_fresh` position key; the docstring's second named reader, `resolve_next_action`'s Row PBI,
   is correct.
3. **Overtaken by INFRA-340 — the CER's claim is now stale, the comment is now true.** The Row-PBI
   comment at `next_action.py:1762-1766` reads "unlike checkpoint-time's `checkpoint-intent`, this
   emission carries no model override." When CER-156 was filed that implied a falsehood, because
   `checkpoint-intent` hardcoded `model=None`. INFRA-340 has since landed and `checkpoint-intent`
   now resolves a real model via `select_intent_reviewer_model(phase_class)`
   (`next_action.py:1708-1711`). So the comment is factually correct as written; the only currency
   work left is to cite the wiring source so the next reader does not re-file this finding. This is
   exactly the "check INFRA-340's landed shape first" caveat the stub raised, resolved.
4. **Still present.** `.claude/agents/spec-writer.md:6-9` reads "(no `select_spec_writer_model` tier
   exists yet — INFRA-333 is separate follow-on scope...)". INFRA-333 landed in Phase 116:
   `select_spec_writer_model` exists in `model_selector.py` and is called from `next_action.py`'s
   Row-2 `spawn-spec-writer` resolution (see the `_SPAWN_ACTIONS` comment block,
   `next_action.py:423-425`).
5. **New instance found by the sweep — same drift class, same file family, not named in the CER.**
   `.claude/agents/docs-reviewer.md:7-12` reads "checkpoint-docs currently resolves with `model=None`
   from `next_action.py` (no `select_docs_reviewer_model` exists yet, unlike its
   checkpoint-security/checkpoint-intent siblings — INFRA-325 wires the shell/dispatch entry only;
   adding a dedicated model-selection tier is separate follow-on scope)". All three assertions are
   now false: `select_docs_reviewer_model` exists at `model_selector.py:550`, `next_action.py:1700-1703`
   calls it for `CHECKPOINT_DOCS`, and the "unlike its siblings" contrast is inverted — post-INFRA-340
   all three checkpoint roles resolve a real model. This is the same sentence pattern as instance 4
   in the sibling agent shell, so fixing 4 without 5 would leave the sweep half-done.

**Why this story adds a regression test despite `story_class: doc`.** This is the third recurrence
of this drift class (CER-078, CER-085, now CER-156), and a previous builder attempt on this very
story returned a fabricated PASS claiming all four instances were fixed while producing no committed
diff — the residue is still sitting uncommitted in the main checkout (see `## Requires`). Prose-only
Ensures are exactly what made that fabrication undetectable. A small phrase-absence guard in
`tests/pairmode/test_docs.py` turns every assertion in `## Ensures` into something a test run either
confirms or denies, which is the only durable defence against both the drift and the fabrication.

## Requires

- **All other Phase 117 stories have landed.** Per `docs/phases/phase-117.md` § Ordering, INFRA-349
  builds **last** — it sweeps for currency against this phase's *final* wiring, not a mid-phase
  snapshot. In particular INFRA-340 (checkpoint-security/checkpoint-intent model dispatch) must be
  merged, because Ensures 3 asserts a comment describing INFRA-340's landed behaviour. Verified
  merged at spec time: `06e412c1 feat(story-INFRA-340)`.
- **The uncommitted residue from the prior fabricated attempt on this story must be discarded from
  the main checkout before the story worktree is created.** `git status --porcelain` in
  `/mnt/work/flex` currently shows modifications to `.claude/agents/spec-writer.md`,
  `skills/pairmode/scripts/flex_build.py`, and `skills/pairmode/scripts/next_action.py` that were
  never committed and never reviewed. They are not part of this story's record. Discard them
  (`git checkout -- <paths>`) so the builder starts from a `HEAD` that still contains the defects
  this story is specified to fix. If they are left in place, the builder's worktree (which branches
  from `HEAD`, not the working tree) will still see the defects, but the eventual merge back into
  the main checkout will collide with unreviewed edits.
- `skills/pairmode/scripts/model_selector.py` defines `select_spec_writer_model`,
  `select_docs_reviewer_model`, `select_intent_reviewer_model`, and `select_security_auditor_model`
  (all verified present at spec time). This story only describes them; it does not add or change any
  of them.
- `tests/pairmode/test_docs.py` exists and is a flat module of top-level `test_*` functions using a
  module-level `REPO_ROOT = Path(__file__).resolve().parent.parent.parent`.

## Ensures

<!-- State the correct signal AND the forbidden proxy (INFRA-314): e.g. "the
     write is absent after refusal; forbidden proxy: a warning line while the
     write happens anyway." -->

1. `cmd_next_action`'s docstring in `skills/pairmode/scripts/flex_build.py` (as of `HEAD`, lines
   3548-3556) no longer contains the substrings `Advisory only` or `not wired into the live`, and
   instead states that this command is the live decision engine the `CLAUDE.build.md` build loop
   calls each iteration. `git grep -c -F "Advisory only — not wired into the live" -- skills/pairmode/scripts/flex_build.py`
   returns no match. Forbidden proxy: softening the claim (e.g. "may be wired", "advisory in some
   contexts") without positively naming `CLAUDE.build.md`'s build loop as the caller; or deleting
   the sentence outright, leaving the docstring silent about how the command is used.

2. `cmd_record_intent_review`'s docstring in `skills/pairmode/scripts/flex_build.py` (as of `HEAD`,
   lines 4513-4532) no longer contains the substring `_is_fresh_phase`, and the reader it names is
   `resolve_next_action`'s Row PBI. `git grep -n -F "_is_fresh_phase" -- skills/pairmode/scripts/flex_build.py`
   returns no match. Forbidden proxy: renaming the reference to `next_action._phase_is_fresh` (the
   real symbol) without checking that it is actually a reader of this evidence — it is not.
   `_phase_is_fresh` computes `position["phase_is_fresh"]` from a git-log scan and never reads
   `state.json["pre_build_intent_review"]`; the only reader of that key is `infer_position`'s
   `pre_build_intent_verdict` population feeding Row PBI. A substitution that keeps a wrong claim
   with a correct symbol name fails this assertion.

3. The Row-PBI comment in `skills/pairmode/scripts/next_action.py` (as of `HEAD`, lines 1762-1767)
   that contrasts the pre-build `spawn-intent-reviewer` emission's `model=None` against
   checkpoint-time `checkpoint-intent` names `INFRA-340` and `select_intent_reviewer_model` as the
   reason `checkpoint-intent` carries a model override. Note explicitly: the comment's *claim* is
   already correct post-INFRA-340 (see `## Context` § Spec-time verification item 3) — this is a
   citation/currency edit, not a correction. Forbidden proxy: "fixing" the comment to say
   `checkpoint-intent` carries **no** model override, which was CER-156's original (now stale)
   reading and would re-introduce a falsehood into a comment that is currently true.

4. `.claude/agents/spec-writer.md`'s frontmatter comment (as of `HEAD`, lines 6-9) no longer
   contains the substring `no select_spec_writer_model tier exists yet`, and instead states that
   `spawn-spec-writer` resolves its model via `select_spec_writer_model(story_class)` in
   `next_action.py`'s Row-2 resolution, wired by INFRA-333. The `model: opus` frontmatter value
   itself is unchanged. Forbidden proxy: editing the `model:` value, or deleting the explanatory
   comment instead of correcting it — the comment exists to tell a reader why the shell's static
   value and the resolver's dynamic value can differ, and that question still needs an answer.

5. `.claude/agents/docs-reviewer.md`'s frontmatter comment (as of `HEAD`, lines 7-12) no longer
   contains the substrings `no select_docs_reviewer_model exists yet` or
   `checkpoint-docs currently resolves with model=None`, and instead states that `checkpoint-docs`
   resolves its model via `select_docs_reviewer_model(phase_class)` in `next_action.py`'s Row-9
   checkpoint-step resolution, wired by INFRA-333. The `model: sonnet` and `# fallback: haiku
   (never below)` lines are unchanged. Forbidden proxy: leaving the inverted
   "unlike its checkpoint-security/checkpoint-intent siblings" contrast in place — post-INFRA-340
   all three checkpoint roles resolve a real model, so the contrast is backwards as well as the
   claim being false.

6. A bounded stale-phrase sweep over this story's four declared source files reports zero hits:

   ```bash
   git grep -n -F -e "Advisory only" -e "not wired into" -e "exists yet" \
     -e "separate follow-on scope" -e "_is_fresh_phase" \
     -- skills/pairmode/scripts/flex_build.py skills/pairmode/scripts/next_action.py \
        .claude/agents/spec-writer.md .claude/agents/docs-reviewer.md
   ```

   ...with exactly one permitted exception: `next_action.py:119`'s `no keyed record exists yet`,
   which describes a legitimate runtime state (a legacy flat record with no keyed entry) and is not
   drift. The builder must confirm that line's text still reads as a runtime-state description and
   leave it alone. Forbidden proxy: editing `next_action.py:119` to make the grep clean.

7. `tests/pairmode/test_docs.py` gains a test function named
   `test_harness_docstrings_have_no_stale_wiring_claims` that fails if any of the five specific
   stale phrases from Ensures 1-5 reappears in its own file. The test must assert per-phrase with a
   message naming the file and phrase, not a single opaque boolean. Forbidden proxy: a test that
   greps for the *corrected* text instead of the *stale* text — asserting the fix is present does
   not prevent the stale sentence being re-added alongside it, and a grep-for-correct-text test
   passes trivially on an unfixed file that happens to also mention the right symbol names
   elsewhere.

8. `tests/pairmode/test_docs.py` also gains a test function named
   `test_model_selector_functions_named_in_agent_shells_exist` that, for each of
   `select_spec_writer_model` and `select_docs_reviewer_model` named in the corrected agent-shell
   comments, asserts the symbol is actually defined in `skills/pairmode/scripts/model_selector.py`.
   This closes the loop: the reason CER-156 exists is that comments named a wiring state nobody
   checked. Forbidden proxy: importing `model_selector` and using `hasattr` on the module without
   also covering the agent-shell side — the test must read the two `.claude/agents/*.md` files and
   derive the names it checks from what those files actually claim, so a future shell comment that
   invents a nonexistent selector fails immediately.

9. `docs/cer/backlog.md`'s CER-156 row gains an appended
   `**RESOLVED Phase 117 — INFRA-349: ...**` sentence describing the landed sweep, mirroring the
   `**RESOLVED Phase 117 — ...**` annotation convention already used for CER-152/CER-153 in the same
   table, replacing the row's current `**Absorbed at spec time by INFRA-349 (Phase 117)** — folded
   in rather than deferred; resolution annotation lands when that story completes.` sentence. The
   annotation must record that the sweep found and fixed a fifth instance
   (`.claude/agents/docs-reviewer.md`) not named in the original finding, and that CER-156's
   `checkpoint-intent` claim was overtaken by INFRA-340 rather than being a live defect. No other
   cell in that row and no other row in `docs/cer/backlog.md` changes.

10. No behavioural change ships in this story: `git diff` for
    `skills/pairmode/scripts/flex_build.py` and `skills/pairmode/scripts/next_action.py` touches
    only comment and docstring lines — no statement, expression, signature, import, or literal
    outside a comment/docstring is added, removed, or reordered. Forbidden proxy: "while I was in
    there" refactors, even obviously-correct ones; they belong in a separate story and would make
    this story's diff unreviewable as a documentation sweep.

11. `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` is green (no `-x`, so a
    pre-existing failure cannot mask a new one — see `## Tests`).

## Instructions

**Read this first:** every "current text" quoted below was verified at spec time against `HEAD`
(`git show HEAD:<path>`), not the working tree. If a quoted string is not where this spec says it
is, stop and report that in the build result rather than inventing a plausible edit — a prior
attempt on this story fabricated a PASS for edits it never made, and the correct response to a
missing anchor is a `revised` signal, not a guess.

1. **`flex_build.py` — `cmd_next_action` docstring (Ensures 1).** Locate the function (`HEAD` line
   3548; grep for `def cmd_next_action`). Replace the two-line sentence:

   ```
   Pure-read: no file is written.  Advisory only — not wired into the live
   CLAUDE.build.md loop (DP7).
   ```

   with a statement that this is the live decision engine: it is pure-read (no file is written) and
   it is the command `CLAUDE.build.md`'s build loop invokes each iteration to obtain the next
   action. Keep the surrounding docstring lines (the summary line and the `--json` paragraph)
   untouched. Do not delete the DP7 reference wholesale if you can keep it accurate — DP7 is the
   design principle the resolver implements; what was wrong was the "advisory only" claim, not the
   principle citation.

2. **`flex_build.py` — `cmd_record_intent_review` docstring (Ensures 2).** Locate the function
   (`HEAD` line 4513). In the sentence beginning "This is the durable "already reviewed"
   evidence...", delete the ``next_action._is_fresh_phase``/ reference so the named reader is
   `resolve_next_action`'s Row PBI alone. Do **not** substitute `_phase_is_fresh`: that function
   computes the `phase_is_fresh` position key from a git-log scan and is not a reader of
   `state.json["pre_build_intent_review"]` — substituting it would keep the claim wrong while making
   the symbol name right (Ensures 2's forbidden proxy). Leave the rest of the docstring, including
   the whole `verdict`-validation paragraph, byte-identical.

3. **`next_action.py` — Row-PBI comment (Ensures 3).** Locate the comment at `HEAD` lines 1762-1767,
   inside `if pre_build_intent_verdict is None:`. It currently reads
   "...unlike checkpoint-time's `checkpoint-intent`, this emission carries no model override."
   The claim is **already true** post-INFRA-340. Add the citation only: make it say that
   `checkpoint-intent` carries a model override resolved via `select_intent_reviewer_model`
   (INFRA-340), whereas this pre-build emission deliberately carries none. Do not invert the
   sentence. Cross-check against the `_SPAWN_ACTIONS` comment block at `HEAD` lines 414-421 and the
   Row-9 dispatch at lines 1700-1711, which already describe this correctly — the Row-PBI comment
   should be consistent with them, not restate them at length.

4. **`.claude/agents/spec-writer.md` frontmatter comment (Ensures 4).** Replace the parenthetical
   "(no `select_spec_writer_model` tier exists yet — INFRA-333 is separate follow-on scope, this
   story wires the shell/dispatch entry only)" so the comment states: `spawn-spec-writer` resolves
   its model via `select_spec_writer_model(story_class)` in `next_action.py`'s Row-2 resolution
   (wired by INFRA-333), and this frontmatter `model:` value mirrors the default the selector
   returns whenever the orchestrator does not pass an explicit override. Do not change
   `model: opus`, `name:`, `description:`, or `tools:`.

5. **`.claude/agents/docs-reviewer.md` frontmatter comment (Ensures 5).** This is the instance the
   original CER did not name; do not skip it. Replace the comment at `HEAD` lines 7-12 so it states:
   `checkpoint-docs` resolves its model via `select_docs_reviewer_model(phase_class)` in
   `next_action.py`'s Row-9 checkpoint-step resolution (wired by INFRA-333), and this frontmatter
   value is the effective default whenever the orchestrator does not pass an explicit override.
   Remove the "unlike its checkpoint-security/checkpoint-intent siblings" contrast entirely — it is
   inverted post-INFRA-340. Keep `model: sonnet` and the `# fallback: haiku  (never below)` line
   exactly as they are.

6. **Run the bounded sweep (Ensures 6)** with the `git grep` command in Ensures 6 and confirm the
   only remaining hit is `next_action.py:119`'s `no keyed record exists yet`. Read that line in
   context and confirm it describes a runtime state (legacy flat record, no keyed entry) rather than
   a wiring claim, then leave it untouched. If the sweep surfaces any *other* hit that this spec did
   not anticipate, fix it if it is the same drift class and name it in the build result; if it is
   not drift, leave it and say why in the build result.

7. **Add the two guard tests (Ensures 7-8) to `tests/pairmode/test_docs.py`.** Follow the file's
   existing style: flat top-level `def test_*() -> None:` functions, `REPO_ROOT` for paths, plain
   `assert` with an f-string message. Sketch:

   ```python
   _STALE_WIRING_PHRASES: dict[str, tuple[str, ...]] = {
       "skills/pairmode/scripts/flex_build.py": (
           "Advisory only",
           "not wired into the live",
           "_is_fresh_phase",
       ),
       ".claude/agents/spec-writer.md": ("select_spec_writer_model tier exists yet",),
       ".claude/agents/docs-reviewer.md": (
           "select_docs_reviewer_model exists yet",
           "checkpoint-docs currently resolves with model=None",
       ),
   }


   def test_harness_docstrings_have_no_stale_wiring_claims() -> None:
       for rel_path, phrases in _STALE_WIRING_PHRASES.items():
           text = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
           for phrase in phrases:
               assert phrase not in text, (
                   f"{rel_path} contains stale wiring claim {phrase!r} (CER-156, INFRA-349) — "
                   "the comment describes a prior or aspirational state, not the shipped one"
               )
   ```

   For `test_model_selector_functions_named_in_agent_shells_exist`, read
   `.claude/agents/spec-writer.md` and `.claude/agents/docs-reviewer.md`, extract every
   `select_*_model` identifier they mention (a `re.findall(r"select_\w+_model", text)` over each
   file is sufficient), and assert each extracted name appears as `def <name>(` in
   `skills/pairmode/scripts/model_selector.py`. Deriving the names from the shells rather than
   hardcoding them is the point (Ensures 8's forbidden proxy) — it makes any future shell comment
   that invents a selector fail immediately.

   Note the deliberate asymmetry: `next_action.py` is intentionally absent from
   `_STALE_WIRING_PHRASES`. Its Ensures-3 edit is a citation addition to an already-true comment,
   so there is no stale phrase to guard against, and adding a phrase-presence assertion there would
   violate Ensures 7's forbidden proxy (grepping for corrected text).

8. **Annotate CER-156 (Ensures 9).** In `docs/cer/backlog.md`, find CER-156's row (currently line
   243, in the `## Do Now` table). Replace its trailing `**Absorbed at spec time by INFRA-349
   (Phase 117)** — folded in rather than deferred; resolution annotation lands when that story
   completes.` sentence with a `**RESOLVED Phase 117 — INFRA-349: ...**` sentence, matching the
   CER-152/CER-153 annotation style already in that table. The annotation must record (a) which
   docstrings/comments were corrected, (b) that the sweep found a fifth instance in
   `.claude/agents/docs-reviewer.md` that the original finding did not name, and (c) that CER-156's
   `checkpoint-intent` sub-claim was overtaken by INFRA-340 (the behaviour was wired, so the comment
   became true) rather than being a live defect at fix time. Do not touch the row's Source, Date, or
   Phase cells, and do not touch any other row.

9. **Keep the diff comment-only in the two `.py` files (Ensures 10).** Before finishing, run
   `git diff -- skills/pairmode/scripts/flex_build.py skills/pairmode/scripts/next_action.py` and
   confirm every changed line is inside a docstring or a `#` comment. If a linter or formatter
   reflows executable code, revert that hunk.

10. **Do not update `docs/architecture.md`.** This story corrects source-level comments only; the
    architecture doc's descriptions of the resolver, model selection, and checkpoint dispatch were
    updated by INFRA-333/INFRA-340 in their own scope and are not part of this sweep. See
    `## Out of scope`.

**Ideology-alignment note (Step 4a, resolved inline):** `docs/ideology.md`'s "We prefer
rationale-bearing decisions over bare rules" conviction and its "Rationale preservation" comparison
dimension both argue against the cheapest fix here, which would be to delete the four offending
comments outright and leave the code silent. Ensures 1, 4, and 5 therefore each require the comment
to be *corrected and to keep explaining why*, and each names comment-deletion as a forbidden proxy
— the rationale a reader needs (why a shell's static `model:` can differ from the resolver's
dynamic one) survives the fix rather than being removed along with the error.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_docs.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Plus the two non-pytest verifications, both of which must be pasted into the build result as
literal command output (not summarised):

```bash
git grep -n -F -e "Advisory only" -e "not wired into" -e "exists yet" \
  -e "separate follow-on scope" -e "_is_fresh_phase" \
  -- skills/pairmode/scripts/flex_build.py skills/pairmode/scripts/next_action.py \
     .claude/agents/spec-writer.md .claude/agents/docs-reviewer.md

git diff -- skills/pairmode/scripts/flex_build.py skills/pairmode/scripts/next_action.py
```

Acceptance:

- `test_harness_docstrings_have_no_stale_wiring_claims` and
  `test_model_selector_functions_named_in_agent_shells_exist` both pass, and both are demonstrably
  new (they do not exist before this story).
- The full `tests/pairmode/` suite is green. Run it **without `-x`** — a known pre-existing failure
  plus `-x` hides every later real failure behind it. If a pre-existing failure exists, deselect it
  by name and say so in the build result rather than reaching for `-x`.
- The `git grep` sweep returns only `next_action.py:119`'s `no keyed record exists yet`.
- The `git diff` for the two `.py` files shows only docstring/comment lines changed.

## Out of scope

- **Any behavioural change to model selection, the resolver, or checkpoint dispatch.** This story
  describes what INFRA-333 and INFRA-340 already built; it changes no selector, no action object, no
  dispatch path. If a comment turns out to be wrong because the *code* is wrong (rather than the
  comment being stale), that is a new finding for the CER backlog, not an in-scope fix here.
- **`docs/architecture.md`.** Its resolver / model-selection / checkpoint-dispatch prose is not part
  of this sweep. If the sweep incidentally reveals the architecture doc is also stale on one of
  these points, file it rather than fixing it inline — INFRA-347 already carries architecture-doc
  currency work for its own surface, and mixing a second doc surface into this story would make the
  comment-only diff assertion (Ensures 10) unverifiable.
- **The other seven files in `.claude/agents/`** (`builder.md`, `gate-worker.md`,
  `intent-reviewer.md`, `loop-breaker.md`, `reconstruction-agent.md`, `reviewer.md`,
  `security-auditor.md`). Only `spec-writer.md` and `docs-reviewer.md` were flagged by the bounded
  sweep in Ensures 6. A full audit of every agent shell's frontmatter comment against live wiring is
  a reasonable follow-on, but it is unbounded relative to CER-156's finding and would turn a doc
  story into an audit.
- **A general docstring-currency linter.** The two guard tests added here cover exactly the five
  phrases this story fixes. A generic mechanism that detects "comment describes a symbol that does
  not exist" across the whole `skills/pairmode/scripts/` tree would address the recurring CER-078 /
  CER-085 / CER-156 class properly, but it is a code story with real design questions (how to
  distinguish a symbol reference from prose), not a line item in a sweep. File it if it is wanted.
- **Retroactively correcting the stale `status:` frontmatter on Phase 117's already-merged stories.**
  That is INFRA-347's named follow-up work, tracked in its own `## Out of scope`; this story does not
  touch any other story file.

<!-- SPEC-PREFLIGHT NOTE: the scan may flag skills/pairmode/scripts/model_selector.py and
     docs/phases/phase-117.md as named-but-not-in-scope. Both are intentional:
     model_selector.py is only read (Ensures 8 asserts symbols defined there exist) and is
     never written by this story; phase-117.md is cited for its § Ordering constraint only.
     The seven unflagged .claude/agents/*.md files are named solely to declare them out of
     scope, so they must not appear in touches:. -->
