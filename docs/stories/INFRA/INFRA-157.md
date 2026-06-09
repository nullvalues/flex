---
id: INFRA-157
rail: INFRA
title: "System of Record API: `GET /api/repos/:id/system`"
status: complete
phase: "63"
story_class: code
primary_files:
  - skills/observability/api/src/routes/system.ts
  - skills/observability/api/src/parsers/phaseIndex.ts
  - skills/observability/api/src/parsers/phaseDoc.ts
  - skills/observability/api/src/parsers/storyFrontmatter.ts
touches:
  - skills/observability/api/src/server.ts
---

# INFRA-157 — System of Record API: `GET /api/repos/:id/system`

## Context

This story adds the System of Record endpoint that returns the full
era → phase → story hierarchy for a registered repo. It reads markdown
files only — no database, no LLM calls.

The data sources are:
- `docs/phases/index.md` — phase list table
- `docs/phases/phase-NNN.md` — per-phase metadata and stories table
- `docs/stories/<RAIL>/<RAIL>-NNN.md` — per-story frontmatter
- `docs/eras/*.md` — era metadata (if present)

## Ensures

1. `GET /api/repos/:id/system` is registered on the Fastify instance.

2. If `:id` is not in the registry, returns HTTP 404:
   `{"error": "repo not found", "id": "<id>"}`.

3. Successful response shape:
   ```json
   {
     "repo_id": "flex",
     "generated_at": "<ISO timestamp>",
     "phases": [
       {
         "phase_ref": "63",
         "file": "docs/phases/phase-63.md",
         "title": "Observability SPA — read-only window glass",
         "status": "planned",
         "checkpoint_tag": null,
         "era": "002",
         "stories": [
           {
             "id": "INFRA-156",
             "rail": "INFRA",
             "title": "...",
             "status": "planned",
             "story_class": "code",
             "flex_factor": 1.0,
             "primary_files": ["..."],
             "touches": []
           }
         ],
         "deferred": []
       }
     ]
   }
   ```

4. `phases` is ordered by phase number ascending (1, 2, … 63).

5. Phase `status` is derived from the index.md table column value
   (`complete`, `planned`, etc.). If the column is absent or unparseable,
   default to `"unknown"`.

6. Phase `checkpoint_tag` is the tag string from the index.md tag column
   (e.g. `cp63-observability-spa`), or `null` if absent / not yet tagged.

7. Story `flex_factor` defaults to `1.0` when the frontmatter key is absent.

8. If `docs/phases/index.md` is missing in the repo, returns:
   `{"repo_id": "...", "generated_at": "...", "phases": []}`.

9. If a phase file is listed in the index but does not exist on disk, the
   phase entry is included with `"stories": []` and `"title": null`.

10. If a story file listed in a phase doc does not exist on disk, the story
    entry has `"status": "missing"` and no other frontmatter fields.

11. The endpoint is read-only. No files are written.

12. Response is cached in-process for 2 seconds per `(repo_id)` key to
    absorb page-load fan-out. Cache is a simple `Map<string, {ts, data}>`.

## Instructions

### Phase index parser (`parsers/phaseIndex.ts`)

Parse `docs/phases/index.md` to extract the phase table rows. The table
columns are: `Phase`, `Title`, `Status`, `Tag`. Parse with a simple regex
line scan — do not use a markdown library. Each row yields:
`{phase_ref, title, status, file, checkpoint_tag, era}`.

The era is read from the frontmatter of the phase file itself (`era: "002"`
YAML block), not from the index. Default to `null` if absent.

### Phase doc parser (`parsers/phaseDoc.ts`)

For a given phase file path, extract:
- The stories table rows: `|ID|Title|Status|` columns
- Any `## Deferred stories` section: list the story IDs mentioned there

### Story frontmatter parser (`parsers/storyFrontmatter.ts`)

For a given story file path, parse the YAML frontmatter block (between the
first and second `---` delimiters). Extract: `id`, `rail`, `title`, `status`,
`story_class`, `flex_factor`, `primary_files`, `touches`. Use the `js-yaml`
package for YAML parsing. Do not use a custom parser.

### Route (`routes/system.ts`)

Wire the three parsers together. Fan out story reads in parallel
(`Promise.all`) per phase to keep the response fast.

## Tests

Manual verification:
```bash
curl -s http://127.0.0.1:7777/api/repos/flex/system | python3 -m json.tool | head -60
```
Assert: `phases` array is non-empty, each phase has `phase_ref` and `stories`,
story entries have `id`, `rail`, `status`.

## Out of scope

- Era-level grouping above the phase list (the `phases` flat list is the
  surface; era is a field on each phase).
- Reading lesson files (INFRA-158).
- Context metrics (INFRA-159).
