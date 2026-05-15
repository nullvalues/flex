# anchor — Phase 33: Build loop portability and sibling catch-up

← [Phase 32: Story-as-contract and story_context CLI](phase-32.md)

## Goal

Phase 32 delivered effort tracking and model selection tuning. After comparing
sibling projects during the Phase 32 post-review, two blocking problems surfaced:

1. **Every script call in `CLAUDE.build.md.j2` uses a relative path**
   (`skills/pairmode/scripts/`) that only resolves when CWD is the anchor repo.
   All four sibling projects (cora, radar, aab, forqsite) have no local `skills/`
   directory, so every `record_attempt.py`, `permission_scope.py`, and
   `story_update.py` call silently fails in sibling builds. Months of build
   activity have produced zero effort data in those projects.

2. **`sync-agents` only re-renders YAML frontmatter** — body sections added to
   agent templates (e.g., `## Contract check` from Phase 32) are never propagated
   to sibling projects.

Three supporting improvements round out the phase:

- `select_reviewer_model` returns only a string (unlike `select_builder_model`,
  which already returns `(model, reason)`). The reason is never captured in
  reviewer records.
- Bootstrap doesn't write standard Bash allow rules, so builders in sibling
  projects prompt for `uv run pytest` on every invocation.
- `pairmode_version` is still `0.1.0` with no staleness signal for projects
  that haven't been synced.

The final story deploys all fixes to cora, radar, aab, and forqsite via
`sync-build --apply` and `sync-agents --yes`.

**Story dependencies:**
- INFRA-083 must build after INFRA-079 (both touch `CLAUDE.build.md` and
  `CLAUDE.build.md.j2`; INFRA-079 introduces `{{ pairmode_scripts_dir }}`
  which INFRA-083's template edits must coexist with).
- INFRA-081 and INFRA-082 are independent and may build in parallel.
- INFRA-080 is independent.
- INFRA-084 must build last (depends on INFRA-079 for correct template,
  INFRA-081 for body propagation, INFRA-082 for Bash allow rules, and
  INFRA-083 for the model reason in reviewer records).

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-079 | Fix relative script paths in `CLAUDE.build.md.j2` | complete |
| INFRA-080 | `pairmode_version` bump to `0.2.0` + outdated signal | planned |
| INFRA-081 | `sync-agents` additive body section propagation | complete |
| INFRA-082 | Bootstrap writes standard Bash allow rules | planned |
| INFRA-083 | `select_reviewer_model` returns `(model, reason)` tuple | complete |
| INFRA-084 | Sibling deployment catch-up | planned |

---

### Story INFRA-079 — Fix relative script paths in `CLAUDE.build.md.j2`

**Rail:** INFRA | **story_class:** code

## Requires
- `CLAUDE.build.md.j2` and `pairmode_sync.py` exist and pass template tests.
- Sibling projects (cora, radar, aab, forqsite) have no local `skills/` directory.

## Ensures
- `pairmode_sync.py`'s `_build_template_context()` returns a `pairmode_scripts_dir`
  key whose value is the absolute path to anchor's scripts directory
  (`str(Path(__file__).parent)`).
- `bootstrap.py`'s context dict includes the same `pairmode_scripts_dir` key
  (`str(pathlib.Path(__file__).parent)`).
- `CLAUDE.build.md.j2` contains no occurrences of the literal string
  `skills/pairmode/scripts` — all 10 actionable occurrences are replaced with
  `{{ pairmode_scripts_dir }}` (the example placeholder on the `primary_files`
  illustration line may also be updated; it is harmless either way).
- Anchor's own `CLAUDE.build.md` is regenerated via
  `pairmode sync-build --apply --yes --project-dir .` so it reflects the new
  absolute paths.
- `tests/pairmode/test_pairmode_sync.py` has a test asserting that the rendered
  build template does not contain the literal string `skills/pairmode/scripts`
  and does contain the absolute scripts path.

**Instructions:**

1. In `skills/pairmode/scripts/pairmode_sync.py`, update `_build_template_context()`:
   ```python
   return {
       "project_name": project_name,
       "build_command": pctx.get("build_command") or state.get("build_command") or "",
       "test_command": pctx.get("test_command") or state.get("test_command") or "",
       "migration_command": pctx.get("migration_command") or state.get("migration_command") or "",
       "pairmode_scripts_dir": str(Path(__file__).parent),
   }
   ```

2. In `skills/pairmode/scripts/bootstrap.py`, add `"pairmode_scripts_dir"` to
   the `context` dict (line ~789 area, near the other build-related keys):
   ```python
   "pairmode_scripts_dir": str(pathlib.Path(__file__).parent),
   ```

3. In `skills/pairmode/templates/CLAUDE.build.md.j2`, replace every occurrence of
   `skills/pairmode/scripts` with `{{ pairmode_scripts_dir }}`. There are 10
   actionable occurrences across these patterns:
   - `sys.path.insert(0, str(Path('skills/pairmode/scripts').resolve()))` →
     `sys.path.insert(0, '{{ pairmode_scripts_dir }}')`
   - `sys.path.insert(0, str(pathlib.Path('skills/pairmode/scripts').resolve()))` →
     `sys.path.insert(0, '{{ pairmode_scripts_dir }}')`
   - `sys.path.insert(0, 'skills/pairmode/scripts')` →
     `sys.path.insert(0, '{{ pairmode_scripts_dir }}')`
   - `uv run python skills/pairmode/scripts/record_attempt.py` →
     `uv run python {{ pairmode_scripts_dir }}/record_attempt.py`
   - `uv run python skills/pairmode/scripts/story_update.py` →
     `uv run python {{ pairmode_scripts_dir }}/story_update.py`

4. Regenerate anchor's own `CLAUDE.build.md`:
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/pairmode_sync.py \
     sync-build --project-dir . --apply --yes
   ```

**Primary files:** `skills/pairmode/templates/CLAUDE.build.md.j2`
**Touches:** `skills/pairmode/scripts/pairmode_sync.py`, `skills/pairmode/scripts/bootstrap.py`,
`CLAUDE.build.md`, `tests/pairmode/test_pairmode_sync.py`

**Tests:**
- `test_pairmode_sync.py`: call `_build_template_context(project_dir)` and assert
  `result["pairmode_scripts_dir"]` is an absolute path ending in
  `skills/pairmode/scripts`.
- `test_pairmode_sync.py`: render the build template and assert the output contains
  no literal `skills/pairmode/scripts` substring and does contain the absolute path.
- Existing `test_templates.py` tests must continue to pass.

---

### Story INFRA-080 — `pairmode_version` bump to `0.2.0` + outdated signal

**Rail:** INFRA | **story_class:** code

## Requires
- `PAIRMODE_VERSION = "0.1.0"` defined in `bootstrap.py` and imported by `sync.py`.
- `pairmode_status.py` reads `state["pairmode_version"]` and displays it.

## Ensures
- `PAIRMODE_VERSION` in `bootstrap.py` is `"0.2.0"`.
- `pairmode status` — when a project's `state["pairmode_version"]` differs from
  `PAIRMODE_VERSION` — prints a one-line hint:
  `Update available: run pairmode sync to update to v{PAIRMODE_VERSION}`.
- `pairmode status` — when the versions match — prints nothing extra (no regression
  in the normal case).

**Instructions:**

1. In `skills/pairmode/scripts/bootstrap.py`, change:
   ```python
   PAIRMODE_VERSION = "0.1.0"
   ```
   to:
   ```python
   PAIRMODE_VERSION = "0.2.0"
   ```

2. In `skills/pairmode/scripts/pairmode_status.py`:
   - At module level (top of file, with other imports), add:
     ```python
     from bootstrap import PAIRMODE_VERSION as _CURRENT_PAIRMODE_VERSION
     ```
   - Inside the `status` function, after the `lines: list[str] = [...]` construction
     (which appends `f"Pairmode v{pairmode_version}"` at index 0) and **before**
     `lines.extend(registered_lines)`, insert:
     ```python
     if pairmode_version != _CURRENT_PAIRMODE_VERSION:
         lines.append(
             f"  Update available: run pairmode sync to update to v{_CURRENT_PAIRMODE_VERSION}"
         )
     ```
     This appends the hint to the `lines` list so it appears below the version line
     in the block output, not as a stray print outside the formatted block.

**Primary files:** `skills/pairmode/scripts/bootstrap.py`
**Touches:** `skills/pairmode/scripts/pairmode_status.py`,
`tests/pairmode/test_pairmode_status.py`

**Tests:**
- `test_pairmode_status.py`: assert that status output for a project with
  `pairmode_version = "0.1.0"` contains the "Update available" hint.
- `test_pairmode_status.py`: assert that status output for a project with
  `pairmode_version = "0.2.0"` does NOT contain the "Update available" hint.

---

### Story INFRA-081 — `sync-agents` additive body section propagation

**Rail:** INFRA | **story_class:** code

## Requires
- `pairmode sync-agents` exists and re-renders agent file frontmatter while
  preserving the body.
- The `## Contract check` section added in Phase 32 is absent from all sibling
  projects' `reviewer.md` because `sync-agents` never propagates body sections.

## Ensures
- `pairmode sync-agents` merges new `## ` (H2) sections from the rendered template
  into the target file body, additively. Sections present in the template but absent
  from the target are appended. Sections already present in the target are left
  untouched.
- `pairmode sync-agents` never removes sections from the target that are absent
  from the template (project-specific body additions are preserved).
- The diff output for `--dry-run` includes the added sections in `+` lines.
- `tests/pairmode/test_pairmode_sync.py` covers the additive merge case.

**Instructions:**

1. Add a helper function `_merge_body_sections(template_body: str, target_body: str) -> str`:
   - Parse `template_body` into sections: split on lines beginning with `## `.
     Each section is `(heading_line, content)`. The leading content before the
     first `## ` heading is the preamble (preserve as-is).
   - Parse `target_body` into sections the same way.
   - Collect the set of heading lines present in the target.
   - For each section in the template that has a heading NOT in the target set:
     append `"\n" + heading_line + content` to the target body.
   - Return the merged target body.

2. In `_collect_changes()`, after building `new_content = new_frontmatter + body`,
   call `_merge_body_sections(template_body, body)` to get the merged body, then
   use `new_content = new_frontmatter + merged_body`. The template body is the
   portion of the rendered template after the closing `---`.

   To extract the template body: after rendering the template with
   `_render_template_frontmatter`, render the full template (not just frontmatter)
   and call `_split_agent_file()` on the result to get its body. This requires
   `_render_full_template(template_path, context) -> str` — add this helper that
   renders without the frontmatter-only extraction step.

3. In `test_pairmode_sync.py`, add:
   - A test where the template body has `## Contract check` and the target body
     does not; assert `_merge_body_sections` appends the section.
   - A test where the target has a project-specific `## Local overrides` section
     not in the template; assert it is preserved.
   - A test where both have `## Contract check`; assert the target version is
     unchanged (no duplication).

**Primary files:** `skills/pairmode/scripts/pairmode_sync.py`
**Touches:** `tests/pairmode/test_pairmode_sync.py`

**Tests:** see above (3 new tests in `test_pairmode_sync.py`).

---

### Story INFRA-082 — Bootstrap writes standard Bash allow rules

**Rail:** INFRA | **story_class:** code

## Requires
- `bootstrap.py` writes `DEFAULT_DENY` entries to `.claude/settings.local.json`
  via `_merge_deny_rules()`.
- No equivalent function exists for `permissions.allow`.

## Ensures
- `bootstrap.py` defines `PAIRMODE_ALLOW` — a list of standard build-tool Bash
  allow rules:
  ```python
  PAIRMODE_ALLOW: list[str] = [
      "Bash(uv run *)",
      "Bash(git *)",
      "Bash(python3 *)",
      "Bash(grep *)",
  ]
  ```
- `bootstrap.py` defines `_merge_allow_rules(settings_path, new_entries)` — same
  structure as `_merge_deny_list` but operates on `permissions.allow`.
- After writing deny rules, `bootstrap.py` calls
  `_merge_allow_rules(settings_path, PAIRMODE_ALLOW)` so every bootstrapped project
  gets the four standard rules without prompting.
- `tests/pairmode/test_bootstrap.py` asserts that after bootstrap, the project's
  `settings.local.json` contains all four `PAIRMODE_ALLOW` entries under
  `permissions.allow`.

**Instructions:**

1. In `skills/pairmode/scripts/bootstrap.py`, add after `DEFAULT_DENY`:
   ```python
   PAIRMODE_ALLOW: list[str] = [
       "Bash(uv run *)",
       "Bash(git *)",
       "Bash(python3 *)",
       "Bash(grep *)",
   ]
   ```

2. Add `_merge_allow_rules(settings_path: pathlib.Path, new_entries: list[str]) -> None`:
   Same implementation as `_merge_deny_list` but operates on `permissions.allow`
   (not `deny`). No glob-subsumption pruning needed — allow rules accumulate.

3. In the bootstrap function, after the existing `_merge_deny_list(...)` call,
   add:
   ```python
   _merge_allow_rules(settings_path, PAIRMODE_ALLOW)
   ```

**Primary files:** `skills/pairmode/scripts/bootstrap.py`
**Touches:** `tests/pairmode/test_bootstrap.py`

**Tests:**
- `test_bootstrap.py`: run bootstrap on a temp project dir; read
  `settings.local.json`; assert all four `PAIRMODE_ALLOW` entries appear in
  `permissions.allow`.
- `test_bootstrap.py`: run bootstrap twice; assert no duplicates in
  `permissions.allow`.

---

### Story INFRA-083 — `select_reviewer_model` returns `(model, reason)` tuple

**Rail:** INFRA | **story_class:** code

## Requires
- INFRA-079 complete: `{{ pairmode_scripts_dir }}` is in the template, so
  this story's template edits coexist with the path fix cleanly.
- `select_builder_model` already returns `tuple[str, str]`.
- `select_reviewer_model`, `select_intent_reviewer_model`,
  `select_security_auditor_model` return `str`.

## Ensures
- `select_reviewer_model` returns `tuple[str, str]` — `(model, reason)`.
  Reason values: `"auto-baseline"` (attempt 1), `"doc-class-baseline"` (doc/lesson
  story class any attempt), `"retry-upgrade"` (code story attempt >= 2),
  `"methodology-upgrade"` (methodology with same-phase code story), `"methodology-baseline"`
  (methodology, no same-phase code story, attempt >= 2).
- `select_intent_reviewer_model` and `select_security_auditor_model` return
  `tuple[str, str]` with the same `(model, reason)` convention.
- `CLAUDE.build.md.j2` reviewer model selection block unpacks the tuple:
  `model, reason = select_reviewer_model(...)` and passes `reason` to the
  reviewer `record_attempt.py` call as `--model-selection-reason $reason`.
- `CLAUDE.build.md.j2` checkpoint security-auditor and intent-reviewer model
  selection blocks unpack the tuple and use `_` for the reason (not passed to
  `record_attempt.py` for checkpoint agents, as those calls don't exist today).
- `CLAUDE.build.md` (anchor's own) is regenerated via `sync-build --apply --yes`
  to reflect the updated template.
- All existing `test_model_selector.py` tests are updated to unpack the returned
  tuples.

**Instructions:**

1. In `skills/pairmode/scripts/model_selector.py`, change `select_reviewer_model`
   return type and all return statements:
   ```python
   def select_reviewer_model(...) -> tuple[str, str]:
       ...
       if attempt_number <= 1:
           return MODEL_SONNET, "auto-baseline"
       if story_class in _ALWAYS_SONNET_CLASSES:
           return MODEL_SONNET, "doc-class-baseline"
       if story_class == "code":
           return MODEL_OPUS, "retry-upgrade"
       # methodology
       if phase_id is not None and project_dir is not None:
           if _phase_has_code_story(phase_id, Path(project_dir)):
               return MODEL_OPUS, "methodology-upgrade"
       return MODEL_SONNET, "methodology-baseline"
   ```

2. Change `select_intent_reviewer_model` and `select_security_auditor_model`
   return types to `tuple[str, str]`. Add a descriptive reason to each return
   statement (e.g., `"production-class"`, `"non-production-class"`).

3. In `skills/pairmode/templates/CLAUDE.build.md.j2`, update the reviewer model
   selection block (around line 284–298) to:
   ```python
   model, reason = select_reviewer_model(
       story_class='code',
       attempt_number=1,
       phase_id='24',
       project_dir=Path('.'),
   )
   print(model)
   print(reason)
   ```
   And update the surrounding prose to say: "The first printed line is the model;
   the second is the selection reason. Pass the model as the `model` parameter
   when spawning the reviewer; pass the reason to `record_attempt.py` as
   `--model-selection-reason`."

4. Update the security-auditor and intent-reviewer model selection blocks in the
   checkpoint sequence section to use `model, _ = select_...(...)` (reason
   discarded; checkpoint agents don't record effort today).

5. Update `record_attempt.py` example call in the reviewer step to include
   `--model-selection-reason $reason` (using the shell variable set from the
   printed reason line).

6. Regenerate anchor's `CLAUDE.build.md`:
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/pairmode_sync.py \
     sync-build --project-dir . --apply --yes
   ```

**Primary files:** `skills/pairmode/scripts/model_selector.py`
**Touches:** `skills/pairmode/templates/CLAUDE.build.md.j2`, `CLAUDE.build.md`,
`tests/pairmode/test_model_selector.py`

**Tests:**
- `test_model_selector.py`: all existing tests updated to unpack `(model, reason)`.
- Assert `select_reviewer_model("code", 1)` returns `(MODEL_SONNET, "auto-baseline")`.
- Assert `select_reviewer_model("code", 2)` returns `(MODEL_OPUS, "retry-upgrade")`.
- Assert `select_reviewer_model("doc", 2)` returns `(MODEL_SONNET, "doc-class-baseline")`.
- Assert `select_intent_reviewer_model(...)` and `select_security_auditor_model(...)`
  return 2-tuples.

---

### Story INFRA-084 — Sibling deployment catch-up

**Rail:** INFRA | **story_class:** methodology

## Requires
- INFRA-079 complete: `CLAUDE.build.md.j2` uses `{{ pairmode_scripts_dir }}`.
- INFRA-081 complete: `sync-agents` propagates new body sections additively.
- INFRA-082 complete: bootstrap writes `PAIRMODE_ALLOW` rules.
- INFRA-083 complete: reviewer model selection outputs `(model, reason)`.
- All four sibling projects accessible at `../cora`, `../radar`, `../aab`,
  `../forqsite` relative to anchor root (`/mnt/work/<sibling>`).

## Ensures
- Each sibling's `CLAUDE.build.md` is updated to the rendered template (with
  absolute `pairmode_scripts_dir` paths), or the diff is reviewed and any
  project-specific sections are preserved by manual adjustment before applying.
- Each sibling's `.claude/agents/reviewer.md` contains the `## Contract check`
  section from Phase 32's INFRA-075.
- Each sibling's `.claude/settings.local.json` contains all four `PAIRMODE_ALLOW`
  Bash allow rules (merged non-destructively — existing rules are preserved).
- A smoke-test `record_attempt.py` call succeeds on at least one sibling (exits 0,
  writes an entry to that sibling's `effort.db`).
- Changes to each sibling are committed in that sibling's repo with message
  `chore(pairmode): sync-build and sync-agents from anchor v0.2.0`.

**Instructions:**

This is a deployment story. The orchestrator performs the steps directly — no
builder subagent needed.

For each sibling in `[/mnt/work/cora, /mnt/work/radar, /mnt/work/aab, /mnt/work/forqsite]`:

**Step A — sync-build:**

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/pairmode_sync.py \
  sync-build --dry-run --project-dir /mnt/work/<sibling>
```

Review the diff. If the sibling's `CLAUDE.build.md` has project-specific sections
(content beyond what the template renders), note them. For forqsite specifically:
the file is 693 lines vs ~563 for the rendered template — inspect the extra content
before applying.

If safe to apply:
```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/pairmode_sync.py \
  sync-build --apply --yes --project-dir /mnt/work/<sibling>
```

If the sibling has project-specific additions that should be preserved:
apply the template, then manually re-add the project-specific sections, then
commit.

**Step B — sync-agents:**

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/pairmode_sync.py \
  sync-agents --project-dir /mnt/work/<sibling> --yes
```

Verify the sibling's `.claude/agents/reviewer.md` now contains `## Contract check`.

**Step C — Bash allow rules:**

```bash
PATH=$HOME/.local/bin:$PATH uv run python -c "
import sys, pathlib
sys.path.insert(0, '/mnt/work/anchor/skills/pairmode/scripts')
from bootstrap import PAIRMODE_ALLOW, _merge_allow_rules
_merge_allow_rules(
    pathlib.Path('/mnt/work/<sibling>/.claude/settings.local.json'),
    PAIRMODE_ALLOW,
)
print('allow rules applied')
"
```

**Step D — smoke test record_attempt:**

Pick a story file that exists in the sibling:
```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/record_attempt.py \
  --story-file /mnt/work/<sibling>/docs/stories/<RAIL>/<RAIL>-001.md \
  --agent-role builder \
  --model claude-sonnet-4-6 \
  --attempt-number 99 \
  --tokens-total 1 \
  --tool-uses 1 \
  --duration-ms 1 \
  --outcome PASS \
  --project-dir /mnt/work/<sibling>
```

Confirm exit 0 and that `.companion/effort.db` in the sibling is updated.

**Step E — commit each sibling:**

In each sibling's directory:
```bash
git add CLAUDE.build.md .claude/agents/reviewer.md .claude/settings.local.json
git commit -m "chore(pairmode): sync-build and sync-agents from anchor v0.2.0"
```

**Primary files:** (none — orchestrator-only deployment story)
**Touches:** `/mnt/work/cora/CLAUDE.build.md`, `/mnt/work/radar/CLAUDE.build.md`,
`/mnt/work/aab/CLAUDE.build.md`, `/mnt/work/forqsite/CLAUDE.build.md`,
`/mnt/work/cora/.claude/agents/reviewer.md`,
`/mnt/work/radar/.claude/agents/reviewer.md`,
`/mnt/work/aab/.claude/agents/reviewer.md`,
`/mnt/work/forqsite/.claude/agents/reviewer.md`,
`/mnt/work/cora/.claude/settings.local.json`,
`/mnt/work/radar/.claude/settings.local.json`,
`/mnt/work/aab/.claude/settings.local.json`,
`/mnt/work/forqsite/.claude/settings.local.json`

**Tests:** Methodology story — no test file expected. Verify by:
- Confirming `## Contract check` present in each sibling's `reviewer.md`.
- Confirming the sibling's `CLAUDE.build.md` contains the absolute path
  (e.g., `/mnt/work/anchor/skills/pairmode/scripts/record_attempt.py`).
- Confirming the smoke-test `record_attempt.py` call exits 0.

---

Tag: `cp33-build-loop-portability`
