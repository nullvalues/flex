---
id: INFRA-297
rail: INFRA
title: Scope commit build-evidence to the commit's own story; shared escaped-pipe table-split helper
status: complete
phase: "113"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/table_utils.py
  - skills/pairmode/scripts/next_story.py
  - skills/pairmode/scripts/story_resolver.py
  - skills/pairmode/scripts/index_integrity.py
  - skills/pairmode/scripts/flex_build.py
touches:
  - skills/pairmode/scripts/story_update.py
  - skills/pairmode/scripts/next_action.py
  - tests/pairmode/test_table_utils.py
  - tests/pairmode/test_next_story.py
  - tests/pairmode/test_story_resolver.py
  - tests/pairmode/test_index_integrity.py
  - tests/pairmode/test_flex_build_mark_phase_complete.py
  - tests/pairmode/test_story_update.py
  - tests/pairmode/test_next_action.py
  - tests/pairmode/test_checkpoint_routing.py
  - docs/architecture.md
  - docs/cer/backlog.md
  - docs/stories/INFRA/INFRA-297.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Two resolver-layer defects share one root: the build loop decides *which story
is next* from text it parses too loosely.

**CER-116 (the live one).** `next_story._has_story_commit`
(`next_story.py:142-171`) decides a story is built if its ID appears anywhere in
a commit's `git log --oneline` line, word-boundary matched, with commits
prefixed `spec(` skipped (RELEASE-041). That whole-subject search cannot tell
"this commit built X" from "this commit mentions X." Commit `e83ce900` —
`story(RELEASE-066): forqsite.help migrated; ... RELEASE-067+ held for operator
ruling` — therefore marked **RELEASE-067** as built while it was still `draft`
and unbuilt, and `find_next_story` silently skipped past it to RELEASE-068. The
resolver's failure mode is silent skipping, which is the worst shape a build
loop can have: no error, no verdict, just a story that never gets built. The
phase-106 fleet campaign runs on this resolver, so the defect gates
RELEASE-068's dispatch.

**CER-069 (the recurring one).** The same "split a Markdown table row on `|`
then index positionally" shape has now been fixed twice in isolation
(`story_update.py`, Phase 94/INFRA-207; `next_action._check_phase_completion`,
Phase 95/INFRA-222) and still lives, unaudited, at seven further sites. `\|` is
a *literal cell character* in a Markdown table, so a title cell like
`Edit\|Write` shreds into extra columns and shifts every positional read after
it — the status column silently becomes the wrong cell. Two correct
implementations exist and are copy-pasted regex literals; nothing stops an
eighth site appearing. This story ends the recurrence by giving the split one
owner.

Both fixes are parsing corrections to the layer every rail stands on — phase
113's stated purpose — and INFRA-298's tests read phase tables, so this story
lands before it.

## Requires

Verified live at spec time (2026-07-29, `main` @ `1c4af83d`). The builder must
re-read each anchor before editing; if any has drifted, fix the anchor and note
the drift in the build record rather than editing blind.

**CER-116 surface**

- `next_story._has_story_commit(story_id, git_log)` at
  `skills/pairmode/scripts/next_story.py:142-171`: builds
  `re.compile(r'\b' + re.escape(story_id) + r'\b', re.IGNORECASE)`, iterates
  `git_log.splitlines()`, extracts `message = line.split(" ", 1)[1] if " " in
  line else ""`, `continue`s when `message.lstrip().startswith("spec(")`, then
  returns True on `pattern.search(line)` — note it searches the **raw line**,
  not `message`.
- Its docstring (`:142-165`) documents three legitimate shapes that must keep
  counting: `story-`-prefixed scope (`feat(story-INFRA-100): done`),
  parenthetical merge suffix (`merge(fold-prep): ... (RELEASE-014)`), and bare
  mention (`chore(orchestrator): RELEASE-014 status update`).
- Sole caller: `find_next_story` at `next_story.py:207`, ahead of the
  `_SKIP_STATUSES` and `claimed` checks.
- Module docstring `next_story.py:1-36` restates the whole-subject rule.
- Existing coverage that must keep passing unchanged in intent:
  `tests/pairmode/test_next_story.py` — `test_case_insensitive_commit_match`
  (`:244`, lowercase scope `feat(story-infra-100)`), `test_bare_mention_commit_match`
  (`:265`, both merge-suffix and bare-mention shapes),
  `test_numeric_prefix_does_not_false_match` (`:292`),
  `test_spec_authoring_commit_does_not_false_match` (`:315`),
  `test_genuine_build_commit_still_matches_after_spec_exclusion` (`:345`).
- Rail-token shape in use elsewhere: `flex_build.py:122`
  `_STORY_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*-\d{3}$")`;
  `subagent_transcript.py:116` `re.compile(r"\b([A-Z][A-Z0-9]*-\d{2,})\b")`.
  Rails are **uppercase** by construction (`story_new.py:305`
  `_RAIL_RE = re.compile(r"[A-Z][A-Z0-9_]*")`).

**CER-069 surface — seven positional sites (drift corrected, see Instructions §0)**

| # | Site | Shape |
|---|------|-------|
| 1 | `next_story.py:95` | `parts = [p.strip() for p in stripped.split('|')]`; reads `parts[1]`, `parts[3]` |
| 2 | `story_resolver.py:166` | `parts = [p.strip() for p in stripped.split('|')]`; reads `parts[1]` |
| 3 | `index_integrity.py:124` | `parts = [p.strip() for p in stripped.split("|")]`; header-derived `phase_col_idx`/`status_col_idx` |
| 4 | `flex_build.py:839` | `parts = [p.strip() for p in stripped.split("|")]`; reads `parts[1]`, `parts[3]` |
| 5 | `flex_build.py:1139` | `cells = [p.strip() for p in stripped.split("|")[1:-1]]`; reads `cells[0]`/`cells[2]`, **rewrites and rejoins** the row |
| 6 | `flex_build.py:1256` | same shape as 5, era-ledger rewrite path |
| 7 | `flex_build.py:2256` | `parts = [p.strip() for p in stripped.split("|")]`; reads `parts[1]`, `parts[2]`, `parts[3]` |

Reference implementations (already correct, regex literal duplicated):

- `story_update.py:270` — `parts = re.split(r'(?<!\\)\|', stripped)`, with the
  CER-066 rationale comment at `:264-269`.
- `next_action.py:379` — `raw_cols = re.split(r'(?<!\\)\|', stripped)`, rationale
  comment at `:375-378`.

Eighth, non-positional-but-filtered site:

- `next_action.py:429` (`_check_cer_do_now`) —
  `cols = [c.strip() for c in stripped.split("|") if c.strip()]`. The
  `if c.strip()` filter **drops empty cells and shifts indices**, and it is
  load-bearing: `cols[0].lower() in ("id", "finding")` is the header test and
  `is_placeholder_row(cols)` (INFRA-294, `cer.py`) consumes the filtered list.

- No `table_utils.py` exists under `skills/pairmode/scripts/` yet. Sibling
  imports use the `sys.path.insert(0, str(Path(__file__).parent))` convention
  (`next_story.py:47`, `index_integrity.py:37`, `flex_build.py:32`).
- `index_integrity` already imports from `next_story` (`index_integrity.py:40`)
  and `flex_build` imports `index_integrity` lazily to avoid a cycle
  (`index_integrity.py:21` comment) — the new module must import nothing from
  siblings so it cannot participate in a cycle.

**Prior stories:** none blocking. INFRA-296 touches
`cmd_create_story_worktree`, a different region of `flex_build.py`; no
conflicting hunks.

## Ensures

### A. The shared split helper

1. **A1.** A new module `skills/pairmode/scripts/table_utils.py` exists,
   imports only the Python standard library (`re`), and imports no sibling
   pairmode module. `grep -nE '^(from|import) ' skills/pairmode/scripts/table_utils.py`
   lists nothing but stdlib.
2. **A2.** It exposes `split_table_row(stripped: str) -> list[str]` implemented
   as `re.split(r'(?<!\\)\|', stripped)` — returning the raw parts, including
   the leading empty string before the first `|` and the trailing empty string
   after the last, with **no** per-cell `.strip()` applied. Callers keep their
   own stripping and slicing.
3. **A3.** `split_table_row` is **non-destructive**: it does not unescape `\|`.
   `split_table_row(r"| a | b\|c | d |") == ["", " a ", r" b\|c ", " d ", ""]`.
   The docstring states this explicitly, with the reason: the
   `mark-phase-complete` rewrite paths (`flex_build.py:1139`, `:1256`) rejoin
   the returned cells with `" | "` and write the row back, so an unescaping
   split would silently corrupt every row it touched.
4. **A4.** The docstring carries the rationale (not just the rule, per
   `docs/ideology.md` § "rationale-bearing decisions"): `\|` is a literal cell
   character; a naive `str.split('|')` shreds a title like `Edit\|Write` into
   extra columns and shifts every positional read after it; names CER-066,
   CER-069, INFRA-207 and INFRA-222 as the prior single-site fixes, and this
   story as the consolidation.

### B. Call-site conversion

5. **B1.** All **seven** positional sites in the Requires table consume
   `split_table_row`. Behaviour at each is otherwise unchanged: the same
   `.strip()`, the same slicing (`[1:-1]` preserved at `flex_build.py:1139`
   and `:1256`), the same indices.
6. **B2.** The two existing correct sites — `story_update.py:270` and
   `next_action.py:379` — are rewired to `split_table_row`, so the
   `(?<!\\)\|` regex literal exists in exactly one place. Their local CER-066
   rationale comments are reduced to a one-line pointer at the call site
   ("split rationale: `table_utils.split_table_row`"); the full rationale lives
   in the helper docstring and is not deleted from the repo.
7. **B3.** After the change,
   `grep -rnE "stripped\.split\(['\"]\|['\"]\)" skills/pairmode/scripts/*.py`
   returns **zero** hits, and
   `grep -rn "(?<!\\\\)\\\\|" skills/pairmode/scripts/*.py` returns exactly one
   hit — inside `table_utils.py`. (Comments and docstrings may mention the old
   shape in prose; the greps above match code form, not prose.)
8. **B4.** `next_action._check_cer_do_now` (`next_action.py:429`) is converted
   as well and **keeps its `if c.strip()` filter verbatim**:
   `cols = [c.strip() for c in split_table_row(stripped) if c.strip()]`. The
   filter is preserved, not dropped — it shifts indices and both the
   `cols[0].lower() in ("id", "finding")` header test and
   `cer.is_placeholder_row(cols)` (INFRA-294) depend on the shifted shape. A
   test pins this: a Do Now row whose finding cell contains `\|` is classified
   identically before and after, and the placeholder row is still exempted.
9. **B5.** No call site gains a *new* escaped-pipe behaviour beyond correct
   splitting: no site starts unescaping, re-escaping, or normalising cell text.

### C. Build-evidence scoping (CER-116)

10. **C1.** `_has_story_commit` gains a scope rule: if the commit subject's
    conventional-commit **scope** — the text inside the first `(...)` of a
    leading `type(scope):` prefix — contains at least one uppercase story-ID
    token matching `\b[A-Z][A-Z0-9_]*-\d{2,}\b`, then **only** those scope
    tokens count as build evidence from that commit; `story_id` matches only if
    it equals one of them (case-insensitive comparison). Otherwise the existing
    whole-subject `\b`-bounded, case-insensitive search runs unchanged
    (fallback).
11. **C2.** The scope-ID detector is **uppercase-only and deliberately so**:
    lowercase scopes such as `phase-112`, `era-004`, `fold-prep` and
    `story-infra-100` do not activate the restriction, so they fall back to
    whole-subject search. This is the conservative direction — a missed
    restriction re-offers a story (loud, recoverable) whereas a wrong
    restriction skips one silently. The docstring states this trade-off and
    names `story_new.py:305`'s uppercase `_RAIL_RE` as the reason rails are
    uppercase by construction.
12. **C3.** The `spec(` skip (RELEASE-041) is unchanged and still evaluated
    **before** the scope rule, and it still matches on `message.lstrip()`.
13. **C4.** All three docstring-documented legitimate shapes still count as
    evidence:
    - `feat(story-INFRA-100): done` → `INFRA-100` True (uppercase scope token).
    - `feat(story-infra-100): mixed case` → `INFRA-100` True (lowercase scope,
      fallback path — pins `test_case_insensitive_commit_match`).
    - `merge(fold-prep): fold RELEASE work (RELEASE-014)` → `RELEASE-014` True
      (scope has no story ID → fallback).
    - `chore(orchestrator): RELEASE-014 status update` → `RELEASE-014` True
      (fallback).
    - `INFRA-1001`-style numeric-prefix non-match still False for `INFRA-100`
      on both paths.
14. **C5.** **The live regression is pinned as a unit test on a synthetic git
    log.** Given a one-line log whose subject is exactly `e83ce900`'s:

    `story(RELEASE-066): forqsite.help migrated; E6 split verdict — E4b grammar replacement PROVEN in field, CER-101 content half PROVEN via reviewer row 14, builder row 13 pending on termination-detection artifact (new-1); RELEASE-067+ held for operator ruling`

    `_has_story_commit("RELEASE-067", log)` is **False** and
    `_has_story_commit("RELEASE-066", log)` is **True**. The test must build
    the log itself (a literal string, or a fixture repo containing only that
    subject) — it must **not** read this repository's real `git log`, because
    RELEASE-067 has since been genuinely built by `0978447b` and the real log
    no longer reproduces the false positive. The test docstring says so and
    names CER-116 and `e83ce900`.
15. **C6.** The fallback search is applied to the commit **message** (the
    subject after the first space), not the raw `git log --oneline` line. A
    test asserts a story ID is not matched out of the abbreviated SHA field.
16. **C7.** `_has_story_commit`'s docstring is rewritten: it names CER-116,
    states the scope rule and the fallback, keeps all three legitimate shapes
    enumerated, and states the interim operator discipline the rule replaces
    ("never name sibling story IDs in non-`spec(` commit subjects").
    `next_story.py`'s module docstring (`:1-36`) is updated to match — it
    currently asserts the whole-subject rule with no scope qualifier.
17. **C8.** `find_next_story`'s ordering is unchanged: commit evidence still
    precedes the `_SKIP_STATUSES` and `claimed` checks (`next_story.py:207`),
    and `claimed` still never overrides commit evidence (CER-095.1 / A5).

### D. Documentation and backlog

18. **D1.** `docs/architecture.md` records both: (a) `table_utils.split_table_row`
    as the single owner of Markdown-table row splitting, with the escaped-pipe
    rationale and the instruction that new table readers import it rather than
    write a fresh `split`; (b) the build-evidence rule — scope-restricted with
    whole-subject fallback — in the section that documents story resolution.
19. **D2.** The `CER-116` and `CER-069` rows in `docs/cer/backlog.md` are
    annotated `RESOLVED (INFRA-297)` with the file:line evidence and, for
    CER-069, the corrected site count (seven positional sites, not six — see
    §0 of Instructions).

### E. Suite

20. **E1.** `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` is
    run **without `-x`** and is green apart from the known pre-existing
    `test_observability_ui` failure, which must be shown to reproduce on clean
    `HEAD` before the diff is claimed clean.

### F. Release-channel promotion (operator-run, post-merge)

The phase-106 fleet campaign runs its CLIs from `/mnt/work/flex-harness`, not
from this repository. A fix on `main` is invisible to the campaign until it is
ff-merged to that channel, and CER-116 gates RELEASE-068's dispatch — so, in
the INFRA-293 F3/F4 pattern, the fix is not "landed" until it is on the
channel.

21. **F1 (operator-run, post-merge).** After this story merges to `main`, the
    change is promoted to `/mnt/work/flex-harness` by ff-only merge, and the
    channel copy is verified:

    ```bash
    PATH=$HOME/.local/bin:$PATH uv run python - <<'PY'
    import sys; sys.path.insert(0, "/mnt/work/flex-harness/skills/pairmode/scripts")
    from next_story import _has_story_commit
    log = ("e83ce900 story(RELEASE-066): forqsite.help migrated; E6 split verdict "
           "— ...; RELEASE-067+ held for operator ruling")
    print(_has_story_commit("RELEASE-067", log), _has_story_commit("RELEASE-066", log))
    PY
    ```

    prints `False True`, and

    ```bash
    PATH=$HOME/.local/bin:$PATH uv run python \
      /mnt/work/flex-harness/skills/pairmode/scripts/next_story.py \
      /mnt/work/flex/docs/phases/phase-106.md --project-dir /mnt/work/flex --json
    ```

    returns `RELEASE-068` — the campaign's true next story — with no error.
22. **F2.** The F1 result (date, channel commit promoted to, both observed
    outputs) is recorded in phase-113's CP-113 cold-eyes checklist block,
    orchestrator-filled. **RELEASE-068 must not be dispatched before F1 is
    recorded PASS**, and **phase 113 cannot be checkpointed with F1 unrun**.
    F1/F2 are operator work, not builder work — a builder that cannot reach
    `/mnt/work/flex-harness` leaves them outstanding and says so, and must not
    substitute a weaker in-repo check for them.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Do not touch `/mnt/work/flex-harness` — F1/F2 are the operator's.

**§0 — Plan drift you are inheriting (already corrected above; re-verify anyway).**
The closeout plan named *six* naive-split sites. There are **seven**:
`story_resolver.py:166` was omitted from the plan's list although CER-069's own
backlog row names it. `story_resolver._parse_stories_table` is what
`next_story` calls to get story IDs in table order, so leaving it naive would
have left the exact defect class inside the resolver this story is fixing.
Convert it. Re-run the Requires-table grep before you start; if the line
numbers have moved, use the shapes, not the numbers.

**§1 — Write the helper first.** Create `table_utils.py` with
`split_table_row` and its rationale docstring (A1-A4). Add
`tests/pairmode/test_table_utils.py` and get it green before touching any call
site. Cover: plain row; row with `\|` in a cell (round-trip — split then
`" | ".join(parts[1:-1])` reproduces the original inner text byte-for-byte);
leading/trailing empties present; single-cell row; row with no pipes at all;
empty string. Assert the module imports no sibling (A1) with a source-level
check, not a comment.

**§2 — Convert the seven positional sites, one file at a time**, running that
file's tests after each. Import via the established convention — the modules
already do `sys.path.insert(0, str(Path(__file__).parent))`, so
`from table_utils import split_table_row  # noqa: E402` after that line is
correct. At `flex_build.py:1139` and `:1256`, the split feeds a rewrite: keep
`[1:-1]`, keep `" | ".join(cells)`, and add a test that a row whose *title*
cell contains `\|` survives `mark-phase-complete` unchanged except for the
status cell. That test is the whole point of A3 — write it before you trust
the conversion.

**§3 — Rewire the two reference sites** (`story_update.py:270`,
`next_action.py:379`) so the regex literal is single-sourced (B2). Do not
delete their rationale — move it into the helper docstring and leave a pointer
comment. Then convert `next_action.py:429` **keeping `if c.strip()`** (B4);
write the escaped-pipe Do Now row test and the placeholder-row test before
you change it, so you can prove the classification is identical.

**§4 — `_has_story_commit`.** Add a module-level scope regex, e.g.
`_SCOPE_RE = re.compile(r'^[A-Za-z]+\(([^)]*)\)\s*:')` and
`_SCOPE_STORY_ID_RE = re.compile(r'\b[A-Z][A-Z0-9_]*-\d{2,}\b')`. Per commit
line: extract `message` as today; `continue` on the `spec(` prefix (C3);
`_SCOPE_RE.match(message.lstrip())`; if it matches and
`_SCOPE_STORY_ID_RE.findall(scope)` is non-empty, return True only if
`story_id.upper()` is in that set (uppercased); otherwise fall through to the
existing `\b`-bounded case-insensitive search — applied to `message`, not
`line` (C6). Do not delete the RELEASE-041 `spec(` skip and do not widen the
word-boundary pattern.

**Do not "simplify" to scope-only matching.** The plan's original CER-116
wording ("only count a mention when the ID is in the commit's own scope")
breaks the merge-suffix and bare-mention shapes the docstring documents and the
suite pins (`test_bare_mention_commit_match`). The corrected rule — restrict
*when the scope names a story ID*, fall back otherwise — is the one specified
here (closeout plan §C.6). If a test forces you toward scope-only matching,
the test is wrong; stop and report rather than deleting a documented shape.

**§5 — Docs and backlog** (D1, D2). Then run the full suite without `-x` (E1).

*Ideology note (Step 4a, resolved inline):* the helper is deliberately a pure
stdlib function with no sibling imports and no state, so it cannot participate
in an import cycle or blur the hook/sidebar write-ownership boundary
(`docs/ideology.md` § "Sidebar owns all state writes"); and its docstring
carries the *reason* for the escaped-pipe rule, not just the rule, per
§ "rationale-bearing decisions over bare rules". No conviction conflicts were
found.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_table_utils.py \
  tests/pairmode/test_next_story.py \
  tests/pairmode/test_story_resolver.py \
  tests/pairmode/test_index_integrity.py \
  tests/pairmode/test_flex_build_mark_phase_complete.py \
  tests/pairmode/test_story_update.py \
  tests/pairmode/test_next_action.py \
  tests/pairmode/test_checkpoint_routing.py -q
```

Then, once, without `-x` (per the project's known-failure rule — `-x` masks
later real failures behind the known one):

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

**Acceptance.** Both runs green apart from the known `test_observability_ui`
failure, which must be demonstrated to reproduce on clean `HEAD`. New tests
required, at minimum:

- `test_table_utils.py` — escaped-pipe split; round-trip preservation (A3);
  boundary cases; stdlib-only import assertion.
- `test_next_story.py` — the `e83ce900` synthetic-log pin (C5, both
  directions); scope-restriction positive and negative; lowercase-scope
  fallback; SHA-field non-match (C6). Existing shape tests at `:244`, `:265`,
  `:292`, `:315`, `:345` pass unmodified.
- `test_flex_build_mark_phase_complete.py` — a row whose title cell contains
  `\|` is rewritten with only the status cell changed.
- `test_next_action.py` — `_check_cer_do_now` classification identical for an
  escaped-pipe Do Now row; placeholder row still exempted (B4).
- A grep-form assertion (in `test_table_utils.py`) proving B3: no
  `stripped.split("|")` remains in `skills/pairmode/scripts/*.py` and the
  `(?<!\\)\|` literal appears in exactly one module.

## Out of scope

- **`_has_story_commit` is not replaced by a trailer-based or notes-based
  evidence scheme.** Reading `git log --format` trailers (e.g. a
  `Story-Id:` trailer) would be a stronger contract, but it invalidates every
  commit already in this repo's history and every consumer project's history.
  The subject-line heuristic stays; only its precision improves.
- **No change to `find_next_story`'s ordering, the `claimed` filter, or
  `_SKIP_STATUSES`.** CER-095's semantics are settled (INFRA-280..286).
- **No new table *parser*.** This story factors out the split only. Column
  discovery, header detection and status normalisation remain per-site;
  unifying them is a larger refactor and is not attempted here.
- **`table_utils` gains no other helpers** — no `parse_table`, no
  `cells_for_row`, no escaping/unescaping utilities. One function, one reason
  to change.
- **No commit-message linting or hook** to enforce the "never name sibling
  story IDs in non-`spec(` subjects" discipline. The scope rule makes that
  discipline unnecessary as a correctness measure; a linter is a separate
  concern and is not filed as work by this story.
- **Observability TS-side table parsing** (`skills/observability/**`) is
  untouched; it is INFRA-306/309 territory.
- **F1/F2 channel promotion is not builder work** — see § Ensures F.
