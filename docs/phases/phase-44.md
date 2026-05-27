# flex — Phase 44: Fix `sync-agents` silent rendering failure

← [Phase 43: Replace DB-based context budget gate with orchestrator context check](phase-43.md)

## Goal

`sync-agents` is inoperable for any project whose agent templates reference
`build_command`, `test_command`, `domain_isolation_rule`, or `protected_paths` —
which is every agent template flex ships.

**Root cause:** `sync-agents` line 451 builds the Jinja2 context as
`{"project_name": project_name}` — a single key. The rendering functions use
`jinja2.StrictUndefined`, which raises `UndefinedError` for any missing variable.
Every current agent template uses at least one of the four missing variables, so
every render fails. `_collect_changes` catches each `jinja2.TemplateError` and
skips the file with a warning to stderr. With zero surviving changes, the command
prints `"No changes to apply."` — which is false.

`sync-build` correctly calls `_build_template_context()`, which reads all the
needed keys from `pairmode_context.json` and `state.json`. `sync-agents` never
got the equivalent.

**Two fixes:**

1. **Context** — extend `_build_template_context()` to include
   `domain_isolation_rule` and `protected_paths` from `pairmode_context.json`,
   then use it in `sync-agents` instead of the bare single-key dict.

2. **Silent failure** — when rendering errors occur in `_collect_changes`, track
   them and surface them as errors. Exit non-zero if any file was skipped due to
   a rendering failure. "No changes to apply." must only appear when all files
   rendered cleanly and produced no diffs.

**Two stories:**

| ID | Title | Status |
|----|-------|--------|
| INFRA-114 | Fix `sync-agents` to use full template context | complete |
| INFRA-115 | Surface rendering errors instead of silently skipping in `sync-agents` | complete |

**Story dependencies:** INFRA-115 depends on INFRA-114 (they both touch
`_collect_changes` and `sync-agents`; build sequentially).

---

## Stories

### Story INFRA-114 — Fix `sync-agents` to use full template context

**Rail:** INFRA | **story_class:** code

#### Requires

- `skills/pairmode/scripts/pairmode_sync.py` exists with `_build_template_context`
  returning only `project_name`, `build_command`, `test_command`,
  `migration_command`, and `pairmode_scripts_dir`.
- `sync-agents` at line 451 sets `context = {"project_name": project_name}`.
- `_load_pairmode_context` exists and reads `.companion/pairmode_context.json`.

#### Ensures

**`skills/pairmode/scripts/pairmode_sync.py`**

1. `_build_template_context(project_dir)` returns two additional keys:
   - `"domain_isolation_rule"`: `str` — read from
     `pctx.get("domain_isolation_rule") or state.get("domain_isolation_rule") or ""`
   - `"protected_paths"`: `list` — read from
     `pctx.get("protected_paths") or state.get("protected_paths") or []`
   All existing keys (`project_name`, `build_command`, `test_command`,
   `migration_command`, `pairmode_scripts_dir`) are preserved unchanged.

2. In `sync-agents`, the line `context = {"project_name": project_name}` and
   the preceding `project_name = _get_project_name(project_path, state)` are
   replaced with a single call:
   ```python
   context = _build_template_context(project_path)
   ```
   The `state = _load_state(project_path)` call that preceded it is removed from
   `sync-agents` (it is now handled inside `_build_template_context`).

3. No other behaviour of `sync-agents` or `sync-build` changes.

**`tests/pairmode/test_pairmode_sync.py`**

4. Existing `TestBuildTemplateContext` class gains two new test methods:
   - `test_domain_isolation_rule_from_pairmode_context` — write a
     `pairmode_context.json` with `"domain_isolation_rule": "no raw SQL"`;
     assert `_build_template_context` returns `{"domain_isolation_rule": "no raw SQL", ...}`.
   - `test_protected_paths_from_pairmode_context` — write a
     `pairmode_context.json` with `"protected_paths": ["src/core/"]`;
     assert `_build_template_context` returns `{"protected_paths": ["src/core/"], ...}`.

5. A new integration test `test_sync_agents_renders_with_full_context` verifies
   end-to-end that when `.claude/agents/builder.md` exists, a minimal
   `pairmode_context.json` is present, and `sync-agents` is invoked, at least
   one change is detected (i.e. rendering succeeds and the false-negative
   "No changes to apply." is gone). The test uses a real builder template fixture
   or a minimal synthetic template that uses `{{ build_command }}` and
   `{{ protected_paths }}`.

#### Instructions

**`skills/pairmode/scripts/pairmode_sync.py`**

1. In `_build_template_context`, add after the `test_command` line:
   ```python
   "domain_isolation_rule": pctx.get("domain_isolation_rule") or state.get("domain_isolation_rule") or "",
   "protected_paths": pctx.get("protected_paths") or state.get("protected_paths") or [],
   ```

2. In `sync-agents`, replace:
   ```python
   state = _load_state(project_path)
   project_name = _get_project_name(project_path, state)
   context = {"project_name": project_name}
   ```
   with:
   ```python
   context = _build_template_context(project_path)
   ```

**`tests/pairmode/test_pairmode_sync.py`**

Add the two `TestBuildTemplateContext` methods and the integration test as
described in Ensures 4–5. Use `tmp_path` fixtures for all file I/O.

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_pairmode_sync.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

All new tests must pass. Full suite must pass.

---

### Story INFRA-115 — Surface rendering errors instead of silently skipping in `sync-agents`

**Rail:** INFRA | **story_class:** code

#### Requires

- INFRA-114 complete.
- `_collect_changes` in `pairmode_sync.py` currently catches rendering errors
  with `click.echo(f"warning: ...", err=True)` and continues, returning only
  successful changes.
- `sync-agents` prints `"No changes to apply."` when `_collect_changes` returns
  an empty list, regardless of whether that empty list is due to genuine no-diff
  or due to all files failing to render.

#### Ensures

**`skills/pairmode/scripts/pairmode_sync.py`**

1. `_collect_changes` returns a second value: a list of `(filename, error_message)`
   pairs for files that were skipped due to rendering errors. Signature becomes:
   ```python
   def _collect_changes(
       agents_dir, templates_dir, context
   ) -> tuple[list[tuple[Path, str, str]], list[tuple[str, str]]]:
   ```
   The second element is empty when no rendering errors occurred. Warnings
   previously printed to stderr for rendering failures are removed from
   `_collect_changes`; the caller is responsible for reporting them.

2. In `sync-agents`, after calling `_collect_changes`, if `render_errors` is
   non-empty:
   - Print each error to stderr: `"error: failed to render {filename}: {reason}"`
   - If `changes` is also empty (i.e. every file either errored or was skipped
     for other reasons): print `"sync-agents: {N} file(s) failed to render — run
     with --dry-run to debug"` to stderr and exit with code 1.
   - If `changes` is non-empty alongside errors: proceed with the diff/apply
     flow for the successful changes, but also print the render errors to stderr
     before the final summary.

3. `"No changes to apply."` is printed only when `changes` is empty **and**
   `render_errors` is empty — i.e. all eligible files rendered cleanly and
   produced no diffs.

4. The `--dry-run` path is unaffected: it still prints diffs and returns without
   writing; it now also prints any render errors before returning.

5. All existing skip paths (no template found for file, no frontmatter block)
   retain their existing stderr warning behaviour unchanged — only the rendering
   error path changes.

**`tests/pairmode/test_pairmode_sync.py`**

6. `test_sync_agents_exits_nonzero_on_render_failure` — set up a project with
   a synthetic agent file whose template requires an undefined variable (use a
   temporary template file). Invoke `sync-agents` via `CliRunner`. Assert exit
   code is 1 and output contains `"failed to render"`.

7. `test_no_changes_message_only_when_clean` — set up a project where all
   agent files already match their rendered templates. Assert exit code is 0
   and output contains `"No changes to apply."` — confirming it is not printed
   when there are render errors (covered by test 6) or changes (covered by
   existing tests).

#### Instructions

**`skills/pairmode/scripts/pairmode_sync.py`**

1. Change `_collect_changes` to accumulate a `render_errors: list[tuple[str, str]]`
   list (filename, str(exc)) instead of printing to stderr. Return
   `(changes, render_errors)` as a tuple.

2. Update all callers of `_collect_changes` to unpack the tuple. The only caller
   is `sync-agents`.

3. In `sync-agents`, after unpacking, implement the error-reporting logic from
   Ensures 2–4.

**`tests/pairmode/test_pairmode_sync.py`**

Add tests 6–7 as described. For test 6, inject a custom template directory with
a synthetic `.md.j2` file that references `{{ undefined_variable_xyz }}`.

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_pairmode_sync.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

All new tests must pass. Full suite must pass.

---

Tag: `cp44-sync-agents-context-fix`
