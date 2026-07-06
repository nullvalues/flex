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
# BUILD-043: Reviewer FAIL reason capture via --notes
# ---------------------------------------------------------------------------

_REVIEWER_TEMPLATE = (
    _REPO_ROOT / "skills" / "pairmode" / "templates" / "agents" / "reviewer.md.j2"
)
_BUILD_TEMPLATE = (
    _REPO_ROOT / "skills" / "pairmode" / "templates" / "CLAUDE.build.md.j2"
)
_LIVE_REVIEWER = _REPO_ROOT / ".claude" / "agents" / "reviewer.md"


def test_reviewer_template_contains_fail_cause_instruction() -> None:
    """reviewer.md.j2 must emit FAIL-CAUSE before git checkout on FAIL."""
    text = _REVIEWER_TEMPLATE.read_text(encoding="utf-8")
    lines = text.splitlines()

    assert "Before reverting, emit one line" in text, (
        "reviewer.md.j2 missing 'Before reverting, emit one line' instruction"
    )
    assert "FAIL-CAUSE:" in text, "reviewer.md.j2 missing FAIL-CAUSE: marker"

    # FAIL-CAUSE: must appear before git checkout
    fail_cause_line = next(
        (i for i, ln in enumerate(lines) if "FAIL-CAUSE:" in ln), None
    )
    git_checkout_line = next(
        (i for i, ln in enumerate(lines) if "git checkout" in ln), None
    )
    assert fail_cause_line is not None, "FAIL-CAUSE: not found in reviewer.md.j2"
    assert git_checkout_line is not None, "git checkout not found in reviewer.md.j2"
    assert fail_cause_line < git_checkout_line, (
        f"FAIL-CAUSE: (line {fail_cause_line}) must appear before "
        f"git checkout (line {git_checkout_line}) in reviewer.md.j2"
    )


def test_build_template_passes_notes_on_reviewer_fail() -> None:
    """CLAUDE.build.md.j2 must pass --notes near --outcome FAIL in record_attempt."""
    text = _BUILD_TEMPLATE.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Find all lines containing --outcome FAIL
    fail_lines = [i for i, ln in enumerate(lines) if "--outcome FAIL" in ln]
    assert fail_lines, "No '--outcome FAIL' found in CLAUDE.build.md.j2"

    # For at least one --outcome FAIL occurrence, --notes must appear within 30 lines
    found_notes_near_fail = False
    for fail_idx in fail_lines:
        window_start = max(0, fail_idx - 30)
        window_end = min(len(lines), fail_idx + 30)
        window = "\n".join(lines[window_start:window_end])
        if "--notes" in window:
            found_notes_near_fail = True
            break

    assert found_notes_near_fail, (
        "--notes flag not found within 30 lines of '--outcome FAIL' in CLAUDE.build.md.j2"
    )


def test_live_reviewer_contains_fail_cause_instruction() -> None:
    """The live .claude/agents/reviewer.md must contain the FAIL-CAUSE instruction."""
    text = _LIVE_REVIEWER.read_text(encoding="utf-8")
    assert "Before reverting, emit one line" in text, (
        ".claude/agents/reviewer.md missing 'Before reverting, emit one line' instruction"
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
