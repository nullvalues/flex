---
id: INFRA-146
rail: INFRA
title: "`global_session_check.py` — global SessionStart pairmode hook"
status: complete
phase: "57"
primary_files:
  - skills/pairmode/scripts/global_session_check.py
touches:
  - skills/pairmode/SKILL.md
---

# INFRA-146 — `global_session_check.py`: global SessionStart pairmode hook

## Context

Every new Claude Code session starts cold. Projects that have pairmode set up get no
automatic reminder of their state; non-pairmode projects get no nudge toward bootstrap.
A global `SessionStart` hook in `~/.claude/settings.json` runs once at session open and
can inject a lightweight status block — or a soft bootstrap prompt — into the model's
context before the first user message.

The hook is installed manually for now. A future "publish as skill" phase will wrap the
install step.

## Acceptance criteria

### Script: `skills/pairmode/scripts/global_session_check.py`

1. **Detection** — a project is considered pairmode-enabled if
   `(cwd / ".companion" / "pairmode_context.json").exists()`. Fallback: treat as
   pairmode-enabled if both `CLAUDE.build.md` and `docs/phases/index.md` are present.

2. **Non-pairmode output** (soft prompt, not silent):
   ```
   ⚡ Pairmode not configured for this project.
      Run /flex:pairmode bootstrap to set up the structured build loop.
      (Skip this if pairmode is not applicable here.)
   ```
   Output to stdout. Exit 0. No blocking.

3. **Pairmode output** — when detected, print a status block:
   ```
   ◆ Pairmode active — <project_name>
     Current story : <id> — <title>  (or "none set")
     Active era    : <era_id>         (or "—")
     Last tag      : <tag>            (from git describe --tags --abbrev=0, or "—")
     Canon sync    : <status>         (see §4)
   ```
   Read `project_name` from `.companion/pairmode_context.json`.
   Read `current_story` from `.companion/state.json` (dict with `"id"` key, or absent).
   Read active era by scanning `docs/eras/*.md` for `status: active` in frontmatter (use
   simple line-by-line scan — no YAML parser dependency).
   Read last tag via `subprocess.run(["git", "describe", "--tags", "--abbrev=0"])`.

4. **Canon sync status** — check whether the project's scaffold is current:
   - Locate flex: check `FLEX_DIR` env var → `~/.claude/pairmode_config.json` key
     `"flex_dir"` → common paths `["/mnt/work/flex", os.path.expanduser("~/flex"),
     os.path.expanduser("~/projects/flex")]` in order.
   - If found: compare the project's `.companion/state.json["pairmode_version"]` against
     the version string in `<flex_dir>/skills/pairmode/SKILL.md` (grep for
     `pairmode_version:` or the `## Version` heading). If they match: `up to date`.
     If project version is absent: `unknown (run /flex:pairmode audit)`.
     If versions differ: `behind canon — run /flex:pairmode sync`.
   - If flex not found: `Set FLEX_DIR env var to enable currency check`.

5. **Stdlib only** — no imports beyond the standard library. The hook runs as bare
   `python3`, not `uv run python`. No click, no rich, no jinja2.

6. **Graceful failure** — any exception at any step is caught; the hook prints a single
   warning line and exits 0. It never blocks the session.

7. **Tests** in `tests/pairmode/test_global_session_check.py`:
   - Non-pairmode project → correct soft-prompt text in stdout
   - Pairmode project with active story → status block with story id
   - Pairmode project with no story set → "none set"
   - Currency check: flex found, versions match → "up to date"
   - Currency check: flex found, versions differ → "behind canon"
   - Currency check: flex not found → correct message
   - Exception during git tag lookup → gracefully suppressed, rest of output present

### SKILL.md update

Add a section `### Global session hook` under the `phase-new` section documenting:
- What the hook does and when to install it
- The manual install steps (copy + settings.json edit, see below)
- How to configure `FLEX_DIR` or `~/.claude/pairmode_config.json`

### Manual install (to be performed as part of story acceptance)

```bash
# 1. Copy the hook script to the global hooks directory
mkdir -p ~/.claude/hooks
cp /mnt/work/flex/skills/pairmode/scripts/global_session_check.py ~/.claude/hooks/pairmode_check.py

# 2. Add SessionStart entry to ~/.claude/settings.json
# Merge into the existing "hooks" key, or add it:
# "hooks": {
#   "SessionStart": [{
#     "hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/pairmode_check.py", "timeout": 10}]
#   }]
# }
```

The install step is part of acceptance: after the script is written and tests pass,
perform the install and verify the hook fires at the next session start.

## Implementation notes

- Use `os.getcwd()` to get the project directory — hooks run in the project root.
- For the era scan, read each `.md` file in `docs/eras/` line by line; match
  `status: active` (strip whitespace). Extract era `id:` from the same frontmatter block.
  No YAML library needed.
- For `pairmode_version` comparison: read `SKILL.md` and look for a line starting with
  `pairmode_version:` or `**Version:**`. If not found, skip the comparison and output
  `unknown (version field not found in SKILL.md)`.
- The `~/.claude/pairmode_config.json` file does not need to be created by this story —
  just read it if it exists. Format: `{"flex_dir": "/path/to/flex"}`.

## Out of scope

- An automated install CLI command (future story)
- A `/flex:pairmode status` skill command alias (future)
- Modifying any hook in `hooks/` (this is a new user-global file, not a project hook)
