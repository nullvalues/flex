---
id: INFRA-209
rail: INFRA
title: "Re-run the fleet rollout of the newly-registered context-budget-gate hooks across every already-bootstrapped sibling repo's .claude/settings.json (per repo, same mechanical pattern as the manual INFRA-206 rollout), verifying each fleet project now carries the UserPromptSubmit/SessionStart/PostToolUse Task|Agent registrations"
status: complete
phase: "95"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - docs/fleet-snapshot.md
touches: []
---

# INFRA-209 — Fleet rollout of the context-budget-gate hook registrations

## Context

This is an **operational rollout story**, not a code-change story in flex's own
tree. INFRA-208 generalizes `bootstrap.py`/`sync.py` so *future* bootstrap and
sync runs register the three context-budget-gate hooks (`UserPromptSubmit`,
`SessionStart`, `PostToolUse` `Task|Agent`) into a downstream project's
`.claude/settings.json`. Per INFRA-208 Ensures #9, that change is **future-only**:
it does not retroactively rewrite the `settings.json` files of projects
bootstrapped before the fix. Every already-bootstrapped fleet project therefore
still carries only the `PreToolUse` block and remains subject to the CER-067
failure mode (a decorative budget gate that is being silently worked around).

This story directs the orchestrator to **apply INFRA-208's generalized
registration to every already-bootstrapped fleet project's own
`.claude/settings.json`**, in each project's own separate git repo, each getting
its own commit — exactly the same way the CER-065 / INFRA-206 `PreToolUse` fix was
rolled out manually per-repo across the fleet in this same era.

### Why `story_class: code` and why there is no new automated test

flex's schema (`skills/pairmode/scripts/schema_validator.py`,
`VALID_STORY_CLASSES = {"code", "doc", "lesson", "methodology"}`) has **no
"operational" class**, and non-draft stories require a non-empty `primary_files`
(`schema_validator.py:168-171`). This story is therefore filed as `code` — the
closest available class — but it introduces **no automated test in flex's own
tree**. The generalized registration logic and its tests are owned by INFRA-208;
this story exercises that already-tested function against external targets. The
"test" for this story is the **post-hoc verification** that each fleet repo's
`settings.json` now carries the three new registrations (see Ensures / Tests).

### Why `primary_files` points at `docs/fleet-snapshot.md`

The real targets of this story are **outside flex's own git tree** — the
`.claude/settings.json` files of the 15 fleet projects, each in its own repo.
Those files cannot be listed as flex `primary_files`. Because the schema validator
rejects an empty `primary_files` for a non-draft story, `primary_files` is
anchored to the single in-flex file this rollout is **driven from and verified
against**: `docs/fleet-snapshot.md` (the authoritative fleet list). No content
change to `fleet-snapshot.md` is required by this story; it is the scope anchor,
and the external nature of the true targets is stated explicitly here.

### Fleet scope (from `docs/fleet-snapshot.md`, 16 discovered projects minus `anchor` minus `cora`)

`anchor` is excluded — it was determined **not** to be a pairmode consumer; it is
a separate sibling plugin repo. `cora` is also excluded — it is a known carve-out
project and must not be touched by this rollout (see § `cora` exclusion below).
That leaves **14 target projects**:

`coherra`, `meander`, `caddy`, `forqsite`, `forqsite.help`, `radar`, `asp`,
`aab`, `lumin`, `halfhorse`, `base56`, `pokus`, `rockue`, `ud`.

(All under `/mnt/work/<name>`. `asp` is the repo where the CER-067 live symptom was
reported — prioritize verifying it, and check whether the forged
`context_budget_acknowledged_*` workaround keys were left in its `state.json`.)

### `cora` exclusion

`cora` is a known carve-out project and is explicitly out of scope for this
rollout — it is not to be touched by this process. It retains its manually-added
`PostToolUse` (`Edit|Write|MultiEdit` → `pnpm typecheck`) and `Stop` hooks as-is,
without the new `UserPromptSubmit`/`SessionStart`/`PostToolUse Task|Agent`
registrations. Any future decision to bring `cora` into the standard fleet
registration is a separate, deliberate follow-up story — not an implicit
consequence of this one.

## Ensures

1. **All 14 target fleet projects carry the three new registrations.** After the
   rollout, each project's `.claude/settings.json` `hooks` object contains:
   - a matcher-less `UserPromptSubmit` block whose command targets that project's
     resolved `user_prompt_submit.py`;
   - a matcher-less `SessionStart` block whose command targets `session_start.py`;
   - a `PostToolUse` block with matcher `"Task|Agent"` whose command targets
     `post_tool_use.py`.

2. **Existing registrations preserved.** Each project's pre-existing `PreToolUse`
   (INFRA-206) block is left intact, and any project-local `PostToolUse` block
   (e.g. a pytest runner) is preserved as a **sibling**, not merged or replaced
   (guaranteed by INFRA-208's by-command registrar).

3. **`anchor` and `cora` are untouched.** No commit, no `settings.json` change is
   made in `/mnt/work/anchor` or `/mnt/work/cora`.

4. **One commit per repo, `settings.json` only.** Each fleet repo receives exactly
   one commit containing only its `.claude/settings.json` change. Any other
   unrelated uncommitted state already present in a repo is left untouched and is
   **not** swept into the commit.

5. **Diff-preview-then-confirm.** For each repo, the settings.json diff is
   presented for confirmation before the commit is made (mirroring the INFRA-206
   manual rollout), so no repo is committed to blind.

6. **Idempotent / no-op safe.** Applying the generalized registration to a project
   that (somehow) already carries the three hooks produces no duplicate blocks and
   an empty diff — that repo is skipped (no empty commit).

7. **Post-hoc verification recorded.** After the rollout, each of the 14 target
   projects is re-inspected and confirmed to carry the three registrations; the
   result is recorded in the phase CP-95 checklist (or the story's completion
   note).

## Instructions

This is an operational procedure run by the orchestrator against external repos —
**not** a `pytest` gate in flex. For each of the 14 target fleet projects (all
except `anchor` and `cora`):

1. **Apply the generalized registration** to that project's
   `<project>/.claude/settings.json` using the **fixed** registrar from INFRA-208
   — the same mechanical pattern as the INFRA-206 rollout: import the generalized
   registration function(s) from `skills/pairmode/scripts/bootstrap.py`
   (e.g. `_register_pretooluse_hook` + the new
   `_register_context_budget_hooks`, or whatever combined entry point INFRA-208
   lands), with `plugin_root = /mnt/work/flex`, and apply it to the target
   project's `settings.json`. The resolved hook command paths point at flex's own
   `hooks/*.py` (absolute), consistent with how these version-bound fleet projects
   already reference flex.
2. **Diff-preview.** Show the resulting `settings.json` diff (git diff or a
   before/after) for that repo and present it for confirmation. If the diff is
   empty (already registered), skip the repo — no commit.
3. **Commit per repo.** In the project's own repo, stage and commit **only**
   `.claude/settings.json` with a message referencing INFRA-209 / CER-067. Do not
   `git add -A`; do not touch other uncommitted files in that repo.
4. **Verify.** Re-read the committed `settings.json` and confirm it contains the
   `UserPromptSubmit`, `SessionStart`, and `PostToolUse` `Task|Agent`
   registrations plus the pre-existing `PreToolUse` block.
5. **Prefer `pairmode sync` where clean.** Because INFRA-208 wires the generalized
   registrar through `sync.py:616`, running `/flex:pairmode sync` (or `sync-all`)
   in a project achieves the same registration. Use `sync`/`sync-all` when a
   project's working tree is otherwise clean enough that the sync's other effects
   (deny-list merge, state.json version bump) are acceptable in the same commit;
   otherwise apply the registrar function directly to `settings.json` only, to
   keep the commit surgically scoped (matching the INFRA-206 approach).

Special handling:
- **`asp`** — after registration, inspect `.companion/state.json` for the forged
  CER-067 workaround keys (`context_budget_acknowledged_at`,
  `context_budget_acknowledged_user_turn_seq` set to defeat the gate). Note their
  presence in the completion record; deciding whether to reset them is a follow-up,
  not required by this story.
- **`cora`** — excluded from this rollout entirely (see § `cora` exclusion above).
  Do not apply the registrar, do not diff, do not commit. Its manually-added
  `PostToolUse`/`Stop` pair from CER-067 is left exactly as-is.

## Tests

`story_class: code` by schema necessity, but **there is no new automated test in
flex's tree for this story** — the registrar and its unit tests are INFRA-208's.
Verification is operational and post-hoc:

- For each of the 14 target fleet projects, confirm `.claude/settings.json`
  `hooks` contains `UserPromptSubmit`, `SessionStart`, and a `PostToolUse`
  `Task|Agent` block (plus the pre-existing `PreToolUse` block).
- Confirm `anchor` and `cora` were not modified.
- Confirm each commit touched only `.claude/settings.json`.

flex's own gate (`PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`)
must still pass, but it exercises INFRA-208's registrar, not this rollout. Record
the per-project verification result in the CP-95 checklist.

## Out of scope

- Any change to flex's own tree beyond this story doc — the registrar generalization
  is INFRA-208.
- **`anchor`** — excluded (not a pairmode consumer; separate sibling plugin repo).
- **`cora`** — excluded (known carve-out project; not to be touched by this
  process — see § `cora` exclusion).
- Registering the four deferred companion/sidebar blocks (`Stop`,
  `PermissionRequest`/`ExitPlanMode`, `PostToolUse` `Write|Edit|MultiEdit`,
  `SessionEnd`) in fleet projects — out of scope for the same reason as INFRA-208.
- Cleaning up / resetting any forged CER-067 workaround state (e.g. in `asp`) — a
  separate follow-up.
- Re-bootstrapping or version-bumping fleet projects beyond what a scoped
  `settings.json` registration (or an accepted `pairmode sync`) entails.

## Completion note

Read-only fleet audit (2026-07-21) found the rollout already applied ahead of
this story's build: 13 of the 14 target projects (`coherra`, `meander`, `caddy`,
`forqsite`, `forqsite.help`, `radar`, `asp`, `aab`, `lumin`, `halfhorse`,
`base56`, `pokus`, `rockue`, `ud` — 14 total) already carried all three
registrations (`UserPromptSubmit`, `SessionStart`, `PostToolUse` `Task|Agent`)
with the pre-existing `PreToolUse` block preserved in every case. No further
commits were required.

- `anchor` — confirmed untouched (no `UserPromptSubmit`/`SessionStart` present).
- `cora` — excluded per the § `cora` exclusion above; confirmed untouched. Its
  manual `PostToolUse` (`Edit|Write|MultiEdit` → `pnpm typecheck`) and `Stop`
  hooks remain exactly as before.
- `asp` — registrations confirmed present. Inspected `.companion/state.json`:
  the forged CER-067 workaround keys (`context_budget_acknowledged_at`,
  `context_budget_acknowledged_user_turn_seq`) are still present. Resetting
  them remains out of scope / a separate follow-up, per this story.

No `settings.json` diffs were needed anywhere in the 14-project target set —
this story closes as a verification-only pass.
