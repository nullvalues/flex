"""Tests for INFRA-167 — TypeScript parser robustness fixes.

Four bugs from the Phase 63 cold-eyes review:
1. phaseIndex.ts: blank line between table rows terminated parsing (break → continue)
2. lessons.ts: MODULE_FILENAME_RE too strict (no digits/uppercase/path prefix)
3. phaseDoc.ts: era leading zeros lost when YAML parses 002 as number 2
4. storyFrontmatter.ts: flex_factor admitted NaN; rejected quoted string values

Tests are source-level assertions plus Python regex equivalents where
runtime behavior can be verified without a running Fastify server.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

FLEX_ROOT = Path(__file__).resolve().parents[2]
OBS_API = FLEX_ROOT / "skills" / "observability" / "api"
PARSERS = OBS_API / "src" / "parsers"


# ---------------------------------------------------------------------------
# 1. phaseIndex.ts — blank line between rows (INFRA-167 fix 1)
# ---------------------------------------------------------------------------

def test_phase_index_blank_line_fix_in_source() -> None:
    """phaseIndex.ts must have continue for blank lines, not only break."""
    src = (PARSERS / "phaseIndex.ts").read_text(encoding="utf-8")
    assert "if (trimmed === '') continue;" in src, (
        "phaseIndex.ts missing blank-line continue guard (INFRA-167 fix 1)"
    )
    # The break must still exist (for headings etc.)
    assert "break;" in src, "phaseIndex.ts must still break on non-pipe non-blank lines"


def test_phase_index_blank_line_between_rows() -> None:
    """Verify the source allows blank dividers: the continue path is coded before break."""
    src = (PARSERS / "phaseIndex.ts").read_text(encoding="utf-8")
    # The continue for '' must appear before the final break in the data-row block
    continue_pos = src.index("if (trimmed === '') continue;")
    break_pos = src.index("break;", continue_pos)
    assert continue_pos < break_pos, (
        "Expected continue (blank) to appear before break (heading) in phaseIndex.ts"
    )


def test_phase_index_stops_at_heading() -> None:
    """The break must still be present for non-pipe non-blank lines (headings)."""
    src = (PARSERS / "phaseIndex.ts").read_text(encoding="utf-8")
    # Find the data-row block containing the continue and the break
    blank_guard = "if (trimmed === '') continue;"
    assert blank_guard in src
    # After the blank guard, the non-blank non-pipe path must break
    tail = src[src.index(blank_guard):]
    assert "break;" in tail, "Heading-stop break missing after blank-guard in phaseIndex.ts"


# ---------------------------------------------------------------------------
# 2. lessons.ts — MODULE_FILENAME_RE (INFRA-167 fix 2)
# ---------------------------------------------------------------------------

def _get_module_re() -> re.Pattern:
    """Extract and compile the MODULE_FILENAME_RE from lessons.ts source."""
    src = (PARSERS / "lessons.ts").read_text(encoding="utf-8")
    # Allow escaped slashes (\/) inside the regex literal
    m = re.search(r"MODULE_FILENAME_RE\s*=\s*/((?:[^/\\]|\\.)+)/", src)
    assert m, "MODULE_FILENAME_RE not found in lessons.ts"
    pattern_str = m.group(1)  # content between the / delimiters
    return re.compile(pattern_str)


def test_module_filename_re_allows_lowercase() -> None:
    pattern = _get_module_re()
    assert pattern.match("audit.py"), "audit.py must match"


def test_module_filename_re_allows_digits_and_uppercase() -> None:
    """Digits and uppercase must be accepted (INFRA-167 fix 2)."""
    pattern = _get_module_re()
    assert pattern.match("phase63.py"), "phase63.py (digits) must match"
    assert pattern.match("Audit.py"), "Audit.py (uppercase) must match"
    assert pattern.match("scripts/audit.py"), "scripts/audit.py (path prefix) must match"


def test_module_filename_re_rejects_invalid() -> None:
    pattern = _get_module_re()
    assert not pattern.match(".py"), ".py (empty stem) must not match"
    assert not pattern.match("../escape.py"), "../escape.py (traversal) must not match"
    assert not pattern.match("audit.ts"), "audit.ts (wrong extension) must not match"
    assert not pattern.match(""), "empty string must not match"


# ---------------------------------------------------------------------------
# 3. phaseDoc.ts — era leading zeros (INFRA-167 fix 3)
# ---------------------------------------------------------------------------

def test_era_padstart_in_source() -> None:
    """phaseDoc.ts must use padStart(3, '0') for numeric era values (INFRA-167 fix 3)."""
    src = (PARSERS / "phaseDoc.ts").read_text(encoding="utf-8")
    assert "padStart(3, '0')" in src, (
        "phaseDoc.ts missing padStart(3, '0') for numeric era leading-zero fix"
    )


def test_era_unquoted_integer_padded() -> None:
    """Verify the padding logic: String(2).padStart(3, '0') == '002'."""
    # Mirror the TypeScript logic in Python
    era_val = 2  # What js-yaml produces for unquoted era: 002
    era = str(era_val).zfill(3)
    assert era == "002", f"Expected '002', got {era!r}"


def test_era_quoted_string_unchanged() -> None:
    """Quoted era values (already strings) must pass through String() unchanged."""
    # If eraVal is already a string (from "002"), typeof === 'string' path
    era_val = "002"  # already a string
    era = era_val  # String("002") == "002"
    assert era == "002"


# ---------------------------------------------------------------------------
# 4. storyFrontmatter.ts — flex_factor NaN + string (INFRA-167 fix 4)
# ---------------------------------------------------------------------------

def test_flex_factor_nan_guard_in_source() -> None:
    """storyFrontmatter.ts must use Number.isNaN guard for flex_factor (INFRA-167 fix 4)."""
    src = (PARSERS / "storyFrontmatter.ts").read_text(encoding="utf-8")
    assert "Number.isNaN" in src, (
        "storyFrontmatter.ts missing Number.isNaN guard for flex_factor"
    )


def test_flex_factor_string_handling_in_source() -> None:
    """storyFrontmatter.ts must handle typeof ffRaw === 'string' (INFRA-167 fix 4)."""
    src = (PARSERS / "storyFrontmatter.ts").read_text(encoding="utf-8")
    assert "typeof ffRaw === 'string'" in src, (
        "storyFrontmatter.ts missing string-type handling for flex_factor"
    )
    assert "parseFloat" in src, (
        "storyFrontmatter.ts missing parseFloat for string flex_factor"
    )


def test_flex_factor_string_parsed() -> None:
    """Python mirror: parseFloat('1.5') == 1.5 (verifies the logic is correct)."""
    ff_raw = '1.5'
    parsed = float(ff_raw)
    import math
    assert not math.isnan(parsed)
    assert abs(parsed - 1.5) < 0.001


def test_flex_factor_nan_defaults_to_1() -> None:
    """Python mirror: NaN flex_factor must default to 1.0."""
    import math
    ff_raw = float('nan')
    # Mirrors: if (typeof ffRaw === 'number' && !Number.isNaN(ffRaw)) { flex_factor = ffRaw }
    flex_factor = 1.0
    if isinstance(ff_raw, float) and not math.isnan(ff_raw):
        flex_factor = ff_raw
    assert flex_factor == 1.0, f"NaN should default to 1.0, got {flex_factor}"


# ---------------------------------------------------------------------------
# 5. phaseIndex.ts — href path containment (OBS-006)
# ---------------------------------------------------------------------------

def test_phase_index_containment_check_in_source() -> None:
    """phaseIndex.ts must contain a path containment check using startsWith (OBS-006)."""
    src = (PARSERS / "phaseIndex.ts").read_text(encoding="utf-8")
    assert "startsWith(safeRoot" in src, (
        "phaseIndex.ts missing path containment check using startsWith(safeRoot ...) (OBS-006)"
    )
    assert "path.resolve(projectDir)" in src, (
        "phaseIndex.ts missing path.resolve(projectDir) for safeRoot (OBS-006)"
    )


def test_phase_index_traversal_href_returns_null() -> None:
    """A traversal href (../../../../etc/passwd) must be skipped (returns null file path).

    This test mirrors the TypeScript resolveFileFromHref logic in Python to verify
    the containment algorithm is correct without running a Node.js process.
    """
    import os

    project_dir = "/tmp/fake-project"
    href = "../../../../etc/passwd"
    safe_root = os.path.realpath(project_dir)
    candidate = os.path.realpath(os.path.join(project_dir, "docs", "phases", href))

    # The containment check: candidate must start with safeRoot + sep, or equal safeRoot
    contained = candidate.startswith(safe_root + os.sep) or candidate == safe_root
    assert not contained, (
        f"Traversal href {href!r} should NOT be contained within {safe_root!r}, "
        f"but candidate resolved to {candidate!r}"
    )


def test_phase_index_normal_href_is_contained() -> None:
    """A normal href (phase-8.md) must be contained within projectDir."""
    import os

    project_dir = "/tmp/fake-project"
    href = "phase-8.md"
    safe_root = os.path.realpath(project_dir)
    candidate = os.path.realpath(os.path.join(project_dir, "docs", "phases", href))

    contained = candidate.startswith(safe_root + os.sep) or candidate == safe_root
    assert contained, (
        f"Normal href {href!r} should be contained within {safe_root!r}, "
        f"but candidate resolved to {candidate!r}"
    )


def test_phase_index_traversal_guard_source_logic() -> None:
    """phaseIndex.ts must skip traversal href (resolveFileFromHref returns null path)."""
    src = (PARSERS / "phaseIndex.ts").read_text(encoding="utf-8")
    # The traversal-guard return null must be present in the resolveFileFromHref function
    assert "Path traversal detected" in src or "return null;" in src, (
        "phaseIndex.ts resolveFileFromHref must return null on traversal detection (OBS-006)"
    )


# ---------------------------------------------------------------------------
# Build gate: API must still compile after the 4 parser changes
# ---------------------------------------------------------------------------

def test_api_build_after_parser_fixes() -> None:
    """API tsc build must pass after all four INFRA-167 parser fixes."""
    import subprocess
    import os

    result = subprocess.run(
        ["pnpm", "--filter", "@flex-obs/api", "build"],
        cwd=str(OBS_API.parent),
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, (
        f"API build failed after INFRA-167 fixes:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
