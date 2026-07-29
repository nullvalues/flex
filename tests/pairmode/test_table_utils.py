"""Tests for table_utils.split_table_row — the single owner of Markdown-table
row splitting (INFRA-297, consolidating CER-066/CER-069)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "skills" / "pairmode" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from table_utils import split_table_row  # noqa: E402


# ---------------------------------------------------------------------------
# A2 — raw parts, no stripping
# ---------------------------------------------------------------------------


def test_plain_row_returns_raw_parts_with_leading_and_trailing_empties():
    assert split_table_row("| a | b | c |") == ["", " a ", " b ", " c ", ""]


def test_no_per_cell_strip_is_applied():
    """A2: cells come back un-stripped; callers keep their own stripping."""
    parts = split_table_row("|   spaced   |")
    assert parts == ["", "   spaced   ", ""]


# ---------------------------------------------------------------------------
# A3 — escaped pipes are cell content, and are not unescaped
# ---------------------------------------------------------------------------


def test_escaped_pipe_stays_inside_its_cell():
    assert split_table_row(r"| a | b\|c | d |") == ["", " a ", r" b\|c ", " d ", ""]


def test_split_is_non_destructive_no_unescaping():
    """A3: `\\|` survives the split verbatim."""
    parts = split_table_row(r"| Edit\|Write | complete |")
    assert r"Edit\|Write" in parts[1]
    assert "\\" in parts[1]


def test_round_trip_rewrite_preserves_the_row_byte_for_byte():
    """A3's reason: the mark-phase-complete rewrite paths split, edit one cell
    and rejoin with `" | "`. With no cell edited, the row must come back out
    byte-for-byte identical."""
    row = r"| 113 | Edit\|Write hardening | planned |"
    cells = [p.strip() for p in split_table_row(row)[1:-1]]
    assert cells == ["113", r"Edit\|Write hardening", "planned"]
    assert "| " + " | ".join(cells) + " |" == row


def test_naive_split_would_have_shredded_the_same_row():
    """Pins the defect this helper exists to prevent (CER-066/CER-069)."""
    row = r"| 113 | Edit\|Write hardening | planned |"
    naive = [p.strip() for p in row.split("|")[1:-1]]
    correct = [p.strip() for p in split_table_row(row)[1:-1]]
    assert len(naive) == 4  # shredded: one extra column
    assert len(correct) == 3
    # The positional status read is the wrong cell under the naive split.
    assert naive[2] != correct[2]
    assert correct[2] == "planned"


# ---------------------------------------------------------------------------
# Boundary cases
# ---------------------------------------------------------------------------


def test_single_cell_row():
    assert split_table_row("| only |") == ["", " only ", ""]


def test_row_with_no_pipes_at_all():
    assert split_table_row("not a table row") == ["not a table row"]


def test_empty_string():
    assert split_table_row("") == [""]


def test_row_that_is_only_escaped_pipes_has_one_part():
    assert split_table_row(r"a\|b\|c") == [r"a\|b\|c"]


def test_separator_row():
    assert split_table_row("|---|---|") == ["", "---", "---", ""]


# ---------------------------------------------------------------------------
# A1 — stdlib-only, no sibling imports
# ---------------------------------------------------------------------------


def test_module_imports_only_stdlib_and_no_siblings():
    """A1: source-level check, not a comment. Every import line in
    table_utils.py must be a stdlib import; no sibling pairmode module."""
    source = (_SCRIPTS_DIR / "table_utils.py").read_text(encoding="utf-8")
    import_lines = [
        ln.strip()
        for ln in source.splitlines()
        if re.match(r"^(from|import)\s", ln)
    ]
    assert import_lines, "expected at least one import line"
    allowed = {"from __future__ import annotations", "import re"}
    assert set(import_lines) <= allowed, f"unexpected imports: {import_lines}"

    sibling_names = {
        p.stem for p in _SCRIPTS_DIR.glob("*.py") if p.stem != "table_utils"
    }
    for name in sibling_names:
        assert not re.search(rf"^(from|import)\s+{re.escape(name)}\b", source, re.M)


# ---------------------------------------------------------------------------
# B3 — the split has exactly one owner
# ---------------------------------------------------------------------------


def _scripts_sources() -> dict[Path, str]:
    return {p: p.read_text(encoding="utf-8") for p in sorted(_SCRIPTS_DIR.glob("*.py"))}


def test_no_naive_stripped_split_remains_in_pairmode_scripts():
    """B3: `stripped.split("|")` is gone from skills/pairmode/scripts/*.py."""
    naive_re = re.compile(r"""stripped\.split\(['"]\|['"]\)""")
    offenders = [
        f"{p.name}:{i}"
        for p, src in _scripts_sources().items()
        for i, line in enumerate(src.splitlines(), 1)
        if naive_re.search(line)
    ]
    assert offenders == [], f"naive table splits remain: {offenders}"


def test_unescaped_pipe_regex_literal_lives_in_exactly_one_module():
    """B3: the `(?<!\\\\)\\|` literal appears in table_utils.py and nowhere else."""
    literal = r"(?<!\\)\|"
    owners = [p.name for p, src in _scripts_sources().items() if literal in src]
    assert owners == ["table_utils.py"], f"split literal duplicated in: {owners}"
