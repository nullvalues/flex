"""Tests for cer.py — CER triage CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from skills.pairmode.scripts.cer import (
    cli,
    append_finding,
    extract_gate_condition,
    find_groomable_rows,
    find_open_do_now_rows,
    is_placeholder_row,
    is_resolution_marked,
    _escape_table_cell,
    _load_or_create_backlog,
    _next_cer_id,
    _parse_entries_from_backlog,
    _render_backlog,
    _scan_rows_in_sections,
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
# Test: CER IDs increment from existing entries on re-run
# ---------------------------------------------------------------------------

def test_cer_id_increments_from_existing(tmp_path: Path) -> None:
    """When backlog already contains CER-001 through CER-003, new entry gets CER-004."""
    runner = CliRunner()

    # Seed CER-001 through CER-003
    for i, finding in enumerate(["First", "Second", "Third"], start=1):
        result = _invoke(
            runner,
            ["--project-dir", str(tmp_path), "--finding", finding, "--quadrant", "now"],
        )
        assert result.exit_code == 0, result.output

    # Add a fourth entry — must be CER-004, not CER-001
    result = _invoke(
        runner,
        ["--project-dir", str(tmp_path), "--finding", "Fourth", "--quadrant", "later"],
    )
    assert result.exit_code == 0, result.output
    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    assert "CER-004" in content
    # CER-001 through CER-003 must still be present
    for expected in ["CER-001", "CER-002", "CER-003"]:
        assert expected in content


def test_cer_id_not_restarted_after_gap(tmp_path: Path) -> None:
    """When backlog has CER-001 and CER-003 (gap at CER-002), new entry gets CER-004."""
    runner = CliRunner()

    # Seed CER-001 and CER-003 directly via two calls, then simulate a gap
    # by building CER-001, CER-002, CER-003 and then manually removing CER-002's row
    # from the markdown so entries list has a gap.
    for finding in ("Alpha", "Beta", "Gamma"):
        result = _invoke(
            runner,
            ["--project-dir", str(tmp_path), "--finding", finding, "--quadrant", "now"],
        )
        assert result.exit_code == 0, result.output

    # Remove the CER-002 row from backlog.md to simulate a resolved/removed entry
    backlog = _backlog_path(tmp_path)
    original = backlog.read_text(encoding="utf-8")
    lines = [ln for ln in original.splitlines(keepends=True) if "CER-002" not in ln]
    backlog.write_text("".join(lines), encoding="utf-8")

    # Now add a new finding — should use max+1 = CER-004, not len+1 = CER-003
    result = _invoke(
        runner,
        ["--project-dir", str(tmp_path), "--finding", "Delta", "--quadrant", "later"],
    )
    assert result.exit_code == 0, result.output
    content = backlog.read_text(encoding="utf-8")
    assert "CER-004" in content
    assert "Delta" in content


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


# ---------------------------------------------------------------------------
# Tests: depth guard
# ---------------------------------------------------------------------------

def test_depth_guard_root_exits_nonzero() -> None:
    """--project-dir / is too shallow: must exit non-zero with error message."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project-dir", "/", "--finding", "x", "--quadrant", "now"],
        catch_exceptions=False,
    )
    assert result.exit_code != 0
    assert "too shallow" in (result.output + (result.stderr if hasattr(result, "stderr") else "")).lower() or \
           "too shallow" in result.output.lower()


def test_depth_guard_tmp_exits_nonzero() -> None:
    """--project-dir /tmp is only 2 parts deep: must exit non-zero."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project-dir", "/tmp", "--finding", "x", "--quadrant", "now"],
        catch_exceptions=False,
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Tests: malformed-markdown warning (INFRA-010)
# ---------------------------------------------------------------------------

_MALFORMED_BACKLOG = """\
# Some Project — CER Backlog

This file has more than five lines but contains no pipe-delimited table rows.
It uses freeform prose instead of the expected markdown table format.
There are no CER IDs here at all.
Just a heading and some paragraphs.
No tables to parse.
Nothing that matches the row regex.
End of file.
"""


def test_malformed_backlog_emits_warning(tmp_path: Path) -> None:
    """backlog.md with 10+ lines but no table rows → warning printed to stderr; process continues."""
    backlog = _backlog_path(tmp_path)
    backlog.parent.mkdir(parents=True, exist_ok=True)
    backlog.write_text(_MALFORMED_BACKLOG, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Finding after malformed backlog",
            "--quadrant", "now",
        ],
        catch_exceptions=False,
    )

    # Process must continue without error
    assert result.exit_code == 0, result.output
    # Warning must appear in output (Click merges stderr into output by default)
    assert "Warning: backlog.md exists but no table rows were parsed" in result.output
    # Finding must be written
    content = backlog.read_text(encoding="utf-8")
    assert "Finding after malformed backlog" in content


def test_normal_backlog_no_warning(tmp_path: Path) -> None:
    """backlog.md with CER-001 and CER-002 → no warning; CER-003 assigned to new finding."""
    runner = CliRunner()

    # Seed two entries
    for finding in ("First finding", "Second finding"):
        result = runner.invoke(
            cli,
            [
                "--project-dir", str(tmp_path),
                "--finding", finding,
                "--quadrant", "now",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

    # Now add a third entry
    result = runner.invoke(
        cli,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Third finding",
            "--quadrant", "now",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    # No warning should be emitted for a well-formed backlog
    assert "Warning: backlog.md exists but no table rows were parsed" not in result.output

    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    assert "CER-001" in content
    assert "CER-002" in content
    assert "CER-003" in content
    assert "Third finding" in content


# ---------------------------------------------------------------------------
# Test: is_placeholder_row (INFRA-294)
# ---------------------------------------------------------------------------

def test_is_placeholder_row_do_now_shape() -> None:
    assert is_placeholder_row(["—", "*(none)*", "—", "—", "—"]) is True


def test_is_placeholder_row_do_never_shape() -> None:
    assert is_placeholder_row(["—", "*(none)*", "—", "—", "—", "—"]) is True


def test_is_placeholder_row_four_cell_caddy_shape() -> None:
    assert is_placeholder_row(["—", "*(none)*", "—", "—"]) is True


def test_is_placeholder_row_real_finding_returns_false() -> None:
    assert is_placeholder_row(
        ["CER-999", "An unresolved finding", "some-source", "2026-01-01", "1"]
    ) is False


def test_is_placeholder_row_empty_returns_false() -> None:
    assert is_placeholder_row([]) is False


# ---------------------------------------------------------------------------
# Test: is_resolution_marked (INFRA-322 / CER-130)
# ---------------------------------------------------------------------------

def test_bolded_upper_marker_is_recognised() -> None:
    assert is_resolution_marked("… fixed. **RESOLVED Phase 55 — INFRA-1**") is True


def test_plain_title_case_marker_is_recognised() -> None:
    # CER-130 direction 1: a case-sensitive substring test on "RESOLVED"
    # never matches this row, permanently blocking a consuming repo's
    # checkpoint. It must match here.
    assert is_resolution_marked("Resolved cp-34 — INFRA-1") is True
    assert "RESOLVED" not in "Resolved cp-34 — INFRA-1"


def test_lowercase_marker_is_recognised() -> None:
    assert is_resolution_marked("resolved cp-34 — INFRA-1") is True


def test_parenthesised_and_bracketed_markers_are_recognised() -> None:
    assert is_resolution_marked("… (RESOLVED INFRA-297)") is True
    assert is_resolution_marked("… [RESOLVED]") is True
    assert is_resolution_marked("… *Resolved*") is True


def test_superseded_keyword_is_recognised() -> None:
    assert is_resolution_marked("… **SUPERSEDED by CER-9**") is True


def test_marker_at_cell_boundary_is_recognised() -> None:
    assert is_resolution_marked("| Resolved cp-34 — INFRA-1 |") is True


def test_unresolved_is_not_a_marker() -> None:
    # CER-130 direction 2: the bare substring test matched this row because
    # "RESOLVED" is a substring of "UNRESOLVED".
    assert is_resolution_marked("UNRESOLVED naming gap between …") is False


def test_should_be_resolved_prose_is_not_a_marker() -> None:
    assert is_resolution_marked("this should be RESOLVED before cp") is False


def test_negated_prose_is_not_a_marker() -> None:
    assert is_resolution_marked("to be resolved in 116") is False
    assert is_resolution_marked("not resolved yet") is False
    assert is_resolution_marked("**Not resolved**") is False


def test_partially_resolved_is_not_a_marker() -> None:
    assert is_resolution_marked("PARTIALLY RESOLVED phase 3") is False


def test_quoted_or_code_span_literal_is_not_a_marker() -> None:
    assert is_resolution_marked("the `RESOLVED` literal") is False
    assert is_resolution_marked('if "RESOLVED" not in stripped') is False


def test_underscore_identifier_is_not_a_marker() -> None:
    assert is_resolution_marked("_RESOLVED_RE") is False


def test_empty_and_non_string_inputs_return_false() -> None:
    assert is_resolution_marked("") is False
    assert is_resolution_marked(None) is False  # type: ignore[arg-type]
    assert is_resolution_marked(0) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests: find_open_do_now_rows (INFRA-313, Requires 1)
# ---------------------------------------------------------------------------

_DO_NOW_HEADER = (
    "# CER Backlog\n\n"
    "## Do Now\n\n"
    "| ID | Finding | Source | Date | Phase |\n"
    "|----|---------|--------|------|-------|\n"
)


def test_find_open_do_now_rows_empty_section_returns_empty() -> None:
    text = _DO_NOW_HEADER + "| — | *(none)* | — | — | — |\n\n## Do Later\n\n"
    assert find_open_do_now_rows(text) == []


def test_find_open_do_now_rows_open_row_returned() -> None:
    text = (
        _DO_NOW_HEADER
        + "| CER-900 | A still-open finding | src | 2026-07-29 | 116 |\n\n"
        "## Do Later\n\n"
    )
    rows = find_open_do_now_rows(text)
    assert len(rows) == 1
    assert rows[0]["id"] == "CER-900"
    assert "still-open finding" in rows[0]["text"]


def test_find_open_do_now_rows_resolved_row_excluded() -> None:
    text = (
        _DO_NOW_HEADER
        + "| CER-900 | A finding. **RESOLVED Phase 1** | src | 2026-07-29 | 116 |\n\n"
        "## Do Later\n\n"
    )
    assert find_open_do_now_rows(text) == []


def test_find_open_do_now_rows_first_80_chars_truncatable() -> None:
    long_finding = "X" * 200
    text = (
        _DO_NOW_HEADER
        + f"| CER-901 | {long_finding} | src | 2026-07-29 | 116 |\n\n"
        "## Do Later\n\n"
    )
    rows = find_open_do_now_rows(text)
    assert len(rows) == 1
    # The full row text is returned; callers (gate) truncate to 80 chars.
    assert len(rows[0]["text"][:80]) == 80


# ---------------------------------------------------------------------------
# Tests: extract_gate_condition (Ensures 5)
# ---------------------------------------------------------------------------


def test_extract_gate_condition_present() -> None:
    finding = (
        "HIGH: something bad. gate: next canon change to a seeded-doc "
        "template or the first post-0.3.1 fleet sync campaign."
    )
    condition = extract_gate_condition(finding)
    assert condition == (
        "next canon change to a seeded-doc template or the first "
        "post-0.3.1 fleet sync campaign."
    )


def test_extract_gate_condition_stops_at_bold_token() -> None:
    finding = "Some finding. gate: condition text here. **RESOLVED Phase 1**"
    assert extract_gate_condition(finding) == "condition text here."


def test_extract_gate_condition_absent_returns_none() -> None:
    assert extract_gate_condition("A finding with no gate token at all.") is None


def test_extract_gate_condition_case_insensitive() -> None:
    finding = "A finding. GATE: some condition"
    assert extract_gate_condition(finding) == "some condition"


def test_extract_gate_condition_empty_or_none_input() -> None:
    assert extract_gate_condition("") is None
    assert extract_gate_condition(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests: find_groomable_rows (Ensures 4/5 — live CER-121/CER-125 fixtures)
# ---------------------------------------------------------------------------

_LATER_HEADER = (
    "# CER Backlog\n\n"
    "## Do Now\n\n"
    "| ID | Finding | Source | Date | Phase |\n"
    "|----|---------|--------|------|-------|\n"
    "| — | *(none)* | — | — | — |\n\n"
    "## Do Later\n\n"
    "| ID | Finding | Source | Date | Phase |\n"
    "|----|---------|--------|------|-------|\n"
)

_MUCH_LATER_TRAILER = (
    "\n## Do Much Later\n\n"
    "| ID | Finding | Source | Date | Phase |\n"
    "|----|---------|--------|------|-------|\n"
)


def test_find_groomable_rows_with_and_without_gate_shapes() -> None:
    """CER-121 and CER-125 shape: a Do Later row with a gate: token and one
    without, plus a Do Much Later row with a gate: token."""
    text = (
        _LATER_HEADER
        + "| CER-121 | HIGH: some drift. gate: next canon change to a "
        "seeded-doc template or the first post-0.3.1 fleet sync campaign — "
        "whichever comes first. | Cold-eyes review 2026-07-29 | 2026-07-29 | — |\n\n"
        + _MUCH_LATER_TRAILER
        + "| CER-125 | LOW: stale manifest. gate: next hand edit to "
        "phase-64.md for any reason. | Cold-eyes review 2026-07-29 | "
        "2026-07-29 | — |\n\n"
        "| CER-200 | A plain finding with no gate token. | src | "
        "2026-07-29 | — |\n\n"
    )
    rows = find_groomable_rows(text)
    by_id = {row["id"]: row for row in rows}

    assert by_id["CER-121"]["quadrant"] == "Do Later"
    assert by_id["CER-121"]["gate"] == (
        "next canon change to a seeded-doc template or the first "
        "post-0.3.1 fleet sync campaign — whichever comes first."
    )

    assert by_id["CER-125"]["quadrant"] == "Do Much Later"
    assert by_id["CER-125"]["gate"] == (
        "next hand edit to phase-64.md for any reason."
    )

    assert by_id["CER-200"]["quadrant"] == "Do Much Later"
    assert by_id["CER-200"]["gate"] is None


def test_find_groomable_rows_excludes_do_now() -> None:
    """groom scans Do Later + Do Much Later only, never Do Now."""
    text = (
        _DO_NOW_HEADER
        + "| CER-999 | An open Do Now finding | src | 2026-07-29 | 116 |\n\n"
        "## Do Later\n\n"
    )
    assert find_groomable_rows(text) == []


def test_find_groomable_rows_excludes_resolved_rows() -> None:
    text = (
        _LATER_HEADER
        + "| CER-300 | A finding. **RESOLVED Phase 1** | src | "
        "2026-07-29 | — |\n\n"
    )
    assert find_groomable_rows(text) == []


def test_find_groomable_rows_excludes_placeholder_row() -> None:
    text = _LATER_HEADER + "| — | *(none)* | — | — | — |\n\n"
    assert find_groomable_rows(text) == []


# ---------------------------------------------------------------------------
# Tests: cer.py gate CLI subcommand (Ensures 1)
# ---------------------------------------------------------------------------


def test_gate_exits_0_on_clean_do_now(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["gate", "--project-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output


def test_gate_exits_1_and_lists_open_rows(tmp_path: Path) -> None:
    cer_dir = tmp_path / "docs" / "cer"
    cer_dir.mkdir(parents=True)
    (cer_dir / "backlog.md").write_text(
        _DO_NOW_HEADER
        + "| CER-900 | A still-open finding blocking the tag | src | "
        "2026-07-29 | 116 |\n\n## Do Later\n\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["gate", "--project-dir", str(tmp_path)])
    assert result.exit_code == 1
    assert "CER-900" in result.output


def test_gate_exits_0_when_do_now_resolved(tmp_path: Path) -> None:
    cer_dir = tmp_path / "docs" / "cer"
    cer_dir.mkdir(parents=True)
    (cer_dir / "backlog.md").write_text(
        _DO_NOW_HEADER
        + "| CER-900 | A finding. **RESOLVED Phase 1** | src | "
        "2026-07-29 | 116 |\n\n## Do Later\n\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["gate", "--project-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# Tests: cer.py groom CLI subcommand (Ensures 4 — never writes the backlog)
# ---------------------------------------------------------------------------


def test_groom_leaves_backlog_byte_identical(tmp_path: Path) -> None:
    """Forbidden proxy check: groom's diff must be empty."""
    cer_dir = tmp_path / "docs" / "cer"
    cer_dir.mkdir(parents=True)
    backlog_path = cer_dir / "backlog.md"
    backlog_path.write_text(
        _LATER_HEADER
        + "| CER-121 | HIGH: some drift. gate: next canon change. | "
        "Cold-eyes review 2026-07-29 | 2026-07-29 | — |\n\n",
        encoding="utf-8",
    )
    before = backlog_path.read_bytes()

    runner = CliRunner()
    result = runner.invoke(cli, ["groom", "--project-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output

    after = backlog_path.read_bytes()
    assert after == before, "groom must never write docs/cer/backlog.md"


def test_groom_prints_gate_condition_and_no_gate_marker(tmp_path: Path) -> None:
    cer_dir = tmp_path / "docs" / "cer"
    cer_dir.mkdir(parents=True)
    (cer_dir / "backlog.md").write_text(
        _LATER_HEADER
        + "| CER-121 | HIGH: some drift. gate: next canon change to a "
        "seeded-doc template. | Cold-eyes review 2026-07-29 | 2026-07-29 | — |\n\n"
        + _MUCH_LATER_TRAILER
        + "| CER-200 | A plain finding with no gate token. | src | "
        "2026-07-29 | — |\n\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["groom", "--project-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "CER-121" in result.output
    assert "next canon change to a seeded-doc template." in result.output
    assert "CER-200" in result.output
    assert "(no gate:)" in result.output


def test_groom_exits_0_with_no_backlog(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["groom", "--project-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output


def test_groom_exit_code_always_0_even_with_open_rows(tmp_path: Path) -> None:
    """Groom informs; the operator decides. Never a nonzero gate-like exit."""
    cer_dir = tmp_path / "docs" / "cer"
    cer_dir.mkdir(parents=True)
    (cer_dir / "backlog.md").write_text(
        _LATER_HEADER
        + "| CER-121 | HIGH: some drift, no gate token. | src | "
        "2026-07-29 | — |\n\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["groom", "--project-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# Test: cli group's default action still works with no subcommand
# ---------------------------------------------------------------------------


def test_cli_group_default_action_still_appends_finding(tmp_path: Path) -> None:
    """Converting cli into a click.Group (INFRA-313) must not break the
    historical no-subcommand invocation documented in SKILL.md."""
    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Group conversion parity check",
            "--quadrant", "now",
        ],
    )
    assert result.exit_code == 0, result.output
    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    assert "Group conversion parity check" in content


# ---------------------------------------------------------------------------
# Tests: INFRA-338 — unified escape-aware row parser (F7 regression)
# ---------------------------------------------------------------------------


def test_parse_entries_handles_escaped_pipe_in_finding_cell() -> None:
    """A finding cell containing an escaped pipe (Task\\|Agent) parses as one
    entry, with the literal `\\|` preserved unshredded (§ D1, § A1)."""
    content = _render_backlog(
        [
            {
                "id": "CER-001",
                "finding": r"Matcher regression (Task\|Agent)",
                "source": "reviewer",
                "date": "2026-07-01",
                "quadrant": "do_now",
            }
        ]
    )
    entries = _parse_entries_from_backlog(content)
    assert len(entries) == 1
    assert entries[0]["id"] == "CER-001"
    assert entries[0]["finding"] == r"Matcher regression (Task\|Agent)"
    assert entries[0]["source"] == "reviewer"
    assert entries[0]["date"] == "2026-07-01"


def test_append_finding_does_not_truncate_neighboring_resolved_row_with_escaped_pipe(
    tmp_path: Path,
) -> None:
    """F7 regression (§ B1/B2): appending a new finding must not mutate a
    neighboring row whose **RESOLVED** annotation contains an escaped pipe.

    Seeds docs/cer/backlog.md directly (bypassing the CLI/append_finding
    path) with a Do Now row already annotated
    ``**RESOLVED Phase 1** — matcher fixed (Task\\|Agent)``, then calls
    ``append_finding`` for an unrelated new finding in the same quadrant.
    The forbidden proxy is "append_finding returns without raising" — this
    test diffs the full seeded row's text instead.
    """
    seeded_entry = {
        "id": "CER-001",
        "finding": r"Matcher regression. **RESOLVED Phase 1** — matcher fixed (Task\|Agent)",
        "source": "reviewer",
        "date": "2026-07-01",
        "quadrant": "do_now",
        "phase": "100",
    }
    before_content = _render_backlog([seeded_entry], project_name="Test Project")
    backlog = _backlog_path(tmp_path)
    backlog.parent.mkdir(parents=True, exist_ok=True)
    backlog.write_text(before_content, encoding="utf-8")

    seeded_line_before = next(
        line for line in before_content.splitlines() if line.strip().startswith("| CER-001")
    )

    # Sanity: the row is open (not resolution-marked) before the fix would be
    # meaningless — it must already read as resolved going in.
    assert "CER-001" not in [
        row["id"] for row in find_open_do_now_rows(before_content)
    ]

    entry = append_finding(tmp_path, finding="Unrelated new finding", quadrant="do_now")
    assert entry["id"] == "CER-002"

    after_content = backlog.read_text(encoding="utf-8")
    seeded_line_after = next(
        line for line in after_content.splitlines() if line.strip().startswith("| CER-001")
    )

    # (a) the seeded row's line is byte-identical before and after.
    assert seeded_line_after == seeded_line_before

    # (b) find_open_do_now_rows — the same predicate the checkpoint-tag gate
    # reads — still excludes CER-001 after the append.
    open_ids = [row["id"] for row in find_open_do_now_rows(after_content)]
    assert "CER-001" not in open_ids
    assert "CER-002" in open_ids


def test_parse_entries_from_backlog_matches_scan_rows_for_escaped_pipe_fixture() -> None:
    """Parity check (§ D1): for the same escaped-pipe row,
    `_parse_entries_from_backlog`'s field values match the cells
    `_scan_rows_in_sections` (the reader half) returns for that row."""
    content = _render_backlog(
        [
            {
                "id": "CER-001",
                "finding": r"Matcher regression (Task\|Agent)",
                "source": "reviewer",
                "date": "2026-07-01",
                "quadrant": "do_now",
                "phase": "100",
            }
        ]
    )
    entries = _parse_entries_from_backlog(content)
    assert len(entries) == 1
    entry = entries[0]

    scanned = list(_scan_rows_in_sections(content, {"## Do Now"}))
    assert len(scanned) == 1
    _header, _stripped, cols = scanned[0]

    assert entry["id"] == cols[0]
    assert entry["finding"] == cols[1]
    assert entry["source"] == cols[2]
    assert entry["date"] == cols[3]
    assert entry.get("phase") == cols[4]


def test_table_row_re_constant_removed() -> None:
    """§ A2 pin: `_TABLE_ROW_RE` is deleted from the module entirely, so a
    future edit cannot silently reintroduce the naive pipe-splitting regex."""
    import inspect

    from skills.pairmode.scripts import cer as cer_module

    source = inspect.getsource(cer_module)
    assert "_TABLE_ROW_RE" not in source
