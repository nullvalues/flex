"""Tests for cer.py — CER triage CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from skills.pairmode.scripts.cer import (
    cli,
    append_finding,
    _escape_table_cell,
    _load_or_create_backlog,
    _next_cer_id,
    _parse_entries_from_backlog,
    BACKLOG_REL_PATH,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _backlog_path(project_dir: Path) -> Path:
    return project_dir / BACKLOG_REL_PATH


def _invoke(runner: CliRunner, args: list[str], input: str | None = None):
    return runner.invoke(cli, args, input=input, catch_exceptions=False)


# ---------------------------------------------------------------------------
# Test: creates backlog.md when it does not exist
# ---------------------------------------------------------------------------

def test_creates_backlog_when_missing(tmp_path: Path) -> None:
    backlog = _backlog_path(tmp_path)
    assert not backlog.exists()

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Missing auth check on admin endpoint",
            "--quadrant", "now",
        ],
    )
    assert result.exit_code == 0, result.output
    assert backlog.exists()
    content = backlog.read_text(encoding="utf-8")
    assert "Missing auth check on admin endpoint" in content
    assert "CER-001" in content


# ---------------------------------------------------------------------------
# Test: appends entry to the correct quadrant section
# ---------------------------------------------------------------------------

def test_appends_to_correct_quadrant(tmp_path: Path) -> None:
    runner = CliRunner()

    # Insert one finding in each quadrant
    quadrants = [
        ("now", "Do Now"),
        ("later", "Do Later"),
        ("much_later", "Do Much Later"),
    ]
    for q, _section in quadrants:
        result = _invoke(
            runner,
            [
                "--project-dir", str(tmp_path),
                "--finding", f"Finding for {q}",
                "--quadrant", q,
            ],
        )
        assert result.exit_code == 0, result.output

    content = _backlog_path(tmp_path).read_text(encoding="utf-8")

    # Each finding should appear under its correct section
    lines = content.splitlines()
    section_to_findings: dict[str, list[str]] = {
        "## Do Now": [],
        "## Do Later": [],
        "## Do Much Later": [],
    }
    current_section: str | None = None
    for line in lines:
        s = line.strip()
        if s in section_to_findings:
            current_section = s
        elif current_section and s.startswith("| CER-"):
            section_to_findings[current_section].append(s)

    assert any("Finding for now" in row for row in section_to_findings["## Do Now"])
    assert any("Finding for later" in row for row in section_to_findings["## Do Later"])
    assert any("Finding for much_later" in row for row in section_to_findings["## Do Much Later"])


# ---------------------------------------------------------------------------
# Test: never without resolution exits 1
# ---------------------------------------------------------------------------

def test_never_without_resolution_exits_1(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Low-value cosmetic thing",
            "--quadrant", "never",
            # no --resolution
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 1
    assert "resolution" in result.output.lower() or "resolution" in (result.exception or Exception()).__str__().lower()


# ---------------------------------------------------------------------------
# Test: never with resolution succeeds
# ---------------------------------------------------------------------------

def test_never_with_resolution_succeeds(tmp_path: Path) -> None:
    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Out of scope suggestion",
            "--quadrant", "never",
            "--resolution", "Not applicable to this project's scale",
        ],
    )
    assert result.exit_code == 0, result.output
    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    assert "Out of scope suggestion" in content
    assert "Not applicable to this project" in content
    assert "CER-001" in content


# ---------------------------------------------------------------------------
# Test: IDs are sequential across quadrants
# ---------------------------------------------------------------------------

def test_ids_sequential_across_quadrants(tmp_path: Path) -> None:
    runner = CliRunner()

    calls = [
        ("now", "First finding"),
        ("later", "Second finding"),
        ("much_later", "Third finding"),
        ("now", "Fourth finding"),
        ("never", "Fifth finding", "Rejected because out of scope"),
    ]

    for args in calls:
        extra = []
        if len(args) == 3:
            extra = ["--resolution", args[2]]
        result = _invoke(
            runner,
            [
                "--project-dir", str(tmp_path),
                "--finding", args[1],
                "--quadrant", args[0],
            ] + extra,
        )
        assert result.exit_code == 0, result.output

    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    for expected_id in ["CER-001", "CER-002", "CER-003", "CER-004", "CER-005"]:
        assert expected_id in content, f"{expected_id} not found in backlog"


# ---------------------------------------------------------------------------
# Test: multiple calls accumulate entries correctly
# ---------------------------------------------------------------------------

def test_multiple_calls_accumulate(tmp_path: Path) -> None:
    runner = CliRunner()

    for i in range(1, 6):
        result = _invoke(
            runner,
            [
                "--project-dir", str(tmp_path),
                "--finding", f"Finding number {i}",
                "--quadrant", "later",
            ],
        )
        assert result.exit_code == 0, result.output

    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    for i in range(1, 6):
        assert f"Finding number {i}" in content

    entries = _parse_entries_from_backlog(content)
    assert len(entries) == 5
    ids = [e["id"] for e in entries]
    assert ids == ["CER-001", "CER-002", "CER-003", "CER-004", "CER-005"]


# ---------------------------------------------------------------------------
# Test: graceful error when backlog.md has unexpected content
# ---------------------------------------------------------------------------

def test_graceful_on_unexpected_content(tmp_path: Path) -> None:
    """If backlog.md exists but has garbage content, append_finding raises ClickException."""
    backlog = _backlog_path(tmp_path)
    backlog.parent.mkdir(parents=True, exist_ok=True)
    # Write completely unparseable binary-like content
    backlog.write_text("<<< MERGE CONFLICT >>>\n<<<<<<<\nfoo\n=======\nbar\n>>>>>>>", encoding="utf-8")

    # Parsing garbage should not crash — it should return empty list (no table rows matched)
    # and then append works fine. The "graceful error" test verifies we don't raise an
    # unexpected exception (i.e., no crash).
    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Finding after corruption",
            "--quadrant", "now",
        ],
    )
    # Should either succeed (with CER-001 appended) or exit with a friendly error
    # but NEVER raise an unhandled exception
    assert result.exit_code in (0, 1)
    if result.exit_code == 0:
        content = backlog.read_text(encoding="utf-8")
        assert "Finding after corruption" in content


# ---------------------------------------------------------------------------
# Test: phase option is stored and rendered
# ---------------------------------------------------------------------------

def test_phase_option_stored(tmp_path: Path) -> None:
    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Phase-tagged finding",
            "--quadrant", "later",
            "--phase", "7",
        ],
    )
    assert result.exit_code == 0, result.output
    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    assert "Phase-tagged finding" in content
    # Phase 7 should appear in the row
    assert "7" in content


# ---------------------------------------------------------------------------
# Test: reviewer option stored as source
# ---------------------------------------------------------------------------

def test_reviewer_stored_as_source(tmp_path: Path) -> None:
    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Security finding",
            "--quadrant", "now",
            "--reviewer", "security-team",
        ],
    )
    assert result.exit_code == 0, result.output
    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    assert "security-team" in content


# ---------------------------------------------------------------------------
# Test: _next_cer_id logic
# ---------------------------------------------------------------------------

def test_next_cer_id_empty() -> None:
    assert _next_cer_id([]) == "CER-001"


def test_next_cer_id_existing() -> None:
    entries = [
        {"id": "CER-001", "finding": "a", "quadrant": "do_now"},
        {"id": "CER-003", "finding": "b", "quadrant": "do_later"},
    ]
    assert _next_cer_id(entries) == "CER-004"


# ---------------------------------------------------------------------------
# Test: project_name read from pairmode_context.json
# ---------------------------------------------------------------------------

def test_project_name_from_context_json(tmp_path: Path) -> None:
    """When .companion/pairmode_context.json has project_name, backlog header uses it."""
    import json

    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(parents=True, exist_ok=True)
    context_file = companion_dir / "pairmode_context.json"
    context_file.write_text(
        json.dumps({"project_name": "MyAwesomeProject"}), encoding="utf-8"
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Auth bypass on admin route",
            "--quadrant", "now",
        ],
    )
    assert result.exit_code == 0, result.output

    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    assert "MyAwesomeProject" in content


# ---------------------------------------------------------------------------
# Test: project_name fallback when no context.json present
# ---------------------------------------------------------------------------

def test_project_name_fallback_no_context(tmp_path: Path) -> None:
    """When pairmode_context.json is absent, heading-parse fallback does not crash."""
    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Some finding without context file",
            "--quadrant", "later",
        ],
    )
    assert result.exit_code == 0, result.output

    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    assert "Some finding without context file" in content
    assert "CER-001" in content


# ---------------------------------------------------------------------------
# Test: project_name from .companion/pairmode_context.json (correct subdir)
# ---------------------------------------------------------------------------

def test_project_name_from_companion_subdir(tmp_path: Path) -> None:
    """project_name is read from .companion/pairmode_context.json (not project root)."""
    import json

    # Write context to the correct location (.companion/ subdir)
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(parents=True, exist_ok=True)
    (companion_dir / "pairmode_context.json").write_text(
        json.dumps({"project_name": "CorrectPathProject"}), encoding="utf-8"
    )

    # Also ensure a stale file at the wrong (old) path does NOT take precedence
    (tmp_path / "pairmode_context.json").write_text(
        json.dumps({"project_name": "WrongPathProject"}), encoding="utf-8"
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Path verification finding",
            "--quadrant", "now",
        ],
    )
    assert result.exit_code == 0, result.output

    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    assert "CorrectPathProject" in content
    assert "WrongPathProject" not in content


# ---------------------------------------------------------------------------
# Test: pipe character in finding text is escaped in table cell
# ---------------------------------------------------------------------------

def test_pipe_in_finding_is_escaped(tmp_path: Path) -> None:
    """A literal | in a finding is escaped as \\| so the markdown table row is not broken."""
    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "foo | bar",
            "--quadrant", "now",
        ],
    )
    assert result.exit_code == 0, result.output

    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    # Escaped form must be present
    assert r"foo \| bar" in content
    # Raw unescaped form must not appear inside a table cell (the heading may contain
    # project name; check only the CER row lines)
    for line in content.splitlines():
        if line.strip().startswith("| CER-"):
            assert "foo | bar" not in line, (
                f"Unescaped pipe found in table row: {line!r}"
            )


# ---------------------------------------------------------------------------
# Test: _escape_table_cell helper
# ---------------------------------------------------------------------------

def test_escape_table_cell_no_pipe() -> None:
    assert _escape_table_cell("no pipes here") == "no pipes here"


def test_escape_table_cell_single_pipe() -> None:
    assert _escape_table_cell("a | b") == r"a \| b"


def test_escape_table_cell_multiple_pipes() -> None:
    assert _escape_table_cell("a | b | c") == r"a \| b \| c"
