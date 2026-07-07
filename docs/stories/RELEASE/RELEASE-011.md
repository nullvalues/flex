---
id: RELEASE-011
rail: RELEASE
title: "pairmode_migrate.py to-030: state.json normalizer and stale-agent cleanup"
status: draft
phase: "HARNESS013-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/pairmode_migrate.py
touches:
  - tests/pairmode/test_pairmode_migrate.py
---

## Ensures

Running `pairmode_migrate.py to-030 --project-dir P [--apply]` on any
0.2.x-bootstrapped project:

- **expected_step_tokens (B6)**: If `state.json["expected_step_tokens"]` equals
  `53000` (the Era 2 fleet-wide stamp), overwrites it with `5000`
  (`THIN_HARNESS_STEP_TOKENS`). Values other than `53000` are left unchanged
  with a `[WARN] custom value kept` notice. Rationale: `sync-all` uses
  `setdefault`, so this normalizer must actively overwrite the stale stamp.
- **pipe_path (B4)**: If `state.json` contains `pipe_path`, prints a
  deprecation notice naming the new fixed location
  (`$TMPDIR/companion.pipe`), and removes the key with `--apply`.
- **state.json seed (B5)**: If `.companion/` exists but `state.json` is absent
  or unreadable, writes a minimal valid `state.json`
  (`{"pairmode_version": "0.3.0", "expected_step_tokens": 5000}`) using
  `_atomic_write_json`.
- **Protected-path preview (B3)**: Lists any project files matching
  `scope_guard.PROTECTED_GLOBS` that appear in `git log --name-only -20`
  (last 20 commits), so the operator sees which habitual edits now require an
  active story. Informational only — no blocking.
- **Stale agent cleanup (B7)**: Checks `.claude/agents/` for any of
  `{builder,reviewer,loop-breaker,security-auditor,intent-reviewer}.md`.
  For each found:
  - If its content hash matches a known 0.2.x rendered template (hash
    allowlist defined as a constant), deletes the file with `--apply`.
  - If the content does not match (project-customized), prints a diff against
    the 0.2.x template and defers to the operator with instructions to
    manually port customizations into the relevant procedure skill.
- **Idempotent**: Running twice produces no additional changes.
- **`--dry-run` is the default**: Nothing is written unless `--apply` is
  passed. Output in dry-run mode clearly labels each action as `[would]`.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_pairmode_migrate.py -x -q`
  passes.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

Add a new `to-030` subcommand to `pairmode_migrate.py` (alongside the existing
`anchor-to-flex` migration logic). Structure:

```python
@cli.command("to-030")
@click.option("--project-dir", required=True, type=click.Path())
@click.option("--apply", is_flag=True, default=False)
def cmd_to_030(project_dir, apply):
    ...
```

**expected_step_tokens rewrite**:
```python
THIN_HARNESS_STEP_TOKENS = 5000
ERA2_STAMP = 53000
state = _load_state(project_dir)
if state.get("expected_step_tokens") == ERA2_STAMP:
    if apply:
        state["expected_step_tokens"] = THIN_HARNESS_STEP_TOKENS
        _atomic_write_json(state_path, state)
    else:
        print(f"[would] rewrite expected_step_tokens: {ERA2_STAMP} → {THIN_HARNESS_STEP_TOKENS}")
```

**pipe_path removal**: similar pattern; detect key presence, warn/remove.

**Protected-path preview**: use `subprocess.run(["git", "log", "--name-only",
"-20", "--pretty=format:"], ...)` to collect recent filenames; cross-reference
with `scope_guard.PROTECTED_GLOBS` via `fnmatch.fnmatch`; print the hits.

**Stale agent hash allowlist**: compute SHA-256 of each known 0.2.x template
render (computed from the Era 2 template + a blank pairmode_context) and store
as a constant dict `_ERA2_AGENT_HASHES: dict[str, str]` keyed by filename stem.

Import `_atomic_write_json` from `state_utils` (already exists from INFRA-200).

## Tests

New `tests/pairmode/test_pairmode_migrate.py` (or extend existing):
- `to-030` with `expected_step_tokens=53000` → rewrites to 5000 (with `--apply`).
- `to-030` with custom `expected_step_tokens=25000` → keeps value, warns.
- `to-030` removes `pipe_path` key (with `--apply`).
- `to-030` seeds missing `state.json` when `.companion/` exists (with `--apply`).
- `to-030` in dry-run mode makes no file changes.
- Stale agent file matching the hash allowlist → deleted (with `--apply`).
- Customized agent file not matching hash allowlist → deferred with diff output.
