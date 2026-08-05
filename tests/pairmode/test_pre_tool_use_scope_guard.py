"""Tests for hooks/pre_tool_use.py Edit/Write → scope_guard dispatch (INFRA-139).

These tests load the hook module in-process and patch sys.stdin/sys.stdout
to drive its `main()` function, mocking `scope_guard.check_path` to avoid
needing a real project tree.
"""
from __future__ import annotations

import importlib
import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_PATH = REPO_ROOT / "hooks" / "pre_tool_use.py"
SCRIPTS_DIR = REPO_ROOT / "skills" / "pairmode" / "scripts"

# Put the pairmode scripts dir on sys.path so test bodies can
# `import scope_guard` / `import context_budget` to patch their attributes.
# The hook itself also inserts this path on module load.
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load_hook_module():
    """Load hooks/pre_tool_use.py as a fresh module each call."""
    # Drop any cached copy so the hook re-imports cleanly each test.
    sys.modules.pop("pre_tool_use_hook_under_test", None)

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "pre_tool_use_hook_under_test", str(HOOK_PATH)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_main(stdin_payload: dict) -> tuple[int, str]:
    """Invoke hook.main() with crafted stdin; return (exit_code, stdout_text)."""
    hook = _load_hook_module()

    stdin_buf = io.StringIO(json.dumps(stdin_payload))
    stdout_buf = io.StringIO()

    exit_code = 0
    with patch.object(sys, "stdin", stdin_buf), patch.object(sys, "stdout", stdout_buf):
        try:
            hook.main()
        except SystemExit as e:
            exit_code = int(e.code) if e.code is not None else 0
    return exit_code, stdout_buf.getvalue()


# ---------------------------------------------------------------------------
# Test 1: Edit allowed → no block emitted
# ---------------------------------------------------------------------------


def test_edit_allowed_path_does_not_block(tmp_path):
    """check_path returning (True, 'allowed') produces no stdout output."""
    import scope_guard  # already on sys.path via _load_hook_module path setup

    with patch.object(scope_guard, "check_path", return_value=(True, "allowed")):
        exit_code, stdout = _run_main({
            "tool_name": "Edit",
            "tool_input": {"file_path": "foo.py"},
            "cwd": str(tmp_path),
        })

    assert exit_code == 0
    assert stdout.strip() == ""


# ---------------------------------------------------------------------------
# Test 2: Edit blocked → block JSON emitted
# ---------------------------------------------------------------------------


def test_edit_blocked_path_emits_block(tmp_path):
    """check_path returning (False, reason) emits a decision:block JSON payload."""
    import scope_guard

    with patch.object(scope_guard, "check_path", return_value=(False, "not in story scope")):
        exit_code, stdout = _run_main({
            "tool_name": "Edit",
            "tool_input": {"file_path": "foo.py"},
            "cwd": str(tmp_path),
        })

    assert exit_code == 0
    payload = json.loads(stdout.strip())
    assert payload == {"decision": "block", "reason": "not in story scope"}


# ---------------------------------------------------------------------------
# Test 3: Write blocked → block JSON emitted
# ---------------------------------------------------------------------------


def test_write_blocked_path_emits_block(tmp_path):
    """Same as Edit-blocked but for the Write tool name."""
    import scope_guard

    with patch.object(scope_guard, "check_path", return_value=(False, "not in story scope")):
        exit_code, stdout = _run_main({
            "tool_name": "Write",
            "tool_input": {"file_path": "bar.py"},
            "cwd": str(tmp_path),
        })

    assert exit_code == 0
    payload = json.loads(stdout.strip())
    assert payload == {"decision": "block", "reason": "not in story scope"}


# ---------------------------------------------------------------------------
# Test 4: scope_guard.check_path raises → fail open (no block)
# ---------------------------------------------------------------------------


def test_scope_guard_exception_fails_open(tmp_path):
    """If check_path raises, the hook must exit cleanly without blocking."""
    import scope_guard

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated scope_guard failure")

    with patch.object(scope_guard, "check_path", side_effect=_raise):
        exit_code, stdout = _run_main({
            "tool_name": "Edit",
            "tool_input": {"file_path": "foo.py"},
            "cwd": str(tmp_path),
        })

    assert exit_code == 0
    assert stdout.strip() == ""


# ---------------------------------------------------------------------------
# Test 5: Task branch unaffected — scope_guard.check_path is not called
# ---------------------------------------------------------------------------


def test_task_branch_unaffected(tmp_path):
    """A Task tool dispatch must not invoke scope_guard.check_path."""
    import scope_guard
    import context_budget

    # context_budget.decide returns a non-block result.
    with patch.object(context_budget, "decide", return_value=None) as mock_decide, \
         patch.object(scope_guard, "check_path") as mock_check:
        exit_code, stdout = _run_main({
            "tool_name": "Task",
            "tool_input": {"subagent_type": "builder"},
            "cwd": str(tmp_path),
            "transcript_path": "",
        })

    assert exit_code == 0
    assert stdout.strip() == ""
    assert mock_check.called is False
    assert mock_decide.called is True


# ---------------------------------------------------------------------------
# Test 6: Unknown tool name exits cleanly
# ---------------------------------------------------------------------------


def test_unknown_tool_name_exits_cleanly(tmp_path):
    """tool_name=Bash (not Task/Edit/Write) exits 0 with no output."""
    import scope_guard
    import context_budget

    with patch.object(scope_guard, "check_path") as mock_check, \
         patch.object(context_budget, "decide") as mock_decide:
        exit_code, stdout = _run_main({
            "tool_name": "Bash",
            "cwd": str(tmp_path),
        })

    assert exit_code == 0
    assert stdout.strip() == ""
    assert mock_check.called is False
    assert mock_decide.called is False


# ---------------------------------------------------------------------------
# INFRA-281 (CER-095.2), B11: _resolve_flex_factor uses resolve_call_story
# ---------------------------------------------------------------------------


def _write_story_with_flex_factor(project_dir: Path, story_id: str, flex_factor: float) -> None:
    rail = story_id.split("-")[0]
    story_dir = project_dir / "docs" / "stories" / rail
    story_dir.mkdir(parents=True, exist_ok=True)
    (story_dir / f"{story_id}.md").write_text(
        f"---\nid: {story_id}\nrail: {rail}\ntitle: T\nstatus: draft\nphase: \"1\"\n"
        f"flex_factor: {flex_factor}\nprimary_files:\n---\n\n## Ensures\n\n- Done.\n"
    )


def _make_linked_worktree(main_root: Path, story_id: str) -> Path:
    worktree_dir = main_root / ".pairmode-worktrees" / story_id
    worktree_dir.mkdir(parents=True)
    git_worktrees_dir = main_root / ".git" / "worktrees" / story_id
    git_worktrees_dir.mkdir(parents=True)
    (worktree_dir / ".git").write_text(f"gitdir: {git_worktrees_dir}\n")
    return worktree_dir


def test_resolve_flex_factor_from_worktree_cwd(tmp_path):
    """flex_factor resolves via resolve_call_story's worktree-cwd signal."""
    hook = _load_hook_module()
    main_root = tmp_path / "main"
    main_root.mkdir()
    worktree_dir = _make_linked_worktree(main_root, "INFRA-300")
    # A real worktree checkout mirrors the repo tree, story files included —
    # _story_path resolves docs/stories/ against project_dir as passed
    # (the worktree cwd), not against the resolved main root.
    _write_story_with_flex_factor(worktree_dir, "INFRA-300", 1.5)

    result = hook._resolve_flex_factor(worktree_dir)
    assert result == 1.5


def test_resolve_flex_factor_defaults_to_1_0_when_ambiguous(tmp_path):
    """Two stories active, cwd is the main checkout — no worktree signal —
    resolution is ambiguous, so the gate falls back to the documented 1.0
    default rather than guessing which story's flex_factor applies."""
    hook = _load_hook_module()
    companion = tmp_path / ".companion"
    companion.mkdir()
    # INFRA-271 (CER-080): fresh, distinct timestamps — a stale-both-entries
    # fixture here would resolve to "stale" rather than "ambiguous" and no
    # longer test what this test's name claims.
    now = datetime.now(timezone.utc)
    (companion / "state.json").write_text(
        json.dumps(
            {
                "current_stories": {
                    "INFRA-301": {"id": "INFRA-301", "set_at": now.isoformat()},
                    "INFRA-302": {
                        "id": "INFRA-302",
                        "set_at": (now + timedelta(seconds=1)).isoformat(),
                    },
                }
            }
        )
    )
    _write_story_with_flex_factor(tmp_path, "INFRA-301", 2.0)
    _write_story_with_flex_factor(tmp_path, "INFRA-302", 3.0)

    result = hook._resolve_flex_factor(tmp_path)
    assert result == 1.0


def test_resolve_flex_factor_defaults_to_1_0_when_no_active_story(tmp_path):
    hook = _load_hook_module()
    result = hook._resolve_flex_factor(tmp_path)
    assert result == 1.0


# ---------------------------------------------------------------------------
# INFRA-320 (CER-128) § A / G2 — standing surfaces at the hook boundary
# ---------------------------------------------------------------------------


def test_hook_allows_standing_surface_and_blocks_undeclared_code_file(tmp_path):
    """End-to-end through the real (unmocked) scope_guard.check_path: a
    standing surface (docs/cer/backlog.md) is allowed and an undeclared code
    file is still blocked, for the same active story."""
    story_id = "INFRA-950"
    companion = tmp_path / ".companion"
    companion.mkdir()
    (companion / "state.json").write_text(
        json.dumps(
            {"current_story": {"id": story_id, "set_at": datetime.now(timezone.utc).isoformat()}}
        )
    )
    perm_dir = tmp_path / "docs" / "phases" / "permissions"
    perm_dir.mkdir(parents=True)
    (perm_dir / f"{story_id}.json").write_text(
        json.dumps({"story_id": story_id, "allowed_paths": ["skills/foo.py"]})
    )

    # Standing surface — no block.
    exit_code, stdout = _run_main(
        {
            "tool_name": "Edit",
            "tool_input": {"file_path": "docs/cer/backlog.md"},
            "cwd": str(tmp_path),
        }
    )
    assert exit_code == 0
    assert stdout.strip() == ""

    # Undeclared code file — still blocked.
    exit_code, stdout = _run_main(
        {
            "tool_name": "Edit",
            "tool_input": {"file_path": "skills/undeclared.py"},
            "cwd": str(tmp_path),
        }
    )
    assert exit_code == 0
    payload = json.loads(stdout.strip())
    assert payload["decision"] == "block"
    assert "not in story scope" in payload["reason"]


# ---------------------------------------------------------------------------
# INFRA-365 (Phase-118 checkpoint-security HIGH) — the shadow-reviewer's
# suggestions file is a standing surface at the real hook boundary. These
# tests drive the real (unmocked) pre_tool_use -> scope_guard.check_path
# path through a live worktree, the same call shape as
# test_hook_allows_standing_surface_and_blocks_undeclared_code_file above —
# not check_path called directly, and not a Path.write_text bypass (the
# defect this story fixes shipped precisely because the covering test used
# that bypass, see docs/stories/INFRA/INFRA-365.md § Context).
# ---------------------------------------------------------------------------


def _make_worktree_with_active_story(tmp_path: Path, story_id: str) -> Path:
    """Build a fake linked worktree (same shape as `_make_linked_worktree`)
    with an active story and a permissions artifact that does NOT declare
    `.pairmode-suggestions.md` — the exact live-dispatch shape described in
    the story's `## Context`."""
    main_root = tmp_path / "main"
    main_root.mkdir()
    companion = main_root / ".companion"
    companion.mkdir()
    (companion / "state.json").write_text(
        json.dumps(
            {"current_story": {"id": story_id, "set_at": datetime.now(timezone.utc).isoformat()}}
        )
    )
    perm_dir = main_root / "docs" / "phases" / "permissions"
    perm_dir.mkdir(parents=True)
    (perm_dir / f"{story_id}.json").write_text(
        json.dumps({"story_id": story_id, "allowed_paths": ["skills/foo.py"]})
    )
    worktree_dir = _make_linked_worktree(main_root, story_id)
    return worktree_dir


def test_hook_allows_write_to_suggestions_file_in_active_story_worktree(tmp_path):
    """Ensures 1 & 3: with an active story resolved and
    `.pairmode-suggestions.md` absent from that story's declared files, a
    real `Write` to `<worktree>/.pairmode-suggestions.md` through the actual
    pre_tool_use hook entry point is not blocked."""
    story_id = "INFRA-962"
    worktree_dir = _make_worktree_with_active_story(tmp_path, story_id)

    exit_code, stdout = _run_main(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": ".pairmode-suggestions.md"},
            "cwd": str(worktree_dir),
        }
    )
    assert exit_code == 0
    assert stdout.strip() == ""


def test_hook_still_blocks_neighbouring_undeclared_paths(tmp_path):
    """Ensures 2 & 4: the allowance is keyed on the exact filename at the
    worktree root — a neighbouring dotfile and a nested path of the same
    name are both still denied, and an ordinary undeclared code path in the
    same worktree is still denied too (the fix did not disable story-scope
    enforcement)."""
    story_id = "INFRA-963"
    worktree_dir = _make_worktree_with_active_story(tmp_path, story_id)

    for undeclared_path in (
        ".pairmode-other.md",
        "subdir/.pairmode-suggestions.md",
        "skills/undeclared.py",
    ):
        exit_code, stdout = _run_main(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": undeclared_path},
                "cwd": str(worktree_dir),
            }
        )
        assert exit_code == 0
        payload = json.loads(stdout.strip())
        assert payload["decision"] == "block", f"expected block for {undeclared_path}"
        assert "not in story scope" in payload["reason"]


# ---------------------------------------------------------------------------
# CER-174 (INFRA-396), Ensures 9 — the agent_type-scoped shadow-reviewer
# write confinement must actually reach `scope_guard.check_path` through the
# hook's real Edit/Write dispatch, not just via a direct check_path() call
# (Ensures 5/6 already cover that — this is exactly the coverage gap that
# let the fix ship inert-in-production in the first attempt). Driven through
# the real (unmocked) `main()` and real `check_path`, following the same
# pattern as `test_hook_allows_write_to_suggestions_file_in_active_story_worktree`
# above.
# ---------------------------------------------------------------------------


def test_hook_blocks_shadow_reviewer_write_outside_suggestions_file(tmp_path):
    """A payload with agent_type="shadow-reviewer", tool_name Edit/Write, and
    a file_path other than .pairmode-suggestions.md emits a decision:block
    payload — proving agent_type reached check_path through the real
    dispatch, not merely a direct check_path() call."""
    story_id = "INFRA-964"
    worktree_dir = _make_worktree_with_active_story(tmp_path, story_id)

    for tool_name in ("Edit", "Write"):
        exit_code, stdout = _run_main(
            {
                "tool_name": tool_name,
                "tool_input": {"file_path": "skills/foo.py"},
                "cwd": str(worktree_dir),
                "agent_type": "shadow-reviewer",
            }
        )
        assert exit_code == 0
        payload = json.loads(stdout.strip())
        assert payload["decision"] == "block", f"expected block for {tool_name}"
        assert payload["reason"]


def test_hook_allows_shadow_reviewer_write_to_suggestions_file(tmp_path):
    """The same real dispatch, for the one path the shadow-reviewer IS
    permitted to write — no block emitted."""
    story_id = "INFRA-965"
    worktree_dir = _make_worktree_with_active_story(tmp_path, story_id)

    exit_code, stdout = _run_main(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": ".pairmode-suggestions.md"},
            "cwd": str(worktree_dir),
            "agent_type": "shadow-reviewer",
        }
    )
    assert exit_code == 0
    assert stdout.strip() == ""


def test_hook_allows_builder_write_to_same_path_shadow_reviewer_is_denied(tmp_path):
    """Same path, same story, agent_type="builder" (the same shape the hook
    forwards for a real builder call) — still allowed, proving the two
    scopes genuinely differ through the real dispatch, not just at the
    check_path() unit level."""
    story_id = "INFRA-966"
    worktree_dir = _make_worktree_with_active_story(tmp_path, story_id)

    exit_code, stdout = _run_main(
        {
            "tool_name": "Edit",
            "tool_input": {"file_path": "skills/foo.py"},
            "cwd": str(worktree_dir),
            "agent_type": "builder",
        }
    )
    assert exit_code == 0
    assert stdout.strip() == ""


# ---------------------------------------------------------------------------
# CER-175 (INFRA-397), Ensures 9 — same real (unmocked) dispatch as the
# INFRA-396 cases directly above, but with an ABSOLUTE file_path — the exact
# form Claude Code actually sends for Edit/Write tool_input.file_path, and
# the coverage gap that let the worktree-prefix bug ship: every INFRA-396
# shadow-reviewer test above used a relative file_path, which never exercises
# the worktree-prefix-stripping path at all.
# ---------------------------------------------------------------------------


def test_hook_allows_shadow_reviewer_write_to_suggestions_file_absolute_path(tmp_path):
    """An absolute `<worktree>/.pairmode-suggestions.md` file_path emits no
    block — the real bug this story fixes: this exact call shape was wrongly
    DENIED before the worktree-prefix strip was added to the shadow-reviewer
    branch."""
    story_id = "INFRA-967"
    worktree_dir = _make_worktree_with_active_story(tmp_path, story_id)
    abs_path = worktree_dir / ".pairmode-suggestions.md"

    exit_code, stdout = _run_main(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": str(abs_path)},
            "cwd": str(worktree_dir),
            "agent_type": "shadow-reviewer",
        }
    )
    assert exit_code == 0
    assert stdout.strip() == ""


def test_hook_blocks_shadow_reviewer_write_outside_suggestions_file_absolute_path(
    tmp_path,
):
    """Forbidden proxy check: the same absolute-path call shape, but to a
    different in-worktree file, still emits decision:block — the fix must
    not have widened the allowed set beyond the one sanctioned filename."""
    story_id = "INFRA-968"
    worktree_dir = _make_worktree_with_active_story(tmp_path, story_id)
    abs_path = worktree_dir / "skills" / "foo.py"

    exit_code, stdout = _run_main(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": str(abs_path)},
            "cwd": str(worktree_dir),
            "agent_type": "shadow-reviewer",
        }
    )
    assert exit_code == 0
    payload = json.loads(stdout.strip())
    assert payload["decision"] == "block"
    assert payload["reason"]
