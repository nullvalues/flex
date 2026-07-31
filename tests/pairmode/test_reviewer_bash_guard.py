"""Tests for skills/pairmode/scripts/reviewer_bash_guard.py (INFRA-324).

Covers: every allowlisted form returns True; every blocked subcommand
returns False with a non-empty reason; a non-"reviewer" agent_type
(including None) always returns True regardless of command content; a
non-git command always returns True.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "skills" / "pairmode" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import reviewer_bash_guard as guard  # noqa: E402


# ---------------------------------------------------------------------------
# Non-reviewer agent_type — always allowed, no inspection.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("agent_type", [None, "builder", "loop-breaker", "security-auditor", "intent-reviewer", "orchestrator"])
@pytest.mark.parametrize("command", ["git reset --hard main", "git revert HEAD", "git push origin main"])
def test_non_reviewer_agent_type_always_allowed(agent_type, command):
    allowed, reason = guard.check_command(command, agent_type)
    assert allowed is True
    assert reason


# ---------------------------------------------------------------------------
# Non-git commands — always allowed for the reviewer role too.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", ["echo hello", "pytest -x -q", "ls -la", "uv run pytest tests/"])
def test_non_git_command_always_allowed(command):
    allowed, reason = guard.check_command(command, "reviewer")
    assert allowed is True
    assert reason


# ---------------------------------------------------------------------------
# Allowlisted git forms for the reviewer role.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git checkout -- foo.py",
        "git checkout -- foo.py bar.py",
        "git checkout .",
        "git clean -fd -- foo.py",
        "git clean -fd",
        "git clean -fdx",
        "git add foo.py",
        "git add -A",
        "git commit -m 'story-INFRA-324'",
        "git diff HEAD",
        "git diff --stat",
        "git status",
        "git status --short",
        "git log -5",
    ],
)
def test_allowlisted_reviewer_forms_return_true(command):
    allowed, reason = guard.check_command(command, "reviewer")
    assert allowed is True
    assert reason


# ---------------------------------------------------------------------------
# Blocked git subcommands/forms for the reviewer role.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git reset --hard main",
        "git reset --hard",
        "git reset HEAD~1",
        "git revert HEAD",
        "git revert --no-edit HEAD",
        "git rebase main",
        "git rebase -i HEAD~3",
        "git push origin main",
        "git push --force origin main",
        "git branch -D some-branch",
        "git branch --delete --force some-branch",
        "git checkout . --force",
        "git clean -fd extra-arg another-arg",
    ],
)
def test_blocked_reviewer_forms_return_false_with_reason(command):
    allowed, reason = guard.check_command(command, "reviewer")
    assert allowed is False
    assert reason
    assert isinstance(reason, str)


def test_blocked_reason_names_the_subcommand_and_discard_worktree():
    allowed, reason = guard.check_command("git reset --hard main", "reviewer")
    assert allowed is False
    assert "reset" in reason
    assert "discard-story-worktree" in reason


def test_empty_command_allowed():
    allowed, reason = guard.check_command("", "reviewer")
    assert allowed is True
    assert reason


def test_unbalanced_quotes_fail_open():
    allowed, reason = guard.check_command("git commit -m 'unterminated", "reviewer")
    assert allowed is True
    assert reason
