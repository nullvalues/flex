"""Tests for documentation file existence and constraints."""

from __future__ import annotations

from pathlib import Path


def test_readme_exists_and_under_400_lines() -> None:
    readme = Path(__file__).resolve().parent.parent.parent / "README.md"
    assert readme.exists(), "README.md does not exist at repo root"
    lines = readme.read_text(encoding="utf-8").splitlines()
    assert len(lines) < 400, f"README.md has {len(lines)} lines, must be under 400"


def test_pipe_architecture_doc_exists() -> None:
    pipe_doc = Path(__file__).resolve().parent.parent.parent / "docs" / "pipe-architecture.md"
    assert pipe_doc.exists(), "docs/pipe-architecture.md does not exist"
