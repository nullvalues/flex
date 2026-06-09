---
id: INFRA-158
rail: INFRA
title: "Lessons + memories + policies API with promotion-candidate filter"
status: complete
phase: "63"
story_class: code
primary_files:
  - skills/observability/api/src/routes/lessons.ts
  - skills/observability/api/src/routes/user.ts
  - skills/observability/api/src/parsers/lessons.ts
  - skills/observability/api/src/parsers/markdownMeta.ts
touches:
  - skills/observability/api/src/server.ts
---

# INFRA-158 — Lessons + memories + policies API with promotion-candidate filter

## Context

Three read-only endpoints that surface lessons, memories, and policies.
The lessons endpoint applies a mechanical promotion-candidate filter (D6
from the phase doc) — no LLM involved.

**Data sources:**
- `lessons/lessons.json` in each registered repo
- `~/.claude/projects/<path-hash>/memory/*.md` — per-project memories
- `~/.claude/policies/*.md` — user-scoped policies

**Promotion-candidate filter (D6):** A lesson is flagged iff ALL of:
1. `status == "applied"`
2. `methodology_change.affects` contains at least one entry matching
   `/^[a-z_]+\.py$/` (a real Python module filename)
3. `methodology_change.description` matches at least one procedural-verb
   pattern (case-insensitive):
   - `add\s+a\s+(check|warning|gate)`
   - `block\s+when`
   - `warn\s+if`
   - `default\s+to`
   - `fail\s+(open|closed)\s+when`

## Ensures

### `GET /api/repos/:id/lessons`

1. Returns HTTP 404 if `:id` not in registry.

2. If `lessons/lessons.json` is absent in the repo, returns:
   `{"repo_id": "...", "generated_at": "...", "lessons": []}`.

3. Successful response:
   ```json
   {
     "repo_id": "flex",
     "generated_at": "...",
     "lessons": [
       {
         "id": "L001",
         "date": "2026-01-15",
         "status": "applied",
         "trigger": "...",
         "problem": "...",
         "learning": "...",
         "methodology_change": {
           "affects": ["audit.py"],
           "description": "Add a check for..."
         },
         "applies_to": ["all"],
         "promotion_candidate": true,
         "promotion_reasons": ["module-named: audit.py", "procedural-verb: 'add a check'"]
       }
     ]
   }
   ```

4. `promotion_candidate` is `false` and `promotion_reasons` is `[]` when the
   lesson does not meet the D6 criteria.

5. `promotion_candidate` is `false` for any lesson with `status != "applied"`.

6. Lessons are returned in file order (same order as `lessons.json`).

7. Response is cached in-process for 2 seconds per `repo_id`.

### `GET /api/user/memories`

8. Scans `~/.claude/projects/` for subdirectories. For each subdirectory,
   reads all `memory/*.md` files.

9. Response:
   ```json
   {
     "generated_at": "...",
     "projects": [
       {
         "project_hash": "-mnt-work-flex",
         "memories": [
           {
             "filename": "MEMORY.md",
             "first_heading": "Memory — flex project",
             "modified_at": "2026-06-09T10:00:00Z",
             "abs_path": "/home/user/.claude/projects/-mnt-work-flex/memory/MEMORY.md",
             "size_bytes": 1234
           }
         ]
       }
     ]
   }
   ```

10. `first_heading` is the text of the first `#`-prefixed markdown heading
    found in the file (any level). If no heading found, use the filename stem.

11. If `~/.claude/projects/` does not exist, returns
    `{"generated_at": "...", "projects": []}`.

12. Files that cannot be read (permission errors) are silently skipped.

### `GET /api/user/policies`

13. Reads all `*.md` files from `~/.claude/policies/`.

14. Response:
    ```json
    {
      "generated_at": "...",
      "policies": [
        {
          "filename": "auth-rbac.md",
          "first_heading": "Policy: RBAC",
          "modified_at": "...",
          "abs_path": "/home/user/.claude/policies/auth-rbac.md",
          "size_bytes": 4567
        }
      ]
    }
    ```

15. If `~/.claude/policies/` does not exist, returns
    `{"generated_at": "...", "policies": []}`.

16. All three endpoints are read-only. No files are written.

## Instructions

- `parsers/lessons.ts` exports `parseLessons(filePath): Promise<Lesson[]>`
  and `applyPromotionFilter(lessons: Lesson[]): Lesson[]`.
- `parsers/markdownMeta.ts` exports `firstHeading(content: string): string`
  for extracting the first markdown heading from file content.
- The promotion-candidate filter runs in-process (pure string regex matching,
  no external calls).
- Use `os.homedir()` to resolve `~` paths — do not hardcode `/home/<user>`.

## Tests

Manual:
```bash
curl -s http://127.0.0.1:7777/api/repos/flex/lessons | python3 -m json.tool | head -40
curl -s http://127.0.0.1:7777/api/user/memories | python3 -m json.tool
curl -s http://127.0.0.1:7777/api/user/policies | python3 -m json.tool
```
Assert lessons response has a `lessons` array; memories response has a
`projects` array; policies response has a `policies` array.

## Out of scope

- Editing or updating lessons from the SPA.
- Promotion workflow (the flag is read-only; acting on it is manual).
- Memories from other users' `~/.claude/` paths.
