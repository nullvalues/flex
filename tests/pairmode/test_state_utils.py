"""Tests for state_utils._atomic_write_json (CER-050 / INFRA-200)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

import sys

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "skills" / "pairmode" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from state_utils import _atomic_write_json  # noqa: E402


def test_atomic_write_json_writes_expected_content(tmp_path: Path) -> None:
    """_atomic_write_json writes the expected JSON content to the target path."""
    target = tmp_path / "state.json"
    data = {"key": "value", "number": 42}

    _atomic_write_json(target, data)

    assert target.exists()
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written == data


def test_atomic_write_json_overwrites_existing(tmp_path: Path) -> None:
    """_atomic_write_json overwrites an existing file correctly."""
    target = tmp_path / "state.json"
    target.write_text(json.dumps({"old": "data"}), encoding="utf-8")

    new_data = {"new": "data", "x": 1}
    _atomic_write_json(target, new_data)

    written = json.loads(target.read_text(encoding="utf-8"))
    assert written == new_data


def test_atomic_write_json_cleans_up_tmp_on_exception(tmp_path: Path) -> None:
    """_atomic_write_json deletes the .tmp file when os.replace raises."""
    target = tmp_path / "state.json"
    data = {"foo": "bar"}

    tmp_files_created: list[str] = []

    original_named_temp = __import__("tempfile").NamedTemporaryFile

    class _CapturingNTF:
        """Thin wrapper that records the tmp path before os.replace is patched."""

        def __init__(self, *args, **kwargs):
            self._ntf = original_named_temp(*args, **kwargs)
            tmp_files_created.append(self._ntf.name)

        def __enter__(self):
            return self._ntf.__enter__()

        def __exit__(self, *a):
            return self._ntf.__exit__(*a)

    with patch("state_utils.os.replace", side_effect=OSError("simulated replace failure")):
        with pytest.raises(OSError, match="simulated replace failure"):
            _atomic_write_json(target, data)

    # Target must not have been created
    assert not target.exists()

    # All .tmp siblings must have been cleaned up
    for p in tmp_files_created:
        assert not Path(p).exists(), f"tmp file not cleaned up: {p}"

    # Verify by scanning the directory directly
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == [], f"leftover .tmp files: {leftovers}"


def test_atomic_write_json_no_tmp_left_after_success(tmp_path: Path) -> None:
    """No .tmp files remain in the directory after a successful write."""
    target = tmp_path / "state.json"
    _atomic_write_json(target, {"a": 1})

    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == [], f"unexpected .tmp files: {leftovers}"
