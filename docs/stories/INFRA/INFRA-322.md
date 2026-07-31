---
id: INFRA-322
rail: INFRA
title: "Anchored, case-insensitive CER resolution-marker grammar: the cer-do-now checkpoint guard stops reading Resolved as unresolved and UNRESOLVED as resolved"
status: complete
phase: "114"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/cer.py
  - skills/pairmode/scripts/next_action.py
touches:
  - tests/pairmode/test_cer.py
  - tests/pairmode/test_next_action.py
  - docs/architecture.md
  - skills/pairmode/skills/checkpoint-docs/procedure.md
  - skills/pairmode/templates/docs/cer/backlog.md.j2
  - docs/cer/backlog.md
  - docs/phases/phase-114.md
  - docs/stories/INFRA/INFRA-322.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

**Pulled from CER-130** (`docs/cer/backlog.md`, operator report 2026-07-29,
phase-35 checkpoint on a consuming repo), a mid-phase addition to Phase 114 by
operator direction rather than from the era-004 closeout reconciliation.

The `cer-do-now` checkpoint guard decides whether a project may enter its
checkpoint sequence. It answers one question per Do Now row — *is this finding
resolved?* — and today it answers it with a bare, case-sensitive substring
membership test on the whole row line
(`skills/pairmode/scripts/next_action.py:437`):

```python
if "RESOLVED" not in stripped and "SUPERSEDED" not in stripped:
    return False  # unresolved Do Now item
```

That single expression is wrong in both directions, and both directions have
been observed.

**Direction 1 — a resolved backlog reads as unresolved (permanent block).**
Hit live on a consuming repo's phase-35 checkpoint. That repo's backlog
convention is title-case: `Resolved cp-34 — …`. `"RESOLVED" not in stripped`
is `True` for every one of its rows, so the guard returns `False`
unconditionally, `check_checkpoint_guards` returns
`{"ok": False, "failed_guard": "cer-do-now"}` (`next_action.py:542-544`), and
`next-action` emits `await-user / checkpoint-guard-failed:cer-do-now` at every
checkpoint forever. The operator's only remedy was to bypass the resolver and
hand-run `record-checkpoint-step checkpoint-tag` — a manual bypass of a gate,
which is exactly the CER-067 failure class (an un-clearable mechanical gate
that agents and operators learn to route around, after which the gate protects
nothing). This is the same shape as CER-072 (a guard that could never pass in
any downstream project) and CER-094/INFRA-294 (the scaffolded placeholder row
that blocked every fresh repo's first checkpoint): a guard whose failure mode
is *always red* is not a strict guard, it is a dead one.

**Direction 2 — an unresolved row reads as resolved (silent pass).** The bare
substring test has no boundaries, so any row containing the letters `RESOLVED`
in any surrounding context passes. Two live-shaped examples:

- `| CER-4xx | UNRESOLVED naming gap between … | … |` — the word `UNRESOLVED`
  contains `RESOLVED`, so the row that says in as many letters that it is *not*
  resolved is classified resolved.
- `| CER-4xx | … the fix direction is documented; this SHOULD BE RESOLVED
  before the 0.4 tag | … |` — future/aspirational prose in an uppercased
  fragment reads as an accomplished resolution.

Direction 2 is the more dangerous of the two: direction 1 announces itself with
a permanent block, while direction 2 waves a genuinely open Do Now item through
a checkpoint silently. A fix that only lowercases the comparison would repair
direction 1 and **widen** direction 2 (`unresolved`, `should be resolved`, and
`to be resolved` all begin matching once case is dropped). Both must be fixed by
the same change, which means the check must be *anchored* to a marker
convention, not merely case-folded.

**Why there is no writer to fix instead.** Nothing in the codebase writes a
resolution marker. `cer.py`'s CLI writes new findings and, for the `never`
quadrant, a rejection reason (`_prompt_resolution`, `cer.py:314-316`) — never a
resolution annotation. Every marker in every backlog in the fleet was written by
hand or by an agent following prose in `checkpoint-docs/procedure.md`, which
says only that items "must be marked `RESOLVED`" (`:58`, `:99`) without
defining what "marked" means. The grammar the guard accepts has therefore never
been written down anywhere a consuming repo could read it — which is the root
cause of the phase-35 block, not a typo in one repo's backlog. Defining the
grammar and publishing it is half of this story.

**What the resolved-marker conventions actually are.** In flex's own backlog
all 14 non-placeholder Do Now rows use a bolded marker-prefix form —
`**RESOLVED Phase 55 — …**`, `**RESOLVED (INFRA-297)**`,
`**RESOLVED cp-HARNESS007-main: …**`, `**RESOLVED Phase 94 (cp94) — …**`. The
consuming repo that blocked uses a plain title-case marker-prefix form —
`Resolved cp-34 — …`. Both are marker prefixes: the keyword *begins* an
annotation segment. Nothing that is genuinely a resolution marker appears
mid-clause, and nothing that appears mid-clause (`should be resolved`,
`UNRESOLVED`, `partially resolved`) is a marker. That observation is the whole
grammar.

## Requires

Re-verified against the working tree at spec time (2026-07-29, `main` @
`24892fe3`). A builder finding an anchor moved should re-locate by symbol name,
not line number, and note the drift in its report.

- `next_action._check_cer_do_now` (`next_action.py:393-441`) — the guard. Pure
  read; returns `True` when `docs/cer/backlog.md` is absent or unreadable
  (fail-open, `:409-414`). Walks the `## Do Now` section only, breaking at the
  next `## ` heading (`:418-423`); skips separator rows (`:425-426`); splits with
  `table_utils.split_table_row` and the index-shifting `if c.strip()` filter
  (`:427-432`); skips header rows via `cols[0].lower() in ("id", "finding")`
  (`:433-434`); skips the scaffolded empty-state row via
  `cer.is_placeholder_row(cols)` (`:435-436`); then applies the defective
  membership test (`:437-438`).
- `cer.is_placeholder_row` (`cer.py:144-173`) — the INFRA-294 precedent this
  story follows for *where* a row-classification rule lives: a shared public
  predicate in `cer.py`, consumed by both `cer._parse_entries_from_backlog`
  (`:124`) and `next_action._check_cer_do_now`, so the rule is defined once
  rather than duplicated with independent writers. Its docstring records why:
  reading the placeholder row as a finding blocked caddy's first 0.3.0
  checkpoint.
- `next_action.check_checkpoint_guards` (`:508-566`) — Guard 2 call site
  (`:541-544`), which turns a `False` into
  `{"ok": False, "failed_guard": "cer-do-now"}`. Untouched by this story: the
  guard's contract, its position in the guard order, and its failure string all
  stay identical.
- `INFRA-297` (merged) converted this function's row splitting from a naive
  `str.split("|")` to `table_utils.split_table_row` and left the membership test
  verbatim, with an explicit comment that the `if c.strip()` filter is
  load-bearing for `cols[0]` and `is_placeholder_row`. **This story changes only
  the membership test.** The split, the filter, the header test and the
  placeholder exemption are not re-litigated.
- `tests/pairmode/test_next_action.py:2324-2403`
  (`TestCheckCerDoNowEscapedPipe`) — the only direct test class for this guard.
  Five cases: unresolved-with-escaped-pipe fails, resolved-with-escaped-pipe
  passes (`**RESOLVED (INFRA-297)**`), classification identical with/without an
  escaped pipe, placeholder row exempted, header-only file passes. All five must
  stay green unchanged.
- `tests/pairmode/test_checkpoint_routing.py:253-335` — guard-through-resolver
  cases; the resolved fixture is `**RESOLVED Phase 1**` (`:287`), which the new
  grammar accepts. `tests/pairmode/test_harness004_isolation.py:265-330` —
  end-to-end `checkpoint-guard-failed:cer-do-now` routing. Both files' fixtures
  must keep their current verdicts; neither file is edited.
- Documentation surfaces that currently describe the convention without defining
  it: `docs/architecture.md:830-836` (build-loop step 10, the checkpoint guards
  paragraph — already names the `is_placeholder_row` exemption and is the
  natural home for the grammar), `skills/pairmode/skills/checkpoint-docs/procedure.md:58`
  and `:99` (the docs-reviewer's own CER Do Now check), and the backlog preamble
  ("resolved findings remain in place with a resolution note") in both
  `skills/pairmode/templates/docs/cer/backlog.md.j2:5-7` — the file every
  consuming repo is bootstrapped from — and flex's own rendered
  `docs/cer/backlog.md:5-7`.
- **INFRA-320** (Phase 113) introduces `scope_guard.STANDING_SURFACES` covering
  `docs/cer/backlog.md` and `docs/architecture.md`. This story declares both in
  `touches:` explicitly and does not depend on INFRA-320 having merged.
- **INFRA-299** (Phase 113, unmerged, under review) owns backlog rows CER-105,
  CER-106 and CER-113. This story edits no backlog row other than CER-130's own
  annotation and the preamble paragraph at `:5-7`.

## Ensures

### A — the grammar is defined once, in `cer.py`

**A1.** `cer.py` gains a public predicate — `is_resolution_marked(text: str) -> bool`
(name indicative) — which returns `True` when `text` contains at least one
**resolution marker** as defined by § A2. It is pure: no I/O, no state, no
mutation of its argument; stdlib-only (`re`, already imported at `cer.py:41`).
It accepts any string, returns `False` for `""` and for a non-`str` falsy input
rather than raising.

**A2.** The **resolution-marker grammar** is specified as follows, and this
specification is what the implementation and the documentation of § D must both
express:

```
MARKER        := SEGMENT_START OPENER* KEYWORD CLOSE
KEYWORD       := "RESOLVED" | "SUPERSEDED"        ; ASCII case-insensitive:
                                                  ; RESOLVED, Resolved, resolved all match
OPENER        := one of  *  (  [                  ; zero or more, any mix — covers
                                                  ; **RESOLVED**, *Resolved*, (RESOLVED …), [RESOLVED]
SEGMENT_START := start of the scanned text
               | a newline
               | one of  .  !  ?  ;  :  —  –  |  )   followed by one or more spaces/tabs
               | an OPENER character
CLOSE         := end of text, or a character that is not [A-Za-z0-9_]
```

In words: **the keyword must begin an annotation segment.** A marker may be
bolded, italicised, parenthesised or bracketed, may be lower-, upper- or
title-case, and may sit at the start of a table cell, after a sentence-ending
`.`/`;`/`:`/em-dash, or after a `|` cell boundary. A keyword that appears
*inside* a clause — preceded by a space and a word — is not a marker.

Consequences that follow from the grammar and must hold:

| text | marker? | why |
|---|---|---|
| `… fixed. **RESOLVED Phase 55 — INFRA-1**` | yes | flex's own convention: `.`+space, then `**` |
| `… fixed. Resolved cp-34 — INFRA-1` | yes | consuming-repo convention: `.`+space, case-folded |
| `\| Resolved cp-34 — INFRA-1 \|` | yes | a `\|` cell boundary followed by a space is a segment start |
| `… (RESOLVED INFRA-297)` / `… [RESOLVED]` / `… *Resolved*` | yes | opener characters |
| `… **SUPERSEDED by CER-9**` | yes | second keyword, same rules |
| `UNRESOLVED naming gap …` | **no** | `RESOLVED` is preceded by `UN`, not a segment start |
| `this should be RESOLVED before cp` | **no** | preceded by `be `+space — a space is not a segment boundary |
| `to be resolved in 116` / `not resolved yet` / `**Not resolved**` | **no** | same: mid-clause |
| `PARTIALLY RESOLVED phase 3` | **no** | mid-clause; a partial resolution keeps blocking (BUILD-006 partial-resolution notes are not closures) |
| ``the `RESOLVED` literal`` / `` `if "RESOLVED" not in stripped` `` | **no** | a backtick and a double quote are deliberately **not** openers, so prose and code quoting the literal — including CER-130's own row text — is not a marker |
| `_RESOLVED_RE` | **no** | `_` is deliberately not an opener; it collides with Python identifier prose |

**A3.** The exclusions in the last three rows of that table are deliberate and
the docstring says so: `` ` ``, `"`, `'` and `_` are **not** accepted openers.
Underscore-emphasis (`__RESOLVED__`) and code-span markers
(`` `RESOLVED` ``) are therefore not recognised. The rule stated in the
docstring: **where the grammar is uncertain it fails closed** — an unrecognised
ornamentation reads as unresolved, which produces a visible block that an
operator can correct, rather than a silent pass. Direction 2 of CER-130 is the
failure this asymmetry exists to prevent; direction 1 is prevented instead by
§ D publishing the accepted forms so a repo never has to guess.

**A4.** `is_resolution_marked`'s docstring is the single source of truth for the
grammar: it states the accepted forms, the rejected forms, the fail-closed rule,
and names CER-130 with both of its directions (title-case backlog blocked
forever on a consuming repo's phase-35 checkpoint; `UNRESOLVED` and
`should be resolved` waved through). It also states that the predicate is
consumed by `next_action._check_cer_do_now` and that any future consumer must
call it rather than re-deriving the test — the `is_placeholder_row` precedent
(§ Requires) verbatim.

**A5.** The compiled pattern is a module-level constant in `cer.py` (e.g.
`_RESOLUTION_MARKER_RE`), compiled once with `re.IGNORECASE`, not compiled
per-call inside the predicate. Case-insensitivity comes from the flag, not from
lowercasing the input, so the caller's string is never copied.

### B — the guard consumes the predicate and changes nothing else

**B1.** `next_action._check_cer_do_now` imports `is_resolution_marked` alongside
`is_placeholder_row` from `cer` (the existing local-import line at
`next_action.py:407`, so the module-import cost stays where it is today) and its
membership test becomes a call to the predicate. The scanned text is the same
text the current code scans — the whole `stripped` row line — so the change is
exactly the substitution of one boolean expression for another. A row is
unresolved when `is_resolution_marked(stripped)` is `False`.

**B2.** Everything else in the function is byte-identical in behavior:
fail-open on a missing or unreadable file, `## Do Now`-only scanning and the
`## ` break, separator skipping, `split_table_row` + the index-shifting
`if c.strip()` filter with its INFRA-297 comment intact, the
`cols[0].lower() in ("id", "finding")` header test, and — § C — the
`is_placeholder_row` exemption. The function stays pure-read: no writes, no
`SCHEMA_VERSION` bump, no Position-shape change, no routing change.

**B3.** `check_checkpoint_guards` is not edited. Guard order, the
`"cer-do-now"` failure string, and the `{"ok": …, "failed_guard": …}` shape are
unchanged, so no caller and no test of the resolver's routing layer needs to
change.

**B4.** The function docstring is updated to describe the anchored grammar
instead of "``RESOLVED`` or ``SUPERSEDED`` anywhere in it", to name
`cer.is_resolution_marked` as the grammar's source of truth, and to cite
INFRA-322/CER-130. The module-header changelog block in `next_action.py`
(`:1-140`, where INFRA-294's entry sits at `:127-140`) gains an INFRA-322 entry
in the same style, noting explicitly that the guard's grammar changed while its
shape did not.

### C — the placeholder exemption is byte-identical

**C1.** The scaffolded empty-state placeholder row continues to be exempted
before any resolution test runs, via the same `cer.is_placeholder_row(cols)`
call on the same `cols` list, in the same position in the loop. `is_placeholder_row`
itself is not edited: not its signature, not its cell-shape tolerance
(four-, five- and six-column rows), not its docstring's INFRA-294 provenance.

**C2.** The exemption's *ordering* is load-bearing and must be preserved: the
placeholder row is skipped **before** the resolution test, so it never reaches
`is_resolution_marked` and its classification cannot depend on the new grammar.
A test asserts the placeholder row still passes, and a second test asserts that
a placeholder row would *not* satisfy `is_resolution_marked` on its own — proving
the exemption, not the new grammar, is what carries it (if that ever inverts, a
change to the grammar could silently start blocking fresh repos again).

**C3.** The real scaffolded backlog from
`skills/pairmode/templates/docs/cer/backlog.md.j2` (rendered, as
`test_checkpoint_routing.py:297-317` already does) still passes the guard, and
so does the four-cell caddy-shaped placeholder row (`:318-335`).

### D — the grammar is published where consuming repos read it

**D1.** `docs/architecture.md`'s build-loop step 10 checkpoint paragraph
(`:830-836`) states the resolution-marker grammar: the two keywords, ASCII
case-insensitivity, the marker-prefix anchoring rule, the accepted opener
characters, the fail-closed rule for anything else, and the fact that
`cer.is_resolution_marked` is the single implementation. It names INFRA-322 /
CER-130 and states both defect directions in one clause each, so a future reader
cannot re-derive a bare substring test believing it equivalent.

**D2.** `skills/pairmode/skills/checkpoint-docs/procedure.md` — the docs-reviewer's
own CER Do Now check at `:58` and `:99` — replaces "must be empty or all
`RESOLVED`" / "every item must be marked `RESOLVED`" with the accepted grammar:
a `RESOLVED` or `SUPERSEDED` marker (any case) beginning an annotation segment,
optionally bolded/italicised/parenthesised/bracketed. The worker's *report*
grammar is unchanged — it still reports the finding string
`"CER Do Now contains unresolved item: [item text]"` — so
`tests/pairmode/test_checkpoint_docs_worker.py:219` stays green.

**D3.** `skills/pairmode/templates/docs/cer/backlog.md.j2`'s preamble (`:5-7`)
— the text every bootstrapped repo receives as its own `docs/cer/backlog.md`
header — states the resolution-note convention concretely rather than
abstractly: findings are never deleted; a resolved finding keeps its row and
gains a marker annotation of the form `**RESOLVED <phase or checkpoint> — <what
landed>**` (or `**SUPERSEDED by CER-NNN**`); the marker must begin its
annotation segment; case does not matter; and the `cer-do-now` checkpoint guard
reads exactly this form. This is the change that prevents CER-130 direction 1
recurring in the next consuming repo, because it is the only copy of the
convention a bootstrapped repo actually has on disk.

**D4.** flex's own rendered `docs/cer/backlog.md` preamble (`:5-7`) is updated
to the same wording, so the template and the rendered file do not drift. This is
a preamble-only edit; **no finding row is touched** except CER-130's own
annotation (§ E1). In particular rows CER-105, CER-106 and CER-113 are left
byte-identical (§ Requires, INFRA-299).

**D5.** No new documentation file is created and the pattern doc
`docs/patterns/operations-orchestration/cer-backlog-living-phases.md` is not
edited — it describes the pattern for external readers, not this repo's guard
contract, and § Out of scope records that decision.

### E — backlog

**E1.** The CER-130 row in `docs/cer/backlog.md` is annotated
`**RESOLVED INFRA-322 (Phase 114)**` with a short statement of what landed: the
shared anchored grammar in `cer.py` (A), the guard's one-expression substitution
(B), the preserved placeholder exemption (C), and the four documentation
surfaces (D). The annotation must be written so that it is itself matched by the
new grammar — a resolution note that the guard cannot read is the bug.

**E2.** The annotation records that **a lowercase-only fix was rejected**: it
would repair direction 1 and widen direction 2. It also records the deliberate
exclusions of § A3 (backtick, quote and underscore are not openers) so a future
reader does not "fix" the grammar by adding them back and re-opening the
prose-collision hole.

**E3.** No other finding row is edited and no row is deleted; the preamble edit
of § D4 is the only non-CER-130 change to the file. `git diff docs/cer/backlog.md`
shows exactly one row plus the preamble paragraph.

### F — tests

**F1.** `tests/pairmode/test_cer.py` gains a table-driven test class for
`is_resolution_marked` covering, as separate assertions, every row of the § A2
table: the four accepted marker shapes (bolded, plain title-case, parenthesised,
bracketed), both keywords, all three cases (upper, title, lower), the three
segment-start kinds (text start, punctuation+space, opener), and the seven
rejected shapes — `UNRESOLVED`, `unresolved`, `should be RESOLVED`,
`to be resolved`, `not resolved yet`, `**Not resolved**`,
`PARTIALLY RESOLVED` — plus the prose/code-quoting cases
(`` `RESOLVED` ``, `if "RESOLVED" not in stripped`, `_RESOLVED_RE`) and the
empty string.

**F2.** `tests/pairmode/test_next_action.py` gains a class for the guard under
the new grammar with at minimum:

- a title-case `Resolved cp-34 — …` row passes the guard — **the CER-130
  direction-1 regression test**, and it must be asserted to fail against the
  old substring expression (i.e. the test's docstring names the old expression
  and the row contains no uppercase `RESOLVED`);
- an `UNRESOLVED …` row **fails** the guard — the CER-130 direction-2
  regression test;
- a `… this should be RESOLVED before the tag` row fails the guard;
- a `**SUPERSEDED by CER-9**` row passes;
- a mixed section (one marked row, one unmarked row) fails — the guard is
  all-rows-must-be-marked, not any-row;
- the placeholder-exemption pair of § C2.

**F3.** The five existing `TestCheckCerDoNowEscapedPipe` cases
(`test_next_action.py:2324-2403`) are unchanged and green — including the
escaped-pipe resolved row, whose `**RESOLVED (INFRA-297)**` marker the new
grammar accepts. `test_checkpoint_routing.py` and
`test_harness004_isolation.py` are not edited and stay green.

**F4.** A parity test pins the new grammar against flex's own live
`docs/cer/backlog.md`: every non-placeholder `## Do Now` row is classified
identically by `is_resolution_marked` and by the old substring expression
(verified at spec time: 14 rows, zero divergence). The test reads the repo's own
backlog by path and skips cleanly if the file is absent, so it cannot fail in a
consuming checkout.

**F5.** Full suite green, run **once without `-x`** so a pre-existing failure
cannot mask a new one, against the `main` baseline plus this story's additions.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Build in order **A → B → C → D → E**, running the focused suites after A and
after B, then the full suite without `-x` at the end.

**A — grammar in `cer.py`, not in `next_action.py`.** Put
`is_resolution_marked` next to `is_placeholder_row`. This is not stylistic: the
placeholder rule was moved into `cer.py` by INFRA-294 precisely because two
independent readers of the same file had drifted, and the resolution rule has
exactly the same two-reader shape today (the guard reads it in code; the
docs-reviewer worker reads it in prose). `cer.py` is already the module that
owns backlog row semantics.

Realise § A2 as one compiled pattern with `re.IGNORECASE`. A working
formulation, validated at spec time against flex's own backlog and the full
§ A2 table:

```python
_RESOLUTION_MARKER_RE = re.compile(
    r"(?:^|\n|[.!?;:—–|)][ \t]+|[*(\[])"  # segment start
    r"[*(\[]*"                                       # optional emphasis/bracket openers
    r"(?:RESOLVED|SUPERSEDED)"                       # keyword
    r"(?![A-Za-z0-9_])",                             # close boundary
    re.IGNORECASE,
)
```

You are not required to use this exact pattern, but whatever you write must
satisfy every row of the § A2 table and the § F1 cases. Two traps if you
re-derive it: a `\b` word boundary before the keyword is **not** sufficient
(`should be RESOLVED` and `not resolved yet` both pass a `\b` test — a space is
a word boundary), and a fixed-width lookbehind cannot express
"punctuation followed by one or more spaces", so consume the boundary in the
match rather than looking behind it. Note also that `(?![A-Za-z0-9_])` rather
than `\b` is what keeps `_` out of the accepted trailing set, which is what
makes `__RESOLVED__` a non-marker per § A3 — do not "improve" it to `\b`
without re-reading § A3.

**B — one expression, nothing else.** The diff to
`next_action._check_cer_do_now` should be the import line, the membership-test
line, and the docstring. If you find yourself changing the split, the
`if c.strip()` filter, the header test, the section walk, or the fail-open
returns, stop: INFRA-297 owns those and their comments explain why they are
shaped as they are. Do not narrow the scanned text from the whole row line to
the finding cell — see § Out of scope R1.

**C — prove the exemption, don't just keep it.** § C2's second assertion (a
placeholder row does not satisfy `is_resolution_marked` on its own) is the one
that will catch a future reordering. Write it even though it looks redundant.

**D — write the grammar where a stranger will find it.** The consuming repo
that blocked had no way to learn what the guard wanted; the template preamble
(§ D3) is the fix for that, and it is the highest-value edit in this story.
Keep the template and flex's rendered copy identical in wording (§ D4). When
editing `docs/cer/backlog.md`, edit only the preamble paragraph and the CER-130
row — the file also contains rows owned by an unmerged branch.

**E — the annotation must pass its own guard.** After writing the CER-130
annotation, run the guard against the repo's own backlog and confirm the row's
classification is what you intend (CER-130 sits in Do Later, so the guard does
not scan it — assert against `is_resolution_marked(row_text)` directly instead).

## Tests

```bash
# Focused — the grammar predicate
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_cer.py -q

# Focused — the guard and its routing
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_next_action.py \
  tests/pairmode/test_checkpoint_routing.py \
  tests/pairmode/test_harness004_isolation.py \
  tests/pairmode/test_checkpoint_docs_worker.py -q

# Full suite — once, WITHOUT -x, so a pre-existing failure cannot mask a new one
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

**Acceptance:**

- Both focused runs green, including every case named in § F1 and § F2.
- The five existing `TestCheckCerDoNowEscapedPipe` cases green **unedited**.
- The § F4 parity test green: zero divergence on flex's own 14 Do Now rows.
- Full suite green against the `main` baseline plus this story's new tests. No
  new failures.
- A `test_observability_ui` failure is worktree-only (CER-090). Fix by
  `rsync`-ing the vendored payload from the main checkout; never `pnpm install`.
  State in the build report that it does not reproduce on a clean `main`
  checkout.

**New tests required** (names indicative):

- `test_bolded_upper_marker_is_recognised`
- `test_plain_title_case_marker_is_recognised`
- `test_lowercase_marker_is_recognised`
- `test_parenthesised_and_bracketed_markers_are_recognised`
- `test_superseded_keyword_is_recognised`
- `test_marker_at_cell_boundary_is_recognised`
- `test_unresolved_is_not_a_marker`
- `test_should_be_resolved_prose_is_not_a_marker`
- `test_negated_prose_is_not_a_marker`
- `test_partially_resolved_is_not_a_marker`
- `test_quoted_or_code_span_literal_is_not_a_marker`
- `test_underscore_identifier_is_not_a_marker`
- `test_empty_and_non_string_inputs_return_false`
- `test_cer_do_now_passes_on_title_case_resolved_row`
- `test_cer_do_now_fails_on_unresolved_row`
- `test_cer_do_now_fails_on_aspirational_resolution_prose`
- `test_cer_do_now_passes_on_superseded_row`
- `test_cer_do_now_fails_when_any_row_is_unmarked`
- `test_placeholder_row_exempted_before_resolution_test`
- `test_placeholder_row_is_not_itself_resolution_marked`
- `test_live_backlog_do_now_classification_parity`

## Out of scope

- **R1 — narrowing the scanned text from the whole row line to the finding
  cell. Rejected for this story, not deferred silently.** It is arguably more
  correct (a `Resolved` in a Source cell is not a resolution), but it is a
  second behavior change layered on the one CER-130 asks for, it depends on the
  index-shifted `cols` shape that INFRA-297's comment explicitly warns about,
  and there is no observed instance of harm. The guard's failure mode today is a
  grammar defect, not a scope defect. If a fleet backlog is ever found whose
  Source or Phase cell carries a false marker, that is a new row.
- **Adding `` ` ``, `"`, `'` or `_` to the accepted openers. Rejected**
  (§ A3). Each collides with prose that legitimately quotes the keyword —
  including CER-130's own row, which contains the literal
  `if "RESOLVED" not in stripped` — and admitting them re-opens direction 2 in
  the exact place this story closes it.
- **A lowercase-only fix (`stripped.upper()` or `.lower()` before the
  membership test). Rejected** (§ Context, § E2). It repairs direction 1 and
  *widens* direction 2: `unresolved`, `should be resolved` and
  `to be resolved` all begin matching. Case-insensitivity without anchoring is
  a net regression.
- **Extending the keyword set** (`OBSOLETE`, `REJECTED`, `AMENDED`,
  `BACKLOG-RETAIN` — the wider set a cold-eyes planning document once used
  ad hoc). Rejected here: the guard's question is "may this checkpoint
  proceed", and only closure and supersession answer it. Widening the set is a
  policy change about what closes a Do Now row, which belongs in its own row
  with an operator decision, not inside a defect fix.
- **Treating a partial-resolution note as resolved.** Rejected (§ A2 table).
  BUILD-006's partial-resolution notes are progress records, not closures; a
  partially-resolved Do Now row must keep blocking.
- **Writing resolution markers programmatically** (a `cer.py resolve`
  subcommand that appends a correctly-formed marker to a row). Genuinely
  attractive — it would make the grammar unforgeable rather than merely
  documented — but it is a new CLI surface with its own row-rewriting hazards,
  and it is not needed to close CER-130. Named here as future work rather than
  half-built.
- **Editing `check_checkpoint_guards`, the guard order, or the
  `"cer-do-now"` failure string** (§ B3). No routing or grammar change at the
  resolver level; `SCHEMA_VERSION` is not bumped.
- **Editing `cer.is_placeholder_row`** (§ C1) or the `is_placeholder_row`
  call in `cer._parse_entries_from_backlog` (`cer.py:124`).
- **Editing `docs/patterns/operations-orchestration/cer-backlog-living-phases.md`**
  (§ D5) — an external-audience pattern doc, not a guard contract.
- **Backlog rows CER-105, CER-106 and CER-113, and
  `docs/stories/INFRA/INFRA-299.md`** — owned by the unmerged INFRA-299 branch.
- **Retro-fixing consuming repos' backlogs.** The grammar now accepts their
  existing title-case convention, so no fleet edit is required. A fleet sweep
  for genuinely mis-marked rows (direction 2 false passes that already slipped
  through a checkpoint) is not part of this story.
