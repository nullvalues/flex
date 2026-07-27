"""Tests for pairmode_register.py — register/unregister/list-projects commands."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from skills.pairmode.scripts.pairmode_register import (
    register,
    unregister,
    list_projects,
    audit_projects,
    _depth_guard,
    REGISTERED_PROJECTS_WRITERS,
    REGISTERED_PROJECTS_PROVENANCE_KEY,
    PROVENANCE_UNKNOWN,
    _provenance_for,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _companion_dir_arg(tmp_path: Path) -> str:
    """Return the string companion dir path to pass via --companion-dir."""
    return str(tmp_path / ".companion")


def _state(tmp_path: Path) -> dict:
    """Read state.json from the isolated companion dir."""
    state_path = tmp_path / ".companion" / "state.json"
    return json.loads(state_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Tests: register
# ---------------------------------------------------------------------------


def test_register_adds_path(tmp_path: Path) -> None:
    """register adds the resolved absolute path to registered_projects."""
    runner = CliRunner()
    project = str(tmp_path / "a" / "b" / "myproject")
    cdir = _companion_dir_arg(tmp_path)

    result = runner.invoke(register, ["--project-dir", project, "--companion-dir", cdir])

    assert result.exit_code == 0, result.output
    state = _state(tmp_path)
    assert str(Path(project).resolve()) in state["registered_projects"]


def test_register_idempotent(tmp_path: Path) -> None:
    """register called twice with the same path prints 'already registered' and does not duplicate."""
    runner = CliRunner()
    project = str(tmp_path / "a" / "b" / "myproject")
    cdir = _companion_dir_arg(tmp_path)

    result1 = runner.invoke(register, ["--project-dir", project, "--companion-dir", cdir])
    assert result1.exit_code == 0, result1.output

    result2 = runner.invoke(register, ["--project-dir", project, "--companion-dir", cdir])
    assert result2.exit_code == 0, result2.output
    assert "already registered" in result2.output

    state = _state(tmp_path)
    registered = state["registered_projects"]
    resolved_str = str(Path(project).resolve())
    assert registered.count(resolved_str) == 1, "path should appear exactly once"


# ---------------------------------------------------------------------------
# Tests: unregister
# ---------------------------------------------------------------------------


def test_unregister_removes_path(tmp_path: Path) -> None:
    """unregister removes a previously registered path."""
    runner = CliRunner()
    project = str(tmp_path / "a" / "b" / "myproject")
    cdir = _companion_dir_arg(tmp_path)

    runner.invoke(register, ["--project-dir", project, "--companion-dir", cdir])

    result = runner.invoke(unregister, ["--project-dir", project, "--companion-dir", cdir])
    assert result.exit_code == 0, result.output

    state = _state(tmp_path)
    assert str(Path(project).resolve()) not in state.get("registered_projects", [])


def test_unregister_noop_when_not_registered(tmp_path: Path) -> None:
    """unregister is a no-op when the path is not present — prints 'not registered'."""
    runner = CliRunner()
    project = str(tmp_path / "a" / "b" / "myproject")
    cdir = _companion_dir_arg(tmp_path)

    result = runner.invoke(unregister, ["--project-dir", project, "--companion-dir", cdir])
    assert result.exit_code == 0, result.output
    assert "not registered" in result.output


# ---------------------------------------------------------------------------
# Tests: list-projects
# ---------------------------------------------------------------------------


def test_list_projects_empty(tmp_path: Path) -> None:
    """list-projects prints 'No projects registered.' when state is absent or empty."""
    runner = CliRunner()
    cdir = _companion_dir_arg(tmp_path)

    result = runner.invoke(list_projects, ["--companion-dir", cdir])
    assert result.exit_code == 0, result.output
    assert "No projects registered." in result.output


def test_list_projects_shows_all(tmp_path: Path) -> None:
    """list-projects prints all registered paths, one per line."""
    runner = CliRunner()
    cdir = _companion_dir_arg(tmp_path)

    project_a = str(tmp_path / "a" / "b" / "proj_a")
    project_b = str(tmp_path / "x" / "y" / "proj_b")

    runner.invoke(register, ["--project-dir", project_a, "--companion-dir", cdir])
    runner.invoke(register, ["--project-dir", project_b, "--companion-dir", cdir])

    result = runner.invoke(list_projects, ["--companion-dir", cdir])
    assert result.exit_code == 0, result.output

    output_lines = result.output.strip().splitlines()
    assert str(Path(project_a).resolve()) in output_lines
    assert str(Path(project_b).resolve()) in output_lines
    assert len(output_lines) == 2


# ---------------------------------------------------------------------------
# Tests: atomic write / JSON validity
# ---------------------------------------------------------------------------


def test_state_is_valid_json_after_operations(tmp_path: Path) -> None:
    """state.json is valid JSON after a register + unregister sequence."""
    runner = CliRunner()
    cdir = _companion_dir_arg(tmp_path)

    project_a = str(tmp_path / "a" / "b" / "proj_a")
    project_b = str(tmp_path / "x" / "y" / "proj_b")

    runner.invoke(register, ["--project-dir", project_a, "--companion-dir", cdir])
    runner.invoke(register, ["--project-dir", project_b, "--companion-dir", cdir])
    runner.invoke(unregister, ["--project-dir", project_a, "--companion-dir", cdir])

    state = _state(tmp_path)  # raises if not valid JSON
    assert isinstance(state, dict)
    remaining = state.get("registered_projects", [])
    assert str(Path(project_b).resolve()) in remaining
    assert str(Path(project_a).resolve()) not in remaining


# ---------------------------------------------------------------------------
# Tests: _depth_guard
# ---------------------------------------------------------------------------


def test_depth_guard_rejects_shallow_path(tmp_path: Path) -> None:
    """register exits with an error when the resolved project-dir has fewer than 3 parts."""
    runner = CliRunner()
    cdir = _companion_dir_arg(tmp_path)

    # /tmp has exactly 2 parts on Linux: ('/', 'tmp')
    result = runner.invoke(register, ["--project-dir", "/tmp", "--companion-dir", cdir])
    assert result.exit_code != 0
    assert "suspicious" in result.output or "suspicious" in (result.stderr or "")


def test_depth_guard_unit() -> None:
    """_depth_guard returns False for shallow paths and True for deep ones."""
    assert _depth_guard(Path("/tmp")) is False          # 2 parts: ('/', 'tmp')
    assert _depth_guard(Path("/a")) is False            # 2 parts: ('/', 'a')
    assert _depth_guard(Path("/a/b/c")) is True         # 4 parts
    assert _depth_guard(Path("/home/user/project")) is True  # 4 parts


# ---------------------------------------------------------------------------
# A1/A2 — CER-058 single-writer invariant
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]

_ASSIGNMENT_PATTERNS = (
    re.compile(r'''\[\s*["']registered_projects["']\s*\]\s*='''),
    re.compile(r'''["']registered_projects["']\s*:\s*'''),
)


def _iter_py_files(*roots: str) -> list[Path]:
    files: list[Path] = []
    for root_name in roots:
        root = _REPO_ROOT / root_name
        if not root.exists():
            continue
        for p in root.rglob("*.py"):
            parts = p.relative_to(_REPO_ROOT).parts
            if "tests" in parts or "__pycache__" in parts:
                continue
            files.append(p)
    return files


def _file_assigns_registered_projects(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    return any(pattern.search(text) for pattern in _ASSIGNMENT_PATTERNS)


def test_registered_projects_has_a_single_writer() -> None:
    """CER-058: exactly one in-repo file may assign registered_projects.

    A new writer either bypasses fleet-discovery accuracy at the pre-fold
    gate (blast-radius sizing depends on registered_projects reflecting only
    deliberate registrations) or must be routed through
    pairmode_register.register/unregister — the two legitimate resolutions.
    If this test fails, either (1) route the new write through `register`, or
    (2) if a bypass is truly required, add the offending file's repo-relative
    path to REGISTERED_PROJECTS_WRITERS with a comment recording why.
    """
    offenders = set()
    for path in _iter_py_files("skills", "hooks"):
        if _file_assigns_registered_projects(path):
            offenders.add(str(path.relative_to(_REPO_ROOT)))

    assert offenders == set(REGISTERED_PROJECTS_WRITERS), (
        f"registered_projects must have exactly one writer "
        f"({set(REGISTERED_PROJECTS_WRITERS)}), found: {offenders}. "
        "This invariant protects fleet-discovery accuracy at the pre-fold "
        "gate (CER-058). Route the new write through "
        "pairmode_register.register/unregister, or add the file to "
        "REGISTERED_PROJECTS_WRITERS with a recorded reason."
    )


def test_single_writer_matcher_does_not_flag_readers() -> None:
    """The assignment regex must not trip on read-only references."""
    for rel in (
        "skills/pairmode/scripts/fleet_discovery.py",
        "skills/pairmode/scripts/pairmode_status.py",
        "skills/pairmode/scripts/lesson_review.py",
    ):
        path = _REPO_ROOT / rel
        assert path.exists(), f"expected {rel} to exist"
        assert not _file_assigns_registered_projects(path), (
            f"{rel} is read-only w.r.t. registered_projects but matched the "
            "single-writer assignment regex"
        )


# ---------------------------------------------------------------------------
# A3/A4/A5 — provenance sidecar
# ---------------------------------------------------------------------------


def test_register_records_provenance_default_source(tmp_path: Path) -> None:
    """register writes a provenance sidecar entry with source 'cli' by default."""
    runner = CliRunner()
    project = str(tmp_path / "a" / "b" / "myproject")
    cdir = _companion_dir_arg(tmp_path)

    result = runner.invoke(register, ["--project-dir", project, "--companion-dir", cdir])
    assert result.exit_code == 0, result.output

    state = _state(tmp_path)
    resolved_str = str(Path(project).resolve())
    sidecar = state[REGISTERED_PROJECTS_PROVENANCE_KEY]
    assert sidecar[resolved_str]["source"] == "cli"
    assert sidecar[resolved_str]["registered_at"]  # non-empty iso8601 string

    # registered_projects itself is unaffected in shape (A4)
    assert isinstance(state["registered_projects"], list)
    assert resolved_str in state["registered_projects"]


def test_register_records_provenance_custom_source(tmp_path: Path) -> None:
    """register --source records the caller-supplied source label."""
    runner = CliRunner()
    project = str(tmp_path / "a" / "b" / "myproject")
    cdir = _companion_dir_arg(tmp_path)

    result = runner.invoke(
        register, ["--project-dir", project, "--companion-dir", cdir, "--source", "bootstrap"]
    )
    assert result.exit_code == 0, result.output

    state = _state(tmp_path)
    resolved_str = str(Path(project).resolve())
    assert state[REGISTERED_PROJECTS_PROVENANCE_KEY][resolved_str]["source"] == "bootstrap"


def test_unregister_removes_provenance_entry(tmp_path: Path) -> None:
    """unregister deletes the matching provenance sidecar entry."""
    runner = CliRunner()
    project = str(tmp_path / "a" / "b" / "myproject")
    cdir = _companion_dir_arg(tmp_path)

    runner.invoke(register, ["--project-dir", project, "--companion-dir", cdir])
    result = runner.invoke(unregister, ["--project-dir", project, "--companion-dir", cdir])
    assert result.exit_code == 0, result.output

    state = _state(tmp_path)
    resolved_str = str(Path(project).resolve())
    assert resolved_str not in state.get(REGISTERED_PROJECTS_PROVENANCE_KEY, {})


def test_register_tolerates_missing_sidecar(tmp_path: Path) -> None:
    """register works fine when the sidecar key is absent (pre-INFRA-270 state)."""
    cdir = tmp_path / ".companion"
    cdir.mkdir()
    (cdir / "state.json").write_text(
        json.dumps({"registered_projects": ["/mnt/work/coherra"]}), encoding="utf-8"
    )

    runner = CliRunner()
    project = str(tmp_path / "a" / "b" / "newproj")
    result = runner.invoke(
        register, ["--project-dir", project, "--companion-dir", str(cdir)]
    )
    assert result.exit_code == 0, result.output

    state = _state(tmp_path)
    # Pre-existing entry survives verbatim (A4).
    assert "/mnt/work/coherra" in state["registered_projects"]
    assert str(Path(project).resolve()) in state["registered_projects"]


@pytest.mark.parametrize("bad_sidecar", [None, [], "not-a-dict", 42])
def test_register_tolerates_malformed_sidecar(tmp_path: Path, bad_sidecar) -> None:
    """register degrades a malformed sidecar value to {} rather than raising."""
    cdir = tmp_path / ".companion"
    cdir.mkdir()
    (cdir / "state.json").write_text(
        json.dumps({"registered_projects": [], REGISTERED_PROJECTS_PROVENANCE_KEY: bad_sidecar}),
        encoding="utf-8",
    )

    runner = CliRunner()
    project = str(tmp_path / "a" / "b" / "newproj")
    result = runner.invoke(
        register, ["--project-dir", project, "--companion-dir", str(cdir)], catch_exceptions=False
    )
    assert result.exit_code == 0, result.output

    state = _state(tmp_path)
    resolved_str = str(Path(project).resolve())
    assert state[REGISTERED_PROJECTS_PROVENANCE_KEY][resolved_str]["source"] == "cli"


def test_provenance_for_unknown_when_no_sidecar_record() -> None:
    """_provenance_for returns the unknown sentinel for an unrecorded path."""
    state = {"registered_projects": ["/mnt/work/coherra"]}
    prov = _provenance_for(state, "/mnt/work/coherra")
    assert prov == {"source": PROVENANCE_UNKNOWN, "registered_at": None}


def test_provenance_for_returns_recorded_entry() -> None:
    """_provenance_for returns the exact recorded entry when present."""
    state = {
        REGISTERED_PROJECTS_PROVENANCE_KEY: {
            "/mnt/work/coherra": {"source": "cli", "registered_at": "2026-01-01T00:00:00+00:00"}
        }
    }
    prov = _provenance_for(state, "/mnt/work/coherra")
    assert prov == {"source": "cli", "registered_at": "2026-01-01T00:00:00+00:00"}


def test_provenance_unknown_constant() -> None:
    assert PROVENANCE_UNKNOWN == "unknown"


def test_provenance_key_constant() -> None:
    assert REGISTERED_PROJECTS_PROVENANCE_KEY == "registered_projects_provenance"


# ---------------------------------------------------------------------------
# A6/A7 — audit-projects command
# ---------------------------------------------------------------------------


def test_audit_projects_reports_unknown_for_preexisting_entries(tmp_path: Path) -> None:
    """A pre-INFRA-270 entry (no sidecar record) audits as unknown."""
    cdir = tmp_path / ".companion"
    cdir.mkdir()
    (cdir / "state.json").write_text(
        json.dumps({"registered_projects": ["/mnt/work/coherra"]}), encoding="utf-8"
    )

    runner = CliRunner()
    result = runner.invoke(audit_projects, ["--companion-dir", str(cdir)])
    assert result.exit_code == 0, result.output
    assert "/mnt/work/coherra" in result.output
    assert "source: unknown" in result.output
    assert "1 unknown (pre-INFRA-270)" in result.output


def test_audit_projects_reports_recorded_provenance(tmp_path: Path) -> None:
    runner = CliRunner()
    cdir = _companion_dir_arg(tmp_path)
    project = str(tmp_path / "a" / "b" / "myproject")

    runner.invoke(register, ["--project-dir", project, "--companion-dir", cdir])
    result = runner.invoke(audit_projects, ["--companion-dir", cdir])

    assert result.exit_code == 0, result.output
    assert "source: cli" in result.output
    assert "0 unknown (pre-INFRA-270)" in result.output


def test_audit_projects_is_read_only(tmp_path: Path) -> None:
    """audit-projects never writes state.json — bytes are unchanged across the call."""
    cdir = tmp_path / ".companion"
    cdir.mkdir()
    state_path = cdir / "state.json"
    state_path.write_text(
        json.dumps({"registered_projects": ["/mnt/work/coherra"]}), encoding="utf-8"
    )
    before = state_path.read_bytes()

    runner = CliRunner()
    result = runner.invoke(audit_projects, ["--companion-dir", str(cdir)])
    assert result.exit_code == 0, result.output

    after = state_path.read_bytes()
    assert before == after


def test_audit_projects_warns_on_missing_path(tmp_path: Path) -> None:
    cdir = tmp_path / ".companion"
    cdir.mkdir()
    ghost = str(tmp_path / "does" / "not" / "exist")
    (cdir / "state.json").write_text(
        json.dumps({"registered_projects": [ghost]}), encoding="utf-8"
    )

    runner = CliRunner()
    result = runner.invoke(audit_projects, ["--companion-dir", str(cdir)])
    assert result.exit_code == 0, result.output
    assert "WARN:" in result.output


def test_audit_projects_json_output(tmp_path: Path) -> None:
    cdir = tmp_path / ".companion"
    cdir.mkdir()
    (cdir / "state.json").write_text(
        json.dumps({"registered_projects": ["/mnt/work/coherra"]}), encoding="utf-8"
    )

    runner = CliRunner()
    result = runner.invoke(audit_projects, ["--companion-dir", str(cdir), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["unknown_count"] == 1
    assert payload["registered"][0]["path"] == "/mnt/work/coherra"
    assert payload["registered"][0]["source"] == PROVENANCE_UNKNOWN
