---
id: INFRA-194
rail: INFRA
title: "bootstrap.py ergonomics: --yes flag and effort_tracking transparency"
status: draft
phase: "HARNESS011-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/bootstrap.py
touches:
  - tests/pairmode/test_bootstrap.py
---

## Acceptance criterion

- **CER-002** — `bootstrap.py` accepts `--yes` / `-y` flag. When set, all interactive
  confirmation prompts (file overwrites, rail confirmation, ideology capture) are
  auto-confirmed without reading stdin. Non-interactive callers no longer need the
  `input="y\n" * N` workaround.
- **CER-017** — When `bootstrap.py` writes `effort_tracking: true` to `state.json`, it
  also prints a one-line summary note to stdout:
  `"  effort tracking enabled (local sqlite only — no data leaves the host)"`.
  This appears in the bootstrap completion summary alongside other written-file lines.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_bootstrap.py -x -q`
  passes.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

### CER-002 — --yes flag

Add `--yes` / `-y` as an argparse boolean flag. Thread it through all prompt-gated code
paths. The existing `--ideology-skip` flag continues to work independently.

For each interactive prompt, the pattern is:
```python
if yes or _confirm_prompt("Overwrite X? [y/N]"):
    ...
```

### CER-017 — effort_tracking note

In `_record_state()` (or wherever `effort_tracking: true` is written to state.json), add
a `print("  effort tracking enabled (local sqlite only — no data leaves the host)")` call.
This should only print once per bootstrap run, not on every state write.

## Tests

Add to `test_bootstrap.py`:
- `--yes` flag causes file-overwrite confirmation to be auto-accepted.
- Effort-tracking note appears in stdout when `_record_state()` writes
  `effort_tracking: true`.
