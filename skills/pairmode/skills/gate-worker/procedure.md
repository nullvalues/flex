# Gate Worker — Output Procedure

## Purpose

Gate workers assess a candidate story against the schema, auth, and stub gates.
Each gate yields one of two verdicts: `clean` (no block) or `block:<reason>`
(blocked with a short machine-readable reason).

## Output format (RESOLVER-013)

Emit a **single JSON object on stdout** with exactly three keys:

```json
{
  "schema":  "clean | block:<reason>",
  "auth":    "clean | block:<reason>",
  "stub":    "clean | block:<reason>"
}
```

All three keys (`schema`, `auth`, `stub`) must always be present.

| Value | Meaning |
|-------|---------|
| `"clean"` | Gate passes — no block. |
| `"block:<reason>"` | Gate blocked. `<reason>` is a short, machine-readable slug (e.g. `no-owner-check`, `missing-management-surface`). |

**Do not emit any other content on stdout.** All diagnostic output, reasoning,
and prose must go to **stderr**. The orchestrator feeds stdout directly to
`parse_worker_verdict_json`; anything that is not valid JSON causes all three
gates to be treated as blocked (fail-closed).

## Example

```json
{"schema": "block:no-management-ui", "auth": "clean", "stub": "clean"}
```

## Error handling

If the worker cannot determine a verdict for a gate, emit `"block:undetermined"`
for that gate rather than omitting the key. A missing key is indistinguishable
from a malformed response and blocks all three gates.
