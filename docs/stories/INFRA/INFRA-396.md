---
id: INFRA-396
rail: INFRA
title: Fix shadow-reviewer Bash-guard shell-chaining bypass and scope its Write grant (CER-174)
status: draft
phase: "126"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/reviewer_bash_guard.py
  - skills/pairmode/scripts/scope_guard.py
touches:
  - tests/pairmode/test_reviewer_bash_guard.py
  - tests/pairmode/test_scope_guard.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

INFRA-388 (Phase 122, shipped and merged to main) restored shadow-reviewer write
capability and turned on `shadow_review=concurrent` in `CLAUDE.build.md` — a
shadow-reviewer agent now runs concurrently with the builder in the same
worktree, gated by two compensating controls: an `agent_type="shadow-reviewer"`
allowlist branch in `reviewer_bash_guard.py`, and a `Write` grant to
`.claude/agents/shadow-reviewer.md` whose *prose* (the procedure's own
`## Non-negotiables` section) promises the agent never writes outside
`.pairmode-suggestions.md`. The Phase 122 checkpoint's security-auditor gate
FAILed both controls (CER-174, filed against this finding — see the phase-126
Goal and this story's own title):

- **CRITICAL — Bash-guard shell-chaining bypass.** The shadow-reviewer branch
  (`_check_shadow_reviewer_command`, `reviewer_bash_guard.py`, roughly lines
  155-187) validates only the *first git invocation found anywhere* in the
  command's token list, via `_find_git_invocation` (roughly lines 190-215) —
  which itself stops collecting tokens at `&&`/`||`/`;`/`|` — but the guard
  still returns allow for the *whole* command string regardless of what
  precedes or follows that git invocation. The auditor verified live: `git
  status && rm -rf docs`, `git log ; touch /tmp/x`, `git status\nrm -rf docs`,
  `rm -rf docs && git log`, `git diff --stat $(rm -rf docs)`, `` git log
  --format=`touch /tmp/x` ``, `git status && git reset --hard`, and `git log
  && git push origin main` all ALLOW. Only `>`/`<`/`|` (redirection) are
  pre-checked; `&&`, `;`, newline, `$( )`, and backticks are unhandled. This is
  the exact reviewer-improvisation bypass class INFRA-324 built the existing
  `reviewer` agent_type's allowlist to block — that existing branch is the
  model this story's fix must follow for `shadow-reviewer` too. The four
  existing shadow-reviewer test cases in `test_reviewer_bash_guard.py` cover no
  chaining/substitution form, which is why this shipped without regression
  coverage catching it.

- **HIGH — Write grant is not role-scoped.** `scope_guard.py`'s `check_path`
  (roughly lines 101-116) takes only `file_path`/`project_dir` — no
  `agent_type` — and resolves the caller to the active story via
  `resolve_call_story` exactly as it does for the builder. The shadow-reviewer
  therefore inherits the builder's entire write scope (the story's
  `primary_files`/`touches` plus every `STANDING_SURFACES` entry —
  `docs/cer/backlog.md`, `docs/architecture.md`, the story spec itself)
  instead of being confined to `.pairmode-suggestions.md`, while running
  concurrently with the builder in the same worktree with no lock or
  ordering. The shadow-reviewer procedure's own prose promise ("Never write to
  any file other than `.pairmode-suggestions.md`") is currently unenforced by
  the hook layer — a stale-read-then-whole-file-Write race (the shadow-reviewer's
  own documented append mechanism) against the builder's real writes could
  silently discard in-flight builder work.

`shadow_review=concurrent` is live right now — the operator chose to leave it
enabled while this fix is built rather than disable it first. This story does
not touch that flag or `CLAUDE.build.md`; it closes the two gaps the flag's own
compensating controls were supposed to provide.

## Requires

- INFRA-388 merged to `main` and live: `agent_type="shadow-reviewer"` exists in
  `reviewer_bash_guard.py`, `shadow_review=concurrent` is set in
  `CLAUDE.build.md`, and the `Write` grant to `shadow-reviewer.md` /
  `shadow-reviewer.md.j2` is in place.
- `reviewer_bash_guard.py`'s existing `agent_type="reviewer"` allowlist branch
  (the INFRA-324 default-deny pattern) is present and passing its own tests —
  it is the model this story's `shadow-reviewer` fix must match, not a
  from-scratch design.
- `scope_guard.py`'s `check_path`/`resolve_call_story` and whatever caller
  (`pre_tool_use.py` or equivalent hook) invokes `check_path` today, so the
  agent-type signal this story threads through has a real, already-existing
  call site to attach to rather than requiring a new plumbing layer invented
  from nothing.

## Ensures

1. For `agent_type="shadow-reviewer"`, every one of these exact strings is
   denied by `reviewer_bash_guard.py`: `git status && rm -rf docs`, `git log ;
   touch /tmp/x`, `git status\nrm -rf docs` (literal embedded newline), `rm -rf
   docs && git log`, `git diff --stat $(rm -rf docs)`, `` git log
   --format=`touch /tmp/x` ``, `git status && git reset --hard`, `git log &&
   git push origin main`. Correct signal: the guard's return/exception
   indicates deny for the whole string. Forbidden proxy: a warning that is
   logged/printed while the command is still allowed to execute (matches this
   story's own background — the current bypass already "allows" while
   satisfying a naive first-token git check).
2. A command containing any shell control/substitution token — `&&`, `||`,
   `;`, a literal newline, `$(`, a backtick, or a bare `&` — is rejected before
   any git-subcommand matching runs, for `agent_type="shadow-reviewer"`. This
   check fires independent of where in the token list the token appears
   (leading, trailing, or embedded) and independent of whether a valid git
   invocation is also present in the string.
3. For `agent_type="shadow-reviewer"`, a command is only allowed when the git
   token is the first token of the (already passed the step-2 chaining check)
   command — no scanning the remainder of the token list for "any" git
   invocation, mirroring how the existing `reviewer` agent_type branch avoids
   the INFRA-324 bypass class.
4. Legitimate shadow-reviewer commands still allow: `git log`, `git status
   --porcelain`, `git diff`.
5. `scope_guard.py`'s `check_path` denies a shadow-reviewer-attributed write to
   any path other than exactly `.pairmode-suggestions.md` (resolved relative to
   the project dir), including a path that is inside the concurrently-running
   builder's own declared scope for the same story (a `primary_files`/`touches`
   entry, or a `STANDING_SURFACES` entry such as `docs/cer/backlog.md` or
   `docs/architecture.md`). The denial is agent-type-driven — the same path
   remains allowed for `agent_type="builder"` on the same story, proving the
   scopes are genuinely different, not both narrowed.
6. `check_path` allows a shadow-reviewer-attributed write to
   `.pairmode-suggestions.md` for the active story.
7. `tests/pairmode/test_reviewer_bash_guard.py` gains one test case per bypass
   string in Ensures 1 (all asserting deny) and one per Ensures 4 (asserting
   allow); `tests/pairmode/test_scope_guard.py` gains a case proving Ensures 5
   (shadow-reviewer denied on a path that is inside the builder's own allowed
   scope) and a case proving Ensures 6.
8. The existing `agent_type="reviewer"` and `agent_type="builder"` test suites
   in both files still pass unmodified — this story narrows only the
   `shadow-reviewer` branch's behavior and adds an `agent_type` parameter to
   `check_path`, it does not change `reviewer`/`builder` outcomes for any
   existing test case.

## Instructions

1. In `reviewer_bash_guard.py`, rework `_check_shadow_reviewer_command` (and
   `_find_git_invocation` if it remains shared) so the shadow-reviewer path
   follows the same two-phase shape as the existing `reviewer` agent_type
   branch: (a) reject on any shell control/substitution token — extend the
   current `>`/`<`/`|` substring pre-check to also cover `&&`, `||`, `;`,
   newline (`\n`), `$(`, backtick, and bare `&` — before any subcommand
   matching runs; (b) only after that check passes, require the git token be
   the *first* token of the command (not "found anywhere" via
   `_find_git_invocation`'s token-scan). Do not weaken the existing `reviewer`
   agent_type branch's own behavior — reuse its pattern, don't merge the two
   branches into one unless doing so is a strict no-behavior-change refactor
   for `reviewer`.
2. In `scope_guard.py`, add an `agent_type` parameter to `check_path` (default
   preserving current `builder`/unspecified behavior so existing callers are
   unaffected). When `agent_type == "shadow-reviewer"`, short-circuit to: allow
   only when the resolved path's project-relative form is exactly
   `.pairmode-suggestions.md`; deny everything else — independent of
   `resolve_call_story`'s `primary_files`/`touches`/`STANDING_SURFACES`
   resolution for that story. Do not fall through to the builder-scope logic
   for this agent type even as a fallback.
3. Find the hook/caller that invokes `check_path` today (`pre_tool_use.py` or
   equivalent) and determine how it currently identifies which agent is
   calling (e.g. an existing `agent_type`/role signal already available at the
   hook layer, per this project's Hooks-are-thin-relays constraint — hooks may
   read/relay a signal but must not add blocking logic beyond passing it
   through). Thread that signal into the new `check_path` parameter. If no
   such signal exists yet at the hook layer, add the minimal plumbing to carry
   it through (e.g. from the same place the shadow-reviewer's own bash-guard
   `agent_type` is already known) — do not invent a second, parallel mechanism
   for identifying the agent type between the two guard scripts.
4. Add the adversarial and legitimate-command test cases from `## Ensures` 1
   and 4 to `tests/pairmode/test_reviewer_bash_guard.py`, and the scope-denial
   and scope-allow cases from `## Ensures` 5 and 6 to
   `tests/pairmode/test_scope_guard.py`.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_reviewer_bash_guard.py tests/pairmode/test_scope_guard.py -q
```
Acceptance: green, including every new adversarial/allow/deny case above.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: full suite green — no regression in `reviewer`/`builder`
agent_type behavior in either guard.

## Out of scope

- Disabling `shadow_review=concurrent` or editing `CLAUDE.build.md` — the
  operator explicitly chose to leave the flag enabled while this fix is built;
  this story closes the compensating-control gaps, it does not touch the flag.
- A lock/ordering mechanism to prevent a stale-read-then-whole-file-Write race
  between the concurrently-running builder and shadow-reviewer even when the
  shadow-reviewer is correctly confined to `.pairmode-suggestions.md` (e.g. two
  shadow-reviewer writes, or a shadow-reviewer write racing an unrelated
  builder read of the same file) — confining the write target closes the
  cross-file corruption risk the HIGH finding raised; intra-file concurrency
  control on `.pairmode-suggestions.md` itself is a separate concern, not
  covered here.
- Extending agent-type-aware scoping in `check_path` to any agent type other
  than `builder`/`shadow-reviewer` (e.g. a future third concurrent role) —
  this story adds exactly the one new branch needed to close CER-174.
