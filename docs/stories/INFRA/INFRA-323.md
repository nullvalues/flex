---
id: INFRA-323
rail: INFRA
title: "Session-lifecycle notices for agent-registration writes: RESTART REQUIRED after bootstrap/migrate/sync, runbook steps, SessionStart staleness advisory"
status: complete
phase: "114"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/session_lifecycle.py
  - skills/pairmode/scripts/bootstrap.py
touches:
  - skills/pairmode/scripts/pairmode_sync.py
  - skills/pairmode/scripts/pairmode_migrate.py
  - hooks/session_start.py
  - skills/pairmode/SKILL.md
  - docs/harness-cutover-runbook.md
  - docs/architecture.md
  - tests/pairmode/test_session_lifecycle.py
  - tests/pairmode/test_bootstrap.py
  - tests/pairmode/test_pairmode_sync.py
  - tests/pairmode/test_pairmode_migrate.py
  - tests/pairmode/test_session_start_hook.py
  - docs/cer/backlog.md
  - docs/phases/phase-114.md
  - docs/stories/INFRA/INFRA-323.md
  - tests/pairmode/test_user_turn_seq.py
  - skills/pairmode/skills/security-auditor/procedure.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

<!-- SPEC-WRITER NOTE (frontmatter): both lists are written **block-style**, not
     flow-style — per RELEASE-066 new-2 / CER-115, `primary_files: [a, b]` parses
     as a *string* in the frontmatter reader and crashes
     `create-story-worktree`'s `generate_permissions_artifact` with a
     `TypeError`. Do not "tidy" these into flow style.
     `docs/cer/backlog.md`, `docs/phases/phase-114.md` and this file are
     STANDING surfaces post-INFRA-320 (`scope_guard.STANDING_SURFACES`) and no
     longer need declaring; they are listed anyway so the story reads correctly
     if it is built from a checkout that predates INFRA-320's merge.
     `hooks/session_start.py` is a PROTECTED path
     (`scope_guard.PROTECTED_GLOBS` = `hooks/**`, `scope_guard.py:32-40`) and is
     therefore satisfiable *only* by this explicit `touches:` entry plus a valid
     permissions artifact (INFRA-253). The declaration is deliberate; see § F. -->

## Context

**Pulled from CER-134** (`docs/cer/backlog.md`, operator report 2026-07-29,
bootstrap session lifecycle), a mid-phase addition to Phase 114 by operator
direction rather than from the era-004 closeout reconciliation.

Claude Code reads `.claude/agents/*.md` agent definitions — and plugin/skill
registrations, and `hooks` blocks in `.claude/settings*.json` — **at session
start**. Every pairmode tooling path that installs or updates those surfaces
writes them **mid-session**:

- `bootstrap.py` renders seven agent shells from `AGENT_FILES`
  (`bootstrap.py:85-92`, written at `:1374-1391`), registers four hook events
  into `.claude/settings.json` (`:1440-1444`), merges allow rules into
  `.claude/settings.local.json` (`:1449-1453`), then prints `Done.` (`:1501`)
  and three "Next steps" (`_print_next_steps`, `:704-722`).
- `pairmode_sync.py sync-agents` rewrites agent-shell frontmatter in place
  (`:797-799`), `sync-all` invokes it as step 2 of three (`:1069-1076`), and
  `audit-hooks --apply` rewrites the `hooks` blocks of both settings files
  (`:1320-1323`).
- `pairmode_migrate.py`'s rule 2 delegates to `sync-agents`
  (`:104-110`, `_apply_subprocess_rule`'s handler branch `:458-482`) and rule 3
  regex-substitutes agent-shell **bodies** (`:111-115`); `to-030`'s B7 step
  deletes or flags agent shells (`:1108-1156`) and then prints
  `to-030 complete.` (`:1158`).

In the very session that just bootstrapped or migrated a repo, none of those
writes are in effect. The running process holds the registry it loaded at
startup. So the operator's next action — spawn a builder, spawn a reviewer,
verify that the new `gate-worker` agent exists — either falls back to
`general-purpose` or fails outright, and the operator's only available
conclusion is *the bootstrap failed*. It did not; it just is not loaded.

**Nothing in the codebase says so.** A grep for `restart`, `new session`, or
`exit the session` across `bootstrap.py`, `pairmode_sync.py`, `sync.py`,
`pairmode_migrate.py`, `hooks/session_start.py`, `skills/pairmode/SKILL.md`,
`docs/harness-cutover-runbook.md` and `docs/pairmode/PAIRMODE.md` returns
exactly one hit, and it is unrelated (`PAIRMODE.md:136`, a sentence about
lessons surviving "agent restarts"). Not one of the three completion outputs
mentions the session boundary. `_print_next_steps` sends the operator straight
into `story_new.py` → `story_context.py` → `audit.py` — all correct, all
runnable in the stale session, and none of which exercise the agent registry,
so the scaffold looks healthy right up to the first spawn.

**`/clear` does not fix it, which is the trap.** The mental model most
operators carry is that `/clear` starts a session. It resets the context window
inside the same process; the agent registry is untouched. `hooks/session_start.py`
fires on `source="clear"` and prints a reassuring status block
(`Pairmode v0.3.0 is active in this repo.` — `:168`) that is true about
`state.json` and silent about registration. A full exit and relaunch is
required.

**The forcing function is imminent.** RELEASE-068 (phase 106, specced
2026-07-29 at `e7439fbf`) performs a canon-only migration of `/mnt/work/Repo-K`
that **creates `gate-worker.md` and rewrites seven agent shells** via
`sync-all --apply` (its step 4), then verifies at step 6 that "seven files
present, sampled pruned headers absent, stale grammar clean". Every one of
those checks is a *file* check, which passes in the stale session — so the
migration will be recorded as verified while the repo's agents are, for that
session, not registered. Its spec had no restart step; a dated one-line
post-spec addendum was added to `RELEASE-068.md` § *Instructions* at this
story's spec time (see § Out of scope).

**Why this is a tooling defect and not an operator-education problem.** The
pattern is CER-067's inverse. CER-067 was a gate that could not be cleared, so
operators routed around it. This is a *silent* precondition with no surface at
all: the tool knows exactly when it has written a registration surface, and says
nothing, so the operator is required to know a Claude Code implementation detail
in order to interpret a successful run. Fleet-wide, the cost is one confused
post-bootstrap debugging session per new repo and per migration.

## Requires

Re-verified against the working tree at spec time (2026-07-29, `main` @
`2586ad4c`). A builder finding an anchor moved should re-locate by symbol name,
not line number, and note the drift in its report.

- `bootstrap.AGENT_FILES` (`bootstrap.py:85-92`) — the seven
  `(dest_rel, template_name)` pairs. The write loop (`:1374-1391`) has three
  outcomes per file: `skipped (project-owned)` when the file exists and
  `--force-agents` is absent, an unconditional overwrite under
  `--force-agents`, and `_write_file` otherwise. Only the second and third
  change the registry.
- `bootstrap._print_next_steps` (`:704-722`) — called once, guarded by
  `if not dry_run` (`:1503-1505`), after the `Done.` line (`:1501`).
- `bootstrap._register_pretooluse_hook` / `_register_context_budget_hooks`
  (called `:1443-1444`) and `_merge_allow_rules` (`:1453`) — the settings-side
  registration writes. `_register_context_budget_hooks` already skips entries an
  installed plugin's `hooks.json` covers (`:596-616`).
- `pairmode_sync.sync_agents` (`:746-799`) — early-returns
  `No changes to apply.` at `:775-778` when `_collect_changes` is empty; writes
  and prints `  updated: {name}` per file at `:795-799`; returns without writing
  under `--dry-run` (`:783-784`) or a declined confirm (`:788-791`).
- `pairmode_sync.sync_all` (`:1008-1097`) — fixed order
  `sync.py` → `sync-agents` → `sync-build`, each a `subprocess.run` whose
  stdout is inherited (`:1090`); fail-fast on non-zero (`:1091-1096`). It
  cannot see *what* a child changed, only its exit status — see § D2.
- `pairmode_sync.audit_hooks` (`:1161-1327`) — in apply mode rewrites both
  settings files unconditionally at `:1320-1323` after printing `kept:` /
  `removed:` lines.
- `pairmode_migrate.MIGRATION_RULES` rules 2 and 3 (`:104-115`) and
  `_apply_subprocess_rule`'s `sync-agents` branch (`:458-482`), which invokes
  `pairmode_sync sync-agents --apply --yes` and captures its output.
- `pairmode_migrate._print_report` (`:691-725`) — the `--- Migration Summary ---`
  block; `report.changed` is the authoritative changed-file list.
- `pairmode_migrate.cmd_to_030`'s B7 agent-cleanup block (`:1108-1156`) and the
  closing `to-030 complete.` (`:1158`).
- `hooks/session_start.py` — thin dispatcher. Reads `.companion/state.json`
  once (`:68-70`), returns silently when `pairmode_version` is absent
  (`:72-74`), delegates the reset decision to `session_reset.decide_reset`,
  performs **one** locked state write via `state_utils.update_state_json`
  (`:120`), builds a `lines` list (`:168-194`) and prints it as
  `hookSpecificOutput.additionalContext` (`:196-203`). `reset_notice`
  (`:126-131`) is the existing precedent for an extra advisory line.
- `session_state.session_view` / `apply_session_view` / `prune_stale_sessions`
  (`session_state.py:167`, `:194`, `:233`) — the per-session entry accessors
  (INFRA-285/CER-097). `session_view` falls back to the flat mirror when the
  `session_id` has no entry.
- `scope_guard.PROTECTED_GLOBS` (`scope_guard.py:32-40`) — includes
  `hooks/**`, `.claude/settings.json`, `.claude/settings.local.json`. Protected
  paths fail closed and are satisfiable only from a story's permissions
  artifact.
- `docs/ideology.md` § *Hooks are thin relays only* (`:113-121`) and
  § *Single-writer state* (`:126-130`); `docs/architecture.md:27` (the
  `session_start.py` dispatcher line), `:2457` (**Non-negotiable: hooks are thin
  relays**), `:2523`, `:2698`.
- `skills/pairmode/SKILL.md` § `bootstrap` (`:21-144`), § `sync` (`:225`),
  § `sync-agents` (`:689`), § `sync-all` (`:826`),
  § `migrate-from-anchor` (`:947`).
- `docs/harness-cutover-runbook.md` § *Per-project mechanic* (`:232`),
  § *6-step Era 3 procedure* (`:240`), § *What `sync-all` does* (`:307`),
  § *Context at sync time* (`:325`), § *Rollback procedure* (`:295`).


## Scope widenings

| path | reason | widened_at |
| --- | --- | --- |
| tests/pairmode/test_user_turn_seq.py | INFRA-323 legitimately edits hooks/session_start.py per its declared touches:; test_user_turn_seq.py's blanket 'hooks/ must be git-clean' guard (from an unrelated earlier story, INFRA-248) is a stale invariant that trips on any future authorized hook change and must be retired, not silenced. | 2026-07-31T01:56:43Z |

| skills/pairmode/skills/security-auditor/procedure.md | hooks/session_start.py now imports session_lifecycle (INFRA-323 § F); the security-auditor's documented thin-delegation exception block must name it or the drift check (test_procedure_skills.py) fails. | 2026-07-31T01:57:00Z |
## Ensures

### A — one notice, defined once, in a new pure module

1. A new module `skills/pairmode/scripts/session_lifecycle.py` exists and is
   **stdlib-only** (no `click`, no `jinja2`, no project imports beyond
   `state_utils`/`session_state` where § F requires them). It is importable by
   both a `click` CLI and a hook.
2. It exposes `RESTART_SURFACES: dict[str, str]` — a mapping of surface keys to
   one-line human descriptions, covering at minimum
   `agent_shells` (`.claude/agents/*.md` — subagent definitions),
   `hook_registration` (`.claude/settings.json` / `settings.local.json` `hooks`
   blocks), and `plugin_skills` (plugin/skill registration files, when a path a
   caller reports falls under `.claude-plugin/` or a `SKILL.md`).
3. It exposes `render_restart_notice(changed: Sequence[str], *, project_dir: str
   | None = None, action: str) -> str` — a pure function returning the notice
   text. It performs **no I/O**, resolves no paths, and never calls
   `click.echo`. Given an empty `changed` sequence it returns `""` (the
   no-op-run contract, § D1).
4. The rendered notice satisfies all of:
   - it opens with a single unmissable banner line containing the exact literal
     `RESTART REQUIRED` in upper case;
   - it names the *action* that wrote (`bootstrap`, `sync-agents`, `sync-all`,
     `migrate`, `to-030`, `audit-hooks`);
   - it **enumerates the changed surfaces** — one line per changed path or
     surface group, not a vague "some files changed";
   - it states the reason in one sentence: Claude Code loads agent definitions
     and hook registrations at session start, so the files just written are not
     in effect in this session;
   - it states the required action explicitly — **exit the session and start a
     new one** — and states that `/clear` and `/compact` are **not** sufficient;
   - it is the **last** thing the command prints, so a long scrollback cannot
     bury it.
5. `render_restart_notice` is the single definition. `grep -c "RESTART REQUIRED"`
   over `skills/` and `hooks/` finds the literal in `session_lifecycle.py` and
   in test files only — no call site re-renders or paraphrases its own banner.
6. It exposes `stamp_agent_surfaces(state: dict, *, changed: Sequence[str],
   action: str, now: str | None = None) -> None` — a pure in-place mutator that
   writes two keys into the passed state dict:
   `agent_surfaces_written_at` (ISO-8601 UTC, `session_state`'s existing
   timestamp format) and `agent_surfaces_written_by` (the action string). It
   performs no file I/O; callers own the write. Absent `changed`, it mutates
   nothing.

### B — bootstrap ends with the notice

7. A completed non-dry-run `bootstrap` prints the § A notice **after**
   `_print_next_steps`, as the final output of the command.
8. The `changed` list the notice enumerates is built from what bootstrap
   *actually wrote*: agent shells whose write was performed (`_write_file`
   or the `--force-agents` overwrite), **excluding** every file that took the
   `skipped (project-owned)` branch; plus `hook_registration` when the
   settings-level registration ran.
9. `--dry-run` prints **no** notice — it prints the existing
   `Dry run complete.` line and nothing about restarting. A dry run changed no
   registration surface.
10. A re-bootstrap of an already-bootstrapped project in which every agent shell
    took the `skipped (project-owned)` branch and no settings entry was added
    prints no notice (§ D1's no-op contract), and a test asserts this.
11. Bootstrap writes the § A6 stamp into the **target project's**
    `.companion/state.json`, folded into the existing `_record_state` write
    (`bootstrap.py:1405+`) — no second write of that file, and no new file.
12. `_print_next_steps`' three existing steps are unchanged in wording and
    order. The notice is additive.

### C — migrate ends with the notice

13. `pairmode_migrate migrate --apply` prints the § A notice after
    `_print_report`, as the command's final output, whenever
    `report.changed` includes any `.claude/agents/*.md` path (rule 2 or rule 3)
    or any settings file. Without `--apply` (report-only), no notice.
14. `pairmode_migrate to-030 --apply` prints the § A notice after
    `to-030 complete.` whenever its B7 block deleted an agent shell, or the
    delegated `sync-agents` invocation reported updates. A `to-030` run whose
    agent-cleanup only *flagged* files for manual porting (the
    `_ERA2_AGENT_HASHES`-empty path, `:1136-1155`) changed nothing and prints
    no notice.
15. The `already_migrated` early return (`_print_report:693-695`) prints no
    notice.
16. `migrate`'s idempotency-gate output and rule ordering are unchanged.

### D — sync paths print the notice only when something changed

17. **No-op runs stay quiet.** `sync-agents` that prints
    `No changes to apply.` (`:775-778`), any `--dry-run` invocation, and a
    declined confirmation prompt (`:788-791`) all print no notice. Notice
    fatigue is the failure mode this guards: a banner on every sync teaches
    operators to skip it, which is CER-067's lesson applied to output rather
    than to gates.
18. `sync-agents` that wrote at least one file prints the § A notice as its
    final output, enumerating the files from its own `changes` list.
19. `sync-all --apply` prints **one** notice at the end of the chain rather than
    one per child. Because `sync_all` sees only child exit codes
    (`:1090-1096`), the aggregation mechanism must be explicit: the child
    commands write the § A6 stamp into the project's `state.json`, and
    `sync_all` reads that stamp back after the chain to decide whether to print
    and what to enumerate. A child's inherited stdout is **not** parsed — no
    output scraping.
20. `sync.py`'s own methodology-file sync (invoked as chain step 1) is treated
    as a registration surface **only** when the files it wrote include an agent
    shell or a `SKILL.md`; a `CLAUDE.md`-only sync is not a restart trigger.
21. `audit-hooks --apply` that rewrote a settings `hooks` block
    (`:1320-1323`) prints the § A notice naming `hook_registration`; a dry-run
    audit does not.
22. `sync-build` alone (`CLAUDE.build.md` only) prints no notice — that file is
    read per build-loop invocation, not at session start. A test asserts this
    negative, so a future widening cannot silently make every sync noisy.

### E — the restart step is written into the docs an operator actually follows

23. `skills/pairmode/SKILL.md` § `/flex:pairmode bootstrap` gains an explicit
    post-bootstrap restart step, stated before the flag list, in the same
    imperative voice as the surrounding steps.
24. `SKILL.md` § `sync-agents`, § `sync-all` and § `migrate-from-anchor` each
    gain the same restart step, and § `sync` names the agent-shell/`SKILL.md`
    condition from § D20 rather than asserting a blanket restart.
25. `docs/harness-cutover-runbook.md` § *6-step Era 3 procedure* gains the
    restart as an explicit numbered step positioned **after** the sync/migrate
    steps and **before** any step that verifies or exercises agents; § *What
    `sync-all` does* records that step 2 mutates a session-start-only surface.
26. `docs/architecture.md` gains a short subsection recording the
    session-lifecycle contract: which surfaces are session-start-only, which
    tooling paths write them, that the notice is the operator surface, and that
    a `/clear` is not a re-registration. It is cross-referenced from the
    `session_start.py` dispatcher line (`:27`).
27. No doc claims the tooling can restart the session (§ Out of scope R1).

### F — SessionStart staleness advisory (thin, pure read, fail-silent)

28. `session_lifecycle` exposes
    `agent_staleness_notice(*, source: str | None, session_started_at: str |
    None, written_at: str | None, written_by: str | None) -> str | None` — a
    **pure** function, no I/O, no clock read beyond parsing its arguments.
29. It returns a one-line advisory **only** when all of:
    `source in {"clear", "compact"}`; both timestamps parse; and
    `written_at > session_started_at`. In every other case it returns `None`.
    The `startup` and `resume` sources are excluded on the record: both are a
    fresh CLI process, which re-reads the registry, so a warning there would be
    false. This asymmetry is the whole reason the check is worth having — the
    only session boundary that does *not* re-register is the one operators
    believe does.
30. The advisory text names the writing action, the write time, and the required
    exit-and-restart; it does **not** contain the § A4 banner (it is a
    context line in a status block, not a command's terminal output).
31. `hooks/session_start.py`'s diff is confined to: one import, one call to
    `agent_staleness_notice` with values already in hand — `source` from the
    payload, `written_at`/`written_by` from the state dict read at `:68-70`
    **before** the mutation, and `session_started_at` from
    `session_state.session_view(state, session_id)`'s reset timestamp, also read
    pre-mutation — and one conditional `lines.append(...)`, placed immediately
    after the existing `reset_notice` append (`:169-170`).
32. The hook performs **no additional state write**. The existing single locked
    `update_state_json` call (`:120`) is unchanged, `prune_stale_sessions`
    behaviour is unchanged, and the INFRA-175 acceptance criterion that a
    non-reset source leaves `state.json` byte-identical still holds. A test
    asserts the file's mtime/content is untouched by a `clear` invocation that
    emits the advisory.
33. The advisory is wrapped so that any exception — missing keys, unparseable
    timestamps, an import failure — yields no line and never affects the hook's
    exit status or the rest of the status block, matching the existing
    best-effort `try/except` style (`:132-134`, `:165-166`).
34. The state keys the advisory reads have a **writer** (§ A6/B11/D19) and the
    keys written have a **reader** (this hook) — neither half is landed alone.
    A test asserts the round trip: a `sync-agents` run stamps the keys, and a
    subsequent `clear`-sourced hook invocation emits the advisory.
35. `.claude/agents/*.md` **mtime comparison is not the signal.** It is used at
    most as a fallback when the stamp is absent (repos whose last agent write
    predates this story), it never overrides a present stamp, and the fallback
    is documented as advisory: a `git checkout`, a worktree creation, or an
    `rsync` rewrites mtimes without changing content, so mtime alone would
    produce false advisories. If the builder judges the fallback not worth its
    false-positive rate, omitting it is acceptable **provided** the omission is
    recorded in the story's completion notes; the stamp path is not optional.

### G — backlog and phase records

36. `docs/cer/backlog.md`'s CER-134 row gains a
    `**RESOLVED Phase 114 — INFRA-323: …**` annotation, marker-first per the
    grammar INFRA-322 publishes in this same phase, replacing the
    absorbed-at-spec-time sentence.
37. `docs/phases/phase-114.md`'s Stories table row for INFRA-323 moves to
    `complete`.

### H — tests

38. Every Ensure above with an observable outcome has a test. Notice-emitting
    paths are asserted on the presence of the `RESTART REQUIRED` literal **and**
    on the enumerated surface names; every negative (§ B9, B10, C15, D17, D21
    dry-run, D22) asserts the literal is **absent** from the captured output.
39. The suite passes with no `-x`, per the standing repo lesson that `-x` masks
    a later real failure behind a known one.

## Instructions

1. **Read first.** `docs/ideology.md` § *Hooks are thin relays only* and
   § *Single-writer state*; `docs/architecture.md:2457-2530` and `:2698`. § F is
   deliberately the smallest hook diff that can carry the signal, and the reason
   is in those two sections. If the hook change starts growing a second state
   write or a directory scan of its own, stop and re-read them.
2. **Write `session_lifecycle.py` first, with its tests, before touching a
   single caller.** Five call sites will import it; a signature discovered late
   costs five edits. It is pure — `render_restart_notice`,
   `stamp_agent_surfaces` and `agent_staleness_notice` should be testable with
   dicts and strings only.
3. **Wire `bootstrap.py`.** Accumulate the written-surface list where the writes
   happen (the `AGENT_FILES` loop at `:1374-1391` — append only on the branches
   that actually wrote, never on `skipped (project-owned)`; the settings
   registration at `:1440-1444`). Fold the § A6 stamp into `_record_state`'s
   existing write. Emit the notice after `_print_next_steps` inside the existing
   `if not dry_run` guard.
4. **Wire `pairmode_sync.py`.** `sync_agents` already has the exact list it
   needs (`changes`) — stamp and emit after the write loop. `audit_hooks`
   emits after its settings write. `sync_all` reads the stamp back after the
   chain completes and emits once. Do **not** parse child stdout: children
   inherit stdout by design (`:1090`), and re-capturing it to scrape a notice
   would break the live-output behaviour the runbook depends on.
5. **Wire `pairmode_migrate.py`.** `migrate` filters `report.changed` for agent
   and settings paths; `to-030` tracks whether B7 deleted anything and whether
   the delegated `sync-agents` (`:458-482`) reported updates. Emit after each
   command's existing closing line.
6. **Then the hook (§ F), last and smallest.** One import, one call, one
   conditional append, inside the existing best-effort try/except discipline.
   The values it needs are already read at `:68-70` and via
   `session_state.session_view`; do not add a second read of `state.json` and do
   not add a filesystem scan in the hook — if the § A35 mtime fallback is
   implemented, it lives in `session_lifecycle` behind an explicitly passed-in
   path list, so the hook's contribution stays a function call.
7. **Docs (§ E).** SKILL.md's four command sections, the runbook's 6-step
   mechanic, and one architecture subsection. Keep the wording identical across
   surfaces — this is a single contract stated in four places, and a paraphrase
   in one of them is how the next drift starts.
8. **Sibling coordination — read before the first edit.** Four same-phase
   stories overlap this story's files and none of them may be reverted or
   re-formatted by it:
   - **INFRA-319** holds `bootstrap.py` and `pairmode_migrate.py` as
     `primary_files` and `pairmode_sync.py`/`sync.py` in `touches` — the largest
     overlap in the phase. It rewrites hook **registration** (plugin-entry
     precedence, the move to `settings.local.json`, a `to-030` repair block).
     This story adds *output and one state stamp* at the end of the same
     commands. Land INFRA-319 first if both are ready; if this story lands
     first, INFRA-319 must not delete the notice call sites. Where INFRA-319
     changes *which* settings file is written, this story's
     `hook_registration` surface follows it rather than asserting a specific
     filename.
   - **INFRA-303** also holds `pairmode_migrate.py` as a `primary_file`
     (rules 9/10 name parity, `expected_step_tokens` opt-out). No rule is added
     or renumbered here.
   - **INFRA-305** holds `docs/architecture.md` as a `primary_file` for the
     doc-currency sweep. § E26's subsection is additive; do not restructure
     neighbouring sections.
   - **INFRA-321** touches `docs/architecture.md` and the context-accounting
     modules. It does **not** touch `hooks/session_start.py`; this story does,
     and the two must not both edit the same hook. If INFRA-321's scope has
     grown to include `session_start.py` by build time, stop and raise it.
   - **INFRA-304** owns the agent **templates** (`templates/agents/*.j2`). This
     story changes no template.
9. **Protected-path note.** `hooks/session_start.py` is protected
   (`scope_guard.PROTECTED_GLOBS`). The `touches:` entry above plus a valid
   permissions artifact is the only route; if the write is denied, that is the
   guard working — regenerate the artifact via `permissions-create`, do not
   shell around it.
10. **Spec-preflight note (INFRA-320 § C).** The scan will report
    `skills/pairmode/scripts/sync.py` and
    `skills/pairmode/scripts/session_state.py` as named in Ensures/Instructions
    but absent from declared scope. Both are **read-only** references here:
    `sync.py` is described as a chain member whose changed-file set is
    classified (§ D20 — the classification lives in `session_lifecycle`, not in
    `sync.py`), and `session_state.session_view` is called, not modified. Do not
    widen `touches:` to silence the warning; if § D20 turns out to require a
    change inside `sync.py`, use `permissions-widen` with that reason recorded.
11. **Run the suite without `-x`** and report the full result.

## Tests

`tests/pairmode/test_session_lifecycle.py` (new):

- `test_render_notice_contains_restart_required_banner`
- `test_render_notice_enumerates_each_changed_surface`
- `test_render_notice_states_clear_is_not_sufficient`
- `test_render_notice_names_the_action`
- `test_render_notice_empty_changed_returns_empty_string`
- `test_stamp_writes_written_at_and_written_by_into_state_dict`
- `test_stamp_is_noop_for_empty_changed`
- `test_stamp_performs_no_file_io`
- `test_staleness_notice_returns_line_for_clear_source_after_write`
- `test_staleness_notice_returns_line_for_compact_source_after_write`
- `test_staleness_notice_none_for_startup_source`
- `test_staleness_notice_none_for_resume_source`
- `test_staleness_notice_none_when_write_predates_session_start`
- `test_staleness_notice_none_on_missing_or_unparseable_timestamps`
- `test_surface_classification_agent_shell_and_settings_and_skill_md`
- `test_claude_build_md_is_not_a_registration_surface`

`tests/pairmode/test_bootstrap.py` (extend):

- `test_bootstrap_prints_restart_notice_as_final_output`
- `test_bootstrap_notice_enumerates_written_agent_shells`
- `test_bootstrap_notice_excludes_skipped_project_owned_shells`
- `test_bootstrap_dry_run_prints_no_restart_notice`
- `test_rebootstrap_with_all_shells_skipped_prints_no_notice`
- `test_bootstrap_stamps_agent_surfaces_written_at_in_state_json`
- `test_bootstrap_next_steps_wording_unchanged`

`tests/pairmode/test_pairmode_sync.py` (extend):

- `test_sync_agents_prints_restart_notice_after_writing`
- `test_sync_agents_no_changes_prints_no_notice`
- `test_sync_agents_dry_run_prints_no_notice`
- `test_sync_agents_declined_confirm_prints_no_notice`
- `test_sync_agents_stamps_state_json`
- `test_sync_all_prints_exactly_one_notice_for_the_chain`
- `test_sync_all_reads_stamp_rather_than_parsing_child_output`
- `test_sync_build_only_prints_no_notice`
- `test_audit_hooks_apply_prints_notice_naming_hook_registration`
- `test_audit_hooks_dry_run_prints_no_notice`

`tests/pairmode/test_pairmode_migrate.py` (extend):

- `test_migrate_apply_prints_notice_when_agent_files_changed`
- `test_migrate_report_only_prints_no_notice`
- `test_migrate_already_migrated_prints_no_notice`
- `test_to_030_apply_prints_notice_when_agent_shell_deleted`
- `test_to_030_flag_only_agent_cleanup_prints_no_notice`

`tests/pairmode/test_session_start_hook.py` (extend):

- `test_clear_source_emits_staleness_advisory_when_stamp_is_newer`
- `test_startup_source_emits_no_staleness_advisory`
- `test_advisory_does_not_add_a_state_write`
- `test_advisory_absent_when_state_lacks_stamp_keys`
- `test_advisory_failure_does_not_break_status_block`
- `test_stamp_then_clear_round_trip_writer_and_reader_both_exist`

Run:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

(no `-x` — a known pre-existing failure must not mask a new one).

## Out of scope

- **R1 — making the tooling restart the session itself** (re-exec, a
  `/restart` emission, an API call that reloads the registry). **Rejected, not
  deferred.** A skill script is a child process of the session it would have to
  replace; it has no mechanism to reload another process's agent registry, and
  faking one (killing the parent, writing a sentinel a hook re-reads) is exactly
  the hook-and-state-boundary violation `docs/ideology.md:113-130` forbids. The
  session boundary is the operator's to cross; the tool's job is to say so
  unmissably. This rejection is why § A4 spends its effort on *unmissability*
  rather than on automation.
- **R2 — relying on operators reading the docs. Rejected as the primary
  mechanism.** § E exists, but a runbook step is not a substitute for output at
  the moment of the write: the observed failure was an operator with a
  successful bootstrap in front of them and no reason to suspect a session
  boundary. Docs are the secondary surface here, not the fix.
- **R3 — a blocking gate** (refusing the next spawn, exiting non-zero, a
  `PreToolUse` deny when the registry is stale). Rejected: CER-067's lesson is
  that an un-clearable mechanical gate gets routed around and then protects
  nothing, and this precondition is *unverifiable from inside the process* —
  the tooling cannot read Claude Code's loaded registry, so a gate would fire on
  a guess. Advisory, fail-open, unmissable.
- **R4 — mtime-only staleness detection as the authoritative signal.**
  Rejected (§ A35). `git checkout`, worktree creation and the CER-090
  `rsync` payload workaround all rewrite mtimes without changing content; an
  mtime-driven advisory would cry wolf inside the build loop, which is precisely
  how an advisory earns the ignore reflex R3 warns about.
- **R5 — warning on `startup` or `resume`.** Rejected (§ F29). Both are fresh
  CLI processes that re-read the registry; a warning there is false and would
  train operators to dismiss the true one.
- **R6 — a new state file, a new table, or a persisted notice log.** The two
  additive `state.json` keys are the whole persistence footprint, they have both
  a writer and a reader (§ F34), and they need no management UI under the
  global "conceptual rebuild completeness" policy: no new table is introduced
  and the keys are a machine-written cache of the last tooling write, mirroring
  how `context_session_reset_at` is already handled.
- **R7 — a notice on every sync run regardless of changes.** Rejected
  (§ D17): notice fatigue is a real failure mode and the conditional is cheap,
  because every writer already knows its own changed-file list.
- **R8 — parsing child-command stdout in `sync_all`** to detect what changed
  (§ D19). Children inherit stdout by design; capturing it to scrape a banner
  would hide live progress output the runbook's operators watch, and a stamp is
  a cleaner contract than a parser.
- **R9 — `CLAUDE.build.md` / `CLAUDE.md` as restart surfaces** (§ D22, § A2).
  They are read per invocation, not at session start. Widening the trigger to
  every methodology file would put a banner on nearly every sync — see R7.
- **RELEASE-068's own execution.** The addendum instruction line was added to
  `docs/stories/RELEASE/RELEASE-068.md` § *Instructions* at **this story's spec
  time** (2026-07-29, marked as a post-spec operator addendum) so that the Repo-K
  migration is not blocked on this story landing. That file is therefore **not**
  in this story's `touches:` and must not be edited by the builder. Phase 106's
  execution is independent of phase 114's build order.
- **Retro-notifying the fleet.** Repos already migrated in a stale session are
  long since restarted; no sweep is needed.
- **Backlog rows CER-105, CER-106 and CER-113, and
  `docs/stories/INFRA/INFRA-299.md`** — owned by the unmerged INFRA-299 branch.
  The only `backlog.md` edit here is CER-134's own row.

## Completion note

**§ A35 mtime-based staleness fallback: omitted.** The builder implemented the
stamp-based signal (`agent_surfaces_written_at` / `agent_surfaces_written_by`,
written by § A6/B11/D19 and read by § F's `agent_staleness_notice`) as the sole
mechanism and did not add an `.claude/agents/*.md` mtime-comparison fallback
for repos whose last agent write predates this story. § A35 states the
fallback is explicitly optional ("if the builder judges the fallback not
worth its false-positive rate, omitting it is acceptable") and that "the
stamp path is not optional" — the stamp path is fully implemented and tested
per § H. The fallback was judged not worth its false-positive rate: per § A35
and Out-of-scope R4, `git checkout`, worktree creation, and the CER-090
`rsync` payload workaround all rewrite mtimes without changing content, so an
mtime-driven advisory would produce false positives inside the very build
loop this story's harness runs in.
