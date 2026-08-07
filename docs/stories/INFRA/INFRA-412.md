---
id: INFRA-412
rail: INFRA
title: Durable oracle-based fix for story_new.py frontmatter round-trip (CER-214/215/216)
status: draft
phase: "142"
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

`skills/pairmode/scripts/story_new.py`'s `_yaml_block_scalar` decides how a
`primary_files:`/`touches:` list-item value is rendered into frontmatter YAML.
It has been patched three times against a real reader
(`schema_validator._parse_frontmatter`) whose actual parsing rules it never
directly consulted — each patch fixed exactly what a security audit found and
left a new gap in the same function: CER-167 (initial denylist), CER-211 (`'
#'` comment-introducer anywhere, not just leading), CER-213
(`json.dumps`-based escaping replaced with literal quote-wrapping, because the
reader strips one matching quote pair literally and never unescapes), and most
recently CER-214 (a `str.splitlines()`-boundary character, e.g. `\r`, used as
a block-sequence-item injection primitive — CRITICAL), CER-215 (an
incomplete Unicode-whitespace-before-`#` check), and CER-216 (a bare
`---`-suffix value that truncates the entire frontmatter block, silently
dropping every later key — CRITICAL). Each fix corrected the character set
the denylist checked; none of them changed the fact that the denylist is a
hand-maintained approximation of the reader's actual behaviour, so it can
always drift out of sync with the reader again the next time the reader
changes or an audit finds one more character the writer's author did not
think of.

**Why oracle-based, not another denylist.** The durable fix is to stop
approximating the reader and instead ask it directly: render each candidate
form of the value, feed it back through the real reader
(`schema_validator._parse_frontmatter`), and only emit a candidate whose
parsed-back value is byte-identical to the original. This makes the writer's
correctness structurally tied to the reader's actual behaviour — it cannot
drift out of sync the way a hand-maintained character list can, because the
check *is* the reader, not a description of it. A future builder tempted to
"just add the missing character to the denylist" when a new gap is found
would be reintroducing exactly the failure mode this story closes; the fix
belongs in strengthening the oracle round-trip (e.g. widening the sentinel
document used to detect truncation), never in resuming the denylist.

The oracle must also detect frontmatter-*truncation*, not just item-level
corruption (CER-216): a naive round-trip check that only re-parses a single
list item can miss a value that truncates the whole document once a
`sentinel:`-style key follows it. The candidate check therefore embeds the
rendered value inside a minimal multi-key frontmatter document with a
trailing sentinel key and asserts the *entire* parsed document — not just the
recovered value — matches expectation.

## Requires

- `skills/pairmode/scripts/story_new.py` at its current state (CER-213 fix
  already landed: `_yaml_block_scalar` returns bare/double-quoted/single-quoted
  values or raises, no `json.dumps` escaping).
- `schema_validator._parse_frontmatter` (already present in
  `skills/pairmode/scripts/schema_validator.py`) is importable from
  `story_new.py` — `story_new.py` already imports from `schema_validator`
  elsewhere in the file (see the existing `from schema_validator import
  validate_story_file as _vsf` local import), so a similar local or
  module-level import of `_parse_frontmatter` is precedented and not a new
  architectural dependency.

## Ensures

1. `_yaml_block_scalar` no longer contains or consults
   `_YAML_PLAIN_UNSAFE_START` (or any other hand-maintained denylist of
   unsafe characters/prefixes) to decide whether a value is safe to emit
   bare, quoted with `"`, or quoted with `'` — the decision is made solely by
   round-tripping each candidate rendering through
   `schema_validator._parse_frontmatter` and comparing the parsed result to
   the original value. Forbidden proxy: a denylist that has merely been
   renamed, moved, or wrapped in a helper function while still being
   consulted ahead of (or instead of) the round-trip check.
2. For every value that has at least one candidate rendering (bare,
   double-quoted, or single-quoted — restricted to only the quote characters
   not already present in the value, exactly as today) that round-trips
   byte-identically through the oracle described in Ensures 3,
   `_yaml_block_scalar` returns that candidate. When more than one candidate
   round-trips, bare is preferred over quoted, and `"`-quoted is preferred
   over `'`-quoted (preserving today's observable preference order — Ensures
   1 of INFRA-409/CER-213's own test suite already pins the bare-preferred
   case and must keep passing unmodified).
3. The round-trip oracle embeds the candidate rendering inside a minimal
   frontmatter document containing a preceding differently-typed key and a
   *trailing* sentinel key (e.g. `title: t\nk:\n  - <rendered>\nsentinel:
   end\n`), parses it with `schema_validator._parse_frontmatter`, and
   requires the *entire* parsed document to equal the expected dict (not just
   the recovered list item) — so a rendering that truncates the frontmatter
   block and silently drops the sentinel key (CER-216's failure shape) is
   rejected exactly like a rendering that corrupts the item itself.
4. When no candidate rendering round-trips (including the case where the
   value contains both `"` and `'`, so neither quote form is attemptable),
   `_yaml_block_scalar` raises `ValueError` naming the unrepresentable value,
   exactly as today — this story changes *how* unrepresentability is
   detected, not the fact that it still raises rather than silently
   corrupting.
5. A real embedded newline (`\n`) in the value still raises `ValueError`
   before or via the oracle check — never emitted as a literal line break.
   (The oracle path covers this case naturally: no candidate rendering of a
   multi-line value round-trips through a line-based reader; an explicit
   pre-check remains acceptable as a short-circuit but is not required.)
6. `_yaml_block_scalar` never strips, rejects-then-alters, or otherwise
   changes *value* itself in any case it emits — only the on-disk
   representation changes (INFRA-409 Ensures 1's forbidden proxy, preserved
   unmodified by this story).
7. All pre-existing tests in `TestYamlBlockScalarQuoting` (CER-167/CER-211/CER-213
   cases already in `tests/pairmode/test_story_new.py`) pass against the new
   implementation, WITH EXACTLY FOUR NAMED EXCEPTIONS whose *expected output*
   (not their round-trip correctness) must be corrected, not weakened:
   - `test_value_with_colon_space_is_quoted_and_round_trips` (value
     `"docs/notes: a file with a colon.md"`) → rename to
     `test_value_with_colon_space_round_trips_bare`, assert bare.
   - `test_value_with_leading_quote_is_quoted_and_round_trips` (value
     `'"quoted-looking-path.py'`) → rename to
     `test_value_with_leading_quote_round_trips_bare`, assert bare.
   - `test_value_with_both_quote_characters_raises` (value
     `"note: it's a \"quoted\" thing"`) → rename to
     `test_value_with_both_quote_characters_round_trips_bare`, assert bare
     instead of `raises(ValueError)`. Preserve Ensures 4's "both quote
     characters present, unrepresentable" coverage by adding a *new* test
     with a genuinely-unrepresentable value that also contains whitespace
     making it non-bare-eligible (e.g. `' \'quoted\' and "double" '`) —
     confirmed live to still raise under the new implementation.
   - `test_primary_files_entry_with_colon_round_trips_through_frontmatter`
     (value `"docs/weird: path.py"`) → update its assertion from
     `item == f'"{value}"'` to `item == value` (bare), keeping the rest of
     the integration round-trip check unchanged.
   All four values were independently verified (build attempt 2's Evidence
   section, and independently re-verified live by the reviewer against
   attempt 2) to have no leading/trailing whitespace and no real newline, so
   under the oracle-only design (Ensures 1-2) they are legitimately
   representable bare, and bare *does* round-trip byte-identically for all
   four through the real reader. Their prior "must be quoted"/"must raise"
   expectations were artifacts of the old denylist (CER-213's `": " not in
   value` / leading-quote-character / both-quote-character checks), which
   was simply more conservative than the reader actually requires — not a
   genuine round-trip requirement. This four-item list is now the complete
   and final set of sanctioned exceptions (found across build attempts 1 and
   2, both of which correctly stopped/flagged rather than silently
   self-authorizing — attempt 1 filed CER-217, attempt 2's extra two were
   caught by review and required this spec amendment rather than being
   accepted via the builder's own Evidence-section justification). A THIRD
   build attempt must not add any further exceptions on its own authority,
   even with a correct live-verified justification — any additional
   conflict of this class must stop and report, not self-resolve, exactly as
   Ensures 7 already required and as the reviewer correctly enforced. Every
   other pre-existing test in the class is unaffected and must keep passing
   exactly as before.
8. New regression tests exist covering, at minimum and by name: CER-214
   (`"x\r  - hooks/pre_tool_use.py"` — asserting the round-tripped parse has
   exactly one list item, not two, i.e. no injected sibling item), CER-215
   (`"foo\xa0#bar.py"` — a Unicode-whitespace character other than ASCII
   space preceding `#`), and CER-216 (`"foo---"` and `'foo"---'` — a value
   ending in `---` that must not truncate a following frontmatter key).
9. A test suite exists that derives its adversarial character set
   programmatically — via `str.splitlines()` boundary detection (`[chr(c) for
   c in range(N) if len(f"a{chr(c)}b".splitlines()) > 1]`) and `re.search(r"\s",
   ...)` Unicode-whitespace detection — rather than a hand-picked list, and
   asserts every character in both sets, in at least the embeddings named in
   Instructions 4, either causes `_yaml_block_scalar` to raise `ValueError`
   or round-trips exactly (full-document oracle, per Ensures 3) with no
   truncation and no key loss. Forbidden proxy: a test suite whose character
   set is still hand-listed (even if long) rather than derived from the
   stdlib functions that actually define line-boundary/whitespace semantics.
10. At least one test confirms an ordinary plain path (e.g.
    `"skills/pairmode/scripts/story_new.py"`) still emits bare — i.e. this
    story does not overcorrect into quoting or raising for values that were
    always safe.
11. At least one test each confirms the previously-fixed representable cases
    still emit (not raise): a value with an embedded real tab (quoted, not
    bare), a value containing `'` alone (double-quoted), a value containing
    `"` alone (single-quoted), and a value with an embedded `" #"` (quoted).
12. `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` exits 0.

## Instructions

1. In `skills/pairmode/scripts/story_new.py`, add a local (or module-level)
   import of `_parse_frontmatter` from `schema_validator`, matching the
   existing local-import precedent already in this file
   (`from schema_validator import validate_story_file as _vsf`).
2. Replace the body of `_yaml_block_scalar` with an oracle-based
   implementation along these lines (adapt as needed, but preserve the
   observable behaviour in Ensures 1-6):
   ```python
   def _reads_back_intact(value: str, rendered: str) -> bool:
       doc = f"---\ntitle: t\nk:\n  - {rendered}\nsentinel: end\n---\n"
       try:
           parsed = _parse_frontmatter(doc)
       except Exception:
           return False
       return parsed == {"title": "t", "k": [value], "sentinel": "end"}

   def _yaml_block_scalar(value: str) -> str:
       candidates = []
       # Bare is only attempted when the value has no leading/trailing
       # whitespace and no embedded real newline — those are structurally
       # unrepresentable as a single plain scalar line regardless of what
       # the oracle says. Everything else about "is this safe bare" is
       # decided by the round-trip below, not by a denylist.
       if value and value == value.strip() and "\n" not in value:
           candidates.append(value)
       if '"' not in value:
           candidates.append(f'"{value}"')
       if "'" not in value:
           candidates.append(f"'{value}'")
       for rendered in candidates:
           if _reads_back_intact(value, rendered):
               return rendered
       raise ValueError(
           f"value cannot round-trip through schema_validator._parse_frontmatter "
           f"as a single block-sequence list item: {value!r}"
       )
   ```
   This is a sketch to establish intent, not a literal patch — adapt as
   needed, but preserve the observable behaviour in Ensures 1-6 and the
   candidate preference order in Ensures 2 (bare, then `"`, then `'`). Do
   not reintroduce `_YAML_PLAIN_UNSAFE_START` or any equivalent
   hand-maintained character list as a gate ahead of the oracle check —
   the oracle round-trip is the sole safety decision (Ensures 1).
3. Delete `_YAML_PLAIN_UNSAFE_START` entirely once nothing references it, and
   update this function's docstring to describe the oracle-based approach
   (referencing CER-214/215/216 and explaining, briefly, why it replaces a
   denylist — this becomes the on-disk record a future maintainer reads
   before considering another narrow patch).
4. In `tests/pairmode/test_story_new.py`'s `TestYamlBlockScalarQuoting`
   class (leave existing tests in place — do not delete or weaken any of
   them):
   - Add a reusable helper, e.g. `assert_roundtrip_or_raises(value)`, that
     calls `_yaml_block_scalar(value)` inside a `try/except ValueError`, and
     on success asserts the emitted rendering round-trips exactly through
     the same full-document oracle shape used in Ensures 3 (build a
     `title:`/`k:`/`sentinel:` document, parse it, and assert the parsed
     dict equals `{"title": "t", "k": [value], "sentinel": "end"}`).
   - Add a test that derives `LINE_BOUNDARY_CHARS` via `str.splitlines()`
     detection and `REGEX_WS_CHARS` via `re.search(r"\s", ...)` detection
     (as in Ensures 9), and for each character in the union of both sets,
     exercises `assert_roundtrip_or_raises` in at least these embeddings:
     the character alone as the whole value, the character embedded
     mid-value (e.g. `f"foo{ch}bar.py"`), at the start of the value, at the
     end of the value, immediately before a `#` (e.g. `f"foo{ch}#bar.py"`),
     and immediately before `---` (e.g. `f"foo{ch}---"`).
     If a full `0x110000`-codepoint sweep in every embedding is too slow for
     the normal test run, bound the sweep (e.g. to the first `0x3200`
     codepoints) and mark the test accordingly (e.g. `@pytest.mark.slow` or
     equivalent, or split into a fast bounded default and a separately
     invoked full sweep) — but the chosen bound and the reason it is
     sufficient (e.g. "covers all ASCII, Latin-1, and the common
     whitespace/separator blocks; codepoints beyond this are astral-plane
     and don't add new line-boundary/whitespace categories relevant to this
     reader") must be stated in a code comment next to the bound, not
     silently narrowed without explanation.
   - Add three named regression tests for CER-214, CER-215, and CER-216 per
     Ensures 8, each asserting the specific failure shape described (e.g.
     for CER-214, parse the full document and assert
     `len(parsed["k"]) == 1`, not just that the value round-trips).
   - Add the anti-overcorrection tests from Ensures 10 and 11.
5. Run the full test command in `## Tests` and confirm green before
   returning.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_story_new.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```
Acceptance: both green, including all pre-existing `TestYamlBlockScalarQuoting`
cases (Ensures 7), the new programmatically-derived sweep (Ensures 9), the
three named CER-214/215/216 regressions (Ensures 8), and the
anti-overcorrection cases (Ensures 10/11).

## Out of scope

- Changing `schema_validator._parse_frontmatter` itself — this story treats
  the reader as the fixed oracle and adapts the writer to it, not the
  reverse. Any future reader change is a separate story, and this story's
  own design (Context) is what keeps the writer from drifting out of sync
  when that happens.
- The `title:` line's own CER-092 comment-quoting branch in
  `_story_frontmatter` (the whitespace-`#` check for the top-level `title:`
  scalar) — explicitly left as-is per the existing docstring note; it is a
  different scalar-emission path (top-level, not block-sequence) and not
  touched by this story.
- Any other frontmatter field's writer/reader behaviour outside
  `primary_files:`/`touches:` block-sequence items.
- Widening the codepoint sweep beyond the justified bound "just to be safe"
  without updating the comment explaining the bound — if the bound needs to
  change, that is a deliberate edit to the justification, not a silent
  widening.

**Proportionality note (INFRA-357):** this spec runs longer than the project's
~14-36 line baseline; the length is deliberate, not inflation — it transcribes
a prior dedicated investigation's already-decided design (oracle sketch,
regression-test derivation strategy, and three named historical regressions)
so a fresh-context builder implements exactly that design rather than
re-deriving it and risking another narrow patch, which is the specific
failure mode (CER-167/211/213/214/215/216) this phase exists to close.

**Preflight note:** `hooks/pre_tool_use.py` appears in Ensures 8 only as a
literal adversarial test-value string (`"x\r  - hooks/pre_tool_use.py"`,
CER-214's original repro), not as a real code dependency of this story;
spec-preflight's `scope:` finding on that path is expected and intentional —
no `touches:` entry is warranted for a string literal used as test data.
