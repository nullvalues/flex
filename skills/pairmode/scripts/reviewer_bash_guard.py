"""
reviewer_bash_guard.py — Reviewer-role Bash git-subcommand allowlist for the
pre_tool_use hook (INFRA-324).

check_command(command, agent_type) -> (allowed: bool, reason: str)

Closes the gap named in `docs/stories/INFRA/INFRA-324.md`: the reviewer
subagent's FAIL-path revert contract
(`skills/pairmode/skills/reviewer/procedure.md`'s "On FAIL, revert" section)
sanctions exactly `git checkout -- <path>` / `git checkout .` and
`git clean -fd -- <path>` / `git clean -fd`, plus read-only/record commands
(`git add`, `git commit`, `git diff`, `git status`, `git log`) — but nothing
enforced that contract; the reviewer is an LLM following prose, not a shell
script. This module is the enforcement half; `hooks/pre_tool_use.py`'s new
`Bash` branch is the dispatch half.

Scope: this guard governs the `reviewer` role, and — as of INFRA-388 — the
`shadow-reviewer` role. `agent_type` values outside those two (including
`None` — an orchestrator or non-subagent Bash call, and every other subagent
role: builder, loop-breaker, security-auditor, intent-reviewer) always fail
open with no command inspection at all — this is a defense-in-depth guard
behind the sandbox for specific, already-observed improvisations (a reviewer
running `git reset --hard` / `git revert` on FAIL; a shadow-reviewer that
would otherwise have no enforced boundary on its restored Bash grant,
CER-164), not a general Bash policy engine. The `shadow-reviewer` branch is
strict where the `reviewer` branch is permissive: it default-*denies* both
non-git commands and any git subcommand outside its narrow read-only
allowlist (`log`/`status`/`diff`), since — unlike the reviewer — the
shadow-reviewer holds no other legitimate write path via Bash at all; the
reviewer's fail-open-on-unrecognized-input default would silently reopen
CER-163's Bash-heredoc-append bypass if reused here.

Parsing is deliberately a heuristic, not a full shell parser: tokenize with
`shlex`, look for a `git` invocation, and treat its first non-flag argument as
the subcommand. Good enough for a defense-in-depth layer that sits behind the
sandbox/permission layer flex does not own or control (see story Context item
4 — blast radius is already bounded by `discard-story-worktree`'s
unconditional worktree wipe on every reviewer FAIL).

Fails open on any unexpected exception — a bug in this guard must never block
a legitimate reviewer command; see `scope_guard.py` / `cold_read_guard.py` for
the same convention.
"""
from __future__ import annotations

import shlex

# Sanctioned by reviewer/procedure.md's "On FAIL, revert" section: the two
# scoped forms plus the whole-tree legacy fallback, and the read-only/record
# commands the reviewer legitimately runs during review (status checks,
# staging + committing on PASS, diffing).
_ALLOWED_SUBCOMMANDS = frozenset({
    "checkout",
    "clean",
    "add",
    "commit",
    "diff",
    "status",
    "log",
})

# Never sanctioned anywhere in the reviewer procedure — the exact
# improvisation this story closes (`git reset --hard`, `git revert`), plus
# other destructive/history-rewriting/network subcommands a reviewer has no
# legitimate reason to run.
_BLOCKED_SUBCOMMANDS = frozenset({
    "reset",
    "revert",
    "rebase",
    "push",
})

_DISCARD_POINTER = (
    "use discard-story-worktree (the orchestrator's mechanism for a full "
    "revert), not a raw git command"
)

# Sanctioned by shadow-reviewer/procedure.md's read-only polling protocol
# (INFRA-358/INFRA-388): the shadow-reviewer never commits, reverts, or
# otherwise mutates the worktree via Bash — its only legitimate write path
# is the `Write` tool against `.pairmode-suggestions.md` (scope_guard.py's
# STANDING_SURFACES entry, INFRA-365).
_SHADOW_REVIEWER_ALLOWED_SUBCOMMANDS = frozenset({"log", "status", "diff"})

# CER-174: shell control/substitution tokens that must be rejected before any
# git-subcommand matching runs for agent_type="shadow-reviewer" — independent
# of where in the string they appear (leading, trailing, embedded) and
# independent of whether a valid git invocation is also present. Covers the
# chaining/substitution classes the prior naive "first git invocation found
# anywhere" check missed: `&&`, `||`, `;`, a literal newline, `$(`, a
# backtick, a bare `&`, plus the pre-existing `>`/`<`/`|` redirection check.
_SHADOW_REVIEWER_CONTROL_TOKENS = (
    "&&", "||", ";", "\n", "$(", "`", "&", ">", "<", "|",
)


def _has_control_token(command: str) -> bool:
    return any(tok in command for tok in _SHADOW_REVIEWER_CONTROL_TOKENS)


def check_command(command: str, agent_type: "str | None") -> tuple[bool, str]:
    try:
        if agent_type == "shadow-reviewer":
            if not command or not isinstance(command, str):
                return True, "empty or non-string command — allowing"
            # Instruction 4 (CER-174 follow-up): the shadow-reviewer has no
            # legitimate Bash write path at all, so an untokenizable command
            # must fail CLOSED for this agent type — unlike the `reviewer`
            # branch below, which deliberately fails open on the same
            # ValueError. Run the control-token substring check against the
            # raw string first: if shlex.split then fails, deny outright
            # rather than falling back to the (permissive) reviewer default.
            if _has_control_token(command):
                return False, (
                    "shell control/substitution tokens are blocked for the "
                    "shadow-reviewer role — it has no legitimate write path "
                    "via Bash at all"
                )
            try:
                tokens = shlex.split(command)
            except ValueError:
                return False, (
                    "command did not tokenize — denied for the "
                    "shadow-reviewer role, which has no legitimate write "
                    "path via Bash at all"
                )
            return _check_shadow_reviewer_command(command, tokens)

        if agent_type != "reviewer":
            return True, "not a reviewer-issued command — allowing"

        if not command or not isinstance(command, str):
            return True, "empty or non-string command — allowing"

        try:
            tokens = shlex.split(command)
        except ValueError:
            # Unbalanced quotes etc. — not our job to shell-parse; fail open.
            return True, "command did not tokenize — allowing"

        subcommand, flags = _find_git_invocation(tokens)
        if subcommand is None:
            return True, "not a git invocation — allowing"

        if subcommand == "branch" and _is_branch_delete_force(tokens):
            return False, (
                "git branch -D / --delete --force is blocked for the "
                f"reviewer role — {_DISCARD_POINTER}"
            )

        if subcommand in _BLOCKED_SUBCOMMANDS:
            return False, (
                f"git {subcommand} is blocked for the reviewer role — "
                f"{_DISCARD_POINTER}"
            )

        if subcommand in _ALLOWED_SUBCOMMANDS:
            if subcommand == "clean":
                if not _is_sanctioned_clean(tokens):
                    return False, (
                        "git clean is only sanctioned as 'git clean -fd -- "
                        "<path>' or whole-tree 'git clean -fd' for the "
                        f"reviewer role — {_DISCARD_POINTER}"
                    )
                return True, "sanctioned git clean form — allowing"

            # A bare --force/-f flag on any other allowlisted subcommand is
            # outside the two sanctioned `git clean -fd` forms and is blocked.
            if _has_bare_force_flag(flags):
                return False, (
                    f"git {subcommand} with a --force/-f flag is blocked for "
                    f"the reviewer role — {_DISCARD_POINTER}"
                )
            return True, f"sanctioned git {subcommand} — allowing"

        # Any other git subcommand (not explicitly allowlisted or blocked)
        # is treated conservatively: block, and point at the sanctioned set.
        return False, (
            f"git {subcommand} is not in the reviewer role's sanctioned "
            f"command set (checkout, clean, add, commit, diff, status, log) — "
            f"{_DISCARD_POINTER}"
        )
    except Exception as exc:  # fail open
        return True, f"reviewer_bash_guard error — allowing: {exc}"


def _check_shadow_reviewer_command(command: str, tokens: list[str]) -> tuple[bool, str]:
    """Strict, default-deny check for `agent_type="shadow-reviewer"`.

    Two-phase shape, mirroring the existing `reviewer` agent_type branch's
    own default-deny pattern (CER-174): (a) reject on any shell
    control/substitution token — before any subcommand matching runs; (b)
    only after that check passes, require the `git` token be the *first*
    token of the command — no scanning the remainder of the token list for
    "any" git invocation (the exact `_find_git_invocation`-based bypass class
    this story closes). Only bare `git log`/`git status`/`git diff` (with
    ordinary read-only flags) are sanctioned. No other git subcommand and no
    non-git command is allowed — the shadow-reviewer has no legitimate write
    path via Bash at all (INFRA-388).
    """
    # Phase (a): control/substitution tokens, checked against the raw string
    # so no tokenization step can be used to smuggle one past this check.
    # Kept here (in addition to check_command's own pre-tokenize check) so
    # this function stays independently safe for any other caller.
    if _has_control_token(command):
        return False, (
            "shell control/substitution tokens are blocked for the "
            "shadow-reviewer role — it has no legitimate write path via "
            "Bash at all"
        )

    if not tokens:
        return False, (
            "not a git invocation — blocked for the shadow-reviewer role, "
            "which has no legitimate write path via Bash at all"
        )

    # Phase (b): the git token must be the FIRST token — no scanning the
    # rest of the token list for "any" git invocation (INFRA-324 pattern).
    if tokens[0] != "git":
        return False, (
            "not a git invocation — blocked for the shadow-reviewer role, "
            "which has no legitimate write path via Bash at all"
        )

    subcommand = None
    for arg in tokens[1:]:
        if not arg.startswith("-"):
            subcommand = arg
            break

    if subcommand is None:
        return False, (
            "not a git invocation — blocked for the shadow-reviewer role, "
            "which has no legitimate write path via Bash at all"
        )

    if subcommand not in _SHADOW_REVIEWER_ALLOWED_SUBCOMMANDS:
        return False, (
            f"git {subcommand} is not in the shadow-reviewer role's "
            "sanctioned read-only command set (log, status, diff)"
        )

    return True, f"sanctioned shadow-reviewer read-only git {subcommand} — allowing"


def _find_git_invocation(tokens: list[str]) -> tuple["str | None", list[str]]:
    """Find a `git` token in *tokens* and return (subcommand, remaining_args).

    Handles simple compound commands (`git status && git commit`, `cd x &&
    git checkout -- y`) by scanning for the first `git` token, then reading
    forward for its subcommand (the first following token that doesn't start
    with `-`) and collecting the rest of that git invocation's args (up to
    the next shell operator) as *flags*.
    """
    shell_operators = {"&&", "||", ";", "|"}
    for i, tok in enumerate(tokens):
        if tok != "git":
            continue
        rest = tokens[i + 1:]
        subcommand = None
        args: list[str] = []
        for j, arg in enumerate(rest):
            if arg in shell_operators:
                break
            if subcommand is None and not arg.startswith("-"):
                subcommand = arg
                continue
            args.append(arg)
        if subcommand is not None:
            return subcommand, args
    return None, []


def _is_sanctioned_clean(tokens: list[str]) -> bool:
    """`git clean -fd -- <path>` or whole-tree `git clean -fd` only."""
    _, args = _find_git_invocation(tokens)
    short_flag_letters = set()
    for a in args:
        if a.startswith("-") and not a.startswith("--") and a != "-":
            short_flag_letters.update(a[1:])
    has_f_and_d = "f" in short_flag_letters and "d" in short_flag_letters
    if not has_f_and_d:
        return False
    non_flag_args = [a for a in args if a != "--" and not a.startswith("-")]
    # Either no path (whole-tree) or exactly one path after `-fd`.
    return len(non_flag_args) <= 1


def _has_bare_force_flag(flags: list[str]) -> bool:
    return any(f in ("--force", "-f") for f in flags)


def _is_branch_delete_force(tokens: list[str]) -> bool:
    _, args = _find_git_invocation(tokens)
    has_delete = "-D" in args or "--delete" in args or "-d" in args
    has_force = "-D" in args or "--force" in args or "-f" in args
    return has_delete and has_force
