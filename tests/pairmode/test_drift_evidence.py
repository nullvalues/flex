"""Tests for drift_evidence.py — token-evidence scoring for convergence candidates.

Test scenarios:
- Fewer than 5 attempts returns (None, "insufficient data")
- Absent or empty databases are handled gracefully (no crash)
- Ranking matches seeded data (higher-token project vs lower-token project)
- Multiple projects with mixed data
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure the anchor repo root is on sys.path so imports resolve.
# ---------------------------------------------------------------------------

_ANCHOR_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ANCHOR_ROOT))

from skills.pairmode.scripts.drift_evidence import (  # noqa: E402
    score_convergence_candidate,
    _collect_builder_tokens,
    _MIN_TOTAL_ATTEMPTS,
)
from skills.pairmode.scripts.effort_db import init_db, insert_attempt  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_project(tmp_path: Path, name: str) -> Path:
    """Create a minimal project directory with .companion/."""
    proj = tmp_path / name
    (proj / ".companion").mkdir(parents=True)
    return proj


def _seed_db(project_dir: Path, token_values: list[int], agent_role: str = "builder") -> None:
    """Seed effort.db with builder rows using the given token values."""
    db_path = project_dir / ".companion" / "effort.db"
    init_db(db_path)
    for i, tokens in enumerate(token_values):
        insert_attempt(
            db_path,
            story_id=f"TEST-{i:03d}",
            agent_role=agent_role,
            attempt_number=1,
            tokens_total=tokens,
            ts="2026-01-01T00:00:00+00:00",
        )


# ---------------------------------------------------------------------------
# Tests: insufficient data
# ---------------------------------------------------------------------------


class TestInsufficientData:
    def test_no_projects_returns_insufficient(self, tmp_path):
        score, justification = score_convergence_candidate([], "CLAUDE.build.md::## step 1")
        assert score is None
        assert justification == "insufficient data"

    def test_fewer_than_5_attempts_returns_insufficient(self, tmp_path):
        proj = _make_project(tmp_path, "proj_a")
        _seed_db(proj, [1000, 2000, 1500])  # 3 attempts — below threshold
        score, justification = score_convergence_candidate(
            [proj], "CLAUDE.build.md::## step 1"
        )
        assert score is None
        assert justification == "insufficient data"

    def test_exactly_4_attempts_returns_insufficient(self, tmp_path):
        proj = _make_project(tmp_path, "proj_a")
        _seed_db(proj, [1000, 2000, 1500, 1800])  # exactly 4 — still below threshold
        score, justification = score_convergence_candidate(
            [proj], "CLAUDE.build.md::## review checklist"
        )
        assert score is None
        assert justification == "insufficient data"

    def test_exactly_5_attempts_produces_score(self, tmp_path):
        proj = _make_project(tmp_path, "proj_a")
        _seed_db(proj, [1000, 1200, 1100, 1050, 1150])  # exactly 5 — at threshold
        score, justification = score_convergence_candidate(
            [proj], "CLAUDE.build.md::## step 1"
        )
        # With only one project, fallback splits the list in half;
        # score should be defined and in valid range.
        assert score is not None
        assert 0.0 <= score <= 1.0
        assert isinstance(justification, str)
        assert "insufficient data" not in justification

    def test_only_reviewer_rows_returns_insufficient(self, tmp_path):
        """Builder-only counting — reviewer rows must be ignored."""
        proj = _make_project(tmp_path, "proj_a")
        _seed_db(proj, [1000, 2000, 3000, 4000, 5000], agent_role="reviewer")
        score, justification = score_convergence_candidate(
            [proj], "CLAUDE.build.md::## step 1"
        )
        assert score is None
        assert justification == "insufficient data"


# ---------------------------------------------------------------------------
# Tests: absent / empty databases
# ---------------------------------------------------------------------------


class TestAbsentOrEmptyDB:
    def test_absent_db_no_crash(self, tmp_path):
        proj = _make_project(tmp_path, "proj_no_db")
        # No DB created — just an empty .companion dir
        score, justification = score_convergence_candidate(
            [proj], "CLAUDE.build.md::## some section"
        )
        assert score is None
        assert justification == "insufficient data"

    def test_empty_db_no_crash(self, tmp_path):
        proj = _make_project(tmp_path, "proj_empty")
        db_path = proj / ".companion" / "effort.db"
        init_db(db_path)  # create schema but insert nothing
        score, justification = score_convergence_candidate(
            [proj], "CLAUDE.build.md::## some section"
        )
        assert score is None
        assert justification == "insufficient data"

    def test_mixed_absent_and_present(self, tmp_path):
        """Project with DB plus project without DB: no crash, counts combined."""
        proj_a = _make_project(tmp_path, "proj_a")
        proj_b = _make_project(tmp_path, "proj_b")
        # Only seed proj_a
        _seed_db(proj_a, [1000, 1200, 1100, 1050, 1150])
        # proj_b has no DB
        score, justification = score_convergence_candidate(
            [proj_a, proj_b], "CLAUDE.build.md::## step 1"
        )
        # proj_a has 5 attempts; proj_b contributes 0 → total = 5 → should score
        assert score is not None
        assert 0.0 <= score <= 1.0

    def test_zero_token_rows_are_excluded(self, tmp_path):
        """Rows with tokens_total=0 must not contribute to the count or median."""
        proj = _make_project(tmp_path, "proj_a")
        db_path = proj / ".companion" / "effort.db"
        init_db(db_path)
        # Insert 5 zero-token rows + 4 real rows → effective total < 5
        for i in range(5):
            insert_attempt(
                db_path,
                story_id=f"ZERO-{i:03d}",
                agent_role="builder",
                attempt_number=1,
                tokens_total=0,
                ts="2026-01-01T00:00:00+00:00",
            )
        for i in range(4):
            insert_attempt(
                db_path,
                story_id=f"REAL-{i:03d}",
                agent_role="builder",
                attempt_number=1,
                tokens_total=1000 + i * 100,
                ts="2026-01-01T00:00:00+00:00",
            )
        score, justification = score_convergence_candidate(
            [proj], "CLAUDE.build.md::## step 1"
        )
        assert score is None
        assert justification == "insufficient data"


# ---------------------------------------------------------------------------
# Tests: ranking matches seeded data
# ---------------------------------------------------------------------------


class TestRanking:
    def test_lower_token_project_gets_higher_score(self, tmp_path):
        """When one project has consistently lower tokens, its candidate scores > 0.5."""
        # proj_low: consistently low builder tokens
        proj_low = _make_project(tmp_path, "proj_low")
        _seed_db(proj_low, [500, 520, 510, 530, 515, 505])

        # proj_high: consistently high builder tokens
        proj_high = _make_project(tmp_path, "proj_high")
        _seed_db(proj_high, [5000, 5200, 5100, 5300, 5150, 5050])

        # pattern_id contains "proj_low" to match that project via substring
        score_low, just_low = score_convergence_candidate(
            [proj_low, proj_high], f"{proj_low.name}::## some pattern"
        )
        score_high, just_high = score_convergence_candidate(
            [proj_low, proj_high], f"{proj_high.name}::## some pattern"
        )

        assert score_low is not None
        assert score_high is not None
        # proj_low pattern → should show > 0.5 (lower tokens = better score)
        assert score_low > 0.5, f"Expected > 0.5 for low-token project, got {score_low}"
        # proj_high pattern → should show < 0.5 (higher tokens = worse score)
        assert score_high < 0.5, f"Expected < 0.5 for high-token project, got {score_high}"
        # And low > high
        assert score_low > score_high

    def test_score_in_valid_range(self, tmp_path):
        proj_a = _make_project(tmp_path, "proj_a")
        proj_b = _make_project(tmp_path, "proj_b")
        _seed_db(proj_a, [1000, 1100, 1050, 950, 1000])
        _seed_db(proj_b, [3000, 3200, 3100, 2900, 3050])
        score, _ = score_convergence_candidate(
            [proj_a, proj_b], "CLAUDE.build.md::## step 1"
        )
        assert score is not None
        assert 0.0 <= score <= 1.0

    def test_equal_tokens_score_near_half(self, tmp_path):
        """When all projects have the same token distribution, score should be ~0.5."""
        proj_a = _make_project(tmp_path, "proj_a")
        proj_b = _make_project(tmp_path, "proj_b")
        tokens = [1000, 1000, 1000, 1000, 1000]
        _seed_db(proj_a, tokens)
        _seed_db(proj_b, tokens)
        score, _ = score_convergence_candidate(
            [proj_a, proj_b], "CLAUDE.build.md::## step 1"
        )
        assert score is not None
        # Equal medians → score = 0.5 (within float tolerance)
        assert abs(score - 0.5) < 1e-9

    def test_justification_contains_pct_and_n(self, tmp_path):
        """Justification string must mention attempt count."""
        proj_a = _make_project(tmp_path, "proj_a")
        proj_b = _make_project(tmp_path, "proj_b")
        _seed_db(proj_a, [500, 510, 505, 520, 495])
        _seed_db(proj_b, [5000, 5100, 5050, 5200, 4950])
        _, justification = score_convergence_candidate(
            [proj_a, proj_b], f"{proj_a.name}::## some pattern"
        )
        assert "n=" in justification

    def test_three_projects_ranking(self, tmp_path):
        """Ensure ranking is consistent across three projects."""
        proj_low = _make_project(tmp_path, "proj_low")
        proj_mid = _make_project(tmp_path, "proj_mid")
        proj_high = _make_project(tmp_path, "proj_high")
        _seed_db(proj_low, [400, 410, 405, 420, 395, 400])
        _seed_db(proj_mid, [1000, 1010, 1005, 1020, 995, 1000])
        _seed_db(proj_high, [5000, 5010, 5005, 5020, 4995, 5000])

        all_dirs = [proj_low, proj_mid, proj_high]

        score_low, _ = score_convergence_candidate(all_dirs, f"{proj_low.name}::## p")
        score_mid, _ = score_convergence_candidate(all_dirs, f"{proj_mid.name}::## p")
        score_high, _ = score_convergence_candidate(all_dirs, f"{proj_high.name}::## p")

        assert score_low is not None and score_mid is not None and score_high is not None
        # Low-token project should score higher than high-token project
        assert score_low > score_high


# ---------------------------------------------------------------------------
# Tests: collect_builder_tokens helper
# ---------------------------------------------------------------------------


class TestCollectBuilderTokens:
    def test_absent_db_returns_empty(self, tmp_path):
        proj = _make_project(tmp_path, "proj_a")
        result = _collect_builder_tokens(proj)
        assert result == []

    def test_returns_only_builder_tokens(self, tmp_path):
        proj = _make_project(tmp_path, "proj_a")
        db_path = proj / ".companion" / "effort.db"
        init_db(db_path)
        insert_attempt(
            db_path,
            story_id="B-001",
            agent_role="builder",
            attempt_number=1,
            tokens_total=1000,
            ts="2026-01-01T00:00:00+00:00",
        )
        insert_attempt(
            db_path,
            story_id="R-001",
            agent_role="reviewer",
            attempt_number=1,
            tokens_total=9999,
            ts="2026-01-01T00:00:00+00:00",
        )
        result = _collect_builder_tokens(proj)
        assert result == [1000]

    def test_null_tokens_excluded(self, tmp_path):
        proj = _make_project(tmp_path, "proj_a")
        db_path = proj / ".companion" / "effort.db"
        init_db(db_path)
        insert_attempt(
            db_path,
            story_id="B-001",
            agent_role="builder",
            attempt_number=1,
            tokens_total=None,
            ts="2026-01-01T00:00:00+00:00",
        )
        result = _collect_builder_tokens(proj)
        assert result == []


# ---------------------------------------------------------------------------
# Tests: API surface — never raises
# ---------------------------------------------------------------------------


class TestNeverRaises:
    def test_invalid_project_path_no_crash(self, tmp_path):
        """A path that does not exist should not raise — returns insufficient data."""
        nonexistent = tmp_path / "does_not_exist"
        score, justification = score_convergence_candidate(
            [nonexistent], "CLAUDE.build.md::## step 1"
        )
        assert score is None
        assert justification == "insufficient data"

    def test_empty_pattern_id_no_crash(self, tmp_path):
        proj = _make_project(tmp_path, "proj_a")
        _seed_db(proj, [1000, 1100, 1050, 950, 1000])
        score, justification = score_convergence_candidate([proj], "")
        # Should not raise; may return insufficient data or a score
        assert isinstance(justification, str)

    def test_single_project_no_crash(self, tmp_path):
        proj = _make_project(tmp_path, "proj_a")
        _seed_db(proj, [1000, 1100, 1050, 950, 1000, 1030])
        score, justification = score_convergence_candidate(
            [proj], "CLAUDE.build.md::## step 1"
        )
        assert isinstance(justification, str)
