---
id: INFRA-268
rail: INFRA
title: Document the one-iteration-per-story contract, retire the dead spawn-reviewer action, fix stub-gate quoted-text false positive (CER-074, CER-076)
status: complete
phase: "104"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/scripts/next_action.py
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - docs/architecture.md
touches:
  - tests/pairmode/test_flex_build.py
  - tests/pairmode/test_next_action.py
  - docs/cer/backlog.md
  - docs/stories/INFRA/INFRA-268.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Two loop-contract defects, both surfaced by field use of the Era-003 harness,
both cheap to close, neither one changing how the loop actually runs. This
story closes CER-074 and CER-076.

**CER-074 — the undocumented one-iteration-per-story contract.**
`next_action.SPAWN_REVIEWER` is declared, is a member of `ACTIONS` and
`_SPAWN_ACTIONS`, and is keyed in the orchestrator's `ACTION_SUBAGENT_TYPE`
map — but no code path in `resolve_next_action` ever constructs it. That is
not an oversight: `docs/agreements/HARNESS001-main.md` (DP2/DP3) and
`docs/agreements/HARNESS003-main.md` § 2 both record the decision
deliberately — the reviewer dispatch is *intra-cycle*, held by the
orchestrator inside the `spawn-builder` turn, and the resolver's DP3 outcome
inference is git-authoritative: `infer_position` reports `PASS` only when a
`story-<ID>` commit exists in the log (`next_action.py` § 3b), and only the
reviewer commits, inside the story worktree, with the commit reaching the main
branch only at `merge-story-worktree`.

The consequence is a real trap for anyone who reads the loop literally. After
the builder returns — worktree dirty, nothing committed to the main branch,
attempt counter written — a fresh `next-action` poll sees `attempt_count > 0`,
no `story-<ID>` commit, status still `planned`, and infers `FAIL`. It then
re-issues `spawn-builder` for the same story at attempt 2, discarding a
finished build. The loop only works if the orchestrator treats one poll as one
whole story: builder → reviewer → merge/discard inside a single iteration.
Nothing in `CLAUDE.build.md`, its `.j2` template, or `docs/architecture.md`
says so. forqsite's Era-3 build inferred the contract correctly on 2026-07-22
across six stories; flex's own orchestrator hit the trap again on 2026-07-25.

**The decision this story records (so it is not re-litigated): document the
contract, do not build a builder-completed state.** Emitting `spawn-reviewer`
from a "builder finished" state would require the resolver to detect a dirty
story worktree — non-durable, non-git state that DP7 explicitly keeps out of
the resolver's read-model, which is pure-read over durable state. It would
also split one story's cycle across two polls, re-opening the seam the
one-iteration rule closes. The truthful, cheap fix is to write the contract
down where an orchestrator reads it, and to mark the constant as
orchestrator-dispatched-only rather than delete it. **Deletion is explicitly
rejected**: `spawn-reviewer` is a live member of the action vocabulary — the
orchestrator's `ACTION_SUBAGENT_TYPE` map keys on it, `_SPAWN_ACTIONS`
membership governs whether an action may carry a model override, and
`tests/pairmode/test_next_action_schema.py` and
`tests/pairmode/test_harness003_isolation.py` both assert its presence. The
constant is not dead; only the *resolver-emitted* path is, and that is by
design. CER-074's "remove or clearly mark" is answered with "clearly mark",
plus a regression test that pins the invariant so a future story cannot
quietly start emitting it without noticing this contract.

**CER-076 — the stub gate false-positives on quoted delegation text.**
`check_stub_gate` (`skills/pairmode/scripts/flex_build.py`, helper at ~1483,
regex `_STUB_DELEGATION_RE` at ~1397) searches the whole story body for three
delegation phrases and blocks the story when any matches. It does not
distinguish prose from quoted text. forqsite's HOME-006 instructed its builder
to append a backlog resolution note whose *content* contained one of those
phrases; the gate blocked the story until the deliverable text was reworded —
the gate corrupted a deliverable to satisfy itself. The fix is to mask fenced
code blocks and inline code spans before searching, so a phrase that is quoted
as data does not read as delegation. The alternative CER-076 offers — a
`stub_gate: exempt` frontmatter key — is rejected in `## Out of scope` below:
a per-story bypass switch is a permanent hole in a gate whose whole value is
that it cannot be argued with, and it would need its own reason field, its own
audit path, and its own review rule. Masking needs none of that and is
truthful: quoted text was never delegation.

Note for the builder: this spec deliberately never quotes the three literal
phrases in `_STUB_DELEGATION_RE`. Until this story lands, doing so would make
the gate block *this very file* — CER-076 applied to its own fix. Read the
literals from the source constant when writing fixtures.

## Requires

- Working from a clean checkout of `main` at `/mnt/work/flex` (the builder
  runs inside this story's `.pairmode-worktrees/INFRA-268/` worktree; all
  paths below are relative to the repo root).
- `skills/pairmode/scripts/flex_build.py` defines `_STUB_DELEGATION_RE`
  (~line 1397), `_story_body`, and `check_stub_gate` (~line 1483), and
  `check_stub_gate` is imported and composed by `next_action.infer_position`.
- `skills/pairmode/scripts/next_action.py` declares `SPAWN_REVIEWER`
  (~line 122) and includes it in `ACTIONS` (~line 142) and `_SPAWN_ACTIONS`
  (~line 169); `SCHEMA_VERSION` is 4.
- `CLAUDE.build.md` (repo root, flex's own live bootstrapped loop, which
  carries the flex-harness promote step) and
  `skills/pairmode/templates/CLAUDE.build.md.j2` (the fleet template) both
  exist and both open their `## Build loop` section with the single-line
  paragraph beginning `Story-build actions (`spawn-builder`, ...`.
- `tests/pairmode/test_template_reduction.py` renders the `.j2` and asserts
  the result is **≤ 40 non-blank lines**. It renders to exactly 40 today —
  the template has zero headroom. It also asserts a `BANNED_PHRASES` list is
  absent from the rendered output, including the literal `await-user`.
- `docs/architecture.md` has a `## Pairmode build loop` section (~line 168)
  whose first content is the **Per-story worktree isolation** paragraph, and a
  `## Module structure` entry for `next_action.py` (~line 76).
- `docs/cer/backlog.md` contains rows `CER-074` and `CER-076` under
  `## Do Later`, unresolved (trailing `| — |` phase cell).
- No other phase-104 story is required first; INFRA-268 is independent
  (`docs/phases/phase-104.md` § Ordering).

## Ensures

Each assertion is independently checkable by reading a file or running a
command. Line numbers are orientation only; match on content.

### A — one-iteration-per-story contract (CER-074)

1. **The constant is marked, not removed.**
   `skills/pairmode/scripts/next_action.py` carries a comment block
   immediately above or attached to the `SPAWN_REVIEWER` declaration that
   contains the literal string `CER-074` and states, in words, that
   `resolve_next_action` never emits this action and that the orchestrator
   dispatches the reviewer itself inside the `spawn-builder` iteration.
   Verifiable: `grep -n "CER-074" skills/pairmode/scripts/next_action.py`
   returns at least one line.

2. **Vocabulary membership is unchanged.** `SPAWN_REVIEWER` is still a member
   of both `ACTIONS` and `_SPAWN_ACTIONS`; `SCHEMA_VERSION` is still `4`; no
   action constant is deleted or renamed. Verifiable: the existing
   `tests/pairmode/test_next_action_schema.py` and
   `tests/pairmode/test_harness003_isolation.py` pass unmodified.

3. **A regression test pins the invariant.** `tests/pairmode/test_next_action.py`
   contains a test whose name contains `never_emits_spawn_reviewer`, which
   calls `resolve_next_action` across **at least five** distinct position
   shapes — no active story / phase complete; first attempt (attempt_count 0);
   post-FAIL retry (attempt_count 1, no story commit); escalated retry
   (attempt_count ≥ 2); a gate-blocked story; and a checkpoint-sequence
   position — and asserts the returned `action` is never `spawn-reviewer` in
   any of them. The test constructs positions using the same fixture helpers
   the surrounding tests in that file already use; it does not add a new
   fixture framework.

4. **The live orchestrator states the contract.** `CLAUDE.build.md` §
   `## Build loop` states the one-iteration contract. Its text contains, in
   the `## Build loop` section: the literal `CER-074`; wording that one
   `next-action` poll covers the whole story (builder spawn, reviewer spawn,
   and merge-or-discard inside a single iteration); an explicit statement that
   `next-action` never emits `spawn-reviewer` and the orchestrator dispatches
   the reviewer itself; and an explicit instruction not to re-poll
   `next-action` between the builder's return and the merge, with the reason —
   `PASS` is inferred from a `story-<ID>` commit that does not exist until the
   merge, so a mid-story poll reads the finished attempt as a failure and
   re-dispatches a wasteful second builder.

5. **The template states the same contract.**
   `skills/pairmode/templates/CLAUDE.build.md.j2` carries the same statement
   as assertion 4 (same substance; wording may differ only where the template
   uses Jinja variables).

6. **The template stays within its budget.** The rendered `.j2` is still
   **≤ 40 non-blank lines** — i.e. the contract text is folded into an
   existing non-blank line (the `Story-build actions ...` paragraph is the
   intended host), adding **zero** new non-blank lines. The rendered output
   still contains no phrase from `test_template_reduction.BANNED_PHRASES`; in
   particular the new text does not use the literal `await-user`.
   Verifiable: `tests/pairmode/test_template_reduction.py` passes **unmodified**
   — its `<= 40` limit is not raised and no banned phrase is removed from the
   list.

7. **Architecture records the contract.** `docs/architecture.md` §
   `## Pairmode build loop` contains a paragraph — placed after the
   **Per-story worktree isolation** paragraph and before numbered item 1 —
   whose opening is a bolded label containing `One-iteration-per-story
   contract` and `CER-074`, and whose body states: (a) the resolver never
   emits `spawn-reviewer`; it is orchestrator-dispatched only; (b) the reason
   — DP3 outcome inference is git-authoritative (`PASS` ⇔ a `story-<ID>`
   commit exists), and only the reviewer commits, so no intermediate state
   between builder-return and merge is legible to the resolver; (c) the
   operational rule — exactly one `next-action` poll per story, and a
   mid-story poll re-dispatches a wasteful attempt 2; (d) a pointer to
   `docs/agreements/HARNESS003-main.md` as the originating decision.

8. **The module-structure entry is truthful.** The `next_action.py` line in
   `docs/architecture.md` § `## Module structure` carries a short clause
   stating that `spawn-reviewer` is in `ACTIONS`/`_SPAWN_ACTIONS` for
   orchestrator dispatch but is never emitted by `resolve_next_action`
   (CER-074). The existing content of that line is preserved; the clause is
   appended, not substituted.

9. **No behaviour change in the resolver.** `resolve_next_action` and
   `infer_position` are not modified except for comments. Verifiable:
   `git diff main -- skills/pairmode/scripts/next_action.py` shows only
   comment-line additions — no changed executable statement, no new branch,
   no new import.

### B — stub gate quoted-text false positive (CER-076)

10. **A length-preserving mask helper exists.**
    `skills/pairmode/scripts/flex_build.py` defines a module-level helper
    (name at builder's discretion, e.g. `_mask_code_regions`) that takes the
    story body text and returns a string of **exactly the same length** in
    which every character inside a fenced code block or an inline code span
    has been replaced by a space, newlines preserved verbatim. It handles:
    triple-backtick fences with or without an info string; tilde (`~~~`)
    fences; a fence opener indented by up to three spaces; an unterminated
    fence (masks to end of text); and inline spans delimited by a run of one
    or more backticks closed by a run of the same length on the same line.
    It is pure — no I/O, no state.

11. **The stub gate searches the masked body.** `check_stub_gate` applies the
    mask to the body before `_STUB_DELEGATION_RE.search`, and reports the
    matched line by slicing the **original** body at the match offsets — so
    the `Delegation language found: "..."` message still shows real text, not
    spaces. `_STUB_DELEGATION_RE` itself is unchanged; the acceptance-surface
    check (`_STUB_ACCEPTANCE_RE` against the full file text) is unchanged.

12. **Quoted delegation text passes.** A story file whose only occurrence of a
    delegation phrase is inside a fenced code block passes the gate:
    `check_stub_gate` returns `ok: True`, and `flex_build.py check-stub <id>`
    exits 0 with no output. The same holds for a phrase inside an inline code
    span.

13. **Real delegation still blocks.** A story file with a delegation phrase in
    plain prose still returns `ok: False` with a `Delegation language found`
    reason, and `check-stub` still exits 1. A file containing **both** a
    fenced quotation and a separate prose occurrence blocks, and the reported
    matched line is the prose line — not the fenced one.

14. **The HOME-006 shape is reproduced as a test.**
    `tests/pairmode/test_flex_build.py` gains tests covering, at minimum:
    fenced-quote pass; inline-code-span pass; prose block (unchanged
    behaviour); mixed fenced-quote-plus-prose blocks-and-reports-the-prose-line;
    tilde fence; unterminated fence; and the CLI exit codes for the pass and
    block cases. Each fixture builds its delegation text from
    `flex_build._STUB_DELEGATION_RE`'s own literals (imported or reconstructed
    from the module) rather than hard-coding the phrases in the test source,
    so the tests cannot drift from the regex.

15. **No frontmatter escape hatch is introduced.** No new frontmatter key is
    read by the stub gate. Verifiable:
    `grep -rn "stub_gate" skills/ tests/ docs/architecture.md` returns
    nothing (matches inside this story file do not count).

16. **The existing stub-gate tests pass unmodified.** The tests at
    `tests/pairmode/test_flex_build.py` named `test_check_stub_*` and
    `test_check_stubs_*` are not edited, and all still pass — the change is
    strictly a narrowing of what counts as a match.

### C — backlog rows

17. **Both CER rows carry a resolution note.** In `docs/cer/backlog.md`, the
    `CER-074` and `CER-076` rows each end their Finding cell with a bolded
    note in the house format — beginning `**RESOLVED Phase 104 — INFRA-268`
    — that states what was actually done (for CER-074: contract documented in
    three places, constant marked rather than removed, with the one-sentence
    reason it was not removed and not made resolver-emitted; for CER-076:
    code-region masking, with the one-sentence reason the frontmatter escape
    hatch was rejected). Rows are **not** deleted, not moved between
    quadrants, and their `Source`/`Date` cells are unchanged; the trailing
    phase cell reads `104`.

18. **The backlog table is not corrupted.** Both edited rows still parse as
    table rows with the same column count as their neighbours (any literal
    pipe inside the new note is escaped as `\|`, matching the existing rows'
    convention).

### D — suite

19. **The suite is green.** `uv run pytest tests/pairmode/ -q` (run **without**
    `-x`) shows no new failures relative to clean `HEAD` — see `## Tests`.

## Instructions

Work inside this story's worktree. Order below is deliberate: the stub-gate
fix (B) is self-contained code and should land first, since part A is
documentation whose only executable piece is one new test.

### Part B — stub gate (do this first)

1. In `skills/pairmode/scripts/flex_build.py`, immediately below
   `_STUB_DELEGATION_RE`/`_STUB_ACCEPTANCE_RE`, add the mask helper described
   in assertion 10. Recommended shape — a two-pass, length-preserving mask:

   - Pass 1, fences: walk the text line by line. A line whose stripped-left
     form (≤ 3 leading spaces) starts with a run of ≥ 3 backticks or ≥ 3
     tildes opens a fence; the matching closer is a line whose stripped-left
     form starts with a run of the *same* character of *at least* the opening
     run's length. Blank the fence's content lines **and the fence marker
     lines themselves** by replacing each non-newline character with a space.
     An unterminated fence blanks to end of text.
   - Pass 2, inline spans, applied to the fence-masked text only:
     `re.sub(r"(`+)([^\n]*?)\1", lambda m: " " * len(m.group(0)), text)`.
     Confirm the substitution is length-preserving before returning; a cheap
     `assert len(masked) == len(original)` is acceptable as a guard, but
     prefer raising nothing at runtime — the gate must never crash on a
     malformed story. If a length mismatch is ever possible in your
     implementation, fall back to searching the unmasked body rather than
     raising.

   Keep the helper pure and private (leading underscore). Do not import
   anything new; `re` is already imported.

2. In `check_stub_gate`, replace the `_STUB_DELEGATION_RE.search(body)` call
   with a search over `masked = _mask_code_regions(body)`, keeping the
   existing `line_start`/`line_end`/truncation logic but slicing **`body`**
   (not `masked`) for the reported line. Because the mask is length
   preserving, the offsets are directly reusable — that is the whole reason
   for the length constraint. Leave the acceptance-surface check alone.

3. Add the tests from assertion 14 to `tests/pairmode/test_flex_build.py`,
   next to the existing `test_check_stub_*` group. Build fixture text by
   pulling a literal out of the compiled regex — e.g. import the module and
   derive a phrase from `_STUB_DELEGATION_RE.pattern.split("|")[0]` — so the
   tests never hard-code a phrase that could drift from the constant. Exercise
   both the library helper (`check_stub_gate`) and the CLI (`check-stub`,
   exit 0 / exit 1) at least once each. Do not edit the existing
   `test_check_stub_*` / `test_check_stubs_*` tests.

4. Reproduce the HOME-006 shape explicitly in one test: a story whose
   `## Instructions` tells a builder to append a resolution note, with the
   note's text — containing a delegation phrase — inside a fenced block. That
   story must pass the gate.

### Part A — the contract

5. In `skills/pairmode/scripts/next_action.py`, add the marking comment above
   the `SPAWN_REVIEWER` declaration. Match the existing house style used for
   `CHECKPOINT` a few lines below (a short comment naming the reason and the
   ticket). State: never emitted by `resolve_next_action`; orchestrator
   dispatches the reviewer inside the `spawn-builder` iteration; retained in
   `ACTIONS`/`_SPAWN_ACTIONS` because the orchestrator's
   `ACTION_SUBAGENT_TYPE` map and the model-override rule key on it; see
   `docs/agreements/HARNESS003-main.md`; CER-074. Optionally add a one-line
   pointer in the `_SPAWN_ACTIONS` comment block. **Change no executable
   line in this file.**

6. Add the regression test from assertion 3 to
   `tests/pairmode/test_next_action.py`. Read the existing tests in that file
   first and reuse whatever fixture/monkeypatch pattern they already use to
   drive `resolve_next_action` over a synthetic project; do not build a new
   harness. Parametrize over the position shapes rather than writing five
   near-identical test bodies.

7. Edit `CLAUDE.build.md` (repo root) and
   `skills/pairmode/templates/CLAUDE.build.md.j2`. **Append** the contract
   sentences to the end of the existing single-line paragraph that begins
   `Story-build actions (`spawn-builder`, ...` in each file's `## Build loop`
   section. Do **not** add a new paragraph, heading, blank line, or bullet:
   the rendered template is at exactly 40 non-blank lines and
   `test_template_reduction.py` caps it at 40. Appending to an existing
   physical line adds zero non-blank lines; anything else fails that test, and
   **raising the cap is not an acceptable fix** — the cap is the era's
   thin-harness invariant expressed as a test.

   Suggested text (adapt wording, keep every element assertion 4 requires):

   > **One iteration per story (CER-074):** the loop polls `next-action` once
   > per story — the builder spawn, the reviewer spawn, and the merge or
   > discard all happen inside that single iteration. `next-action` never
   > emits `spawn-reviewer`; the orchestrator dispatches the reviewer itself
   > after the builder returns. Do not re-poll `next-action` between the
   > builder's return and the merge: a story counts as passed only once its
   > `story-<ID>` commit is on the main branch, which the merge is what
   > creates — so a mid-story poll reads the finished attempt as failed and
   > re-dispatches a wasteful second builder over a good build.

   Note the deliberate avoidance of the literal `await-user` in that text —
   it is in `BANNED_PHRASES`. Keep the two files' statements substantively
   identical; the live file and the template are allowed to differ only where
   they already differ (script paths, the flex-harness promote step).

8. Edit `docs/architecture.md`: add the paragraph from assertion 7 to
   § `## Pairmode build loop`, and append the clause from assertion 8 to the
   `next_action.py` entry in § `## Module structure`. Follow the surrounding
   prose style (bolded lead label, ticket reference in parentheses). Do not
   restructure the section or renumber the existing 1–6 sequence.

### Part C — close the CER rows

9. Append the `**RESOLVED Phase 104 — INFRA-268 ...**` notes to the CER-074
   and CER-076 Finding cells and set both trailing phase cells to `104`.
   Copy the format from an already-resolved row (e.g. CER-072 or CER-066).
   Escape any literal pipe inside the new text as `\|`. Do not reword the
   original finding text, do not move the rows to another quadrant, and do
   not delete anything.

### Notes

10. **Ideology note (Step 4a, resolved inline).** Two entries in
    `docs/ideology.md` shaped this spec. *"We prefer codifying policy over
    implicit convention"* is the whole justification for part A: an
    orchestrator contract that only works because two separate orchestrators
    independently guessed it correctly is exactly implicit convention, and
    writing it into the loop file, the template, and the architecture doc is
    the codification. *"We prefer rationale-bearing decisions over bare
    rules"* is why assertions 1, 7, and 17 all require the *reason* to be
    recorded next to the rule — a bare "never emit `spawn-reviewer`" would be
    violated by the first agent that sees an unused constant and tidies it
    away. The *"never silently pass contradictions"* accepted constraint is
    what part B protects rather than weakens: masking quoted text narrows the
    gate to what it always meant, whereas the rejected `stub_gate: exempt`
    key would have created exactly the silent bypass that constraint forbids
    ("silent bypass is never permitted"). No conflict required routing
    around; the hook and sidebar constraints are untouched — nothing here
    changes a hook or writes state.

11. **Do not** touch `README.md`'s loop description in this story (it
    paraphrases the same flow at lines ~177–216); see `## Out of scope`.

## Tests

Targeted, then full:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_build.py \
  tests/pairmode/test_next_action.py tests/pairmode/test_next_action_schema.py \
  tests/pairmode/test_template_reduction.py tests/pairmode/test_templates.py \
  tests/pairmode/test_harness003_isolation.py -q 2>&1 | tail -30
```

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Run the full suite **without `-x`**, so a known pre-existing failure cannot
mask a real one.

**Acceptance:**

- The targeted run is fully green.
- `test_template_reduction.py` passes with the file unmodified (assertion 6).
  If it fails on the 40-line limit, the contract text was added as a new line
  instead of appended to an existing one — fix the edit, not the test.
- The full-suite result is unchanged from clean `HEAD`: green except the known
  pre-existing `test_observability_ui.py::test_ui_build_emits_dist_index_html`
  failure, which must be shown to reproduce on clean `HEAD` if it appears.

Also run the gate against this story file itself, as a live check of part B
(it must exit 0 — this file contains fenced text that the pre-fix gate would
not have objected to, but the post-fix gate must still be clean):

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/flex_build.py \
  check-stub INFRA-268 --project-dir . ; echo "exit=$?"
```

## Out of scope

- **Emitting `spawn-reviewer` from a builder-completed resolver state.**
  Explicitly rejected in `## Context`: it requires non-durable worktree state
  in a pure-read resolver and splits one story across two polls. If a future
  era wants a two-poll cycle, it needs its own agreements doc, not this story.
- **Removing `SPAWN_REVIEWER` from `ACTIONS`/`_SPAWN_ACTIONS`**, or any other
  change to the action vocabulary, `SCHEMA_VERSION`, or the worker-result
  grammar.
- **A `stub_gate: exempt` frontmatter escape hatch** (CER-076's alternative
  fix), and any other per-story gate bypass mechanism.
- **Changing `_STUB_DELEGATION_RE`'s phrase list** — adding, removing, or
  loosening a delegation phrase. Only *where* it is searched changes.
- **Changing the acceptance-surface check** (`_STUB_ACCEPTANCE_RE`) or
  `next_action._count_ensures_nonblank_lines` / the `needs_spec` stub
  heuristic, which is a separate stub signal with its own rules.
- **Markdown-correct parsing.** The mask is a pragmatic two-pass scanner, not
  a CommonMark implementation. Accepted limitation: a story that hides a
  genuine delegation instruction inside a code fence will pass the delegation
  check. That is judged acceptable because the gate's second half (acceptance
  surface) and the resolver's `needs_spec` heuristic both still apply, and
  because a stub author is not an adversary.
- **`README.md`'s narrative description of the loop** (~lines 177, 206, 216).
  It is a downstream paraphrase; syncing it is a documentation-currency item,
  not part of this fix.
- **`sync-build` / `sync-all` rollout** of the amended template to fleet
  projects. This story changes the template; propagating it to consumers is a
  separate, deliberate operation.
- **CER-075** (worktree build-environment provisioning), which sits in the
  same forqsite report but is tracked separately (see also CER-090/Phase 103).
- **Anything in `docs/agreements/`** — those are historical records of
  settled decisions and are read, not edited, by this story.
