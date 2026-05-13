# anchor — Phase 31: Discoverability and status panel

← [Phase 30: Hook security fix and sync tooling gaps](phase-30.md)

## Goal

Make the Phase 29/30 tooling actually usable day-to-day. Three gaps:

1. **SKILL.md is stale** — `drift-report`, `sync-build`, and `register/unregister/list-projects`
   shipped in Phases 29–30 but have no SKILL.md entries. A user reading SKILL.md cannot
   discover them.

2. **`pairmode status` is blind to registered projects** — the status panel shows era, story,
   and modules but says nothing about whether drift tracking is configured or how many
   projects are registered.

3. **Bootstrap gives no next-steps** — after a successful bootstrap the user is dropped back
   at a prompt with no guidance on the next actions (register with anchor, set a story,
   run audit). The dogfooding loop requires knowing to run `pairmode register` after
   bootstrapping; nothing surfaces that today.

These three are independent and can be built in any order.

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-071 | SKILL.md currency — document drift-report, sync-build, register/unregister/list-projects | complete |
| INFRA-072 | `pairmode status` registered-projects panel | complete |
| INFRA-073 | Bootstrap post-completion next-steps | complete |

---

### Story INFRA-071 — SKILL.md currency

**Rail:** INFRA | **story_class:** doc

**Acceptance criterion:** `skills/pairmode/SKILL.md` has complete command entries for every
subcommand shipped in Phases 29–30. Specifically:

- A `### /anchor:pairmode drift-report` section documenting when to use it, inputs, what
  it does, output format, and CLI invocation with all flags (`--projects`, `--convergent`,
  `--output`).
- A `### /anchor:pairmode sync-build` section documenting `--project-dir`, `--dry-run`,
  `--apply`, `--yes`, and the confirmation behavior.
- A `### /anchor:pairmode register` section documenting `register`, `unregister`, and
  `list-projects` as a group (they form one workflow).
- A `## Drift detection workflow` section near the end of SKILL.md that narrates the
  end-to-end sequence: bootstrap a project → register it with anchor → run `drift-report`
  → run `review` to promote convergence candidates → `sync-build` to apply template
  improvements back to projects.

**Instructions:**

1. Read `skills/pairmode/scripts/pairmode_drift_report.py`, `pairmode_sync.py` (sync-build),
   and `pairmode_register.py` to extract the accurate CLI flags, behavior, and output formats
   before writing.

2. Add each section in the same format as existing SKILL.md sections: When to use, Inputs,
   What it does, Output format (where applicable), CLI invocation, Flags.

3. Add the `## Drift detection workflow` section after the existing command sections, before
   any trailing notes. Keep it concise — 8–15 lines of prose with one code block showing
   the sequence of commands.

4. No changes to any Python script or test file.

**Primary files:** `skills/pairmode/SKILL.md`
**Touches:** *(none)*

**Tests:** Documentation story — no test file expected. Verify by reading the written sections
and confirming flag lists match the Click decorators in the referenced scripts.

---

### Story INFRA-072 — `pairmode status` registered-projects panel

**Rail:** INFRA | **story_class:** code

**Acceptance criterion:** `pairmode status` output gains a `Registered` line showing the count
of projects in `registered_projects`. When one or more projects are registered, a drift hint
line is also shown. When none are registered, neither line appears (no visual clutter for
projects that haven't opted into drift tracking).

Example output with two registered projects:
```
Pairmode v0.1.0
───────────────────────────────────
Era:        001 — Initial
Story:      INFRA-072 [planned]
Modules:    pairmode-skill, docs
Registered: 2 project(s)
  Drift:    run pairmode drift-report --projects <paths> to check
───────────────────────────────────
Companion sidebar: not detected
  To start: ...
```

Example output with no registered projects (no change from current):
```
Pairmode v0.1.0
───────────────────────────────────
Era:        001 — Initial
Story:      INFRA-072 [planned]
Modules:    pairmode-skill, docs
───────────────────────────────────
Companion sidebar: not detected
```

**Instructions:**

1. In `skills/pairmode/scripts/pairmode_status.py`:
   - After the `modules_line`, read `state.get("registered_projects", [])`.
   - If the list is non-empty, append a `Registered: N project(s)` line to the output
     block, followed by a `  Drift:    run pairmode drift-report ...` hint line.
   - If the list is empty or absent, append nothing.
   - The `--projects` hint in the drift line should show the actual registered paths,
     space-separated (truncate to first 2 if more than 2, appending `...`).

2. No changes to `docs/architecture.md` needed — the `registered_projects` key is
   already documented there (INFRA-070).

**Primary files:** `skills/pairmode/scripts/pairmode_status.py`
**Touches:** `tests/pairmode/test_pairmode_status.py`

**Tests:** `tests/pairmode/test_pairmode_status.py` — add tests asserting:
- Status output includes `Registered: 2 project(s)` when state has two paths.
- Drift hint line appears and contains the registered paths.
- When `registered_projects` is absent or empty, neither line appears.
- When more than 2 projects registered, hint truncates to first 2 with `...`.

---

### Story INFRA-073 — Bootstrap post-completion next-steps

**Rail:** INFRA | **story_class:** code

**Acceptance criterion:** After a successful `pairmode bootstrap` run, the output ends with a
`## Next steps` block that lists the recommended follow-on actions. The block is always
printed on success — it does not require `--verbose` or any flag. It is not printed on
`--dry-run`.

Example block:
```
## Next steps

  1. Set your current story:
       uv run python skills/pairmode/scripts/story_context.py --set RAIL-001

  2. Register this project with anchor for drift tracking:
       cd <anchor-root>
       uv run python skills/pairmode/scripts/pairmode_sync.py register \
         --project-dir <bootstrapped-project-dir>

  3. Run an audit to verify the scaffold:
       uv run python skills/pairmode/scripts/audit.py --project-dir <project-dir>
```

The `<bootstrapped-project-dir>` placeholder is replaced with the actual resolved project
path. The `<anchor-root>` placeholder is replaced with `Path(__file__).resolve().parent`
evaluated up to the anchor repo root (four levels from `bootstrap.py`).

**Instructions:**

1. In `skills/pairmode/scripts/bootstrap.py`, find the location where a successful
   bootstrap prints its completion summary (the final `click.echo` or equivalent at the
   end of the main bootstrap flow).

2. After that summary, print the next-steps block. Use `click.echo` with a leading blank
   line. Substitute the actual `project_dir` resolved path and anchor root into the
   block text.

3. Guard the block: do not print it when `--dry-run` is active. Print it on all other
   successful completions (fresh bootstrap and re-bootstrap alike).

4. No changes to templates or architecture docs needed for this story.

**Primary files:** `skills/pairmode/scripts/bootstrap.py`
**Touches:** `tests/pairmode/test_bootstrap.py`

**Tests:** `tests/pairmode/test_bootstrap.py` — add tests asserting:
- Bootstrap success output contains "## Next steps".
- Output contains the actual resolved project path (not the placeholder).
- `--dry-run` output does NOT contain "## Next steps".

---

Tag: `cp31-discoverability-and-status`
