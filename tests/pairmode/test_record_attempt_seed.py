"""Effort recording for seed-skill LLM calls (mine_sessions, reconcile).

These tests exercise the in-process ``effort_recorder.record_effort`` helper
the way ``skills/seed/scripts/mine_sessions.py`` and
``skills/seed/scripts/reconcile.py`` do it: with a synthetic usage object,
synthetic ``story_id`` values, and the cross-skill ``agent_role`` values
introduced by INFRA-035.

The seed scripts cannot be subagent-called by the build orchestrator
(``disable-model-invocation: true``), so recording must happen via the
wrapper helper rather than via ``record_attempt.py``'s CLI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skills.pairmode.scripts import effort_db
from skills.pairmode.scripts.effort_recorder import record_effort


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enable_tracking(project_dir: Path, **extra) -> Path:
    state_path = project_dir / ".companion" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"effort_tracking": True}
    payload.update(extra)
    state_path.write_text(json.dumps(payload), encoding="utf-8")
    return state_path


def _fake_usage(input_tokens: int = 1234, output_tokens: int = 567,
                cache_read: int = 100, cache_write: int = 50) -> dict:
    """Build a usage dict shaped like the SDK ResultMessage.usage payload."""
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_write,
    }


# ---------------------------------------------------------------------------
# seed-miner
# ---------------------------------------------------------------------------


class TestSeedMiner:
    def test_records_row_for_seed_miner(self, tmp_path: Path) -> None:
        _enable_tracking(tmp_path)
        usage = _fake_usage()

        row_id = record_effort(
            project_dir=tmp_path,
            story_id="seed:abc12345-deadbeef",
            agent_role="seed-miner",
            model="claude-haiku-4-5-20251001",
            usage=usage,
            attempt_number=1,
            outcome="PASS",
            notes="seed mine_sessions Haiku attempt",
        )
        assert row_id is not None and row_id > 0

        db_path = effort_db.resolve_effort_db_path(tmp_path)
        rows = effort_db.query_by_story(db_path, "seed:abc12345-deadbeef")
        assert len(rows) == 1
        row = rows[0]

        # Synthetic story_id and seed-specific role land verbatim.
        assert row["story_id"] == "seed:abc12345-deadbeef"
        assert row["agent_role"] == "seed-miner"
        assert row["model"] == "claude-haiku-4-5-20251001"

        # phase + rail are NULL for cross-skill rows.
        assert row["phase"] is None
        assert row["rail"] is None

        # Token usage is normalised correctly.
        assert row["tokens_in"] == 1234
        assert row["tokens_out"] == 567
        assert row["tokens_total"] == 1234 + 567
        assert row["cache_read_tokens"] == 100
        assert row["cache_write_tokens"] == 50

        assert row["outcome"] == "PASS"
        assert row["notes"] == "seed mine_sessions Haiku attempt"

    def test_records_haiku_then_sonnet_fallback_attempts(self, tmp_path: Path) -> None:
        """Two attempt rows for the same synthetic seed:<sid> story_id."""
        _enable_tracking(tmp_path)
        story_id = "seed:fallback-session"

        record_effort(
            project_dir=tmp_path,
            story_id=story_id,
            agent_role="seed-miner",
            model="claude-haiku-4-5-20251001",
            usage=_fake_usage(input_tokens=10, output_tokens=20),
            attempt_number=1,
            outcome="FAIL",
        )
        record_effort(
            project_dir=tmp_path,
            story_id=story_id,
            agent_role="seed-miner",
            model="claude-sonnet-4-6",
            usage=_fake_usage(input_tokens=2000, output_tokens=300),
            attempt_number=4,  # mirrors mine_sessions Sonnet numbering
            outcome="PASS",
        )

        db_path = effort_db.resolve_effort_db_path(tmp_path)
        rows = effort_db.query_by_story(db_path, story_id)
        assert len(rows) == 2

        # Distinct attempt numbers preserved
        attempts = {r["attempt_number"] for r in rows}
        assert attempts == {1, 4}

        # Distinct models preserved
        models = {r["model"] for r in rows}
        assert "claude-haiku-4-5-20251001" in models
        assert "claude-sonnet-4-6" in models


# ---------------------------------------------------------------------------
# seed-reconcile
# ---------------------------------------------------------------------------


class TestSeedReconcile:
    def test_records_row_for_seed_reconcile(self, tmp_path: Path) -> None:
        _enable_tracking(tmp_path)

        record_effort(
            project_dir=tmp_path,
            story_id="seed:reconcile",
            agent_role="seed-reconcile",
            model="claude-sonnet-4-6",
            usage=_fake_usage(input_tokens=8000, output_tokens=1500),
            attempt_number=1,
            outcome="PASS",
            notes="seed reconcile LLM merge/assign",
        )

        db_path = effort_db.resolve_effort_db_path(tmp_path)
        rows = effort_db.query_by_story(db_path, "seed:reconcile")
        assert len(rows) == 1
        row = rows[0]

        assert row["story_id"] == "seed:reconcile"
        assert row["agent_role"] == "seed-reconcile"
        assert row["model"] == "claude-sonnet-4-6"
        assert row["phase"] is None
        assert row["rail"] is None
        assert row["tokens_total"] == 9500
        assert row["outcome"] == "PASS"


# ---------------------------------------------------------------------------
# No-op behaviour
# ---------------------------------------------------------------------------


class TestNoOp:
    def test_no_state_json_silently_no_ops(self, tmp_path: Path) -> None:
        # No .companion/state.json — seed runs early in bootstrap and may
        # fire before pairmode setup creates state.json.
        result = record_effort(
            project_dir=tmp_path,
            story_id="seed:reconcile",
            agent_role="seed-reconcile",
            model="claude-sonnet-4-6",
            usage=_fake_usage(),
        )
        assert result is None

        # Confirm no DB file was created.
        assert not (tmp_path / ".companion" / "effort.db").exists()

    def test_effort_tracking_disabled_no_ops(self, tmp_path: Path) -> None:
        state_path = tmp_path / ".companion" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"effort_tracking": False}), encoding="utf-8")

        result = record_effort(
            project_dir=tmp_path,
            story_id="seed:reconcile",
            agent_role="seed-reconcile",
            model="claude-sonnet-4-6",
            usage=_fake_usage(),
        )
        assert result is None
        assert not (tmp_path / ".companion" / "effort.db").exists()

    def test_state_json_present_but_flag_missing(self, tmp_path: Path) -> None:
        state_path = tmp_path / ".companion" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"pairmode_version": "1.0"}), encoding="utf-8")

        result = record_effort(
            project_dir=tmp_path,
            story_id="seed:abc",
            agent_role="seed-miner",
            usage=_fake_usage(),
        )
        assert result is None

    def test_missing_required_fields_no_ops(self, tmp_path: Path) -> None:
        """Empty story_id / agent_role must not raise — best-effort recorder."""
        _enable_tracking(tmp_path)

        # Empty story_id
        assert record_effort(
            project_dir=tmp_path,
            story_id="",
            agent_role="seed-miner",
        ) is None

        # Empty agent_role
        assert record_effort(
            project_dir=tmp_path,
            story_id="seed:foo",
            agent_role="",
        ) is None

        # No DB file created when nothing was recorded.
        assert not (tmp_path / ".companion" / "effort.db").exists()


# ---------------------------------------------------------------------------
# Usage normalisation
# ---------------------------------------------------------------------------


class TestUsageNormalisation:
    def test_usage_none_records_null_tokens(self, tmp_path: Path) -> None:
        _enable_tracking(tmp_path)

        record_effort(
            project_dir=tmp_path,
            story_id="seed:no-usage",
            agent_role="seed-miner",
            model="claude-haiku-4-5-20251001",
            usage=None,
            attempt_number=1,
        )

        db_path = effort_db.resolve_effort_db_path(tmp_path)
        rows = effort_db.query_by_story(db_path, "seed:no-usage")
        assert len(rows) == 1
        assert rows[0]["tokens_in"] is None
        assert rows[0]["tokens_out"] is None
        assert rows[0]["tokens_total"] is None

    def test_usage_attribute_object(self, tmp_path: Path) -> None:
        """Helper accepts a non-dict object exposing the same attribute names."""
        _enable_tracking(tmp_path)

        class FakeUsage:
            input_tokens = 11
            output_tokens = 22
            cache_read_input_tokens = 3
            cache_creation_input_tokens = 4

        record_effort(
            project_dir=tmp_path,
            story_id="seed:attr",
            agent_role="seed-miner",
            usage=FakeUsage(),
        )

        db_path = effort_db.resolve_effort_db_path(tmp_path)
        rows = effort_db.query_by_story(db_path, "seed:attr")
        assert len(rows) == 1
        row = rows[0]
        assert row["tokens_in"] == 11
        assert row["tokens_out"] == 22
        assert row["tokens_total"] == 33
        assert row["cache_read_tokens"] == 3
        assert row["cache_write_tokens"] == 4


# ---------------------------------------------------------------------------
# Coexistence with pairmode loop rows
# ---------------------------------------------------------------------------


class TestCoexistence:
    def test_seed_rows_dont_collide_with_pairmode_loop(self, tmp_path: Path) -> None:
        """Pairmode-loop attempts (story_id=INFRA-035) and seed rows
        (story_id=seed:reconcile) live side-by-side without overlap.
        """
        _enable_tracking(tmp_path)
        db_path = effort_db.resolve_effort_db_path(tmp_path)

        # Pairmode loop row (mimics record_attempt.py output)
        effort_db.init_db(db_path)
        effort_db.insert_attempt(
            db_path,
            story_id="INFRA-035",
            phase="22",
            rail="INFRA",
            agent_role="builder",
            model="claude-sonnet-4-6",
            attempt_number=1,
            tokens_total=5000,
            tokens_in=4000,
            tokens_out=1000,
            ts="2026-05-01T00:00:00+00:00",
        )

        # Seed reconcile row via the helper
        record_effort(
            project_dir=tmp_path,
            story_id="seed:reconcile",
            agent_role="seed-reconcile",
            model="claude-sonnet-4-6",
            usage=_fake_usage(),
        )

        all_rows = effort_db.query_all(db_path)
        assert len(all_rows) == 2

        story_ids = {r["story_id"] for r in all_rows}
        assert story_ids == {"INFRA-035", "seed:reconcile"}

        # Pairmode row keeps phase/rail; seed row has them NULL.
        for r in all_rows:
            if r["story_id"] == "INFRA-035":
                assert r["phase"] == "22"
                assert r["rail"] == "INFRA"
            else:
                assert r["phase"] is None
                assert r["rail"] is None
