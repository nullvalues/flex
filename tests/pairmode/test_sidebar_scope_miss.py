"""Tests for scope_miss extraction and lesson-save logic in sidebar.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure the repo root is on sys.path so sidebar.py's _REPO_ROOT insertion
# (and our own imports from skills/) work correctly.
_REPO_ROOT = Path(__file__).parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# sidebar.py lives in skills/companion/scripts/.  It uses a script-block header
# that uv run processes but plain import ignores. We import the module directly;
# the Rich dependency must already be available (it is listed in sidebar.py's
# inline dependency block and installed in the uv environment).
SIDEBAR_DIR = _REPO_ROOT / "skills" / "companion" / "scripts"
if str(SIDEBAR_DIR) not in sys.path:
    sys.path.insert(0, str(SIDEBAR_DIR))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "sidebar",
    str(SIDEBAR_DIR / "sidebar.py"),
)
sidebar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sidebar)  # type: ignore[union-attr]

_extract_scope_misses = sidebar._extract_scope_misses
_save_scope_miss_lessons = sidebar._save_scope_miss_lessons
_SCOPE_BLOCK_RE = sidebar._SCOPE_BLOCK_RE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jsonl(messages: list[dict]) -> str:
    """Serialise a list of JSONL message objects to a string."""
    return "\n".join(json.dumps(m) for m in messages) + "\n"


def _tool_use_msg(tool_use_id: str, name: str, file_path: str) -> dict:
    """Assistant message containing a single tool_use block."""
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_use_id,
                    "name": name,
                    "input": {"file_path": file_path},
                }
            ],
        },
    }


def _tool_result_msg(tool_use_id: str, text: str) -> dict:
    """User message containing a single tool_result block."""
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": text,
                }
            ],
        },
    }


def _initial_lessons() -> dict:
    return {"version": "1.0.0", "lessons": []}


def _patch_lesson_utils(monkeypatch: pytest.MonkeyPatch, lessons_file: Path) -> None:
    """Redirect lesson_utils LESSONS_FILE and patch sidebar's imported names."""
    import skills.pairmode.scripts.lesson_utils as lesson_utils_mod
    monkeypatch.setattr(lesson_utils_mod, "LESSONS_FILE", lessons_file)
    # sidebar imported load_lessons/save_lessons/next_lesson_id at module load time;
    # patch them at the sidebar module level so _save_scope_miss_lessons sees them.
    monkeypatch.setattr(sidebar, "load_lessons", lesson_utils_mod.load_lessons)
    monkeypatch.setattr(sidebar, "save_lessons", lesson_utils_mod.save_lessons)
    monkeypatch.setattr(sidebar, "next_lesson_id", lesson_utils_mod.next_lesson_id)


# ---------------------------------------------------------------------------
# Tests — _extract_scope_misses
# ---------------------------------------------------------------------------


class TestExtractScopeMisses:
    def test_extract_block_then_elevate(self, tmp_path: Path) -> None:
        """Block followed by elevation should produce elevated=True."""
        transcript = tmp_path / "transcript.jsonl"
        # (a) assistant tool_use Edit on skills/foo/bar.py
        # (b) user tool_result with scope_guard block message
        # (c) assistant tool_use Edit on the same path (elevation)
        messages = [
            _tool_use_msg("tu-001", "Edit", "skills/foo/bar.py"),
            _tool_result_msg(
                "tu-001",
                "not in story scope for INFRA-154: skills/foo/bar.py",
            ),
            _tool_use_msg("tu-002", "Edit", "skills/foo/bar.py"),
        ]
        transcript.write_text(_make_jsonl(messages))

        result = _extract_scope_misses(str(transcript))
        assert result == [
            {"story_id": "INFRA-154", "blocked_path": "skills/foo/bar.py", "elevated": True}
        ]

    def test_extract_blocked_no_elevation(self, tmp_path: Path) -> None:
        """Block without subsequent edit should produce elevated=False."""
        transcript = tmp_path / "transcript.jsonl"
        messages = [
            _tool_use_msg("tu-001", "Edit", "skills/foo/bar.py"),
            _tool_result_msg(
                "tu-001",
                "not in story scope for INFRA-154: skills/foo/bar.py",
            ),
            # No subsequent edit on the same path.
        ]
        transcript.write_text(_make_jsonl(messages))

        result = _extract_scope_misses(str(transcript))
        assert len(result) == 1
        assert result[0]["elevated"] is False
        assert result[0]["story_id"] == "INFRA-154"
        assert result[0]["blocked_path"] == "skills/foo/bar.py"

    def test_extract_ignores_unrelated_tool_results(self, tmp_path: Path) -> None:
        """tool_result blocks with unrelated text should produce no misses."""
        transcript = tmp_path / "transcript.jsonl"
        messages = [
            _tool_result_msg("tu-001", "file not found"),
            _tool_result_msg("tu-002", "command failed: permission denied"),
        ]
        transcript.write_text(_make_jsonl(messages))

        result = _extract_scope_misses(str(transcript))
        assert result == []

    def test_extract_dedupes_repeated_blocks(self, tmp_path: Path) -> None:
        """The same (story_id, path) blocked three times should yield exactly one dict."""
        transcript = tmp_path / "transcript.jsonl"
        messages = [
            _tool_result_msg(
                "tu-001", "not in story scope for INFRA-154: skills/foo/bar.py"
            ),
            _tool_result_msg(
                "tu-002", "not in story scope for INFRA-154: skills/foo/bar.py"
            ),
            _tool_result_msg(
                "tu-003", "not in story scope for INFRA-154: skills/foo/bar.py"
            ),
        ]
        transcript.write_text(_make_jsonl(messages))

        result = _extract_scope_misses(str(transcript))
        assert len(result) == 1
        assert result[0]["story_id"] == "INFRA-154"
        assert result[0]["blocked_path"] == "skills/foo/bar.py"

    def test_extract_no_transcript_none(self) -> None:
        """Passing None should return []."""
        result = _extract_scope_misses(None)  # type: ignore[arg-type]
        assert result == []

    def test_extract_no_transcript_nonexistent(self, tmp_path: Path) -> None:
        """Passing a path that does not exist should return []."""
        result = _extract_scope_misses(str(tmp_path / "nonexistent.jsonl"))
        assert result == []


# ---------------------------------------------------------------------------
# Tests — _save_scope_miss_lessons
# ---------------------------------------------------------------------------


class TestSaveScopeMissLessons:
    def test_save_writes_new_lesson(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One new miss should write one lesson to lessons.json."""
        lessons_file = tmp_path / "lessons.json"
        lessons_file.write_text(json.dumps(_initial_lessons()))
        _patch_lesson_utils(monkeypatch, lessons_file)

        miss = {"story_id": "INFRA-154", "blocked_path": "skills/foo/bar.py", "elevated": True}
        count = _save_scope_miss_lessons([miss])

        assert count == 1
        data = json.loads(lessons_file.read_text())
        assert len(data["lessons"]) == 1
        lesson = data["lessons"][0]
        assert lesson["type"] == "scope_miss"
        assert lesson["trigger"] == "scope_miss:INFRA-154:skills/foo/bar.py"

    def test_save_idempotent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Calling twice with the same miss should write only one lesson."""
        lessons_file = tmp_path / "lessons.json"
        lessons_file.write_text(json.dumps(_initial_lessons()))
        _patch_lesson_utils(monkeypatch, lessons_file)

        miss = {"story_id": "INFRA-154", "blocked_path": "skills/foo/bar.py", "elevated": False}

        count1 = _save_scope_miss_lessons([miss])
        count2 = _save_scope_miss_lessons([miss])

        assert count1 == 1
        assert count2 == 0
        data = json.loads(lessons_file.read_text())
        matching = [
            e for e in data["lessons"]
            if e.get("trigger") == "scope_miss:INFRA-154:skills/foo/bar.py"
        ]
        assert len(matching) == 1

    def test_save_learning_text_varies_by_elevation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Elevated and non-elevated misses should produce different learning text."""
        lessons_file = tmp_path / "lessons.json"
        lessons_file.write_text(json.dumps(_initial_lessons()))
        _patch_lesson_utils(monkeypatch, lessons_file)

        miss_elevated = {
            "story_id": "INFRA-154",
            "blocked_path": "skills/foo/bar.py",
            "elevated": True,
        }
        miss_refused = {
            "story_id": "INFRA-155",
            "blocked_path": "skills/baz/qux.py",
            "elevated": False,
        }

        count = _save_scope_miss_lessons([miss_elevated, miss_refused])
        assert count == 2

        data = json.loads(lessons_file.read_text())
        lessons_by_trigger = {e["trigger"]: e for e in data["lessons"]}

        elevated_lesson = lessons_by_trigger["scope_miss:INFRA-154:skills/foo/bar.py"]
        refused_lesson = lessons_by_trigger["scope_miss:INFRA-155:skills/baz/qux.py"]

        assert elevated_lesson["learning"] != refused_lesson["learning"]
        assert "granted" in elevated_lesson["learning"]
        assert "refused" in refused_lesson["learning"]
