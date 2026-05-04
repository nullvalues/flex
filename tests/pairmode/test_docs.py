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


def test_pairmode_contribution_guide_exists() -> None:
    pairmode_doc = Path(__file__).resolve().parent.parent.parent / "docs" / "pairmode" / "PAIRMODE.md"
    assert pairmode_doc.exists(), "docs/pairmode/PAIRMODE.md does not exist"


def test_changelog_exists_and_under_200_lines() -> None:
    changelog = Path(__file__).resolve().parent.parent.parent / "CHANGELOG.md"
    assert changelog.exists(), "CHANGELOG.md does not exist at repo root"
    lines = changelog.read_text(encoding="utf-8").splitlines()
    assert len(lines) < 200, f"CHANGELOG.md has {len(lines)} lines, must be under 200"


def test_contributing_exists_and_under_200_lines() -> None:
    contributing = Path(__file__).resolve().parent.parent.parent / "CONTRIBUTING.md"
    assert contributing.exists(), "CONTRIBUTING.md does not exist at repo root"
    lines = contributing.read_text(encoding="utf-8").splitlines()
    assert len(lines) < 200, f"CONTRIBUTING.md has {len(lines)} lines, must be under 200"


def test_readme_contains_reactive_and_proactive_positioning() -> None:
    readme = Path(__file__).resolve().parent.parent.parent / "README.md"
    text = readme.read_text(encoding="utf-8").lower()
    assert "reactive" in text, "README.md must mention 'reactive' for companion/pairmode positioning"
    assert "proactive" in text, "README.md must mention 'proactive' for companion/pairmode positioning"


def test_readme_skills_table_has_posture_column() -> None:
    readme = Path(__file__).resolve().parent.parent.parent / "README.md"
    text = readme.read_text(encoding="utf-8")
    assert "Posture" in text, "README.md skills table must contain a 'Posture' column header"


def test_readme_under_400_lines() -> None:
    readme = Path(__file__).resolve().parent.parent.parent / "README.md"
    lines = readme.read_text(encoding="utf-8").splitlines()
    assert len(lines) < 400, f"README.md has {len(lines)} lines, must be under 400"


def test_pairmode_doc_contains_relation_to_companion_section() -> None:
    pairmode_doc = Path(__file__).resolve().parent.parent.parent / "docs" / "pairmode" / "PAIRMODE.md"
    text = pairmode_doc.read_text(encoding="utf-8").lower()
    assert "in relation to companion" in text, (
        "PAIRMODE.md must contain a 'Pairmode in relation to companion' section"
    )
