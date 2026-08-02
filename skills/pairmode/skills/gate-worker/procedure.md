# Gate Worker — Output Procedure

> **Orphan status (INFRA-341):** as of this story, this file has **no live reader**.
> `templates/agents/gate-worker.md.j2` (the actual agent shell the orchestrator
> spawns) delegates to `skills/pairmode/gate_worker/SKILL.md` — a *different*
> file, singular `gate_worker/`, no `skills/` nesting — not to this document.
> This file is corrected here so it no longer actively misleads a future
> reader, but consolidating the two procedure-doc trees is out of this
> story's scope (see `docs/stories/INFRA/INFRA-341.md`). Treat
> `gate_worker/SKILL.md` as the authoritative judgment procedure.

## Purpose

Gate workers assess a candidate story against the schema and auth gates.
(The stub gate is mechanical — it is checked directly by `resolve_next_action`'s
Row 4a before `spawn-gate-worker` is ever emitted, so a gate worker never
judges it: by construction, if `spawn-gate-worker` fires, the stub gate has
already passed.) Each gate yields one of two verdicts: `clean` (no block) or
`block:<reason>` (blocked with a short machine-readable reason).

## Output format

Emit a **single JSON object on stdout** with exactly two keys:

```json
{
  "schema":  "clean | block:<reason>",
  "auth":    "clean | block:<reason>"
}
```

Both keys (`schema`, `auth`) must always be present. `stub` is **never** a
valid key in this return map — it is mechanical and out of a gate worker's
judgment scope (see Purpose above).

| Value | Meaning |
|-------|---------|
| `"clean"` | Gate passes — no block. |
| `"block:<reason>"` | Gate blocked. `<reason>` is a short, machine-readable slug (e.g. `no-owner-check`, `missing-management-surface`). |

**Do not emit any other content on stdout.** All diagnostic output, reasoning,
and prose must go to **stderr**.

## How the verdict is consumed (INFRA-341)

The orchestrator does **not** feed this worker's raw stdout directly to
`parse_worker_verdict_json` — that function requires exactly three keys
(`schema`, `auth`, `stub`) and fail-closes (blocks all three) if any is
missing, which would make every real two-key gate-worker verdict fail-closed
permanently. Instead, `CLAUDE.build.md`'s dispatch loop captures this
worker's stdout and pipes it, unmodified, to
`skills/pairmode/scripts/flex_build.py record-gate-verdict --story-id
<story> --project-dir .` via stdin. `record-gate-verdict` is the CLI
boundary that reconciles the two-key worker contract with
`parse_worker_verdict_json`'s three-key requirement: it injects `"stub":
"clean"` into the parsed JSON before calling `parse_worker_verdict_json`
(reflecting true state — the stub gate already passed, per Purpose above —
not a loosening of the fail-closed contract), then persists the resulting
verdict map to `state.json["gate_verdict"][story_id]`. On the orchestrator's
next `next-action` poll, `resolve_next_action`'s Row 4b reads that durable
verdict and applies `route_gate_verdict`'s DP3.2 aggregation to route to
`await-user` (blocked) or `spawn-builder` (clean/flag) — instead of
re-emitting `spawn-gate-worker` again, which is what closed the INFRA-331
livelock (F8 of the phase-117 cold-eyes review).

Stdin that is not valid JSON, or that already carries an explicit
non-`clean` `"stub"` value, is passed to `parse_worker_verdict_json`
unmodified by `record-gate-verdict` — the fail-closed malformed-JSON path is
untouched, and a worker crash or garbage stdout still leaves durable
evidence (`block:malformed-verdict` on all three gates) rather than
vanishing silently.

## Example

```json
{"schema": "block:no-management-ui", "auth": "clean"}
```

## Error handling

If the worker cannot determine a verdict for a gate, emit `"block:undetermined"`
for that gate rather than omitting the key. Omitting `schema` or `auth`
(other than the deliberate, always-omitted `stub`) is indistinguishable from
a malformed response: `record-gate-verdict` only injects the `stub` key, so
a worker return missing `schema` or `auth` still fails
`parse_worker_verdict_json`'s three-key requirement and blocks all three
gates (`block:malformed-verdict`).
