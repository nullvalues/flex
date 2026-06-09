---
id: INFRA-159
rail: INFRA
title: "Context Management API: `GET /api/repos/:id/context`"
status: complete
phase: "63"
story_class: code
primary_files:
  - skills/observability/api/src/routes/context.ts
  - skills/observability/api/src/readers/stateJson.ts
  - skills/observability/api/src/readers/effortDb.ts
touches:
  - skills/observability/api/src/server.ts
---

# INFRA-159 — Context Management API: `GET /api/repos/:id/context`

## Context

This story adds the context management endpoint that surfaces token counts,
threshold configuration, derived waypoints, effort.db metrics, and
near-miss records for a registered repo.

**Data sources:**
- `.companion/state.json` — current token snapshot + threshold config
- `.companion/effort.db` — attempt history (SQLite, opened read-only)

**Waypoints are derived** (D5 from phase doc): computed by selecting
reviewer FAIL attempts from effort.db with `tokens_total IS NOT NULL`,
plus the current `context_current_tokens` snapshot from state.json.
No new table is written.

**Threshold triples** (D4 from phase doc): every threshold value is
returned as `{name, value, default, source, editable_via, phase2_writable}`
so Phase 64 controls can slot in without re-plumbing.

## Ensures

1. `GET /api/repos/:id/context` is registered on the Fastify instance.

2. Returns HTTP 404 if `:id` not in registry.

3. Successful response shape:
   ```json
   {
     "repo_id": "flex",
     "generated_at": "...",
     "current": {
       "tokens": 84231,
       "recorded_at": "2026-06-09T12:55:00Z",
       "age_seconds": 312,
       "stale": false,
       "story_id": "INFRA-156",
       "phase": "63"
     },
     "thresholds": [
       {
         "name": "context_budget_threshold",
         "value": 120000,
         "default": 120000,
         "source": "state.json",
         "editable_via": "flex_build.py set-context-tokens",
         "phase2_writable": true
       }
     ],
     "waypoints": [
       {
         "ts": "2026-06-08T10:30:00Z",
         "tokens": 138400,
         "story_id": "INFRA-148",
         "phase": "58",
         "agent_role": "reviewer",
         "outcome": "FAIL",
         "near_miss": true,
         "delta_above_threshold": 18400
       }
     ],
     "effort_summary": {
       "total_attempts": 312,
       "by_phase": [
         {
           "phase": "63",
           "attempts": 4,
           "median_tokens": 51200,
           "p90_tokens": 73400,
           "median_duration_ms": 92000
         }
       ]
     },
     "misses": {
       "count": 3,
       "entries": [
         {
           "ts": "...",
           "phase": "47",
           "tokens_at_block": 155000,
           "story_id": "INFRA-128"
         }
       ]
     }
   }
   ```

4. **`current` field:**
   - `tokens` = `state.json["context_current_tokens"]` (integer). `null` if key absent.
   - `recorded_at` = `state.json["context_current_tokens_recorded_at"]`. `null` if absent.
   - `age_seconds` = seconds since `recorded_at`. `null` if `recorded_at` absent.
   - `stale` = `true` if `age_seconds > state.json["context_current_tokens_ttl_minutes"] * 60`
     (default TTL: 60 minutes). `false` otherwise.
   - `story_id` = `state.json["current_story"]`. `null` if absent.
   - `phase` = `state.json["current_phase"]`. `null` if absent.

5. **`thresholds` array** — exactly these 6 entries in this order:
   | name | state.json key | default | editable_via | phase2_writable |
   |---|---|---|---|---|
   | `context_budget_threshold` | `context_budget_threshold` | 120000 | `flex_build.py set-context-tokens` | true |
   | `context_budget_overrun_pct` | `context_budget_overrun_pct` | 0.10 | null | true |
   | `expected_step_tokens` | `expected_step_tokens` | 53000 | `flex_build.py refresh-effort-baseline` | true |
   | `context_budget_reprompt_margin` | `context_budget_reprompt_margin` | 10000 | null | true |
   | `context_current_tokens_ttl_minutes` | `context_current_tokens_ttl_minutes` | 60 | null | false |
   | `flex_factor` | *(story frontmatter, not state.json)* | 1.0 | hand-edit story file | true |

   For each threshold, `source` is `"state.json"` if the key is present in
   state.json (even if the value equals the default), otherwise `"default"`.
   Exception: `flex_factor` always has `source: "story-frontmatter"`.

6. **`waypoints` array** — derived from effort.db:
   - SELECT all rows from `attempts` where `tokens_total IS NOT NULL`
     AND `outcome = 'FAIL'` AND `agent_role = 'reviewer'`.
   - Each row becomes a waypoint entry. `near_miss` = `true` when
     `tokens_total > context_budget_threshold * 0.85` (where threshold is
     the current value from thresholds).
   - `delta_above_threshold` = `tokens_total - threshold` when
     `tokens_total > threshold`, else `null`.
   - Ordered by `ts` descending, max 100 rows.
   - If effort.db does not exist, returns `[]`.

7. **`effort_summary.by_phase`** — for each distinct `phase` in the attempts
   table: count of rows, median `tokens_total` (NULL rows excluded), p90
   `tokens_total`, median `duration_ms`. Ordered by `phase` descending.
   Max 20 phases.

8. **`misses`** — rows where `tokens_total > context_budget_threshold * 1.10`
   (i.e., crossed the overrun ceiling). Count and entries (max 10, most
   recent first).

9. The SQLite file is opened with `?mode=ro` (read-only URI). If the file does
   not exist or cannot be opened, all effort-derived fields return safe defaults
   (`waypoints: []`, `effort_summary: {total_attempts: 0, by_phase: []}`,
   `misses: {count: 0, entries: []}`).

10. Uses `better-sqlite3` (synchronous SQLite driver). Add as a dependency in
    `skills/observability/api/package.json`.

11. Response is cached in-process for 2 seconds per `repo_id`.

12. Endpoint is read-only. No SQLite writes.

## Instructions

- `readers/stateJson.ts` exports `readStateJson(projectDir: string): Promise<Record<string, unknown>>`.
  Returns `{}` if state.json is absent or unparseable.
- `readers/effortDb.ts` exports `openEffortDb(dbPath: string): Database | null`
  (returns null when db absent) and query helpers:
  `queryWaypoints(db, threshold): Waypoint[]`,
  `queryEffortSummary(db): EffortSummary`,
  `queryMisses(db, threshold): MissEntry[]`.
- Compute medians in SQL: `SELECT MEDIAN(...)` is not available in SQLite;
  use `ORDER BY ... LIMIT 1 OFFSET count/2` or a subquery approach.
- Use `os.homedir()` to resolve `~` paths. Do not hardcode user home.

## Tests

Manual:
```bash
curl -s http://127.0.0.1:7777/api/repos/flex/context | python3 -m json.tool
```
Assert: response has `current`, `thresholds` (6 entries), `waypoints`,
`effort_summary`, `misses` keys.

## Out of scope

- Writing threshold values (Phase 64).
- Real-time websocket updates.
- Persisting waypoints to a new table.
- Effort data for the flex repo itself (flex has no effort.db; the endpoint
  returns safe defaults in that case, which is tested by this story).
