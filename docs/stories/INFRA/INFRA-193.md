---
id: INFRA-193
rail: INFRA
title: story_new.py rail validation and empty primary_files
status: draft
phase: "HARNESS011-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/story_new.py
  - skills/pairmode/scripts/schema_validator.py
touches:
  - tests/pairmode/test_story_new.py
  - tests/pairmode/test_schema_validator.py
---

## Ensures

- **CER-010** — `story_new.py --rail` is validated against `re.fullmatch(r"[A-Z][A-Z0-9_]*", rail)`
  before any path construction. Invalid values (including traversal payloads like
  `"../../../etc"`) are rejected with a clear error message and exit 1.
- **CER-006** — `story_new.py` omits `primary_files` and `touches` from the written
  frontmatter when they would be empty; it does not write `primary_files: []`.
  `schema_validator.py` accepts an absent or empty `primary_files` for stories with
  `status: draft`; it rejects empty/absent `primary_files` only for stories with `status`
  other than `draft`.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_story_new.py -x -q`
  passes.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

### CER-010 — --rail validation

In `story_new.py`, add at the CLI entry point (before any directory or file operations):
```python
_RAIL_RE = re.compile(r"[A-Z][A-Z0-9_]*")
if not _RAIL_RE.fullmatch(rail):
    print(f"Error: invalid rail name '{rail}' — must match [A-Z][A-Z0-9_]*", file=sys.stderr)
    sys.exit(1)
```

The `.upper()` normalization that already exists should run BEFORE the regex check (so
`--rail infra` normalizes to `INFRA` and passes). The traversal payload `../../../etc`
uppercased is still `../../../ETC` which fails the regex.

### CER-006 — omit empty primary_files / touches

In `story_new.py`, change the frontmatter template: write `primary_files:` and `touches:`
lines only when the initial values are non-empty. For a new story scaffolded by the CLI
(which has no initial primary_files), simply omit both keys from the written YAML.

In `schema_validator.py`, change the `primary_files` validation rule:
- If story `status == "draft"`: accept missing or empty list.
- If story `status != "draft"`: require non-empty list (existing behavior).

## Tests

Add to `test_story_new.py`:
- Rail `"../../../etc"` rejected (exit 1, error message).
- Rail `"infra"` (lowercase) accepted after normalization.
- Scaffolded story file does not contain `primary_files: []`.

Add to `test_schema_validator.py`:
- Draft story with no `primary_files` key validates successfully.
- Non-draft story with no `primary_files` key fails validation.
