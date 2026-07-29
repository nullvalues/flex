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
from click.testing import CliRunner

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


# ---------------------------------------------------------------------------
# check-stubs
# ---------------------------------------------------------------------------


def _write_stub_story(
    project_dir: Path,
    story_id: str,
    body: str,
) -> Path:
    """Write a story file with the given body under docs/stories/<RAIL>/."""
    rail = story_id.split("-", 1)[0]
    story_dir = project_dir / "docs" / "stories" / rail
    story_dir.mkdir(parents=True, exist_ok=True)
    story_path = story_dir / f"{story_id}.md"
    story_path.write_text(
        f"---\nid: {story_id}\nrail: {rail}\n---\n\n{body}",
        encoding="utf-8",
    )
    return story_path


def test_check_stubs_delegation_detected(tmp_path: Path) -> None:
    _write_stub_story(
        tmp_path,
        "RBAC-001",
        "See phase doc `docs/phases/phase-PM004-main.md` for the full spec.\n",
    )
    result = _run("check-stubs", "--project-dir", str(tmp_path))
    assert result.returncode == 1
    assert "STUB" in result.stdout
    assert "RBAC-001" in result.stdout
    assert "delegation" in result.stdout


def test_check_stubs_no_acceptance_detected(tmp_path: Path) -> None:
    _write_stub_story(
        tmp_path,
        "MEDIA-001",
        "## Background\n\nSome context here.\n\n## Out of scope\n\nNothing.\n",
    )
    result = _run("check-stubs", "--project-dir", str(tmp_path))
    assert result.returncode == 1
    assert "STUB" in result.stdout
    assert "MEDIA-001" in result.stdout
    assert "no-acceptance" in result.stdout


def test_check_stubs_self_contained_not_flagged(tmp_path: Path) -> None:
    _write_stub_story(
        tmp_path,
        "RBAC-010",
        "## Acceptance criterion\n\nThe widget must turn blue.\n",
    )
    result = _run("check-stubs", "--project-dir", str(tmp_path))
    assert result.returncode == 0
    assert "OK" in result.stdout
    assert "RBAC-010" in result.stdout
    assert "STUB" not in result.stdout


def test_check_stubs_missing_stories_dir_returns_clean(tmp_path: Path) -> None:
    result = _run("check-stubs", "--project-dir", str(tmp_path))
    assert result.returncode == 0
    assert "0 stubs" in result.stdout
    assert "0 total" in result.stdout


def test_check_stubs_exit_code_zero_when_no_stubs(tmp_path: Path) -> None:
    _write_stub_story(
        tmp_path,
        "AEO-001",
        "## Acceptance criteria\n\n- It works.\n",
    )
    result = _run("check-stubs", "--project-dir", str(tmp_path))
    assert result.returncode == 0


def test_check_stubs_exit_code_one_when_stubs_present(tmp_path: Path) -> None:
    _write_stub_story(
        tmp_path,
        "AEO-002",
        "See docs/phases/phase-42.md for details.\n",
    )
    result = _run("check-stubs", "--project-dir", str(tmp_path))
    assert result.returncode == 1


# ---------------------------------------------------------------------------
# _parse_index_phases — multi-era tests
# ---------------------------------------------------------------------------

# Import the function under test directly.
sys.path.insert(0, str(_REPO_ROOT / "skills" / "pairmode" / "scripts"))
from flex_build import _parse_index_phases  # noqa: E402


def _make_era_index(era1_rows: list[tuple[str, str]], era2_rows: list[tuple[str, str]]) -> str:
    """Build a two-era index.md text with one table per era."""

    def _table(rows: list[tuple[str, str]]) -> str:
        lines = [
            "| Phase | Title | Status |",
            "|-------|-------|--------|",
        ]
        for ref, status in rows:
            lines.append(f"| {ref} | Phase {ref} | {status} |")
        return "\n".join(lines)

    return (
        "## Era 001\n\n"
        + _table(era1_rows)
        + "\n\n"
        "## Era 002\n\n"
        + _table(era2_rows)
        + "\n"
    )


def test_parse_index_phases_multi_era_returns_all_rows() -> None:
    """Rows from both era tables are returned."""
    text = _make_era_index(
        [("10", "complete"), ("11", "complete")],
        [("20", "complete"), ("21", "planned")],
    )
    rows = _parse_index_phases(text)
    refs = [r for r, _ in rows]
    assert "10" in refs
    assert "11" in refs
    assert "20" in refs
    assert "21" in refs
    assert len(rows) == 4


def test_parse_index_phases_multi_era_active_in_second_era() -> None:
    """A planned row in era 2 is found even when era 1 is all complete."""
    text = _make_era_index(
        [("10", "complete"), ("11", "complete")],
        [("20", "planned")],
    )
    rows = _parse_index_phases(text)
    # era-1 rows present
    assert ("10", "complete") in rows
    assert ("11", "complete") in rows
    # era-2 planned row present
    assert ("20", "planned") in rows


def test_parse_index_phases_single_era_unchanged() -> None:
    """A single-table index returns the same rows as before the fix."""
    text = (
        "| Phase | Title | Status |\n"
        "|-------|-------|--------|\n"
        "| 5 | Phase five | complete |\n"
        "| 6 | Phase six | planned |\n"
    )
    rows = _parse_index_phases(text)
    assert rows == [("5", "complete"), ("6", "planned")]


# ---------------------------------------------------------------------------
# check-stub (BUILD-034)
# ---------------------------------------------------------------------------


def _write_stub_story_fm(
    project_dir: Path,
    story_id: str,
    *,
    body: str = "## Ensures\n\n- It works.\n",
    extra_fm: str = "",
) -> Path:
    """Write a minimal story with YAML frontmatter and given body."""
    rail = story_id.split("-", 1)[0]
    story_dir = project_dir / "docs" / "stories" / rail
    story_dir.mkdir(parents=True, exist_ok=True)
    story_path = story_dir / f"{story_id}.md"
    story_path.write_text(
        f"---\nid: {story_id}\nrail: {rail}\nstatus: planned\nphase: '99'\n"
        f"primary_files: []\ntouches: []\n{extra_fm}---\n\n{body}",
        encoding="utf-8",
    )
    return story_path


def test_check_stub_clean_story_exits_0(tmp_path: Path) -> None:
    """A story with ## Ensures and no delegation language exits 0 silently."""
    _write_stub_story_fm(
        tmp_path,
        "BUILD-900",
        body="## Ensures\n\n- Widget turns blue.\n",
    )
    result = _run("check-stub", "BUILD-900", "--project-dir", str(tmp_path))
    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.strip() == ""


def test_check_stub_delegation_language_exits_1(tmp_path: Path) -> None:
    """A story containing 'See phase doc' exits 1 with PRE-STORY BLOCK."""
    _write_stub_story_fm(
        tmp_path,
        "BUILD-901",
        body="See phase doc `docs/phases/phase-42.md` for the full spec.\n\n## Ensures\n\n- Works.\n",
    )
    result = _run("check-stub", "BUILD-901", "--project-dir", str(tmp_path))
    assert result.returncode == 1
    assert "PRE-STORY BLOCK" in result.stdout
    assert "BUILD-901" in result.stdout
    assert "Delegation language found" in result.stdout


def test_check_stub_missing_acceptance_surface_exits_1(tmp_path: Path) -> None:
    """A story with no ## Ensures or equivalent exits 1."""
    _write_stub_story_fm(
        tmp_path,
        "BUILD-902",
        body="## Background\n\nSome context.\n\n## Out of scope\n\nNothing.\n",
    )
    result = _run("check-stub", "BUILD-902", "--project-dir", str(tmp_path))
    assert result.returncode == 1
    assert "PRE-STORY BLOCK" in result.stdout
    assert "No acceptance surface found" in result.stdout


def test_check_stub_missing_story_file_exits_2(tmp_path: Path) -> None:
    """A nonexistent story ID exits 2 with error on stderr."""
    result = _run("check-stub", "BUILD-999", "--project-dir", str(tmp_path))
    assert result.returncode == 2
    assert "not found" in result.stderr


# ---------------------------------------------------------------------------
# check-stub — quoted-text masking (CER-076, INFRA-268)
# ---------------------------------------------------------------------------

from flex_build import _STUB_DELEGATION_RE, check_stub_gate  # noqa: E402

# Derive a delegation phrase from the compiled regex's own literals so these
# tests cannot drift from the constant (never hard-code the phrase here).
_DELEGATION_PHRASE = _STUB_DELEGATION_RE.pattern.split("|")[0]


def test_check_stub_fenced_quote_passes(tmp_path: Path) -> None:
    """A delegation phrase occurring only inside a fenced code block passes."""
    _write_stub_story_fm(
        tmp_path,
        "BUILD-910",
        body=(
            "## Ensures\n\n- Works.\n\n"
            "Quoted deliverable text:\n\n"
            "```\n"
            f"{_DELEGATION_PHRASE} for the details.\n"
            "```\n"
        ),
    )
    result = check_stub_gate("BUILD-910", tmp_path)
    assert result["ok"] is True, result["reasons"]
    cli = _run("check-stub", "BUILD-910", "--project-dir", str(tmp_path))
    assert cli.returncode == 0, cli.stdout + cli.stderr
    assert cli.stdout.strip() == ""


def test_check_stub_inline_code_span_passes(tmp_path: Path) -> None:
    """A delegation phrase occurring only inside an inline code span passes."""
    _write_stub_story_fm(
        tmp_path,
        "BUILD-911",
        body=(
            "## Ensures\n\n- Works.\n\n"
            f"The gate blocks on the phrase `{_DELEGATION_PHRASE}` in prose.\n"
        ),
    )
    result = check_stub_gate("BUILD-911", tmp_path)
    assert result["ok"] is True, result["reasons"]


def test_check_stub_prose_delegation_still_blocks(tmp_path: Path) -> None:
    """A delegation phrase in plain prose still blocks (unchanged behaviour)."""
    _write_stub_story_fm(
        tmp_path,
        "BUILD-912",
        body=(
            "## Ensures\n\n- Works.\n\n"
            f"{_DELEGATION_PHRASE} for the full spec.\n"
        ),
    )
    result = check_stub_gate("BUILD-912", tmp_path)
    assert result["ok"] is False
    assert any("Delegation language found" in r for r in result["reasons"])
    cli = _run("check-stub", "BUILD-912", "--project-dir", str(tmp_path))
    assert cli.returncode == 1
    assert "PRE-STORY BLOCK" in cli.stdout


def test_check_stub_mixed_fenced_and_prose_reports_prose_line(
    tmp_path: Path,
) -> None:
    """Fenced quote plus a separate prose occurrence blocks; the reported
    matched line is the prose line, not the fenced one."""
    _write_stub_story_fm(
        tmp_path,
        "BUILD-913",
        body=(
            "## Ensures\n\n- Works.\n\n"
            "```\n"
            f"FENCED-MARKER {_DELEGATION_PHRASE} quoted as data.\n"
            "```\n\n"
            f"PROSE-MARKER {_DELEGATION_PHRASE} in real prose.\n"
        ),
    )
    result = check_stub_gate("BUILD-913", tmp_path)
    assert result["ok"] is False
    delegation_reasons = [
        r for r in result["reasons"] if "Delegation language found" in r
    ]
    assert delegation_reasons
    assert "PROSE-MARKER" in delegation_reasons[0]
    assert "FENCED-MARKER" not in delegation_reasons[0]


def test_check_stub_tilde_fence_passes(tmp_path: Path) -> None:
    """A delegation phrase inside a tilde (~~~) fence passes."""
    _write_stub_story_fm(
        tmp_path,
        "BUILD-914",
        body=(
            "## Ensures\n\n- Works.\n\n"
            "~~~\n"
            f"{_DELEGATION_PHRASE} quoted inside a tilde fence.\n"
            "~~~\n"
        ),
    )
    result = check_stub_gate("BUILD-914", tmp_path)
    assert result["ok"] is True, result["reasons"]


def test_check_stub_unterminated_fence_passes(tmp_path: Path) -> None:
    """An unterminated fence masks to end of text — the quoted phrase passes."""
    _write_stub_story_fm(
        tmp_path,
        "BUILD-915",
        body=(
            "## Ensures\n\n- Works.\n\n"
            "```\n"
            f"{_DELEGATION_PHRASE} inside an unterminated fence.\n"
        ),
    )
    result = check_stub_gate("BUILD-915", tmp_path)
    assert result["ok"] is True, result["reasons"]


def test_check_stub_home_006_shape_passes(tmp_path: Path) -> None:
    """The forqsite HOME-006 shape: instructions telling a builder to append a
    resolution note whose fenced content contains a delegation phrase must
    pass the gate (CER-076's originating false positive)."""
    _write_stub_story_fm(
        tmp_path,
        "BUILD-916",
        body=(
            "## Ensures\n\n- The backlog row carries the resolution note.\n\n"
            "## Instructions\n\n"
            "Append the following resolution note to the backlog row:\n\n"
            "```\n"
            f"**RESOLVED** — details recorded; {_DELEGATION_PHRASE} "
            "phase-PM066-main.md\n"
            "```\n"
        ),
    )
    result = check_stub_gate("BUILD-916", tmp_path)
    assert result["ok"] is True, result["reasons"]
    cli = _run("check-stub", "BUILD-916", "--project-dir", str(tmp_path))
    assert cli.returncode == 0, cli.stdout + cli.stderr


# ---------------------------------------------------------------------------
# check-schema-gate (BUILD-034)
# ---------------------------------------------------------------------------


def _write_phase_manifest(
    project_dir: Path,
    phase_id: str,
    stories: list[tuple[str, str, str]],
) -> Path:
    """Write docs/phases/phase-<phase_id>.md with a ## Stories table."""
    phases_dir = project_dir / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    phase_path = phases_dir / f"phase-{phase_id}.md"
    rows = "| ID | Title | Status |\n|----|-------|--------|\n"
    for sid, title, status in stories:
        rows += f"| {sid} | {title} | {status} |\n"
    phase_path.write_text(
        f"---\nid: '{phase_id}'\ntitle: Phase {phase_id}\n---\n\n## Stories\n\n{rows}",
        encoding="utf-8",
    )
    return phase_path


def test_check_schema_gate_false_exits_0(tmp_path: Path) -> None:
    """schema_introduces: false exits 0 silently."""
    _write_stub_story_fm(
        tmp_path,
        "BUILD-910",
        extra_fm="schema_introduces: false\n",
    )
    result = _run("check-schema-gate", "BUILD-910", "--project-dir", str(tmp_path))
    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.strip() == ""


def test_check_schema_gate_absent_exits_0(tmp_path: Path) -> None:
    """schema_introduces absent exits 0 silently."""
    _write_stub_story_fm(tmp_path, "BUILD-911")
    result = _run("check-schema-gate", "BUILD-911", "--project-dir", str(tmp_path))
    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.strip() == ""


def test_check_schema_gate_true_with_mgmt_story_exits_0(tmp_path: Path) -> None:
    """schema_introduces: true with a management story in the phase exits 0."""
    _write_stub_story_fm(
        tmp_path,
        "BUILD-912",
        extra_fm="schema_introduces: true\nphase: '80'\n",
    )
    _write_phase_manifest(
        tmp_path,
        "80",
        [
            ("BUILD-912", "introduce new table", "planned"),
            ("BUILD-913", "management UI for new table", "planned"),
        ],
    )
    result = _run("check-schema-gate", "BUILD-912", "--project-dir", str(tmp_path))
    assert result.returncode == 0, result.stderr + result.stdout


def test_check_schema_gate_true_with_exception_phrase_exits_0(tmp_path: Path) -> None:
    """schema_introduces: true with 'append-only' in story body exits 0."""
    _write_stub_story_fm(
        tmp_path,
        "BUILD-914",
        extra_fm="schema_introduces: true\n",
        body=(
            "## Background\n\nThis is an append-only audit log table.\n\n"
            "## Ensures\n\n- Rows are immutable.\n"
        ),
    )
    result = _run("check-schema-gate", "BUILD-914", "--project-dir", str(tmp_path))
    assert result.returncode == 0, result.stderr + result.stdout


def test_check_schema_gate_true_no_mgmt_exits_1(tmp_path: Path) -> None:
    """schema_introduces: true with no management surface and no exception exits 1."""
    _write_stub_story_fm(
        tmp_path,
        "BUILD-915",
        extra_fm="schema_introduces: true\nphase: '81'\n",
    )
    _write_phase_manifest(
        tmp_path,
        "81",
        [
            ("BUILD-915", "introduce new table", "planned"),
            ("BUILD-916", "add some index", "planned"),
        ],
    )
    result = _run("check-schema-gate", "BUILD-915", "--project-dir", str(tmp_path))
    assert result.returncode == 1
    assert "PRE-STORY BLOCK" in result.stdout
    assert "BUILD-915" in result.stdout


# ---------------------------------------------------------------------------
# check-auth-gate (BUILD-034)
# ---------------------------------------------------------------------------


def test_check_auth_gate_false_exits_0(tmp_path: Path) -> None:
    """auth_gated: false exits 0 silently."""
    _write_stub_story_fm(
        tmp_path,
        "BUILD-920",
        extra_fm="auth_gated: false\n",
    )
    result = _run("check-auth-gate", "BUILD-920", "--project-dir", str(tmp_path))
    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.strip() == ""


def test_check_auth_gate_absent_exits_0(tmp_path: Path) -> None:
    """auth_gated absent exits 0 silently."""
    _write_stub_story_fm(tmp_path, "BUILD-921")
    result = _run("check-auth-gate", "BUILD-921", "--project-dir", str(tmp_path))
    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.strip() == ""


def test_check_auth_gate_true_with_classification_exits_0(tmp_path: Path) -> None:
    """auth_gated: true with **Classification:** line in architecture.md exits 0."""
    _write_stub_story_fm(
        tmp_path,
        "BUILD-922",
        extra_fm="auth_gated: true\n",
    )
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "architecture.md").write_text(
        "# Architecture\n\n**Classification:** RBAC\n\nSome content.\n",
        encoding="utf-8",
    )
    result = _run("check-auth-gate", "BUILD-922", "--project-dir", str(tmp_path))
    assert result.returncode == 0, result.stderr + result.stdout


def test_check_auth_gate_true_no_classification_exits_1(tmp_path: Path) -> None:
    """auth_gated: true with no classification recorded exits 1."""
    _write_stub_story_fm(
        tmp_path,
        "BUILD-923",
        extra_fm="auth_gated: true\n",
    )
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "architecture.md").write_text(
        "# Architecture\n\nNo classification recorded here.\n",
        encoding="utf-8",
    )
    result = _run("check-auth-gate", "BUILD-923", "--project-dir", str(tmp_path))
    assert result.returncode == 1
    assert "AUTH GATE" in result.stdout
    assert "BUILD-923" in result.stdout


# ---------------------------------------------------------------------------
# current-phase (existing test)
# ---------------------------------------------------------------------------


def test_current_phase_finds_active_in_second_era(tmp_path: Path) -> None:
    """cmd_current_phase exits 0 and prints the phase path from era-2 table."""
    # Set up docs/phases/index.md with era-1 all complete, era-2 has active.
    phases_dir = tmp_path / "docs" / "phases"
    phases_dir.mkdir(parents=True)

    index_text = _make_era_index(
        [("10", "complete")],
        [("20", "planned")],
    )
    (phases_dir / "index.md").write_text(index_text, encoding="utf-8")

    # Create the phase file that current-phase should find.
    phase_file = phases_dir / "phase-20.md"
    phase_file.write_text(
        "---\nid: '20'\ntitle: Phase 20\nstatus: planned\n---\n\n## Stories\n",
        encoding="utf-8",
    )

    result = _run("current-phase", "--project-dir", str(tmp_path))
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "phase-20" in result.stdout


# ---------------------------------------------------------------------------
# BUILD-043: Reviewer FAIL reason capture via FAIL-CAUSE / --notes
#
# RELEASE-008 fold note: the retired agent template `reviewer.md.j2` and live
# agent `.claude/agents/reviewer.md` were deleted at the Era 3 fold merge. The
# FAIL-CAUSE instruction was ported into the plugin-versioned reviewer
# procedure skill, which is now the single live reviewer surface. These tests
# were retargeted accordingly.
# ---------------------------------------------------------------------------

_REVIEWER_PROCEDURE = (
    _REPO_ROOT / "skills" / "pairmode" / "skills" / "reviewer" / "procedure.md"
)


def test_reviewer_procedure_contains_fail_cause_instruction() -> None:
    """reviewer procedure.md must emit FAIL-CAUSE before git checkout on FAIL."""
    text = _REVIEWER_PROCEDURE.read_text(encoding="utf-8")
    lines = text.splitlines()

    assert "Before reverting, emit one line" in text, (
        "reviewer procedure.md missing 'Before reverting, emit one line' instruction"
    )
    assert "FAIL-CAUSE:" in text, "reviewer procedure.md missing FAIL-CAUSE: marker"

    # FAIL-CAUSE: must appear before the FAIL-revert git checkout command.
    fail_cause_line = next(
        (i for i, ln in enumerate(lines) if "FAIL-CAUSE:" in ln), None
    )
    git_checkout_line = next(
        (
            i
            for i, ln in enumerate(lines)
            if ln.strip() == "git checkout ."
        ),
        None,
    )
    assert fail_cause_line is not None, "FAIL-CAUSE: not found in reviewer procedure.md"
    assert git_checkout_line is not None, (
        "git checkout . not found in reviewer procedure.md"
    )
    assert fail_cause_line < git_checkout_line, (
        f"FAIL-CAUSE: (line {fail_cause_line}) must appear before "
        f"git checkout . (line {git_checkout_line}) in reviewer procedure.md"
    )


def test_reviewer_procedure_passes_notes_on_reviewer_fail() -> None:
    """The reviewer procedure must document --notes near --outcome FAIL."""
    text = _REVIEWER_PROCEDURE.read_text(encoding="utf-8")
    lines = text.splitlines()

    fail_lines = [i for i, ln in enumerate(lines) if "--outcome FAIL" in ln]
    assert fail_lines, "No '--outcome FAIL' found in reviewer procedure.md"

    found_notes_near_fail = False
    for fail_idx in fail_lines:
        window_start = max(0, fail_idx - 30)
        window_end = min(len(lines), fail_idx + 30)
        window = "\n".join(lines[window_start:window_end])
        if "--notes" in window:
            found_notes_near_fail = True
            break

    assert found_notes_near_fail, (
        "--notes not found within 30 lines of '--outcome FAIL' in reviewer procedure.md"
    )


# ---------------------------------------------------------------------------
# check-story-scope: architecture.md hint
# ---------------------------------------------------------------------------


def _write_story_with_touches(
    project_dir: Path,
    story_id: str,
    *,
    story_class: str = "code",
    primary_files: list[str] | None = None,
    touches: list[str] | None = None,
    phase: str = "83",
) -> Path:
    """Write a minimal story spec with explicit touches list."""
    rail = story_id.split("-", 1)[0]
    story_dir = project_dir / "docs" / "stories" / rail
    story_dir.mkdir(parents=True, exist_ok=True)
    story_path = story_dir / f"{story_id}.md"

    def _yaml_list(items: list[str] | None) -> str:
        if not items:
            return "[]"
        entries = "\n".join(f"  - {p}" for p in items)
        return f"\n{entries}"

    frontmatter = (
        "---\n"
        f"id: {story_id}\n"
        f"rail: {rail}\n"
        f"phase: '{phase}'\n"
        f"story_class: {story_class}\n"
        "status: planned\n"
        f"primary_files: {_yaml_list(primary_files)}\n"
        f"touches: {_yaml_list(touches)}\n"
        "---\n\n"
        "## Acceptance criterion\n\n_(fill in)_\n"
    )
    story_path.write_text(frontmatter, encoding="utf-8")
    return story_path


def test_check_story_scope_code_no_docs_emits_architecture_hint(tmp_path: Path) -> None:
    """code story with no docs/ paths emits 'Scope hint' and 'docs/architecture.md'."""
    _write_story_with_touches(
        tmp_path,
        "TEST-001",
        story_class="code",
        primary_files=["skills/pairmode/scripts/foo.py"],
        touches=[],
    )
    result = _run(
        "check-story-scope",
        "TEST-001",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert "Scope hint" in result.stdout
    assert "docs/architecture.md" in result.stdout


def test_check_story_scope_code_with_docs_path_no_hint(tmp_path: Path) -> None:
    """code story that already touches a docs/ path does NOT emit the architecture hint."""
    _write_story_with_touches(
        tmp_path,
        "TEST-002",
        story_class="code",
        primary_files=["skills/pairmode/scripts/foo.py"],
        touches=["docs/architecture.md"],
    )
    result = _run(
        "check-story-scope",
        "TEST-002",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert "Scope hint" not in result.stdout


def test_check_story_scope_methodology_no_hint(tmp_path: Path) -> None:
    """methodology story does NOT emit the architecture hint."""
    _write_story_with_touches(
        tmp_path,
        "TEST-003",
        story_class="methodology",
        primary_files=["skills/pairmode/templates/agents/builder.md.j2"],
        touches=[],
    )
    result = _run(
        "check-story-scope",
        "TEST-003",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert "Scope hint" not in result.stdout


# ---------------------------------------------------------------------------
# Scope budget warning tests (INFRA-188)
# ---------------------------------------------------------------------------


def test_scope_budget_warning_emitted_when_over_limit(tmp_path: Path) -> None:
    """Story with 5 primary_files + 5 touches (10 total) emits scope budget warning."""
    _write_story_with_touches(
        tmp_path,
        "TEST-010",
        story_class="code",
        primary_files=[
            "skills/pairmode/scripts/a.py",
            "skills/pairmode/scripts/b.py",
            "skills/pairmode/scripts/c.py",
            "skills/pairmode/scripts/d.py",
            "skills/pairmode/scripts/e.py",
        ],
        touches=[
            "tests/pairmode/test_a.py",
            "tests/pairmode/test_b.py",
            "tests/pairmode/test_c.py",
            "tests/pairmode/test_d.py",
            "tests/pairmode/test_e.py",
        ],
    )
    result = _run(
        "check-story-scope",
        "TEST-010",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert "Scope budget" in result.stdout
    assert "10 files" in result.stdout
    assert "consider splitting" in result.stdout


def test_scope_budget_no_warning_at_limit(tmp_path: Path) -> None:
    """Story with exactly 8 declared files does NOT emit scope budget warning."""
    _write_story_with_touches(
        tmp_path,
        "TEST-011",
        story_class="code",
        primary_files=[
            "skills/pairmode/scripts/a.py",
            "skills/pairmode/scripts/b.py",
            "skills/pairmode/scripts/c.py",
            "skills/pairmode/scripts/d.py",
        ],
        touches=[
            "tests/pairmode/test_a.py",
            "tests/pairmode/test_b.py",
            "tests/pairmode/test_c.py",
            "tests/pairmode/test_d.py",
        ],
    )
    result = _run(
        "check-story-scope",
        "TEST-011",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert "Scope budget" not in result.stdout


def test_scope_budget_no_warning_when_empty(tmp_path: Path) -> None:
    """Story with both lists empty does NOT emit scope budget warning."""
    _write_story_with_touches(
        tmp_path,
        "TEST-012",
        story_class="doc",
        primary_files=[],
        touches=[],
    )
    result = _run(
        "check-story-scope",
        "TEST-012",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert "Scope budget" not in result.stdout


def test_scope_budget_exit_code_zero(tmp_path: Path) -> None:
    """Over-limit story still exits 0 (informational, not blocking)."""
    _write_story_with_touches(
        tmp_path,
        "TEST-013",
        story_class="code",
        primary_files=[f"skills/pairmode/scripts/file{i}.py" for i in range(9)],
        touches=[],
    )
    result = _run(
        "check-story-scope",
        "TEST-013",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0
    assert "Scope budget" in result.stdout


# ---------------------------------------------------------------------------
# spec-preflight (INFRA-191)
# ---------------------------------------------------------------------------


def test_spec_preflight_subcommand_exits_0_with_clean_story(tmp_path: Path) -> None:
    """A story with no route/constant references exits 0 with empty stdout."""
    _write_stub_story_fm(
        tmp_path,
        "TEST-800",
        body="## Ensures\n\n- The widget is green.\n",
    )
    result = _run("spec-preflight", "--story-id", "TEST-800", "--project-dir", str(tmp_path))
    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.strip() == ""


def test_spec_preflight_subcommand_missing_story_exits_0(tmp_path: Path) -> None:
    """A nonexistent story ID exits 0 (informational, not blocking)."""
    result = _run("spec-preflight", "--story-id", "INFRA-999", "--project-dir", str(tmp_path))
    assert result.returncode == 0


def test_spec_preflight_subcommand_help_shows_story_id_flag() -> None:
    """spec-preflight --help output must mention --story-id."""
    result = _run("spec-preflight", "--help")
    assert result.returncode == 0, result.stderr
    assert "--story-id" in result.stdout


# ---------------------------------------------------------------------------
# create/merge/discard-story-worktree (INFRA-224)
# ---------------------------------------------------------------------------


def _init_git_repo(project: Path) -> None:
    """Initialise *project* as a git repo with one commit on the default branch."""
    subprocess.run(["git", "init", "-q"], cwd=str(project), check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(project),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=str(project), check=True
    )
    (project / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(project), check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "initial"], cwd=str(project), check=True
    )


def _git(project: Path, *args: str) -> subprocess.CompletedProcess:
    """Run a git command in *project* and capture its output."""
    return subprocess.run(
        ["git", *args],
        cwd=str(project),
        capture_output=True,
        text=True,
    )


def _commit_in(worktree: Path, filename: str, content: str, msg: str) -> None:
    """Create/overwrite *filename* in *worktree* and commit it there."""
    (worktree / filename).write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", filename], cwd=str(worktree), check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", msg], cwd=str(worktree), check=True
    )


def _create_worktree(project: Path, story_id: str) -> subprocess.CompletedProcess:
    """Run ``create-story-worktree`` for *story_id* in *project*.

    A minimal story spec is materialised first when none exists. INFRA-296
    made a permissions-generation failure fatal in ``create-story-worktree``
    (it tears the worktree down and exits 1), and a missing story spec is one
    such failure — so every worktree test needs a spec on disk for the ID it
    uses. An existing spec is left untouched: tests that care about the spec's
    contents (or its malformedness) write their own before calling this.
    """
    rail = story_id.split("-", 1)[0]
    if not (project / "docs" / "stories" / rail / f"{story_id}.md").exists():
        _write_story(project, story_id)
    return _run(
        "create-story-worktree",
        "--story-id", story_id,
        "--project-dir", str(project),
    )


class TestStoryWorktreeLifecycle:
    """create / merge / discard-story-worktree (INFRA-224)."""

    def test_create_story_worktree_creates_branch_and_directory(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)
        result = _create_worktree(tmp_path, "WT-001")
        assert result.returncode == 0, result.stderr
        wt = tmp_path / ".pairmode-worktrees" / "WT-001"
        assert wt.is_dir()
        # stdout is the absolute worktree path.
        assert result.stdout.strip() == str(wt.resolve())
        # git worktree list shows it.
        listing = _git(tmp_path, "worktree", "list")
        assert str(wt.resolve()) in listing.stdout
        # the new branch exists.
        branch = _git(
            tmp_path, "rev-parse", "--verify", "refs/heads/pairmode/WT-001"
        )
        assert branch.returncode == 0

    def test_create_story_worktree_fails_if_already_exists(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)
        first = _create_worktree(tmp_path, "WT-002")
        assert first.returncode == 0, first.stderr
        second = _create_worktree(tmp_path, "WT-002")
        assert second.returncode != 0
        assert "already exists" in second.stderr

    def test_worktree_edits_isolated_from_main_tree(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)
        _create_worktree(tmp_path, "WT-003")
        wt = tmp_path / ".pairmode-worktrees" / "WT-003"
        (wt / "feature.txt").write_text("in-worktree\n", encoding="utf-8")
        # Not visible in the main worktree until merged.
        assert not (tmp_path / "feature.txt").exists()

    def test_merge_story_worktree_lands_commit_on_main_branch(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)
        _create_worktree(tmp_path, "WT-004")
        wt = tmp_path / ".pairmode-worktrees" / "WT-004"
        _commit_in(wt, "feature.txt", "done\n", "add feature")
        result = _run(
            "merge-story-worktree",
            "--story-id", "WT-004",
            "--project-dir", str(tmp_path),
        )
        assert result.returncode == 0, result.stderr
        # The commit is now on the main branch and the file materialised.
        assert (tmp_path / "feature.txt").read_text() == "done\n"
        log = _git(tmp_path, "log", "--oneline")
        assert "add feature" in log.stdout
        # Worktree and branch are gone.
        assert not wt.exists()
        branch = _git(
            tmp_path, "rev-parse", "--verify", "refs/heads/pairmode/WT-004"
        )
        assert branch.returncode != 0

    def test_merge_story_worktree_clears_attempt_counter(
        self, tmp_path: Path
    ) -> None:
        """INFRA-237: a successful merge is the durable PASS signal — clear
        the counter so the next story doesn't inherit a stale FAIL count."""
        _init_git_repo(tmp_path)
        _run(
            "write-attempt-count",
            "--story-id", "WT-100",
            "--count", "2",
            "--project-dir", str(tmp_path),
        )
        counter_path = tmp_path / ".companion" / "attempt_counter.json"
        assert counter_path.exists()

        _create_worktree(tmp_path, "WT-100")
        wt = tmp_path / ".pairmode-worktrees" / "WT-100"
        _commit_in(wt, "feature.txt", "done\n", "add feature")
        result = _run(
            "merge-story-worktree",
            "--story-id", "WT-100",
            "--project-dir", str(tmp_path),
        )
        assert result.returncode == 0, result.stderr
        assert not counter_path.exists()

    def test_merge_story_worktree_rebases_past_intervening_main_commits(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)
        _create_worktree(tmp_path, "WT-005")
        wt = tmp_path / ".pairmode-worktrees" / "WT-005"
        _commit_in(wt, "feature.txt", "wt work\n", "worktree commit")
        # Advance the main branch AFTER the worktree was created.
        (tmp_path / "mainfile.txt").write_text("main work\n", encoding="utf-8")
        subprocess.run(["git", "add", "mainfile.txt"], cwd=str(tmp_path), check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "main commit"],
            cwd=str(tmp_path),
            check=True,
        )
        result = _run(
            "merge-story-worktree",
            "--story-id", "WT-005",
            "--project-dir", str(tmp_path),
        )
        assert result.returncode == 0, result.stderr
        log = _git(tmp_path, "log", "--oneline").stdout
        assert "worktree commit" in log
        assert "main commit" in log
        assert (tmp_path / "feature.txt").exists()
        assert (tmp_path / "mainfile.txt").exists()

    def test_merge_story_worktree_conflict_aborts_cleanly(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)
        # A shared file both branches will edit on the same line.
        (tmp_path / "shared.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "shared.txt"], cwd=str(tmp_path), check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "add shared"],
            cwd=str(tmp_path),
            check=True,
        )
        _create_worktree(tmp_path, "WT-006")
        wt = tmp_path / ".pairmode-worktrees" / "WT-006"
        _commit_in(wt, "shared.txt", "worktree-change\n", "wt edit shared")
        # Conflicting edit on the main branch.
        (tmp_path / "shared.txt").write_text("main-change\n", encoding="utf-8")
        subprocess.run(["git", "add", "shared.txt"], cwd=str(tmp_path), check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "main edit shared"],
            cwd=str(tmp_path),
            check=True,
        )
        main_head_before = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
        # Seed a counter, as a real FAIL-then-retry cycle would have left one.
        _run(
            "write-attempt-count",
            "--story-id", "WT-006",
            "--count", "1",
            "--project-dir", str(tmp_path),
        )

        result = _run(
            "merge-story-worktree",
            "--story-id", "WT-006",
            "--project-dir", str(tmp_path),
        )
        assert result.returncode != 0
        # The rebase was aborted: no lingering rebase state in the worktree gitdir.
        wt_gitdir = _git(
            wt, "rev-parse", "--git-dir"
        ).stdout.strip()
        assert not (Path(wt_gitdir) / "rebase-merge").exists()
        assert not (Path(wt_gitdir) / "rebase-apply").exists()
        # The main worktree is unaffected.
        main_head_after = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
        assert main_head_after == main_head_before
        assert (tmp_path / "shared.txt").read_text() == "main-change\n"
        # A failed merge must not clear the counter — the story hasn't landed.
        counter_path = tmp_path / ".companion" / "attempt_counter.json"
        assert counter_path.exists()

    def test_discard_story_worktree_removes_uncommitted_changes_only_in_worktree(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)
        # Untracked content in the MAIN worktree, mirroring the RELEASE-022
        # docs/stories/CORE/-style scenario — must survive a discard.
        main_untracked = tmp_path / "docs" / "stories" / "CORE"
        main_untracked.mkdir(parents=True)
        (main_untracked / "keep.md").write_text("precious\n", encoding="utf-8")

        _create_worktree(tmp_path, "WT-007")
        wt = tmp_path / ".pairmode-worktrees" / "WT-007"
        # Uncommitted + untracked content inside the worktree (never committed).
        (wt / "scratch.txt").write_text("throwaway\n", encoding="utf-8")

        result = _run(
            "discard-story-worktree",
            "--story-id", "WT-007",
            "--project-dir", str(tmp_path),
        )
        assert result.returncode == 0, result.stderr
        # The worktree and branch are gone.
        assert not wt.exists()
        branch = _git(
            tmp_path, "rev-parse", "--verify", "refs/heads/pairmode/WT-007"
        )
        assert branch.returncode != 0
        # The main worktree's own untracked content is untouched.
        assert (main_untracked / "keep.md").read_text() == "precious\n"


class TestCreateStoryWorktreeAtomicity:
    """create-story-worktree is all-or-nothing (INFRA-296, CER-115)."""

    @staticmethod
    def _write_raw_story(project: Path, story_id: str, fm_lines: str) -> Path:
        """Write a story spec whose frontmatter body is *fm_lines* verbatim."""
        rail = story_id.split("-", 1)[0]
        story_dir = project / "docs" / "stories" / rail
        story_dir.mkdir(parents=True, exist_ok=True)
        story_path = story_dir / f"{story_id}.md"
        story_path.write_text(
            "---\n"
            f"id: {story_id}\n"
            f"rail: {rail}\n"
            "phase: '113'\n"
            "status: planned\n"
            f"{fm_lines}"
            "---\n\n"
            "## Acceptance criterion\n\n_(fill in)_\n",
            encoding="utf-8",
        )
        return story_path

    @staticmethod
    def _git_state(project: Path) -> tuple[str, str]:
        """Capture the git state a half-created worktree would perturb."""
        return (
            _git(project, "worktree", "list", "--porcelain").stdout,
            _git(project, "branch", "--list", "pairmode/*").stdout,
        )

    def test_c4_permissions_failure_leaves_git_state_byte_identical(
        self, tmp_path: Path
    ) -> None:
        """C4: a malformed-frontmatter story fails the create outright — exit 1,
        no worktree, no branch, nothing on stdout, and the story spec path in
        the error."""
        _init_git_repo(tmp_path)
        self._write_raw_story(tmp_path, "WT-300", "primary_files: [a.py, b.py\n")
        before = self._git_state(tmp_path)

        result = _run(
            "create-story-worktree",
            "--story-id", "WT-300",
            "--project-dir", str(tmp_path),
        )

        assert result.returncode == 1
        assert result.stdout.strip() == ""
        assert "docs/stories/WT/WT-300.md" in result.stderr
        assert self._git_state(tmp_path) == before
        assert not (tmp_path / ".pairmode-worktrees" / "WT-300").exists()

    def test_c5_second_attempt_after_failure_succeeds_without_manual_discard(
        self, tmp_path: Path
    ) -> None:
        """C5: the failed create leaves no residue — repairing the frontmatter
        and re-running succeeds, with no discard-story-worktree in between."""
        _init_git_repo(tmp_path)
        self._write_raw_story(tmp_path, "WT-301", "primary_files: [a.py, b.py\n")
        first = _run(
            "create-story-worktree",
            "--story-id", "WT-301",
            "--project-dir", str(tmp_path),
        )
        assert first.returncode == 1

        self._write_raw_story(
            tmp_path, "WT-301", "primary_files:\n  - a.py\n  - b.py\n"
        )
        second = _run(
            "create-story-worktree",
            "--story-id", "WT-301",
            "--project-dir", str(tmp_path),
        )
        assert second.returncode == 0, second.stderr
        wt = tmp_path / ".pairmode-worktrees" / "WT-301"
        assert second.stdout.strip() == str(wt.resolve())
        assert wt.is_dir()

    def test_c6_flow_style_frontmatter_end_to_end(self, tmp_path: Path) -> None:
        """C6: flow-style primary_files/touches produce a permissions artifact
        listing every declared path plus the story spec, in declaration order."""
        _init_git_repo(tmp_path)
        self._write_raw_story(
            tmp_path,
            "WT-302",
            "primary_files: [skills/pairmode/scripts/a.py, docs/architecture.md]\n"
            "touches: [tests/pairmode/test_a.py]\n",
        )
        result = _run(
            "create-story-worktree",
            "--story-id", "WT-302",
            "--project-dir", str(tmp_path),
        )
        assert result.returncode == 0, result.stderr

        payload = json.loads(
            (tmp_path / "docs" / "phases" / "permissions" / "WT-302.json").read_text(
                encoding="utf-8"
            )
        )
        assert payload["allowed_paths"] == [
            "skills/pairmode/scripts/a.py",
            "docs/architecture.md",
            "tests/pairmode/test_a.py",
            "docs/stories/WT/WT-302.md",
        ]

    def test_b4_check_story_scope_exits_1_on_malformed_frontmatter(
        self, tmp_path: Path
    ) -> None:
        """B4: check-story-scope's existing broad handler converts the parser's
        refusal into its own prefixed message and exit 1 — no traceback."""
        self._write_raw_story(tmp_path, "WT-303", "primary_files: [a.py, b.py\n")
        result = _run(
            "check-story-scope", "WT-303", "--project-dir", str(tmp_path)
        )
        assert result.returncode == 1
        assert result.stderr.startswith(
            "check-story-scope: failed to parse frontmatter:"
        )
        assert "Traceback" not in result.stderr


class TestClaimedStoryIds:
    """claimed_story_ids (CER-095.1, INFRA-280) — A1, A2."""

    def test_empty_when_worktrees_dir_absent(self, tmp_path: Path) -> None:
        import flex_build  # noqa: E402

        assert flex_build.claimed_story_ids(tmp_path) == set()

    def test_ignores_plain_file_and_non_matching_directory(
        self, tmp_path: Path
    ) -> None:
        import flex_build  # noqa: E402

        wt_root = tmp_path / ".pairmode-worktrees"
        wt_root.mkdir()
        (wt_root / "INFRA-999").write_text("not a directory\n", encoding="utf-8")
        (wt_root / "tmp").mkdir()
        (wt_root / ".DS_Store").mkdir()
        assert flex_build.claimed_story_ids(tmp_path) == set()

    def test_tracks_create_merge_discard_lifecycle(self, tmp_path: Path) -> None:
        import flex_build  # noqa: E402

        _init_git_repo(tmp_path)
        _create_worktree(tmp_path, "WT-201")
        assert flex_build.claimed_story_ids(tmp_path) == {"WT-201"}

        wt = tmp_path / ".pairmode-worktrees" / "WT-201"
        _commit_in(wt, "feature.txt", "done\n", "add feature")
        merge_result = _run(
            "merge-story-worktree",
            "--story-id", "WT-201",
            "--project-dir", str(tmp_path),
        )
        assert merge_result.returncode == 0, merge_result.stderr
        assert flex_build.claimed_story_ids(tmp_path) == set()

    def test_tracks_create_discard_lifecycle(self, tmp_path: Path) -> None:
        import flex_build  # noqa: E402

        _init_git_repo(tmp_path)
        _create_worktree(tmp_path, "WT-202")
        assert flex_build.claimed_story_ids(tmp_path) == {"WT-202"}

        discard_result = _run(
            "discard-story-worktree",
            "--story-id", "WT-202",
            "--project-dir", str(tmp_path),
        )
        assert discard_result.returncode == 0, discard_result.stderr
        assert flex_build.claimed_story_ids(tmp_path) == set()


class TestStoryWorktreeActiveStoryStamping:
    """create/merge/discard-story-worktree stamp/clear current_story + the
    Layer 1 permission artifact (INFRA-238)."""

    def test_create_story_worktree_stamps_current_story_and_permissions(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)
        _write_story(tmp_path, "WT-200", primary_files=["skills/foo.py"])
        result = _create_worktree(tmp_path, "WT-200")
        assert result.returncode == 0, result.stderr

        state = json.loads((tmp_path / ".companion" / "state.json").read_text())
        assert state["current_story"]["id"] == "WT-200"

        perm_path = tmp_path / "docs" / "phases" / "permissions" / "WT-200.json"
        assert perm_path.exists()
        payload = json.loads(perm_path.read_text())
        assert "skills/foo.py" in payload["allowed_paths"]

    def test_merge_story_worktree_clears_current_story_and_permissions(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)
        _write_story(tmp_path, "WT-201", primary_files=["feature.txt"])
        _create_worktree(tmp_path, "WT-201")
        wt = tmp_path / ".pairmode-worktrees" / "WT-201"
        _commit_in(wt, "feature.txt", "done\n", "add feature")

        result = _run(
            "merge-story-worktree",
            "--story-id", "WT-201",
            "--project-dir", str(tmp_path),
        )
        assert result.returncode == 0, result.stderr

        state = json.loads((tmp_path / ".companion" / "state.json").read_text())
        assert "current_story" not in state
        assert not (
            tmp_path / "docs" / "phases" / "permissions" / "WT-201.json"
        ).exists()

    def test_discard_story_worktree_clears_current_story_and_permissions(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)
        _write_story(tmp_path, "WT-202", primary_files=["scratch.txt"])
        _create_worktree(tmp_path, "WT-202")
        assert (
            tmp_path / "docs" / "phases" / "permissions" / "WT-202.json"
        ).exists()

        result = _run(
            "discard-story-worktree",
            "--story-id", "WT-202",
            "--project-dir", str(tmp_path),
        )
        assert result.returncode == 0, result.stderr

        state = json.loads((tmp_path / ".companion" / "state.json").read_text())
        assert "current_story" not in state
        assert not (
            tmp_path / "docs" / "phases" / "permissions" / "WT-202.json"
        ).exists()

    def test_create_story_worktree_without_story_spec_fails_and_tears_down(
        self, tmp_path: Path
    ) -> None:
        """INFRA-296 (C1) supersedes INFRA-238's best-effort wording for the
        permissions half: a story_id with no matching spec file cannot yield a
        permissions artifact, so the worktree is torn back down and the command
        exits 1 rather than handing a builder an unenforced worktree."""
        _init_git_repo(tmp_path)
        result = _run(
            "create-story-worktree",
            "--story-id", "WT-203",
            "--project-dir", str(tmp_path),
        )
        assert result.returncode == 1
        assert "failed to generate permissions for WT-203" in result.stderr
        assert not (tmp_path / ".pairmode-worktrees" / "WT-203").exists()
        assert result.stdout.strip() == ""
        branch = _git(tmp_path, "rev-parse", "--verify", "refs/heads/pairmode/WT-203")
        assert branch.returncode != 0


class TestScopedActiveStoryClear:
    """INFRA-281 (CER-095.2): merge/discard clear only their own key.

    B8: current_stories retains the sibling entry after merge/discard.
    B9: the CER-095.2 regression — a still-building sibling's scope
    enforcement must not go dark when the first story lands.
    """

    def test_merge_clears_only_its_own_key(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _write_story(tmp_path, "WT-210", primary_files=["a.py"])
        _write_story(tmp_path, "WT-211", primary_files=["b.py"])
        _create_worktree(tmp_path, "WT-210")
        _create_worktree(tmp_path, "WT-211")

        wt_a = tmp_path / ".pairmode-worktrees" / "WT-210"
        _commit_in(wt_a, "a.py", "done\n", "add a")
        result = _run(
            "merge-story-worktree",
            "--story-id", "WT-210",
            "--project-dir", str(tmp_path),
        )
        assert result.returncode == 0, result.stderr

        state = json.loads((tmp_path / ".companion" / "state.json").read_text())
        assert "WT-210" not in state.get("current_stories", {})
        assert "WT-211" in state.get("current_stories", {})

    def test_merge_clears_only_its_own_attempt_counter_key(
        self, tmp_path: Path
    ) -> None:
        """INFRA-282 (CER-095.3): merging one story clears only its own
        attempt-counter entry, leaving a still-building sibling's count
        intact (assertion 10)."""
        _init_git_repo(tmp_path)
        _write_story(tmp_path, "WT-220", primary_files=["a.py"])
        _write_story(tmp_path, "WT-221", primary_files=["b.py"])
        _run("write-attempt-count", "--story-id", "WT-220", "--count", "2", "--project-dir", str(tmp_path))
        _run("write-attempt-count", "--story-id", "WT-221", "--count", "1", "--project-dir", str(tmp_path))
        _create_worktree(tmp_path, "WT-220")
        _create_worktree(tmp_path, "WT-221")

        wt_a = tmp_path / ".pairmode-worktrees" / "WT-220"
        _commit_in(wt_a, "a.py", "done\n", "add a")
        result = _run(
            "merge-story-worktree",
            "--story-id", "WT-220",
            "--project-dir", str(tmp_path),
        )
        assert result.returncode == 0, result.stderr

        read_a = _run("read-attempt-count", "--story-id", "WT-220", "--project-dir", str(tmp_path))
        read_b = _run("read-attempt-count", "--story-id", "WT-221", "--project-dir", str(tmp_path))
        assert read_a.stdout.strip() == "0"
        assert read_b.stdout.strip() == "1"

    def test_discard_clears_only_its_own_key(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _write_story(tmp_path, "WT-212", primary_files=["a.py"])
        _write_story(tmp_path, "WT-213", primary_files=["b.py"])
        _create_worktree(tmp_path, "WT-212")
        _create_worktree(tmp_path, "WT-213")

        result = _run(
            "discard-story-worktree",
            "--story-id", "WT-212",
            "--project-dir", str(tmp_path),
        )
        assert result.returncode == 0, result.stderr

        state = json.loads((tmp_path / ".companion" / "state.json").read_text())
        assert "WT-212" not in state.get("current_stories", {})
        assert "WT-213" in state.get("current_stories", {})

    def test_cer_095_2_regression_sibling_scope_enforcement_survives_merge(
        self, tmp_path: Path
    ) -> None:
        """After merging WT-214, a write from WT-215's worktree to a path
        NOT in WT-215's allow-list must still be DENIED — never allowed via
        the pre-fix 'no active story — allowing' fall-through."""
        import sys as _sys

        scripts_dir = str(Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts")
        if scripts_dir not in _sys.path:
            _sys.path.insert(0, scripts_dir)
        import scope_guard  # noqa: E402  (import after sys.path setup, matches module convention)

        _init_git_repo(tmp_path)
        _write_story(tmp_path, "WT-214", primary_files=["a.py"])
        _write_story(tmp_path, "WT-215", primary_files=["b.py"])
        _create_worktree(tmp_path, "WT-214")
        _create_worktree(tmp_path, "WT-215")

        wt_a = tmp_path / ".pairmode-worktrees" / "WT-214"
        wt_b = tmp_path / ".pairmode-worktrees" / "WT-215"
        _commit_in(wt_a, "a.py", "done\n", "add a")
        merge_result = _run(
            "merge-story-worktree",
            "--story-id", "WT-214",
            "--project-dir", str(tmp_path),
        )
        assert merge_result.returncode == 0, merge_result.stderr

        # WT-215's builder is still writing — a.py is NOT in its allow-list.
        allowed, reason = scope_guard.check_path("a.py", wt_b)
        assert allowed is False
        assert reason != "no active story — allowing"
        assert "no active story — allowing" not in reason

        # And its own declared file remains allowed.
        allowed, reason = scope_guard.check_path("b.py", wt_b)
        assert allowed is True


class TestStoryWorktreeMergeRobustness:
    """CER-098: return-code checks, failed-land contract, merge lock
    (INFRA-286)."""

    # -- A1-A4: unit tests over _teardown_story_worktree / _residue_lines --

    def test_teardown_full_success_returns_empty_and_deletes_branch(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import flex_build  # noqa: E402

        calls: list[list[str]] = []

        def fake_run_git(args, cwd, timeout=120):
            calls.append(list(args))
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        monkeypatch.setattr(flex_build, "_run_git", fake_run_git)
        residue = flex_build._teardown_story_worktree(tmp_path, "WT-300")
        assert residue == []
        assert calls[0][:2] == ["worktree", "remove"]
        assert calls[1][:2] == ["branch", "-D"]

    def test_teardown_failed_worktree_remove_skips_branch_delete(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A2: a failed removal short-circuits the branch delete and
        reports exactly two residue entries."""
        import flex_build  # noqa: E402

        calls: list[list[str]] = []

        def fake_run_git(args, cwd, timeout=120):
            calls.append(list(args))
            if args[0] == "worktree":
                return subprocess.CompletedProcess(
                    args, 1, stdout="", stderr="fatal: worktree is dirty"
                )
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        monkeypatch.setattr(flex_build, "_run_git", fake_run_git)
        residue = flex_build._teardown_story_worktree(tmp_path, "WT-301")
        assert len(residue) == 2
        assert not any(c[0] == "branch" for c in calls)

    def test_teardown_failed_branch_delete_reported_alone(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A3: a failed branch delete after a successful removal reports
        exactly one entry, naming the branch."""
        import flex_build  # noqa: E402

        def fake_run_git(args, cwd, timeout=120):
            if args[0] == "worktree":
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            return subprocess.CompletedProcess(
                args, 1, stdout="", stderr="fatal: branch checked out"
            )

        monkeypatch.setattr(flex_build, "_run_git", fake_run_git)
        residue = flex_build._teardown_story_worktree(tmp_path, "WT-302")
        assert len(residue) == 1
        assert "pairmode/WT-302" in residue[0]

    def test_residue_lines_carry_git_text_and_repair_commands(self) -> None:
        """A4: residue rendering includes the failing call's own message and
        the exact repair commands."""
        import flex_build  # noqa: E402

        residue = ["worktree .pairmode-worktrees/WT-303 still exists: fatal: xyz"]
        lines = flex_build._residue_lines("WT-303", residue)
        assert lines[0] == residue[0]
        assert any(
            "git worktree remove --force .pairmode-worktrees/WT-303" in line
            for line in lines
        )
        assert any("git branch -D pairmode/WT-303" in line for line in lines)

    def test_residue_lines_empty_when_no_residue(self) -> None:
        import flex_build  # noqa: E402

        assert flex_build._residue_lines("WT-304", []) == []

    # -- A5-A7: end-to-end through the CLI --

    def test_clean_merge_reports_no_residue(self, tmp_path: Path) -> None:
        """A5/A7: a fully clean merge exits 0 and emits no residue text."""
        _init_git_repo(tmp_path)
        _create_worktree(tmp_path, "WT-305")
        wt = tmp_path / ".pairmode-worktrees" / "WT-305"
        _commit_in(wt, "feature.txt", "done\n", "add feature")
        result = _run(
            "merge-story-worktree",
            "--story-id", "WT-305",
            "--project-dir", str(tmp_path),
        )
        assert result.returncode == 0, result.stderr
        assert "merged pairmode/WT-305 into" in result.stdout
        assert "residue" not in result.stderr.lower()

    def test_discard_delegates_to_shared_teardown(self, tmp_path: Path) -> None:
        """A6: discard-story-worktree still exits 0 on a clean removal."""
        _init_git_repo(tmp_path)
        _create_worktree(tmp_path, "WT-306")
        result = _run(
            "discard-story-worktree",
            "--story-id", "WT-306",
            "--project-dir", str(tmp_path),
        )
        assert result.returncode == 0, result.stderr
        assert "discarded pairmode/WT-306" in result.stdout

    def test_merge_reports_residue_and_exits_1_after_clearing_state(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A5: state is cleared even when teardown leaves residue, and the
        residue is reported on stderr with exit 1."""
        import flex_build  # noqa: E402

        _init_git_repo(tmp_path)
        _write_story(tmp_path, "WT-307", primary_files=["feature.txt"])
        _create_worktree(tmp_path, "WT-307")
        wt = tmp_path / ".pairmode-worktrees" / "WT-307"
        _commit_in(wt, "feature.txt", "done\n", "add feature")

        original_run_git = flex_build._run_git

        def fake_run_git(args, cwd, timeout=120):
            if args and args[0] == "worktree" and args[1] == "remove":
                return subprocess.CompletedProcess(
                    args, 1, stdout="", stderr="fatal: worktree busy"
                )
            return original_run_git(args, cwd, timeout)

        monkeypatch.setattr(flex_build, "_run_git", fake_run_git)

        runner = CliRunner()
        result = runner.invoke(
            flex_build.flex_build,
            [
                "merge-story-worktree",
                "--story-id", "WT-307",
                "--project-dir", str(tmp_path),
            ],
        )
        assert result.exit_code == 1
        assert "merged pairmode/WT-307 into" in result.output
        assert "repair: git worktree remove --force" in result.output
        assert "repair: git branch -D pairmode/WT-307" in result.output
        # The clears still ran despite the residue (A5's load-bearing order).
        state = json.loads((tmp_path / ".companion" / "state.json").read_text())
        assert "WT-307" not in state.get("current_stories", {})
        assert not (
            tmp_path / "docs" / "phases" / "permissions" / "WT-307.json"
        ).exists()

    def test_discard_exits_before_clearing_state_on_residue(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A6: on discard, residue short-circuits BEFORE the stamps clear —
        the asymmetry with the merge path is deliberate."""
        import flex_build  # noqa: E402

        _init_git_repo(tmp_path)
        _write_story(tmp_path, "WT-308", primary_files=["scratch.txt"])
        _create_worktree(tmp_path, "WT-308")

        original_run_git = flex_build._run_git

        def fake_run_git(args, cwd, timeout=120):
            if args and args[0] == "worktree" and args[1] == "remove":
                return subprocess.CompletedProcess(
                    args, 1, stdout="", stderr="fatal: worktree busy"
                )
            return original_run_git(args, cwd, timeout)

        monkeypatch.setattr(flex_build, "_run_git", fake_run_git)

        runner = CliRunner()
        result = runner.invoke(
            flex_build.flex_build,
            [
                "discard-story-worktree",
                "--story-id", "WT-308",
                "--project-dir", str(tmp_path),
            ],
        )
        assert result.exit_code == 1
        assert "discarded" not in result.output
        state = json.loads((tmp_path / ".companion" / "state.json").read_text())
        assert "WT-308" in state.get("current_stories", {})
        assert (
            tmp_path / "docs" / "phases" / "permissions" / "WT-308.json"
        ).exists()

    # -- B3/B4: the lost-race path and the failed-land recovery contract --

    def test_b3_second_merge_succeeds_via_rebase_absorbing_first(
        self, tmp_path: Path
    ) -> None:
        """The normal, serialized-by-lock outcome: two sequential merges
        from the same tip both succeed, the second rebasing past the
        first's commit."""
        _init_git_repo(tmp_path)
        _create_worktree(tmp_path, "WT-201")
        _create_worktree(tmp_path, "WT-202")
        wt1 = tmp_path / ".pairmode-worktrees" / "WT-201"
        wt2 = tmp_path / ".pairmode-worktrees" / "WT-202"
        _commit_in(wt1, "one.txt", "one\n", "add one")
        _commit_in(wt2, "two.txt", "two\n", "add two")

        r1 = _run(
            "merge-story-worktree",
            "--story-id", "WT-201",
            "--project-dir", str(tmp_path),
        )
        assert r1.returncode == 0, r1.stderr
        r2 = _run(
            "merge-story-worktree",
            "--story-id", "WT-202",
            "--project-dir", str(tmp_path),
        )
        assert r2.returncode == 0, r2.stderr
        assert (tmp_path / "one.txt").exists()
        assert (tmp_path / "two.txt").exists()

    def test_b3_genuine_ff_only_failure_leaves_state_untouched_with_recovery(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A forced --ff-only failure: exit 1, no 'merged' text, a
        'recovery: ' block, and the worktree/branch/counter all survive
        untouched."""
        import flex_build  # noqa: E402

        _init_git_repo(tmp_path)
        _write_story(tmp_path, "WT-203", primary_files=["three.txt"])
        _create_worktree(tmp_path, "WT-203")
        wt = tmp_path / ".pairmode-worktrees" / "WT-203"
        _commit_in(wt, "three.txt", "three\n", "add three")
        _run(
            "write-attempt-count",
            "--story-id", "WT-203",
            "--count", "1",
            "--project-dir", str(tmp_path),
        )

        original_run_git = flex_build._run_git

        def fake_run_git(args, cwd, timeout=120):
            if args and args[0] == "merge" and "--ff-only" in args:
                return subprocess.CompletedProcess(
                    args,
                    1,
                    stdout="",
                    stderr="fatal: Not possible to fast-forward, aborting.",
                )
            return original_run_git(args, cwd, timeout)

        monkeypatch.setattr(flex_build, "_run_git", fake_run_git)

        runner = CliRunner()
        result = runner.invoke(
            flex_build.flex_build,
            [
                "merge-story-worktree",
                "--story-id", "WT-203",
                "--project-dir", str(tmp_path),
            ],
        )
        assert result.exit_code == 1
        assert "merged" not in result.output
        assert "recovery: " in result.output
        assert (tmp_path / ".pairmode-worktrees" / "WT-203").exists()
        branch = _git(
            tmp_path, "rev-parse", "--verify", "refs/heads/pairmode/WT-203"
        )
        assert branch.returncode == 0
        counter = json.loads(
            (tmp_path / ".companion" / "attempt_counter.json").read_text()
        )
        assert counter["stories"]["WT-203"] == 1

    def test_b4_rerun_after_failed_land_is_idempotent(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """B4: after a forced failure, removing the monkeypatch and re-
        running lands the story with no manual repair step."""
        import flex_build  # noqa: E402

        _init_git_repo(tmp_path)
        _create_worktree(tmp_path, "WT-204")
        wt = tmp_path / ".pairmode-worktrees" / "WT-204"
        _commit_in(wt, "four.txt", "four\n", "add four")

        original_run_git = flex_build._run_git
        fail_next = {"on": True}

        def fake_run_git(args, cwd, timeout=120):
            if fail_next["on"] and args and args[0] == "merge" and "--ff-only" in args:
                return subprocess.CompletedProcess(
                    args,
                    1,
                    stdout="",
                    stderr="fatal: Not possible to fast-forward, aborting.",
                )
            return original_run_git(args, cwd, timeout)

        monkeypatch.setattr(flex_build, "_run_git", fake_run_git)
        runner = CliRunner()
        first = runner.invoke(
            flex_build.flex_build,
            [
                "merge-story-worktree",
                "--story-id", "WT-204",
                "--project-dir", str(tmp_path),
            ],
        )
        assert first.exit_code == 1

        fail_next["on"] = False
        second = runner.invoke(
            flex_build.flex_build,
            [
                "merge-story-worktree",
                "--story-id", "WT-204",
                "--project-dir", str(tmp_path),
            ],
        )
        assert second.exit_code == 0, second.output
        assert (tmp_path / "four.txt").read_text() == "four\n"
        assert not (tmp_path / ".pairmode-worktrees" / "WT-204").exists()
        branch = _git(
            tmp_path, "rev-parse", "--verify", "refs/heads/pairmode/WT-204"
        )
        assert branch.returncode != 0

    # -- C1-C6: the merge lock --

    def test_c1_c2_lock_file_created_beside_companion_state(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)
        _create_worktree(tmp_path, "WT-401")
        wt = tmp_path / ".pairmode-worktrees" / "WT-401"
        _commit_in(wt, "feature.txt", "done\n", "add feature")
        result = _run(
            "merge-story-worktree",
            "--story-id", "WT-401",
            "--project-dir", str(tmp_path),
        )
        assert result.returncode == 0, result.stderr
        assert (tmp_path / ".companion" / "merge.lock").exists()

    def test_c4_non_acquisition_is_fail_open_and_warned(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import flex_build  # noqa: E402
        from contextlib import contextmanager

        _init_git_repo(tmp_path)
        _create_worktree(tmp_path, "WT-402")
        wt = tmp_path / ".pairmode-worktrees" / "WT-402"
        _commit_in(wt, "feature.txt", "done\n", "add feature")

        @contextmanager
        def fake_state_lock(path, timeout_seconds=None):
            yield False

        monkeypatch.setattr(flex_build, "state_lock", fake_state_lock)

        runner = CliRunner()
        result = runner.invoke(
            flex_build.flex_build,
            [
                "merge-story-worktree",
                "--story-id", "WT-402",
                "--project-dir", str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "merged pairmode/WT-402 into" in result.output
        assert "warning: merge lock not acquired" in result.output

    def test_c6_two_concurrent_merges_both_land_cleanly(
        self, tmp_path: Path
    ) -> None:
        """C6: two genuinely concurrent merge-story-worktree processes for
        two different stories both succeed and neither leaves a claim
        behind. Skipped where fcntl is unavailable."""
        pytest.importorskip("fcntl")

        _init_git_repo(tmp_path)
        _create_worktree(tmp_path, "WT-501")
        _create_worktree(tmp_path, "WT-502")
        wt1 = tmp_path / ".pairmode-worktrees" / "WT-501"
        wt2 = tmp_path / ".pairmode-worktrees" / "WT-502"
        _commit_in(wt1, "wt501.txt", "one\n", "add wt501")
        _commit_in(wt2, "wt502.txt", "two\n", "add wt502")

        env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT)}
        p1 = subprocess.Popen(
            [
                sys.executable, str(_SCRIPT),
                "merge-story-worktree",
                "--story-id", "WT-501",
                "--project-dir", str(tmp_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        p2 = subprocess.Popen(
            [
                sys.executable, str(_SCRIPT),
                "merge-story-worktree",
                "--story-id", "WT-502",
                "--project-dir", str(tmp_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        out1, err1 = p1.communicate(timeout=60)
        out2, err2 = p2.communicate(timeout=60)

        assert p1.returncode == 0, err1
        assert p2.returncode == 0, err2
        assert (tmp_path / "wt501.txt").exists()
        assert (tmp_path / "wt502.txt").exists()
        assert not (tmp_path / ".pairmode-worktrees" / "WT-501").exists()
        assert not (tmp_path / ".pairmode-worktrees" / "WT-502").exists()


def test_spec_writer_procedure_references_spec_preflight() -> None:
    """INFRA-191 fold location (RELEASE-008): the fat CLAUDE.build.md.j2 step was
    superseded by the thin harness; spec-preflight is wired as a
    `flex_build.py spec-preflight` subcommand and referenced from the
    spec-writer procedure skill instead."""
    procedure = (
        _REPO_ROOT
        / "skills"
        / "pairmode"
        / "skills"
        / "spec-writer"
        / "procedure.md"
    )
    text = procedure.read_text(encoding="utf-8")
    assert "spec-preflight" in text, (
        "spec-preflight not referenced in spec-writer procedure.md"
    )
    assert "flex_build.py" in text, (
        "flex_build.py invocation not referenced in spec-writer procedure.md"
    )
