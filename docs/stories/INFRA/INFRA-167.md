---
id: INFRA-167
rail: INFRA
title: "TypeScript parser robustness — phaseIndex blank-line, MODULE_FILENAME_RE, era leading zeros, flex_factor NaN"
status: backlog
phase: "64"
story_class: code
primary_files:
  - skills/observability/api/src/parsers/phaseIndex.ts
  - skills/observability/api/src/parsers/lessons.ts
  - skills/observability/api/src/parsers/phaseDoc.ts
  - skills/observability/api/src/parsers/storyFrontmatter.ts
touches:
  - tests/pairmode/test_observability_context_api.py
  - tests/pairmode/test_observability_ui.py
---

# INFRA-167 — TypeScript parser robustness

## Context

Four parser bugs from the Phase 63 cold-eyes review (findings 10, 13, 14, 15).
INFRA-166 depends on the `storyFrontmatter.ts` fix in this story.

1. **`phaseIndex.ts:110` blank line terminates parsing.** A blank line between
   table rows triggers `break`, so every phase after the first blank divider
   is silently dropped from the SPA's phase list.

2. **`lessons.ts:57` MODULE_FILENAME_RE too strict.** The regex
   `/^[a-z_]+\.py$/` rejects Python files with digits (`phase63.py`),
   uppercase (`Audit.py`), or path prefixes (`scripts/audit.py`), silently
   under-reporting D6 promotion candidates.

3. **`phaseDoc.ts:48` era leading zeros lost.** Unquoted YAML `era: 002`
   parses to JS number 2; `String(2)` yields `"2"`, not `"002"`. Phase docs
   authored without quotes around the era ID silently break era grouping.

4. **`storyFrontmatter.ts:61` flex_factor admits NaN and rejects string
   values silently.** `typeof NaN === 'number'` passes the guard and NaN
   propagates; a quoted `flex_factor: '1.5'` silently degrades to 1.0.

## Ensures

### `skills/observability/api/src/parsers/phaseIndex.ts`

1. Replace the `break` for non-pipe lines with conditional logic:
   ```typescript
   if (!trimmed.startsWith('|')) {
     if (trimmed === '') continue;   // blank/whitespace-only — skip
     break;                          // non-pipe non-blank (heading etc.) — stop
   }
   ```
   This preserves termination on `## ` headings while skipping blank
   divider rows that authors insert between phase groups.

### `skills/observability/api/src/parsers/lessons.ts`

2. Broaden the module filename regex to allow digits, uppercase, and a single
   path-prefix segment:
   ```typescript
   const MODULE_FILENAME_RE = /^(?:[a-zA-Z0-9_]+\/)?[a-zA-Z0-9_]+\.py$/;
   ```
   This matches: `audit.py`, `phase63.py`, `Audit.py`, `scripts/audit.py`.
   It still rejects: `.py`, `../escape.py`, empty string, non-`.py` extensions.

### `skills/observability/api/src/parsers/phaseDoc.ts`

3. After `String(eraVal)`, if the original YAML value was a number (i.e.,
   `typeof eraVal === 'number'`), pad it to 3 digits:
   ```typescript
   const era: string | null =
     eraVal == null
       ? null
       : typeof eraVal === 'number'
         ? String(eraVal).padStart(3, '0')
         : String(eraVal);
   ```
   Quoted YAML values (`era: "002"`) are already strings and pass through
   `String(eraVal)` unchanged.

### `skills/observability/api/src/parsers/storyFrontmatter.ts`

4. Replace the `flex_factor` type guard with a NaN-safe, string-tolerant
   version:
   ```typescript
   let flex_factor = 1.0;
   const ffRaw = fm['flex_factor'];
   if (typeof ffRaw === 'number' && !Number.isNaN(ffRaw)) {
     flex_factor = ffRaw;
   } else if (typeof ffRaw === 'string') {
     const parsed = parseFloat(ffRaw);
     if (!Number.isNaN(parsed)) flex_factor = parsed;
   }
   // values <= 0 or > 5 are intentionally NOT clamped here;
   // context_budget.decide() applies the clamp at consumption time.
   ```

### Tests

5. New test cases in `test_observability_ui.py` or a new
   `tests/pairmode/test_observability_parsers.py` (whichever the builder
   judges more appropriate given existing test layout):

   - **`test_phase_index_blank_line_between_rows`** — write an `index.md`
     with a blank line between two phase rows. Assert both phases appear in
     the parsed result.

   - **`test_phase_index_stops_at_heading`** — write an `index.md` with a
     `## ` heading after some rows. Assert phases before the heading are
     parsed and phases after are not (correct termination).

   - **`test_module_filename_re_allows_digits_and_uppercase`** — call the
     promotion filter with a lesson whose `affects` contains `['phase63.py']`
     and `['Audit.py']`. Assert both are `promotion_candidate: true`.

   - **`test_era_unquoted_integer_padded`** — write a phase doc with
     frontmatter `era: 2` (no quotes). Assert the parsed phase has
     `era: "002"`.

   - **`test_flex_factor_string_parsed`** — write a story frontmatter with
     `flex_factor: '1.5'` (quoted). Assert parsed `flex_factor` is `1.5`.

   - **`test_flex_factor_nan_defaults_to_1`** — passing `flex_factor: .nan`
     (YAML NaN literal) through the parser. In the test fixture, set the
     raw value via a synthetic fm dict where `flex_factor` is `float('nan')`
     coerced through js-yaml. Assert parsed value defaults to `1.0`.
     (If YAML `.nan` can be reproduced in the test corpus, use that; otherwise
     test via a unit test of the TypeScript function called with a NaN argument.)

6. All existing tests in `test_observability_ui.py` and
   `test_observability_context_api.py` continue to pass.

## Instructions

- `phaseIndex.ts`: the `continue`/`break` split is the only change. Do not
  alter the header-row skip logic or the column-split code.
- `lessons.ts`: the regex change is the only change to the promotion filter.
  Update the `MODULE_FILENAME_RE` constant; do not restructure
  `applyPromotionFilter`.
- `phaseDoc.ts`: the era-padding change is one ternary; do not alter the
  frontmatter slice logic or the stories-table parsing.
- `storyFrontmatter.ts`: the `flex_factor` block is the only change. The
  clamping responsibility stays in `context_budget.py`; this parser only
  converts and validates the raw YAML type.
- Parser tests are pure unit tests (no Fastify server needed). Use the
  existing `subprocess`-based test helpers if the tests call the TypeScript
  build, or write direct Python tests that invoke the compiled JS parsers
  via `node -e` snippets if that is the established pattern in the test
  suite. Use whichever approach the existing tests in
  `test_observability_context_api.py` use.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q -k "parser or observability"
```

All tests must pass.

## Out of scope

- Fixing the `phaseDoc.ts` stories-table column-order assumption (a
  separate hardening concern; not in the 15 findings).
- CRLF era-value corruption (a separate edge case; also not in the 15 findings).
- Clamping `flex_factor` in the parser — that responsibility stays in Python.
