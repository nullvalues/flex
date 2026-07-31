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

Scope: this guard governs the `reviewer` role only. `agent_type != "reviewer"`
(including `None` — an orchestrator or non-subagent Bash call, and every
other subagent role: builder, loop-breaker, security-auditor, intent-reviewer)
always fails open with no command inspection at all — this is a
defense-in-depth guard behind the sandbox for one specific, already-observed
improvisation (a reviewer running `git reset --hard` / `git revert` on FAIL),
not a general Bash policy engine.

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


def check_command(command: str, agent_type: "str | None") -> tuple[bool, str]:
    try:
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
