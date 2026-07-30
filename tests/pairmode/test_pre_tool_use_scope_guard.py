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
