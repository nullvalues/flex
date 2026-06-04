---
id: INFRA-154
rail: INFRA
title: "companion sidebar scope_miss capture from scope_guard elevation pattern"
status: planned
phase: "61"
story_class: code
primary_files:
  - skills/companion/scripts/sidebar.py
  - tests/pairmode/test_sidebar_scope_miss.py
touches: []
---

# INFRA-154 — companion sidebar scope_miss capture from scope_guard elevation pattern

## Context

When `skills/pairmode/scripts/scope_guard.py` blocks an Edit/Write tool call,
the `pre_tool_use` hook emits a JSON envelope of the form:

```json
{"decision": "block", "reason": "not in story scope for RAIL-NNN: path/to/file"}
```

(See `scope_guard.py:36` — the `reason` string is constructed as
`f"not in story scope for {story_id}: {normalised}"`.)

If the developer then approves the edit (elevation granted), the next tool_use
on the same path succeeds and the friction signal disappears. There is no record
that the story spec was insufficient. This is the single most common, least
visible class of methodology error in the build loop.

The companion sidebar (`skills/companion/scripts/sidebar.py`) already reads
Claude Code transcripts and extracts architectural decisions through an
LLM-driven taxonomy: `business_rule | non_negotiable | tradeoff | decision |
conflict` (see `EXTRACTION_SYSTEM` at line ~566). Lessons persistence is already
in place via `skills/pairmode/scripts/lesson_utils.py` (`save_lessons` is
append-only and enforces the L00N ID convention).

INFRA-154 adds a new capture pathway: a deterministic regex-driven scan over
the raw transcript JSONL that detects the block-then-elevate pattern and
writes a `scope_miss` lesson to `lessons/lessons.json` via `save_lessons`.
No LLM is involved — this is a mechanical pattern match.

## Acceptance criteria

### `skills/companion/scripts/sidebar.py`

1. **Add a `scope_miss` value** to the documented capture taxonomy in
   `EXTRACTION_SYSTEM` (line ~574). The existing line:

   ```
   "type": "business_rule | non_negotiable | tradeoff | decision | conflict",
   ```

   becomes:

   ```
   "type": "business_rule | non_negotiable | tradeoff | decision | conflict | scope_miss",
   ```

   This documents the type — the LLM will not produce it (the LLM does not see
   tool_result blocks). The deterministic extractor in (3) is the only producer.

2. **Add a module-level regex constant** near the existing regex constants:

   ```python
   _SCOPE_BLOCK_RE = re.compile(
       r"not in story scope for ([A-Z][A-Z0-9_]*-\d{3}): (\S+)"
   )
   ```

3. **Add a new function `_extract_scope_misses(transcript_path: str) -> list[dict]`.**
   The function:

   a. Returns `[]` if `transcript_path` is falsy or the file does not exist.

   b. Iterates the JSONL file line by line, parsing each line as JSON and
      silently skipping malformed lines (mirrors `read_last_messages` style).
      Unlike `read_last_messages`, it does **not** cap at the last 8 messages
      and does **not** filter by content-block type — it must see tool_use,
      tool_result, and assistant messages.

   c. For each `user` message whose `message.content` is a list, walks the
      content blocks looking for `type == "tool_result"` blocks. The `content`
      field of a tool_result is either a string or a list of `{"type": "text",
      "text": ...}` blocks. Concatenate the text into a single string.

   d. Runs `_SCOPE_BLOCK_RE` against the concatenated tool_result text. For
      each match, records `(story_id, blocked_path, tool_use_id)` where
      `tool_use_id` is the `tool_use_id` field on the tool_result block.

   e. In a single pass, also tracks subsequent `assistant` messages with a
      `tool_use` block whose `name in {"Edit", "Write"}` and whose
      `input.file_path` (normalised: `lstrip("./")`) matches a previously
      recorded `blocked_path`. Treat the edit as the **elevation** if it
      appears chronologically after the blocked tool_use_id. JSONL line order
      is chronological order.

   f. Returns a list of dicts:

      ```python
      {
          "story_id": "RAIL-NNN",
          "blocked_path": "skills/foo/bar.py",
          "elevated": True,   # or False if no subsequent successful edit
      }
      ```

      One dict per distinct `(story_id, blocked_path)` pair; deduplicated.

4. **Add a new function `_save_scope_miss_lessons(misses: list[dict]) -> int`.**

   a. For each miss, build a deterministic dedup key:
      `dedup_key = f"scope_miss:{miss['story_id']}:{miss['blocked_path']}"`

   b. Call `load_lessons()`. For any existing entry whose `trigger` equals
      `dedup_key`, skip (idempotent — re-running over the same transcript
      must never duplicate).

   c. Otherwise construct a new lesson dict:

      ```python
      {
          "id": next_lesson_id(existing_lessons),
          "date": datetime.now().strftime("%Y-%m-%d"),
          "source_project": "flex",
          "trigger": dedup_key,
          "problem": (
              f"Story {miss['story_id']}: builder needed {miss['blocked_path']} "
              "but it was not in primary_files or touches; scope_guard blocked the edit."
          ),
          "learning": (
              f"Spec writer missed {miss['blocked_path']} for story {miss['story_id']}. "
              "Elevation was granted — re-spec should declare this file."
              if miss["elevated"] else
              f"Spec writer missed {miss['blocked_path']} for story {miss['story_id']}. "
              "Elevation was refused — confirm whether the file is genuinely out of scope."
          ),
          "applies_to": ["all"],
          "status": "captured",
          "type": "scope_miss",
      }
      ```

   d. Appends and calls `save_lessons()`. Catches and silently logs any
      exception — the sidebar must never fail because of scope-miss capture.

   e. Returns count of newly-written lessons (0 if all were duplicates).

5. **Wire into `handle_stop`** (line ~1062). After the existing
   `extract_incremental` call and console summary:

   ```python
   try:
       misses = _extract_scope_misses(transcript)
       if misses:
           written = _save_scope_miss_lessons(misses)
           if written:
               console.print(f"[dim]  ✓ {written} scope_miss lesson(s) recorded[/dim]")
   except Exception as _e:
       log_error(f"scope_miss extraction error: {_e}")
   ```

6. The functions are pure (no global state mutation beyond `lessons.json`).
   They make no LLM calls.

### Tests — `tests/pairmode/test_sidebar_scope_miss.py`

7. New test file using the same `importlib` loader pattern as
   `tests/pairmode/test_sidebar_story_panel.py` (lines 24–32) so the sidebar
   module loads despite its inline-script header. Import only
   `_extract_scope_misses`, `_save_scope_miss_lessons`, and `_SCOPE_BLOCK_RE`.

8. Use `tmp_path` for transcript file creation. Use `monkeypatch` on
   `lesson_utils.LESSONS_FILE` to point at a tmp lessons file initialised with
   `{"version": "1.0.0", "lessons": []}`.

9. Required test cases:

   - **`test_extract_block_then_elevate`** — JSONL with: (a) assistant tool_use
     Edit on `skills/foo/bar.py`, (b) user tool_result for that tool_use_id
     containing `"not in story scope for INFRA-154: skills/foo/bar.py"`,
     (c) assistant tool_use Edit on the same path.
     Assert `[{"story_id": "INFRA-154", "blocked_path": "skills/foo/bar.py",
     "elevated": True}]`.

   - **`test_extract_blocked_no_elevation`** — Same but omit step (c).
     Assert `elevated` is `False`.

   - **`test_extract_ignores_unrelated_tool_results`** — tool_result blocks
     containing `"file not found"` or `"command failed"`. Assert `[]`.

   - **`test_extract_dedupes_repeated_blocks`** — Same path blocked three
     times. Assert exactly one dict for that `(story_id, path)` pair.

   - **`test_extract_no_transcript`** — Pass `None` and a non-existent path.
     Assert `[]` in both cases.

   - **`test_save_writes_new_lesson`** — One miss; assert `lessons.json` after
     call has one entry with `type == "scope_miss"`,
     `trigger == "scope_miss:INFRA-154:skills/foo/bar.py"`.

   - **`test_save_idempotent`** — Call twice with the same miss. Assert second
     call returns `0` and file has exactly one entry for that dedup key.

   - **`test_save_learning_text_varies_by_elevation`** — Two misses with
     different `elevated` values. Assert `learning` text differs between the
     two resulting lessons.

## Out of scope

- LLM-based scope_miss inference.
- UI surfacing of scope_miss in the live sidebar chart.
- Modifying `lesson_utils.py`, `scope_guard.py`, or `pre_tool_use.py`.
- Aggregating scope_miss lessons into a per-story dashboard.
- Path normalisation beyond `lstrip("./")` for the elevation match.
