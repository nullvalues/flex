---
id: INFRA-413
rail: INFRA
title: Extend oracle-based round-trip fix to title/source frontmatter scalars (CER-219)
status: draft
phase: "143"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/story_new.py
touches:
  - tests/pairmode/test_story_new.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

INFRA-412 (Phase 142) replaced `_yaml_block_scalar`'s hand-maintained
denylist with an oracle-based renderer: it renders each candidate form of a
`primary_files:`/`touches:` list-item value (bare, `"`-quoted, `'`-quoted)
and only emits the one whose parsed-back result — via
`_reads_back_intact` (`skills/pairmode/scripts/story_new.py:35-48`), which
embeds the candidate in a minimal multi-key document with a *trailing*
sentinel key and asserts the entire parsed document, not just the item,
matches — is byte-identical to the original (`_yaml_block_scalar`,
`story_new.py:51-140`).

That fix was scoped to the block-sequence item renderer only.
`_story_frontmatter` (`story_new.py:180-261`) still renders two sibling
free-text scalars by hand:

- `title:` (`story_new.py:201-207`) — quoted only when `re.search(r"(?:^|\s)#",
  title)` matches (the retired CER-092 check), bare otherwise.
- `source:` (`story_new.py:219-220`) — always emitted bare, never quoted,
  regardless of content.

Both reproduce the exact CER-216 truncation shape the oracle was built to
close: a title or source value ending in `---` (or containing an
unescaped, reader-significant character) silently truncates the rest of the
frontmatter block — `status:`, `phase:`, `primary_files:`, `touches:` all
silently drop — not just the scalar itself. Separately, the same CER-219
audit found `title:`/`source:` values that begin with `[` (e.g. `--title
'[WIP] fix thing'`) hit `schema_validator._parse_frontmatter`'s
`_parse_flow_sequence` (`schema_validator.py:80-135`) on read and raise
`FrontmatterError` for every consumer, and a bracketed value containing a
comma (e.g. `[abc, def] thing`) is silently type-confused into a list
instead of staying a string. Phase 143's Goal names both of these bracket
shapes as in scope for this story, alongside the primary title/source
oracle extension — that scope question is already settled at the phase
level, not left to this spec.

**Lesson carried forward from INFRA-412 (state explicitly, do not let a
third repeat happen quietly):** INFRA-412 needed three build attempts
because each attempt discovered that some pre-existing pinned test's
expected output (quoted vs. bare, or raises vs. succeeds) was an artifact
of the *retired* denylist algorithm, not a genuine round-trip requirement
of the real reader. The correct process, and the one that eventually
worked, was: the **builder stops and reports** the specific conflict
(names the test, the old expectation, and what the oracle proves is
actually correct) rather than deciding unilaterally which one wins, and
the **spec is amended by the orchestrator** to explicitly name the
exception before the next attempt (see INFRA-412 Ensures 7's four named
exceptions, and its note that a third attempt "must not add any further
exceptions on its own authority, even with a correct live-verified
justification"). If this story's builder finds a similar case — an
existing `title:`/`source:` test whose quoted/bare or raises/succeeds
expectation the oracle proves should actually be the opposite — it must
stop, make no code change to resolve the conflict, file a CER row in
`docs/cer/backlog.md` documenting the specific conflict, and report it
rather than self-resolving.

## Requires

- INFRA-412 complete (`_reads_back_intact`/`_yaml_block_scalar` at their
  current oracle-based state, `story_new.py:35-140`) — this story extends
  the same design, it does not re-derive it.

## Ensures

1. `_story_frontmatter`'s `title:` line (currently `story_new.py:201-207`,
   the `re.search(r"(?:^|\s)#", title)` check) is rendered through a
   scalar-position oracle renderer that follows the same design as
   `_yaml_block_scalar`: render each candidate (bare, `"`-quoted,
   `'`-quoted, same eligibility rules and same bare > `"` > `'` preference
   order as `_yaml_block_scalar`), verify each candidate by embedding it
   directly as a top-level scalar (e.g. `title: <rendered>`) in a minimal
   multi-key document with a trailing sentinel key, parsing it with
   `schema_validator._parse_frontmatter`, and requiring the entire parsed
   document — not just the recovered value — to match expectation. Only a
   round-tripping candidate is ever emitted.
2. `_story_frontmatter`'s `source:` line (currently `story_new.py:219-220`,
   unconditional `f"source: {source}"`) is rendered through the same
   scalar-position oracle renderer as Ensures 1 — no longer emitted bare
   unconditionally.
3. The renderer used for Ensures 1/2 may be a new sibling function to
   `_yaml_block_scalar` (a scalar-position analogue of both
   `_yaml_block_scalar` and `_reads_back_intact`) or a shared refactor of
   the existing pair parameterized by embedding shape — builder's choice —
   but there must be exactly one oracle-verification code path used by
   both `title:` and `source:` rendering; no second hand-rolled
   quoting rule is introduced for either field.
4. Existing pinned behavior for the whitespace-preceded-`#` case is
   preserved: `TestTitleHashQuoting.test_title_with_hash_is_quoted` and
   `.test_title_without_hash_is_unquoted`
   (`tests/pairmode/test_story_new.py:1034-1044`) pass unmodified.
5. RESOLVED per CER-220 (option b, orchestrator-sanctioned — build attempt 1
   empirically proved option (a), fixing this by touching
   `schema_validator._parse_frontmatter`'s scalar branch, is out of scope for
   this story and carries broader blast radius than a narrowly-scoped writer
   fix should): a title or source value beginning with `[` (e.g. `[WIP] fix
   thing`) is **not** required to round-trip. Instead, `_story_frontmatter`
   raises `ValueError` naming the unrepresentable value for *any* title/source
   candidate that does not round-trip through the real reader — which a
   bracket-prefixed value never does, for either of `_parse_frontmatter`'s two
   failure shapes (`FrontmatterError`, or silent type-confusion into a list).
   This folds into the general oracle-verify-or-raise design (Ensures 7) as
   simply one more case that always fails the oracle check and therefore
   always raises — no special-casing of `[` is needed in the writer itself.
   Forbidden proxy: catching/suppressing the reader's own `FrontmatterError`
   or silently falling back to some other rendering instead of raising.
6. A bracketed value containing a comma (e.g. `[abc, def] thing`) as a title
   or source likewise raises `ValueError` via the same oracle-verify-or-raise
   path (Ensures 7) — not silently parsed as a list
   (`_parse_flow_sequence`'s type-confusion shape). Same resolution as
   Ensures 5: this is a case the oracle check correctly detects as
   unrepresentable and rejects, not a case requiring special-cased handling.
7. When no candidate rendering round-trips for a title or source value
   (embedded real newline, or the value contains both `"` and `'`),
   `_story_frontmatter` raises `ValueError` naming the unrepresentable
   value — the same failure mode `_yaml_block_scalar` already uses for
   `primary_files:`/`touches:` entries (no silent corruption).
8. A title or source with no special characters (e.g. `"Plain title"`,
   `"myproject"`) still emits bare — this story does not overcorrect into
   quoting values that were always safe.
9. `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` exits 0.

## Instructions

1. Read `_reads_back_intact`/`_yaml_block_scalar`
   (`skills/pairmode/scripts/story_new.py:35-140`) as the reference design
   before writing any new code — do not re-derive the oracle approach from
   scratch.
2. Add a scalar-position oracle-verification path (new sibling function(s),
   or a parameterized refactor of the existing pair — builder's choice per
   Ensures 3) and route both the `title:` line (replacing the
   `story_new.py:204-207` regex branch) and the `source:` line (replacing
   `story_new.py:219-220`'s unconditional bare append) through it.
3. `_yaml_block_scalar`'s docstring currently states (around
   `story_new.py:110-112`) that it "Does not touch the CER-092
   title-quoting branch above; that branch's `#`-detection rule is for a
   top-level scalar (`title:`), not a block-sequence list item, and is left
   as-is." That branch no longer exists in its old hand-rolled form after
   this story — update or remove this note so it does not go stale and
   mislead the next reader.
4. Add tests to `tests/pairmode/test_story_new.py` covering: a
   bracket-prefixed title and a bracket-prefixed source (Ensures 5), a
   comma-containing bracketed title (Ensures 6), an unrepresentable
   title/source raising `ValueError` (Ensures 7), and a plain
   title/source still emitting bare (Ensures 8). Do not delete or weaken
   any existing test, including `TestTitleHashQuoting` and the `--source`
   tests already in the file.
5. **Stop-and-report, not self-resolve (see Context's lesson):** if
   implementing this story surfaces a pre-existing pinned test whose
   quoted/bare or raises/succeeds expectation for `title:`/`source:`
   conflicts with what the oracle proves is actually correct, stop, make
   no code change to resolve that specific conflict, file a CER row in
   `docs/cer/backlog.md` naming the test, its current expectation, and
   what the oracle proves, and report the conflict in the build result —
   exactly as INFRA-412's first attempt did, and exactly what a later
   attempt should not skip by deciding unilaterally.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_story_new.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```
Acceptance: both green, including the pinned `TestTitleHashQuoting` cases
(Ensures 4) and the new bracket/comma/unrepresentable/plain-value cases
(Ensures 5-8).

## Out of scope

- Changing `schema_validator._parse_frontmatter` itself — same reasoning as
  INFRA-412's Out of scope: this story treats the reader as the fixed
  oracle and adapts the writer to it, not the reverse.
- Any scalar-position frontmatter field other than `title:`/`source:`
  (e.g. `phase:`, `status:`, `story_class:`) — those are constrained/enum
  values already validated elsewhere in `story_new.py`, not free-text
  operator input, and are not part of the CER-219 audit this story closes.
  A future gap found there is a separate CER.
- Any other file's own title/source-shaped frontmatter rendering outside
  `story_new.py` (e.g. `phase_new.py`, if it has a similar hand-rolled
  scalar renderer) — this story's `primary_files:`/`touches:` scope is
  `story_new.py` only; a similar gap elsewhere is a separate story.
