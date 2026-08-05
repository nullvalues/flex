---
id: INFRA-397
rail: INFRA
title: Close shadow-reviewer git-flag write bypass and worktree-path scope_guard gap (CER-175)
status: complete
phase: "127"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/reviewer_bash_guard.py
  - skills/pairmode/scripts/scope_guard.py
touches:
  - tests/pairmode/test_reviewer_bash_guard.py
  - tests/pairmode/test_scope_guard.py
  - tests/pairmode/test_pre_tool_use_scope_guard.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

The Phase 122 checkpoint's security-auditor gate was re-run immediately after
INFRA-396 (CER-174) merged. It reverified CER-174's two named defects as
genuinely fixed, and found two new HIGH defects that leave
`shadow_review=concurrent` still unsafe *and* still inert (CER-175):

- **git-flag write bypass.** `reviewer_bash_guard.py`'s
  `_check_shadow_reviewer_command` screens shell control/substitution tokens
  and requires `git` to be the first token, but never inspects git's *own*
  flags. Several git flags carry real write or execution semantics on
  otherwise-allowlisted subcommands: `git diff --output=<path>` (and the
  separated `--output <path>` form) creates/truncates an arbitrary file, and
  `git --exec-path=<dir> log` redirects git's subcommand resolution to an
  attacker-chosen directory. Auditor-verified live:
  `check_command("git diff --output=/tmp/pwn.txt HEAD", "shadow-reviewer")`
  returns allow, and the file is created. This directly contradicts the
  guard's own stated invariant that the shadow-reviewer has no legitimate
  write path via Bash at all — the same arbitrary-write class INFRA-396
  closed for chaining/substitution, reached through an unscreened flag
  instead.
- **scope_guard worktree-prefix gap.** INFRA-396's `agent_type ==
  "shadow-reviewer"` short-circuit (`scope_guard.py` ~lines 124-134) compares
  `_normalise(...)`'s output against the literal `.pairmode-suggestions.md`,
  but unlike the builder path (which calls `_strip_worktree_prefix`, ~line
  193) it never strips a `.pairmode-worktrees/<story-id>/` prefix. The
  shadow-reviewer is dispatched *into* the per-story worktree and the real
  `Write` call carries an absolute path, so the one sanctioned write is
  currently DENIED in production while a relative-path write is allowed —
  exactly backwards. INFRA-396's own end-to-end tests all used relative
  `file_path` values, which is why this shipped.

Both fixes are containable in the two guard scripts; `hooks/pre_tool_use.py`
already forwards `agent_type` on every relevant branch (INFRA-396) and needs
no change.

## Requires

- INFRA-396 merged and live: `_check_shadow_reviewer_command`'s
  control-token/first-token checks, `check_path`'s `agent_type` parameter and
  `shadow-reviewer` short-circuit, and `hooks/pre_tool_use.py`'s
  `agent_type=` pass-through on the `Edit`/`Write` dispatch branch all exist.
- `scope_guard.py`'s `_strip_worktree_prefix` and `resolve_call_story` are
  present and passing their own tests — this story reuses them, it does not
  re-derive worktree-prefix handling.

## Ensures

1. For `agent_type="shadow-reviewer"`, `reviewer_bash_guard.check_command`
   returns deny for each of these exact strings: `git diff --output=/tmp/x
   HEAD`, `git diff --output /tmp/x HEAD`, `git --exec-path=/tmp/evil log`,
   `git --exec-path /tmp/evil log`, `git log -o /tmp/x`, `git -C /tmp log`,
   `git --git-dir=/tmp/evil/.git log`, `git --work-tree=/tmp diff`, `git -c
   core.pager=/tmp/evil.sh log`, `git --config-env=core.pager=EVIL log`.
   Correct signal: the returned `allowed` is `False`. Forbidden proxy: a
   warning in the reason string while `allowed` stays `True` — the live
   bypass already "allows" past a naive subcommand check.
2. The flag screen matches a denied flag whether it appears attached
   (`--output=<v>`) or separated (`--output <v>`), and whether it appears
   before the subcommand (git-global position) or after it — the screen is
   over every token of the command, not just the tokens following the
   subcommand.
3. Legitimate shadow-reviewer commands still return allow: `git log`, `git
   status --porcelain`, `git diff`, `git log --oneline -n 20`, `git diff
   --stat`.
4. INFRA-396's Ensures 1-8 behavior is unchanged, asserted by its existing
   test cases still passing unmodified: chaining/substitution strings still
   deny, `git` must still be the first token, an untokenizable command still
   denies for `shadow-reviewer` only, and `agent_type="reviewer"` /
   default-builder outcomes are unchanged for every existing case.
5. For `agent_type="reviewer"`, `git diff --output=/tmp/x HEAD` and `git
   --exec-path=/tmp/evil log` return the same result they return today
   (allow) — the new screen is scoped strictly to the `shadow-reviewer`
   branch, proven by a test case for each.
6. `scope_guard.check_path` with `agent_type="shadow-reviewer"` returns allow
   for the absolute path `<main>/.pairmode-worktrees/<active-story-id>/.pairmode-suggestions.md`
   when `<active-story-id>` is the resolved active story for the call, and
   continues to return allow for the plain relative `.pairmode-suggestions.md`.
7. `check_path` with `agent_type="shadow-reviewer"` still returns deny for
   every other absolute in-worktree path (e.g.
   `<main>/.pairmode-worktrees/<active-story-id>/skills/foo.py`,
   `<main>/.pairmode-worktrees/<active-story-id>/docs/architecture.md`) and
   for a `.pairmode-suggestions.md` under a *different* story's worktree
   segment — per-story worktree isolation is preserved, the allowed set stays
   exactly one logical file.
8. Builder/unspecified-`agent_type` behavior in `check_path` is unchanged:
   the existing worktree-stripping, protected-path, and story-scope test
   cases in `tests/pairmode/test_scope_guard.py` pass unmodified.
9. Driven end-to-end through `hooks/pre_tool_use.py`'s real `main()` with the
   real (unmocked) `check_path` — following the existing pattern in
   `tests/pairmode/test_pre_tool_use_scope_guard.py` (see
   `test_hook_allows_shadow_reviewer_write_to_suggestions_file`) — a payload
   with `agent_type="shadow-reviewer"`, `tool_name` `Write`, and an
   **absolute** `file_path` of `<worktree>/.pairmode-suggestions.md` emits no
   block (empty stdout), while the same payload with an absolute
   `<worktree>/skills/foo.py` emits `decision: block`. Forbidden proxy: a
   relative-path-only test — that is exactly the coverage shape that let this
   defect ship.

## Instructions

1. In `reviewer_bash_guard.py`, add a module-level denied-flag set and screen
   it inside `_check_shadow_reviewer_command`, after the control-token check
   and before/alongside the subcommand allowlist check. Deny when any token
   equals a denied flag or starts with `<denied flag>=`. Minimum set (git
   flags with write, execution, or repo/dir-redirection semantics that the
   `log`/`status`/`diff` allowlist does not otherwise reject): `--output`,
   `-o`, `--exec-path`, `-c`, `--config-env`, `-C`, `--git-dir`,
   `--work-tree`, `--namespace`. None of these has a legitimate read-only use
   for this role, so a false denial is cheap; a miss is the CER-175 class.
2. Do not touch the `agent_type="reviewer"` branch, `_find_git_invocation`,
   `_ALLOWED_SUBCOMMANDS`, or `_BLOCKED_SUBCOMMANDS` — the reviewer role's
   own need for these flags is separately scoped and explicitly out of this
   story (Ensures 5 is the regression guard).
3. In `scope_guard.py`'s `agent_type == "shadow-reviewer"` short-circuit,
   normalise as today, then obtain the active story id the same way the
   builder branch does (`resolve_call_story(project_dir, file_path)`, handed
   the *raw* `project_dir`) and pass it through `_strip_worktree_prefix`
   before comparing against `_SHADOW_REVIEWER_ONLY_PATH`. Compare the
   stripped candidate; deny everything else. Using `resolve_call_story` here
   is for prefix *identity* only — the allowed set remains exactly one
   filename, so the branch still never inherits the builder's
   `primary_files`/`touches`/`STANDING_SURFACES` scope (INFRA-396's Ensures
   5, still asserted). When no active story resolves, `_strip_worktree_prefix`
   returns the path unchanged and the write is denied: fail-closed is the
   correct outcome for this role.
4. Add the test cases for Ensures 1/3/5 to
   `tests/pairmode/test_reviewer_bash_guard.py`, Ensures 6/7 to
   `tests/pairmode/test_scope_guard.py`, and Ensures 9 to
   `tests/pairmode/test_pre_tool_use_scope_guard.py` (extend that file's
   existing shadow-reviewer cases with absolute-path variants, reusing its
   `_make_worktree_with_active_story` helper — no new test file, and no
   change to `hooks/pre_tool_use.py`, which already forwards `agent_type`).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_reviewer_bash_guard.py tests/pairmode/test_scope_guard.py tests/pairmode/test_pre_tool_use_scope_guard.py -q
```
Acceptance: green, including every new deny/allow case above.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: full suite green — no regression in `reviewer`/`builder`
behavior in either guard.

## Out of scope

- Screening `--output`/`--exec-path`/`-c` (or any other flag) for
  `agent_type="reviewer"` or the default/builder case — the reviewer's
  legitimate flag needs are a separate scoping question; this story narrows
  only `shadow-reviewer`.
- Replacing the guard's heuristic `shlex`-based parsing with a real shell/git
  parser, or moving from a denied-flag screen to a default-deny flag
  allowlist — either is a larger redesign; this story closes the named
  CER-175 vector on the existing structure.
- Any change to `hooks/pre_tool_use.py`, `CLAUDE.build.md`, or the
  `shadow_review=concurrent` flag itself. (Spec-preflight reports
  `hooks/pre_tool_use.py` as named-but-out-of-declared-scope: intentional —
  it is referenced only as an unchanged dependency and as the driver of the
  Ensures-9 end-to-end test, so it stays out of `touches:`.)
- Intra-file concurrency control on `.pairmode-suggestions.md` (the
  stale-read-then-whole-file-Write race), already out of scope in INFRA-396.
