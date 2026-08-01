---
id: INFRA-337
rail: INFRA
title: Fix JSON-verdict parser: parse_worker_outcome must handle braces inside BUILD-RESULT/REVIEW-RESULT string fields
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/subagent_transcript.py
touches:
  - tests/pairmode/test_subagent_transcript.py
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

HIGH finding F6 of `docs/build-loop-cold-eyes-review-20260801.md`, corroborated independently at
the identical line by both reviewers: `subagent_transcript.py`'s `parse_worker_outcome` extracts a
candidate JSON object with the non-nesting regex `\{[^{}]*\}`. A BUILD-RESULT/REVIEW-RESULT whose
`reason`/`findings`/`fail_cause` string field quotes a code snippet containing a literal `{...}`
(routine reviewer prose in this codebase — e.g. "the guard `if (x) { revert() }` is unreachable")
fails to match as a single balanced object; only an unparseable inner fragment matches. The whole
outcome then stays `None` — no effort outcome, no FAIL bump, no escalation — directly feeding
INFRA-336's F1 symptom. Reconcile re-runs the same parser on retry, so a once-malformed row never
self-heals.

Fix direction: replace the regex with a proper balanced-brace scan (or attempt sequential
`json.JSONDecoder.raw_decode` calls starting at each `{` in the text) so nested/quoted braces inside
string values don't truncate the match.

## Requires

(none — this story has no prerequisite story or system-state condition;
per the phase-117 Ordering section it may build any time, independent of
INFRA-336.)

## Ensures

1. **The non-nesting regex is gone.** `skills/pairmode/scripts/subagent_transcript.py`'s
   `parse_worker_outcome` no longer matches candidate JSON objects with
   `re.finditer(r"\{[^{}]*\}", text, re.DOTALL)` (the exact pattern at the
   current `subagent_transcript.py:501`). Forbidden proxy: leaving the
   regex in place and only widening the character class (e.g. adding one
   more nesting level with a hand-rolled alternation) — that still fails on
   arbitrarily-nested or repeated `{...}` inside a string field; the fix
   must not depend on a fixed nesting depth.
2. **Candidate objects are found via a balanced scan, not a fixed-depth
   pattern.** The replacement locates each candidate JSON object either by
   a brace-depth counting scan that correctly treats braces inside JSON
   string literals (respecting `"..."` quoting and `\"` escapes) as
   non-structural, or by calling `json.JSONDecoder().raw_decode(text, idx)`
   at each successive `{` position and advancing past a successful parse
   (both approaches are acceptable; pick one and do not mix them). Either
   way, the same object-shape and `type`/`outcome`/`verdict`/`fail_cause`
   handling already present in `parse_worker_outcome` (RECOGNISED_BUILD_OUTCOMES/
   RECOGNISED_REVIEW_VERDICTS enum gating, `_note_rejected`, `fail_cause`
   fallback) is preserved unchanged — this story changes only *how a
   candidate `{...}` span is located*, not what happens once one is found.
3. **A `reason`/`findings`/`fail_cause` string containing a literal
   `{...}` no longer breaks parsing.** For a `tool_response` text
   containing a single well-formed
   `{"type": "REVIEW-RESULT", "verdict": "FAIL", "findings": [{"file": "x.py", "detail": "the guard `if (x) { revert() }` is unreachable", "severity": "HIGH"}]}`
   object (nested dict inside a list value, and a `{`/`}` pair embedded
   inside a quoted string), `parse_worker_outcome` returns
   `("FAIL", None)` or `("FAIL", <a fail_cause string>)` — not `(None,
   None)`. This is the regression case for HIGH finding F6 of
   `docs/build-loop-cold-eyes-review-20260801.md` and must be a named,
   asserted test (not covered only incidentally by a broader fixture).
4. **A quoted brace inside `reason`/`fail_cause` alone (no nested dict) is
   also covered.** A `tool_response` text containing
   `{"type": "BUILD-RESULT", "outcome": "FAIL", "fail_cause": "the guard `if (x) { revert() }` is unreachable"}`
   — a single non-nested object whose *string value* itself contains an
   unbalanced-looking `{`/`}` pair — parses to `("FAIL", "the guard `if
   (x) { revert() }` is unreachable")`. (This is the specific shape the old
   `\{[^{}]*\}` regex silently truncated at the first inner `}`, producing
   an unparseable fragment; forbidden proxy: a fix that only handles a
   *matched* nested dict, per Ensures 3, but still mis-scans a bare quoted
   brace with no surrounding object nesting.)
5. **Multiple result objects in one transcript still resolve correctly.**
   A `tool_response` text containing two candidate objects in sequence
   (e.g. a JSON `BUILD-RESULT` followed later by a `FAIL-CAUSE:` legacy
   line, or a JSON object whose `reason` string quotes what looks like a
   second `{"type": ...}` object as prose) still returns the same
   `outcome`/`fail_cause` precedence `parse_worker_outcome` already
   documents (JSON wins over the legacy `_LEGACY_RESULT_LINE_RE` fallback;
   last non-empty `fail_cause` wins on a second JSON match) — unchanged
   from current behavior, now correctly reached because the brace-inside-
   string cases above no longer prevent the first candidate from being
   found at all.
6. **Malformed input still returns `(None, None)` and never raises.** Text
   with an unterminated `{`, a `{` immediately followed by non-JSON
   content, or no `{` at all, still returns `(None, None)` from
   `parse_worker_outcome` — the balanced/raw_decode scan is bounded to the
   input text's length and does not loop unboundedly or throw on
   malformed input (mirrors the existing `try: json.loads(...) except
   json.JSONDecodeError: continue` discipline, adapted to the new scan
   shape).
7. **Every pre-existing `TestParseWorkerOutcome*`-prefixed test class in
   `tests/pairmode/test_subagent_transcript.py` still passes unmodified.**
   The rewrite is a drop-in replacement for the candidate-object-finding
   loop only; no existing assertion about enum gating, `_note_rejected`,
   legacy-line precedence, or ALIGNED/PASS/FAIL handling changes.
8. **Suite green.** Full `tests/pairmode/` run (no `-x`) passes, including
   the new regression tests added for Ensures 3/4.

## Instructions

1. Read `parse_worker_outcome` in full (`subagent_transcript.py:440-553`)
   before changing anything — the candidate-object loop at line 501
   (`for match in re.finditer(r"\{[^{}]*\}", text, re.DOTALL): ...`) is the
   only part of this function that changes. Everything inside the loop
   body (the `type`/`outcome`/`verdict` handling, `RECOGNISED_BUILD_OUTCOMES`/
   `RECOGNISED_REVIEW_VERDICTS` gating, `_note_rejected`, `fail_cause`
   fallback) stays as-is; only the mechanism that produces each candidate
   `obj` (currently `json.loads(match.group(0))` on a regex match) changes.
2. Implement a helper (module-private, e.g. `_iter_json_objects(text)`)
   that yields each syntactically-parseable top-level `{...}` object found
   in `text`, in order, using one of the two approaches named in Ensures
   2. The `json.JSONDecoder().raw_decode(text, idx)` approach is simpler
   to reason about and reuses the stdlib's own JSON string/escape
   handling rather than reimplementing brace/quote scanning by hand —
   prefer it unless a concrete reason (found while implementing) rules it
   out; if you choose the hand-rolled balanced-scan approach instead,
   document why in a comment at the helper's definition.
   - For the `raw_decode` approach: scan `text` for each `{` character;
     at each one, attempt `decoder.raw_decode(text, idx)`; on success,
     yield the decoded object and advance `idx` past the consumed span
     (`raw_decode` returns `(obj, end_index)`); on `json.JSONDecodeError`,
     advance `idx` by 1 and keep scanning (a `{` that isn't the start of a
     valid object, e.g. one appearing only inside an already-consumed
     string, is skipped this way — the same "best-effort, never raises"
     discipline the rest of the module already follows).
   - Skip a candidate `{` that falls inside the span already consumed by
     a successful prior `raw_decode` call, so a `{` embedded in an already
     -parsed object's string value is never re-offered as a second
     top-level candidate.
3. Replace the `for match in re.finditer(...)` loop's header with `for obj
   in _iter_json_objects(text):` and drop the `json.loads`/`isinstance(obj,
   dict)`/`except json.JSONDecodeError` lines the old loop needed (the new
   helper already guarantees each yielded item parsed successfully; keep
   the `isinstance(obj, dict)` guard only if the helper's contract doesn't
   already guarantee a dict — top-level JSON could technically be a list
   or scalar, so keep that guard for safety).
4. Delete the now-unused `\{[^{}]*\}` regex pattern; do not leave it
   defined-but-unused.
5. Do not touch any other regex or extraction path in this file (e.g.
   `_LEGACY_RESULT_LINE_RE`, `_FAIL_CAUSE_LINE_RE`, `_STORY_ID_RE`,
   `_PHASE_DOC_PATH_RE`) — this story is scoped to the single
   candidate-JSON-object-finding mechanism inside `parse_worker_outcome`.
6. Add the two named regression cases (Ensures 3 and 4) as new tests in
   `TestParseWorkerOutcome` (or a new `TestParseWorkerOutcomeBalancedBraces`
   class alongside it, matching the file's existing per-concern class
   grouping convention — see `TestParseWorkerOutcomeRejectedOutList` at
   `tests/pairmode/test_subagent_transcript.py:4203` for the pattern of a
   focused follow-on class) — do not fold them as bare asserts into an
   unrelated test.
7. Add at least one test for Ensures 5 (multiple candidate objects present)
   and one for Ensures 6 (malformed/no-brace input still yields `(None,
   None)`, never raises).
8. Run the full suite (not `-x`) before declaring done, per this
   project's "pytest -x masks failures" convention — a story touching a
   shared hook-path parser must confirm no other test file's fixture
   depended on the old regex's truncation behavior.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_subagent_transcript.py -k "ParseWorkerOutcome" -q 2>&1 | tail -30
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -10
```

Acceptance: both commands exit green. The first command must show the two
new regression tests (Ensures 3, 4) passing by name in the output. Reviewer
negative check: `grep -n '\\{\[\^{}\]\*\\}' skills/pairmode/scripts/subagent_transcript.py`
returns no match (the old pattern is fully removed, not just unused
alongside a new one).

## Out of scope

- `reconcile_one` / `reconcile_pending_attempts`'s own outcome handling —
  they call `parse_worker_outcome` and inherit this fix automatically;
  this story does not change their call sites.
- INFRA-336's attempt-counter bump / FAIL-escalation ladder fix — a
  different symptom of the same live failure mode (per the phase-117
  Context note: "feeds the same live symptom but touches a different
  file with no code dependency"), tracked and built separately.
- `worker_result.py`'s own JSON schema validation for a *live* worker
  return path (as opposed to this module's independent, import-light
  hook-path copy) — out of scope; this story only fixes how a candidate
  object is *located* in already-flattened transcript text, not how a
  found object's shape is validated.
- Any change to `RECOGNISED_BUILD_OUTCOMES` / `RECOGNISED_REVIEW_VERDICTS`
  or the enum-gating behavior around them — unchanged by this story.

Note (spec-preflight, INFRA-190/191): `docs/build-loop-cold-eyes-review-20260801.md`
is named above only as the citation source for HIGH finding F6 — this
story does not read, write, or otherwise touch that file, so it is
deliberately absent from `primary_files`/`touches`.
