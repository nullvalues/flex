"""Tests for skills/pairmode/scripts/flex_build.py — the consolidated CLI
that replaces the 8 inline ``uv run python -c "..."`` blocks in
``skills/pairmode/templates/CLAUDE.build.md.j2`` (Story INFRA-131).

Each subcommand is exercised through ``subprocess.run`` so that the CLI's
real argv parsing and stdout/stderr behaviour are validated end-to-end.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPT = _REPO_ROOT / "skills" / "pairmode" / "scripts" / "flex_build.py"

# Make sibling modules importable for test-side helpers (seeding effort.db).
sys.path.insert(0, str(_REPO_ROOT / "skills" / "pairmode" / "scripts"))

import effort_db  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(*args: str) -> subprocess.CompletedProcess:
    """Invoke flex_build.py with *args*; return the completed process."""
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHONPATH": str(_REPO_ROOT),
        },
    )


def _write_story(
    project_dir: Path,
    story_id: str,
    *,
    story_class: str = "code",
    primary_files: list[str] | None = None,
    phase: str = "47",
) -> Path:
    """Write a minimal story spec under ``docs/stories/<RAIL>/<STORY_ID>.md``."""
    rail = story_id.split("-", 1)[0]
    story_dir = project_dir / "docs" / "stories" / rail
    story_dir.mkdir(parents=True, exist_ok=True)
    story_path = story_dir / f"{story_id}.md"

    pf_block = ""
    if primary_files:
        pf_block = "primary_files:\n" + "\n".join(
            f"  - {p}" for p in primary_files
        ) + "\n"
    else:
        pf_block = "primary_files: []\n"

    frontmatter = (
        "---\n"
        f"id: {story_id}\n"
        f"rail: {rail}\n"
        f"phase: '{phase}'\n"
        f"story_class: {story_class}\n"
        "status: planned\n"
        + pf_block
        + "touches: []\n"
        "---\n\n"
        "## Acceptance criterion\n\n_(fill in)_\n"
    )
    story_path.write_text(frontmatter, encoding="utf-8")
    return story_path


# ---------------------------------------------------------------------------
# select-builder-model
# ---------------------------------------------------------------------------


def test_select_builder_model_minimal_code_story(tmp_path: Path) -> None:
    _write_story(tmp_path, "INFRA-200", primary_files=["a.py"])
    result = _run(
        "select-builder-model",
        "--story-id", "INFRA-200",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout.strip()
    assert "|" in out
    assert out.startswith("sonnet"), f"expected sonnet, got {out!r}"


def test_select_builder_model_five_primary_files_prompts_upgrade(
    tmp_path: Path,
) -> None:
    _write_story(
        tmp_path,
        "INFRA-201",
        primary_files=["a.py", "b.py", "c.py", "d.py", "e.py"],
    )
    result = _run(
        "select-builder-model",
        "--story-id", "INFRA-201",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "opus|prompted-upgrade"


# ---------------------------------------------------------------------------
# write-permissions
# ---------------------------------------------------------------------------


def test_write_permissions_creates_story_scope(tmp_path: Path) -> None:
    _write_story(tmp_path, "INFRA-202", primary_files=["src/foo.py"])
    (tmp_path / ".claude").mkdir()

    result = _run(
        "write-permissions",
        "--story-id", "INFRA-202",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""

    scope_file = tmp_path / ".claude" / "story_scope.json"
    assert scope_file.exists()


# ---------------------------------------------------------------------------
# check-guardrail
# ---------------------------------------------------------------------------


def test_check_guardrail_empty_db_silent(tmp_path: Path) -> None:
    """With no historical data, the guardrail must not fire and stderr is empty."""
    result = _run(
        "check-guardrail",
        "--story-id", "INFRA-203",
        "--tokens", "50000",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr.strip() == ""


def test_check_guardrail_fires_on_excess_tokens(tmp_path: Path) -> None:
    """Seed effort.db with 3 PASS builder rows; latest tokens > 3x median fires."""
    db_path = tmp_path / ".companion" / "effort.db"
    db_path.parent.mkdir(parents=True)
    effort_db.init_db(db_path)

    now = _dt.datetime.now(tz=_dt.timezone.utc).isoformat()
    for i, tokens in enumerate([10000, 10000, 10000]):
        effort_db.insert_attempt(
            db_path,
            story_id=f"INFRA-19{i}",
            rail="INFRA",
            agent_role="builder",
            attempt_number=1,
            tokens_total=tokens,
            outcome="PASS",
            ts=now,
        )

    result = _run(
        "check-guardrail",
        "--story-id", "INFRA-204",
        "--tokens", "100000",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert "effort guardrail" in result.stderr
    assert "INFRA-204" in result.stderr


# ---------------------------------------------------------------------------
# select-reviewer-model
# ---------------------------------------------------------------------------


def test_select_reviewer_model_attempt_one_is_sonnet(tmp_path: Path) -> None:
    _write_story(tmp_path, "INFRA-205", primary_files=["a.py"])
    result = _run(
        "select-reviewer-model",
        "--story-id", "INFRA-205",
        "--attempt", "1",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines[0] == "sonnet"


def test_select_reviewer_model_attempt_two_is_opus(tmp_path: Path) -> None:
    _write_story(tmp_path, "INFRA-206", primary_files=["a.py"])
    result = _run(
        "select-reviewer-model",
        "--story-id", "INFRA-206",
        "--attempt", "2",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines[0] == "opus"


# ---------------------------------------------------------------------------
# clear-permissions
# ---------------------------------------------------------------------------


def test_clear_permissions_removes_story_scope(tmp_path: Path) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    scope_file = claude_dir / "story_scope.json"
    scope_file.write_text(
        json.dumps({"story_id": "INFRA-207", "added_rules": []}),
        encoding="utf-8",
    )
    assert scope_file.exists()

    result = _run(
        "clear-permissions",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert not scope_file.exists()


# ---------------------------------------------------------------------------
# select-security-auditor-model / select-intent-reviewer-model
# ---------------------------------------------------------------------------


_VALID_MODELS = {"haiku", "sonnet", "opus"}


def test_select_security_auditor_model_production() -> None:
    result = _run(
        "select-security-auditor-model",
        "--phase-class", "production",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() in _VALID_MODELS


def test_select_intent_reviewer_model_production() -> None:
    result = _run(
        "select-intent-reviewer-model",
        "--phase-class", "production",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() in _VALID_MODELS


# ---------------------------------------------------------------------------
# context-health
# ---------------------------------------------------------------------------


def test_context_health_empty_db_returns_json_with_recommendation(
    tmp_path: Path,
) -> None:
    result = _run(
        "context-health",
        "--phase", "47",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "recommendation" in payload


def test_context_health_output_has_message_field(tmp_path: Path) -> None:
    result = _run(
        "context-health",
        "--phase", "47",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "message" in payload
    assert isinstance(payload["message"], str)
    assert payload["message"] != ""
