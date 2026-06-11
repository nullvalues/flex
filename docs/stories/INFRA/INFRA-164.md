---
id: INFRA-164
rail: INFRA
title: "`flex_observability.py` CLI hardening — subprocess exit, atomic write, ID uniqueness"
status: planned
phase: "64"
story_class: code
primary_files:
  - skills/observability/scripts/flex_observability.py
  - tests/pairmode/test_flex_observability.py
touches: []
---

# INFRA-164 — `flex_observability.py` CLI hardening

## Context

Three bugs found in the Phase 63 cold-eyes review (findings 3, 4, 9):

1. `serve` uses `subprocess.run([...])` without checking the return code — a
   crashed node server reports exit 0, misleading callers and shell scripts.
2. `_write_registry` produces a non-unique tmp filename (`registry.tmp`),
   so two concurrent `register` invocations race on the same file and one
   registration is silently lost.
3. `register` deduplicates only by `project_dir`; two invocations with
   different paths but the same `--name` both succeed, and the second repo
   is permanently unreachable from every API route.

## Ensures

### `skills/observability/scripts/flex_observability.py`

1. **subprocess exit propagation.** `serve` captures the `CompletedProcess`
   result and calls `sys.exit(result.returncode)` after `subprocess.run`
   returns. `KeyboardInterrupt` still prints "Server stopped." and exits 0.

2. **Unique tmp filename.** `_write_registry` is updated to use:
   ```python
   import tempfile
   with tempfile.NamedTemporaryFile(
       dir=path.parent, delete=False, suffix='.tmp'
   ) as f:
       tmp_path = Path(f.name)
   tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
   os.replace(str(tmp_path), str(path))
   ```
   The temp file is created in the same directory as the registry file
   (required for atomic `os.replace` on Linux). `delete=False` lets the
   file survive after the context manager closes, so `write_text` can
   write to it and `os.replace` can rename it.

3. **ID uniqueness on register.** Before appending a new entry, the register
   command checks whether any existing entry already uses the requested `id`
   (name):
   - If the same `(id, project_dir)` pair already exists: idempotent, print
     `already registered: <path>` and exit 0 (unchanged).
   - If `id` is already used by a **different** `project_dir`: print
     `name already in use: <name> → <existing_path>` and exit 1.
   - Otherwise: append and register normally.

### `tests/pairmode/test_flex_observability.py`

4. New test cases:

   - **`test_serve_propagates_nonzero_exit`** — patch `subprocess.run` to
     return a `CompletedProcess` with `returncode=1`. Assert CLI exits 1.

   - **`test_write_registry_tmp_is_unique`** — call `_write_registry` twice
     concurrently (via `threading.Thread`); assert both registrations persist
     (no entry lost). Use a `tmp_path`-backed registry path.

   - **`test_register_duplicate_name_different_dir_exits_1`** — register
     `/mnt/work/flex` (name defaults to `flex`); then register
     `/mnt/work/other` with `--name flex`. Assert second call exits 1 and
     stdout contains `name already in use`.

   - **`test_register_duplicate_name_same_dir_idempotent`** — register
     `/mnt/work/flex` twice. Assert exit 0 on both and registry has one
     entry (existing idempotency test covers this, but make the name-check
     variant explicit).

5. All existing tests in `test_flex_observability.py` continue to pass.

## Instructions

- Import `tempfile` at the top of `flex_observability.py` (stdlib, no new
  dependency).
- The `serve` subcommand: store `result = subprocess.run(...)` and call
  `sys.exit(result.returncode)` at the end of the `try` block. The
  `KeyboardInterrupt` handler already does `sys.exit(0)` — don't touch it.
- The unique-tmp fix touches only `_write_registry`; `register`,
  `unregister`, and `list` call `_write_registry` and need no changes.
- For the ID-uniqueness test: to mock `subprocess.run` cleanly in
  `test_serve_propagates_nonzero_exit`, call the CLI via `subprocess` (as
  existing tests do) but use `unittest.mock.patch` via a helper script, or
  test the `returncode` propagation by pointing at a `node` shim that exits 1.
  Simplest: create a tiny shell script in `tmp_path` that `exit 1`s, set
  `PATH` so it shadows real `node`, pass that env to the CLI.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_observability.py -x -q
```

All tests must pass.

## Out of scope

- `unregister` depth guard (filed as CER-044 Do Later asymmetry note).
- `fsync` before `os.replace` (durability improvement; not a correctness bug
  in single-writer scenarios).
- Multi-writer locking beyond the atomic-rename guarantee.
