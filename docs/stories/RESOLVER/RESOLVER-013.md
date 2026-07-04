---
id: RESOLVER-013
rail: RESOLVER
title: Gate verdict JSON schema + parser hardening
status: planned
phase: "HARNESS009-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
  - tests/pairmode/test_parse_worker_verdict_json.py
touches:
  - skills/pairmode/skills/gate-worker/procedure.md
---

## Context

`next_action.py`'s `parse_worker_verdict_text` splits gate worker stdout on `": "` to extract
`gate: verdict` pairs (e.g. `schema: block — reason text`). A gate worker returning
`schema:block:reason` (no space after colon) or `schema — block` (wrong separator) is silently
skipped — that gate appears clean when it is not. This is a fail-open bug in the load-bearing
control path.

The fix: replace the text parser with `parse_worker_verdict_json` which calls `json.loads()`
on the worker's stdout. Workers emit a structured JSON object; a `json.JSONDecodeError` or
missing key is treated as a gate failure with `reason="malformed-verdict"` (fail-closed).
The gate worker procedure is updated in the same story so both sides change together.

Gate verdict grammar (new):
```json
{
  "schema":  "clean | block:<reason>",
  "auth":    "clean | block:<reason>",
  "stub":    "clean | block:<reason>"
}
```
All three keys always present. `clean` = no block. `block:<reason>` = blocked.

## Ensures

- `parse_worker_verdict_json(text: str) -> dict` exists in `next_action.py`. It:
  - Calls `json.loads(text)`.
  - On `json.JSONDecodeError` → returns `{"schema": "block:malformed-verdict", "auth": "block:malformed-verdict", "stub": "block:malformed-verdict"}` (all gates blocked, fail-closed).
  - On missing key (`schema`, `auth`, or `stub`) → same fail-closed block result.
  - On valid JSON with all three keys → returns the dict as-is (values not validated further).
- `parse_worker_verdict_text` is **replaced** by `parse_worker_verdict_json` in all call sites
  within `next_action.py`. The old function can be removed or retained as dead code with a
  deprecation note — removing is preferred.
- The resolver's routing is unaffected: the action emitted for a blocked gate remains
  `await-user`; only the parsing mechanism changes.
- `skills/pairmode/skills/gate-worker/procedure.md` is updated to document the JSON output
  format. Workers are instructed to emit only the JSON object on stdout (all other output
  to stderr).
- No backward compatibility with the old text format — the gate worker procedure is the
  source of truth; both sides change in this commit.
- Tests in `tests/pairmode/test_parse_worker_verdict_json.py` cover:
  - Valid JSON with all three keys and all-clean values → clean dict returned
  - Valid JSON with one block value → dict returned as-is with block entry
  - Malformed JSON (not JSON at all) → all gates blocked
  - Valid JSON but missing `schema` key → all gates blocked
  - Valid JSON but missing `auth` key → all gates blocked
  - Valid JSON but missing `stub` key → all gates blocked
  - Empty string → all gates blocked
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

1. Write `parse_worker_verdict_json(text: str) -> dict` in `next_action.py`. Place it near
   `parse_worker_verdict_text` (around line 1076).

2. Update all call sites of `parse_worker_verdict_text` in `next_action.py` to call
   `parse_worker_verdict_json` instead. Search for all usages.

3. Remove `parse_worker_verdict_text` (or mark deprecated). Removing is preferred to avoid
   confusion.

4. Update `skills/pairmode/skills/gate-worker/procedure.md` to specify the JSON output format.
   If that path doesn't exist, check `skills/pairmode/skills/` for the gate worker procedure
   and update the correct file.

5. Write `tests/pairmode/test_parse_worker_verdict_json.py` covering all cases in Ensures.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_parse_worker_verdict_json.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: `parse_worker_verdict_json` replaces text parser; fail-closed on malformed JSON
or missing keys; gate worker procedure updated; no backward compatibility shim; full test suite green.
