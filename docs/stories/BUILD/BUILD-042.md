---
id: BUILD-042
rail: BUILD
title: "Enable effort_tracking on flex itself"
status: planned
phase: "83"
story_class: methodology
auth_gated: false
schema_introduces: false
primary_files:
  - .companion/state.json
  - CLAUDE.md
touches:
---

## Requires

- `.companion/state.json` exists at the project root with keys including `pairmode_version`, `registered_projects`, `context_current_tokens`, etc.
- `skills/pairmode/scripts/record_attempt.py` honours the `effort_tracking` flag in `.companion/state.json` — lines ~270–275 check `state.get("effort_tracking")` and no-op when absent or false.

## Ensures

- `.companion/state.json` contains the key `"effort_tracking"` with boolean value `true` (not the string "true").
- `CLAUDE.md` review checklist item 6 (TEST COVERAGE) contains text noting that `effort_tracking` in `.companion/state.json` must remain `true`, and that setting it to `false` or removing it without a BUILD-rail story authorising the change is a HIGH finding.
- Running `PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/record_attempt.py --story-id BUILD-042 --agent-role builder --outcome PASS --project-dir .` exits 0 and does not print `effort_tracking disabled` (i.e. the flag is honoured and recording proceeds).

## Instructions

**1. Edit `.companion/state.json`.**

The file contains no `effort_tracking` key. Add `"effort_tracking": true` as a top-level key. Preserve all existing keys. Write compact 2-space-indented JSON (match existing format).

**2. Edit `CLAUDE.md` review checklist item 6.**

Locate item 6 (TEST COVERAGE). It currently reads:

```
6. TEST COVERAGE
   Does the diff include Python logic modules in `skills/pairmode/scripts/` with
   no corresponding test file in `tests/pairmode/`?
   Missing tests for logic modules are HIGH.
```

Extend it to read:

```
6. TEST COVERAGE
   Does the diff include Python logic modules in `skills/pairmode/scripts/` with
   no corresponding test file in `tests/pairmode/`?
   Missing tests for logic modules are HIGH.

   Also verify: `effort_tracking` in `.companion/state.json` must remain `true`.
   If any diff sets it to `false` or removes it without a BUILD-rail story
   explicitly authorising the change: HIGH.
```

No other section of `CLAUDE.md` changes.

**3. No changes to any Python script.** This is a methodology + config story.

## Tests

This is a `methodology` story_class. No new Python logic module is introduced.

Reviewer manual verification:

```bash
# Ensures 1: key present and boolean true
python3 -c "import json; d=json.load(open('.companion/state.json')); assert d.get('effort_tracking') is True, d"

# Ensures 2: checklist updated
grep -n "effort_tracking" CLAUDE.md

# Ensures 3: record_attempt no longer skips
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/record_attempt.py \
  --story-id BUILD-042 --agent-role builder --outcome PASS --project-dir . 2>&1 | grep -v "disabled"
```
