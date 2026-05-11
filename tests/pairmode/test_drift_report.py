"""Tests for pairmode_drift_report.py.

Fixture projects are created in tmp_path with known MISSING/EXTRA/DRIFT sections.
Tests assert correct classification and --convergent behaviour.

Note: INTENTIONAL classification (via .pairmode-overrides) is tested in INFRA-064.
Here we only verify the stub/hook exists and returns an empty set when the file
is absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skills.pairmode.scripts.pairmode_drift_report import (
    _depth_guard,
    _find_convergence_candidates,
    _load_overrides,
    _normalise,
    _safe_project_dir,
    _split_sections,
    drift_report,
    DriftItem,
    ProjectDriftResult,
)
from skills.pairmode.scripts import pairmode_drift_report as _mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEMPLATES_DIR = _mod.TEMPLATES_DIR
AGENTS_TEMPLATES_DIR = _mod.AGENTS_TEMPLATES_DIR


def _render_template(template_rel: str, context: dict | None = None) -> str:
    """Render a template with an empty (or provided) context."""
    import jinja2

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        undefined=jinja2.Undefined,
        keep_trailing_newline=True,
    )
    return env.get_template(template_rel).render(**(context or {}))


def _write_state(project_dir: Path, version: str | None = "0.1.0") -> None:
    companion = project_dir / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    state: dict = {}
    if version is not None:
        state["pairmode_version"] = version
    (companion / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _make_project(
    tmp_path: Path,
    name: str,
    *,
    claude_build_content: str | None = None,
    agent_contents: dict[str, str] | None = None,
) -> Path:
    """Create a minimal project fixture in *tmp_path/<name>/*.

    - If *claude_build_content* is None, CLAUDE.build.md is not created.
    - *agent_contents* maps agent filename (e.g. "builder.md") → file content.
      If a file maps to None, the file is not created.
    """
    project_dir = tmp_path / name
    project_dir.mkdir()
    _write_state(project_dir)

    if claude_build_content is not None:
        (project_dir / "CLAUDE.build.md").write_text(claude_build_content, encoding="utf-8")

    if agent_contents:
        agents_dir = project_dir / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        for filename, content in agent_contents.items():
            if content is not None:
                (agents_dir / filename).write_text(content, encoding="utf-8")

    return project_dir


def _canonical_build_md(project_name: str = "testproj") -> str:
    """Return the canonical CLAUDE.build.md rendered with a given project name.

    The project_name must match the directory name used in _make_project so that
    the drift_report's _load_project_context (which falls back to project_dir.name)
    renders the same content as the file on disk.
    """
    return _render_template(
        "CLAUDE.build.md.j2",
        {
            "project_name": project_name,
            "build_command": "",
            "test_command": "",
            "migration_command": "",
        },
    )


def _canonical_agent(agent_stem: str, project_name: str = "testproj") -> str:
    """Return the canonical agent file rendered with a given project name.

    The project_name must match the directory name used in _make_project.
    """
    return _render_template(
        f"agents/{agent_stem}.md.j2",
        {"project_name": project_name, "protected_paths": []},
    )


# ---------------------------------------------------------------------------
# _depth_guard
# ---------------------------------------------------------------------------


def test_depth_guard_rejects_shallow_path(tmp_path: Path) -> None:
    """Paths with fewer than 3 parts must raise ValueError."""
    # /tmp itself has 2 parts on most systems — guard against root-adjacent dirs
    shallow = Path("/tmp")
    if len(shallow.resolve().parts) < 3:
        with pytest.raises(ValueError, match="too shallow"):
            _depth_guard(shallow)
    else:
        # If /tmp resolves to 3+ parts, use / which always has 1 part
        with pytest.raises(ValueError, match="too shallow"):
            _depth_guard(Path("/"))


def test_depth_guard_accepts_deep_path(tmp_path: Path) -> None:
    """Paths with 3+ components must resolve and return successfully."""
    resolved = _depth_guard(tmp_path)
    assert resolved == tmp_path.resolve()


# ---------------------------------------------------------------------------
# _safe_project_dir
# ---------------------------------------------------------------------------


def test_safe_project_dir_rejects_missing_dir(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist"
    result = _safe_project_dir(missing)
    assert result is None


def test_safe_project_dir_accepts_valid_dir(tmp_path: Path) -> None:
    result = _safe_project_dir(tmp_path)
    assert result == tmp_path.resolve()


# ---------------------------------------------------------------------------
# _split_sections
# ---------------------------------------------------------------------------


def test_split_sections_basic() -> None:
    text = (
        "# Title\n\npreamble text\n\n"
        "## Section A\n\nbody A\n\n"
        "## Section B\n\nbody B\n"
    )
    sections = _split_sections(text)
    keys = list(sections.keys())
    # Should have preamble + two sections
    assert any("section a" in k for k in keys)
    assert any("section b" in k for k in keys)


def test_split_sections_separator() -> None:
    text = "## A\n\nbody A\n\n---\n\n## B\n\nbody B\n"
    sections = _split_sections(text)
    # Separator keys should not be surfaced as meaningful sections
    from skills.pairmode.scripts.pairmode_drift_report import _is_separator_key
    non_separator_keys = [k for k in sections if not _is_separator_key(k)]
    assert len(non_separator_keys) == 2


# ---------------------------------------------------------------------------
# _load_overrides
# ---------------------------------------------------------------------------


def test_load_overrides_missing_file(tmp_path: Path) -> None:
    """When .pairmode-overrides is absent, returns an empty set."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    result = _load_overrides(project_dir)
    assert result == set()


def test_load_overrides_parses_entries(tmp_path: Path) -> None:
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    overrides_file = project_dir / ".pairmode-overrides"
    overrides_file.write_text(
        "# comment\n"
        "\n"
        "CLAUDE.build.md: ## session modes\n"
        ".claude/agents/builder.md: ## before writing anything\n",
        encoding="utf-8",
    )
    result = _load_overrides(project_dir)
    assert ("CLAUDE.build.md", "## session modes") in result
    assert (".claude/agents/builder.md", "## before writing anything") in result


def test_load_overrides_ignores_lines_without_colon(tmp_path: Path) -> None:
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    overrides_file = project_dir / ".pairmode-overrides"
    overrides_file.write_text("no-colon-line\n", encoding="utf-8")
    result = _load_overrides(project_dir)
    assert result == set()


# ---------------------------------------------------------------------------
# Classification: MISSING
# ---------------------------------------------------------------------------


def test_missing_entire_file(tmp_path: Path) -> None:
    """When CLAUDE.build.md is absent, all canonical sections are MISSING."""
    project_dir = _make_project(tmp_path, "missing_build")
    # No CLAUDE.build.md created, no agents dir

    result = drift_report([project_dir], convergent=False)
    project_data = result["projects"][0]

    assert len(project_data["missing"]) > 0
    missing_files = {item["file"] for item in project_data["missing"]}
    assert "CLAUDE.build.md" in missing_files


def test_missing_section_in_existing_file(tmp_path: Path) -> None:
    """A file that exists but is missing a canonical section produces a MISSING item."""
    # Create CLAUDE.build.md without the "## Session modes" section
    canonical = _canonical_build_md("testproj")
    # Remove the "## Session modes" block
    import re
    truncated = re.sub(
        r"## Session modes\n.*?(?=^##|\Z)",
        "",
        canonical,
        flags=re.MULTILINE | re.DOTALL,
    )

    project_dir = _make_project(tmp_path, "missing_section", claude_build_content=truncated)
    result = drift_report([project_dir])
    project_data = result["projects"][0]

    missing_sections = {
        (item["file"], item["section"]) for item in project_data["missing"]
    }
    # "## session modes" (normalised) should appear as MISSING
    assert any(
        item["file"] == "CLAUDE.build.md" and "session modes" in item["section"]
        for item in project_data["missing"]
    ), f"Expected session modes MISSING; got: {project_data['missing']}"


# ---------------------------------------------------------------------------
# Classification: EXTRA
# ---------------------------------------------------------------------------


def test_extra_section_in_claude_build(tmp_path: Path) -> None:
    """A section present in the project file but not in the canonical template is EXTRA."""
    canonical = _canonical_build_md("testproj")
    extra_content = canonical + "\n\n## Project-custom section\n\nSome custom content here.\n"

    project_dir = _make_project(tmp_path, "extra_section", claude_build_content=extra_content)
    result = drift_report([project_dir])
    project_data = result["projects"][0]

    extra_sections = {item["section"] for item in project_data["extra"]}
    assert any(
        "project-custom section" in s for s in extra_sections
    ), f"Expected project-custom section as EXTRA; got: {project_data['extra']}"


def test_extra_agent_file_without_template(tmp_path: Path) -> None:
    """An agent file with no matching canonical template is classified as EXTRA."""
    canonical_build = _canonical_build_md("testproj")
    agent_content = "---\nname: custom-agent\n---\n\n## Custom section\n\nContent.\n"

    project_dir = _make_project(
        tmp_path,
        "extra_agent",
        claude_build_content=canonical_build,
        agent_contents={"custom-agent.md": agent_content},
    )
    result = drift_report([project_dir])
    project_data = result["projects"][0]

    extra_files = {item["file"] for item in project_data["extra"]}
    assert ".claude/agents/custom-agent.md" in extra_files


# ---------------------------------------------------------------------------
# Classification: DRIFT
# ---------------------------------------------------------------------------


def test_drift_detected_in_claude_build(tmp_path: Path) -> None:
    """When a section's body differs from the canonical template, it is DRIFT."""
    canonical = _canonical_build_md("testproj")
    # Replace a known section body with different content
    import re
    drifted = re.sub(
        r"(## Session modes\n\n)(.*?)(\n\n---|\n\n##)",
        r"\g<1>CUSTOM SESSION MODES CONTENT\g<3>",
        canonical,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )

    project_dir = _make_project(tmp_path, "drift_build", claude_build_content=drifted)
    result = drift_report([project_dir])
    project_data = result["projects"][0]

    drift_sections = {item["section"] for item in project_data["drift"]}
    assert any(
        "session modes" in s for s in drift_sections
    ), f"Expected session modes DRIFT; got: {project_data['drift']}"


def test_no_drift_for_identical_file(tmp_path: Path) -> None:
    """When the project file exactly matches the canonical template, no DRIFT is produced.

    The directory name IS the project_name used in the fallback context, so we render
    the canonical template with the same name as the directory to avoid false DRIFT.
    """
    dir_name = "clean_build"
    canonical = _canonical_build_md(dir_name)
    project_dir = _make_project(tmp_path, dir_name, claude_build_content=canonical)
    result = drift_report([project_dir])
    project_data = result["projects"][0]

    # CLAUDE.build.md should have no DRIFT items
    drift_for_build = [
        item for item in project_data["drift"] if item["file"] == "CLAUDE.build.md"
    ]
    assert drift_for_build == [], f"Expected no drift for identical file; got: {drift_for_build}"


# ---------------------------------------------------------------------------
# Classification: DRIFT in agent files
# ---------------------------------------------------------------------------


def test_drift_detected_in_agent_file(tmp_path: Path) -> None:
    """When an agent file body differs from the canonical template, it is DRIFT."""
    canonical_build = _canonical_build_md("testproj")
    canonical_builder = _canonical_agent("builder", "testproj")

    # Modify the builder agent's "## Before writing anything" section
    import re
    drifted_builder = re.sub(
        r"(## Before writing anything\n\n)(.*?)(\n\n##|\Z)",
        r"\g<1>DIFFERENT CONTENT HERE.\g<3>",
        canonical_builder,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )

    project_dir = _make_project(
        tmp_path,
        "agent_drift",
        claude_build_content=canonical_build,
        agent_contents={"builder.md": drifted_builder},
    )
    result = drift_report([project_dir])
    project_data = result["projects"][0]

    drift_items = [
        item for item in project_data["drift"]
        if item["file"] == ".claude/agents/builder.md"
    ]
    assert len(drift_items) > 0, (
        f"Expected drift in builder.md; drift={project_data['drift']}"
    )


# ---------------------------------------------------------------------------
# Convergence detection
# ---------------------------------------------------------------------------


def test_convergent_identifies_shared_drift(tmp_path: Path) -> None:
    """Drift appearing identically in 2+ projects must appear as a convergence candidate."""
    canonical = _canonical_build_md("testproj")

    # Replace the "## Session modes" section with the same custom content in both projects
    import re
    drifted = re.sub(
        r"(## Session modes\n\n)(.*?)(\n\n---|\n\n##)",
        r"\g<1>IDENTICAL CUSTOM CONTENT\g<3>",
        canonical,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )

    proj_a = _make_project(tmp_path, "convergent_a", claude_build_content=drifted)
    proj_b = _make_project(tmp_path, "convergent_b", claude_build_content=drifted)

    result = drift_report([proj_a, proj_b], convergent=True)

    candidates = result["convergence_candidates"]
    assert len(candidates) > 0, "Expected at least one convergence candidate"

    # The shared drift in "## session modes" should surface
    candidate_keys = {(c["file"], c["section"]) for c in candidates}
    assert any(
        f == "CLAUDE.build.md" and "session modes" in s
        for f, s in candidate_keys
    ), f"Expected session modes as convergence candidate; got: {candidates}"

    # Count must be 2
    for c in candidates:
        if c["file"] == "CLAUDE.build.md" and "session modes" in c["section"]:
            assert c["count"] == 2
            assert set(c["projects"]) == {"convergent_a", "convergent_b"}
            break


def test_convergent_excludes_unique_drift(tmp_path: Path) -> None:
    """Drift unique to one project must NOT appear as a convergence candidate.

    Uses directory-name-matched canonical content to avoid spurious preamble drift.
    """
    # Each project's canonical content uses its own directory name as project_name
    # so the drift-report re-render matches the on-disk file (no spurious preamble drift).
    canonical_a = _canonical_build_md("unique_a")
    canonical_b = _canonical_build_md("unique_b")

    # Project A: drift in Session modes (unique content)
    import re
    drifted_a = re.sub(
        r"(## Session modes\n\n)(.*?)(\n\n---|\n\n##)",
        r"\g<1>UNIQUE CONTENT FOR A ONLY\g<3>",
        canonical_a,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )

    # Project B: no intentional drift (canonical content)
    proj_a = _make_project(tmp_path, "unique_a", claude_build_content=drifted_a)
    proj_b = _make_project(tmp_path, "unique_b", claude_build_content=canonical_b)

    result = drift_report([proj_a, proj_b], convergent=True)
    candidates = result["convergence_candidates"]

    # No candidate should have count >= 2 (unique drift does not converge)
    assert all(
        c["count"] < 2 for c in candidates
    ), f"Expected no convergence for unique drift; got: {candidates}"


def test_convergent_false_returns_empty_candidates(tmp_path: Path) -> None:
    """When --convergent is False, convergence_candidates must be empty."""
    canonical = _canonical_build_md("testproj")

    import re
    drifted = re.sub(
        r"(## Session modes\n\n)(.*?)(\n\n---|\n\n##)",
        r"\g<1>SHARED DRIFT CONTENT\g<3>",
        canonical,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )

    proj_a = _make_project(tmp_path, "noc_a", claude_build_content=drifted)
    proj_b = _make_project(tmp_path, "noc_b", claude_build_content=drifted)

    result = drift_report([proj_a, proj_b], convergent=False)
    assert result["convergence_candidates"] == []


# ---------------------------------------------------------------------------
# Output format: JSON
# ---------------------------------------------------------------------------


def test_json_output_structure(tmp_path: Path) -> None:
    """JSON output must have 'projects' and 'convergence_candidates' keys."""
    project_dir = _make_project(tmp_path, "json_struct")
    result = drift_report([project_dir], convergent=True, output_format="json")

    assert "projects" in result
    assert "convergence_candidates" in result
    assert isinstance(result["projects"], list)
    assert isinstance(result["convergence_candidates"], list)


def test_json_project_entry_has_required_keys(tmp_path: Path) -> None:
    """Each project entry in JSON output must have missing/extra/drift/intentional keys."""
    canonical = _canonical_build_md("testproj")
    project_dir = _make_project(tmp_path, "json_keys", claude_build_content=canonical)
    result = drift_report([project_dir], output_format="json")

    assert len(result["projects"]) == 1
    entry = result["projects"][0]
    for key in ("project", "project_dir", "missing", "extra", "drift", "intentional"):
        assert key in entry, f"Missing key '{key}' in project entry"


# ---------------------------------------------------------------------------
# Output format: Text
# ---------------------------------------------------------------------------


def test_text_output_contains_project_name(tmp_path: Path) -> None:
    """Text output must include the project name."""
    from click.testing import CliRunner
    from skills.pairmode.scripts.pairmode_drift_report import main

    canonical = _canonical_build_md("textproj")
    project_dir = _make_project(tmp_path, "textproj", claude_build_content=canonical)

    runner = CliRunner()
    invoke_result = runner.invoke(
        main, ["--projects", str(project_dir), "--output", "text"]
    )

    assert invoke_result.exit_code == 0, f"CLI failed: {invoke_result.output}"
    assert "textproj" in invoke_result.output


def test_text_output_convergence_section(tmp_path: Path) -> None:
    """Text output with --convergent must include a CONVERGENCE CANDIDATES section."""
    from click.testing import CliRunner
    from skills.pairmode.scripts.pairmode_drift_report import main

    canonical = _canonical_build_md("testproj")

    import re
    drifted = re.sub(
        r"(## Session modes\n\n)(.*?)(\n\n---|\n\n##)",
        r"\g<1>SHARED FOR CONVERGENCE\g<3>",
        canonical,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )

    proj_a = _make_project(tmp_path, "text_conv_a", claude_build_content=drifted)
    proj_b = _make_project(tmp_path, "text_conv_b", claude_build_content=drifted)

    runner = CliRunner()
    invoke_result = runner.invoke(
        main,
        [
            "--projects", str(proj_a),
            "--projects", str(proj_b),
            "--convergent",
            "--output", "text",
        ],
    )

    assert invoke_result.exit_code == 0, f"CLI failed: {invoke_result.output}"
    assert "CONVERGENCE" in invoke_result.output


# ---------------------------------------------------------------------------
# _find_convergence_candidates (unit)
# ---------------------------------------------------------------------------


def test_find_convergence_candidates_two_projects() -> None:
    """_find_convergence_candidates groups identical DRIFT items from 2+ projects."""
    item_a = DriftItem(
        file="CLAUDE.build.md",
        section="## session modes",
        classification="DRIFT",
        project_body="custom content",
        canonical_body="original content",
    )
    item_b = DriftItem(
        file="CLAUDE.build.md",
        section="## session modes",
        classification="DRIFT",
        project_body="custom content",  # same body
        canonical_body="original content",
    )

    result_a = ProjectDriftResult(
        project_name="proj_a",
        project_dir=Path("/tmp/proj_a"),
        items=[item_a],
    )
    result_b = ProjectDriftResult(
        project_name="proj_b",
        project_dir=Path("/tmp/proj_b"),
        items=[item_b],
    )

    candidates = _find_convergence_candidates([result_a, result_b])
    assert len(candidates) == 1
    assert candidates[0].count == 2
    assert set(candidates[0].projects) == {"proj_a", "proj_b"}


def test_find_convergence_candidates_different_body_not_grouped() -> None:
    """DRIFT items with different bodies are not grouped as convergence candidates."""
    item_a = DriftItem(
        file="CLAUDE.build.md",
        section="## session modes",
        classification="DRIFT",
        project_body="content A",
        canonical_body="original",
    )
    item_b = DriftItem(
        file="CLAUDE.build.md",
        section="## session modes",
        classification="DRIFT",
        project_body="content B",  # different body
        canonical_body="original",
    )

    result_a = ProjectDriftResult("proj_a", Path("/tmp/proj_a"), items=[item_a])
    result_b = ProjectDriftResult("proj_b", Path("/tmp/proj_b"), items=[item_b])

    candidates = _find_convergence_candidates([result_a, result_b])
    assert candidates == []


def test_find_convergence_candidates_missing_not_grouped() -> None:
    """MISSING items are not included in convergence grouping (only DRIFT items are)."""
    item_a = DriftItem(
        file="CLAUDE.build.md",
        section="## session modes",
        classification="MISSING",
    )
    item_b = DriftItem(
        file="CLAUDE.build.md",
        section="## session modes",
        classification="MISSING",
    )

    result_a = ProjectDriftResult("proj_a", Path("/tmp/proj_a"), items=[item_a])
    result_b = ProjectDriftResult("proj_b", Path("/tmp/proj_b"), items=[item_b])

    candidates = _find_convergence_candidates([result_a, result_b])
    assert candidates == []


def test_find_convergence_candidates_extra_not_grouped() -> None:
    """EXTRA items are not included in convergence grouping (only DRIFT items are)."""
    item_a = DriftItem(
        file="CLAUDE.build.md",
        section="## custom",
        classification="EXTRA",
        project_body="same extra content",
    )
    item_b = DriftItem(
        file="CLAUDE.build.md",
        section="## custom",
        classification="EXTRA",
        project_body="same extra content",
    )

    result_a = ProjectDriftResult("proj_a", Path("/tmp/proj_a"), items=[item_a])
    result_b = ProjectDriftResult("proj_b", Path("/tmp/proj_b"), items=[item_b])

    candidates = _find_convergence_candidates([result_a, result_b])
    assert candidates == []


# ---------------------------------------------------------------------------
# Classification: INTENTIONAL (via .pairmode-overrides)
# ---------------------------------------------------------------------------


def test_intentional_drift_section_reclassified(tmp_path: Path) -> None:
    """A DRIFT section declared in .pairmode-overrides is reclassified as INTENTIONAL."""
    canonical = _canonical_build_md("testproj")

    # Replace the "## Session modes" section body with custom content → would be DRIFT
    import re
    drifted = re.sub(
        r"(## Session modes\n\n)(.*?)(\n\n---|\n\n##)",
        r"\g<1>INTENTIONAL CUSTOM SESSION CONTENT\g<3>",
        canonical,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )

    project_dir = _make_project(tmp_path, "testproj", claude_build_content=drifted)

    # Declare the section as intentional in .pairmode-overrides
    overrides_file = project_dir / ".pairmode-overrides"
    overrides_file.write_text(
        "# Intentional overrides\n"
        "CLAUDE.build.md: ## Session modes\n",
        encoding="utf-8",
    )

    result = drift_report([project_dir])
    project_data = result["projects"][0]

    # The section must NOT appear in drift
    drift_sections = {item["section"] for item in project_data["drift"]}
    assert not any(
        "session modes" in s for s in drift_sections
    ), f"Declared override must not appear in drift; drift={project_data['drift']}"

    # The section MUST appear in intentional
    intentional_sections = {item["section"] for item in project_data["intentional"]}
    assert any(
        "session modes" in s for s in intentional_sections
    ), f"Declared override must appear in intentional; intentional={project_data['intentional']}"


def test_intentional_extra_section_reclassified(tmp_path: Path) -> None:
    """An EXTRA section declared in .pairmode-overrides is reclassified as INTENTIONAL."""
    canonical = _canonical_build_md("testproj")
    content_with_extra = canonical + "\n\n## Custom override section\n\nProject-specific content.\n"

    project_dir = _make_project(tmp_path, "testproj", claude_build_content=content_with_extra)

    # Declare the extra section as intentional
    overrides_file = project_dir / ".pairmode-overrides"
    overrides_file.write_text(
        "CLAUDE.build.md: ## Custom override section\n",
        encoding="utf-8",
    )

    result = drift_report([project_dir])
    project_data = result["projects"][0]

    # Must NOT appear in extra
    extra_sections = {item["section"] for item in project_data["extra"]}
    assert not any(
        "custom override section" in s for s in extra_sections
    ), f"Declared override must not appear in extra; extra={project_data['extra']}"

    # Must appear in intentional
    intentional_sections = {item["section"] for item in project_data["intentional"]}
    assert any(
        "custom override section" in s for s in intentional_sections
    ), f"Declared override must appear in intentional; intentional={project_data['intentional']}"


def test_intentional_excluded_from_convergence_candidates(tmp_path: Path) -> None:
    """INTENTIONAL items must not appear as convergence candidates."""
    canonical = _canonical_build_md("testproj")

    # Create identical drift in both projects
    import re
    drifted = re.sub(
        r"(## Session modes\n\n)(.*?)(\n\n---|\n\n##)",
        r"\g<1>SHARED INTENTIONAL CONTENT\g<3>",
        canonical,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )

    proj_a = _make_project(tmp_path, "intl_a", claude_build_content=drifted)
    proj_b = _make_project(tmp_path, "intl_b", claude_build_content=drifted)

    # Declare the drifted section as intentional in both projects
    override_content = "CLAUDE.build.md: ## Session modes\n"
    (proj_a / ".pairmode-overrides").write_text(override_content, encoding="utf-8")
    (proj_b / ".pairmode-overrides").write_text(override_content, encoding="utf-8")

    result = drift_report([proj_a, proj_b], convergent=True)

    # No convergence candidates — the drift was reclassified as intentional in both
    candidates = result["convergence_candidates"]
    assert not any(
        c["file"] == "CLAUDE.build.md" and "session modes" in c["section"]
        for c in candidates
    ), f"INTENTIONAL items must not appear as convergence candidates; candidates={candidates}"


def test_intentional_count_in_json_output(tmp_path: Path) -> None:
    """JSON output must include intentional items in the project entry."""
    canonical = _canonical_build_md("testproj")

    import re
    drifted = re.sub(
        r"(## Session modes\n\n)(.*?)(\n\n---|\n\n##)",
        r"\g<1>INTENTIONAL DRIFT CONTENT\g<3>",
        canonical,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )

    project_dir = _make_project(tmp_path, "testproj", claude_build_content=drifted)
    (project_dir / ".pairmode-overrides").write_text(
        "CLAUDE.build.md: ## Session modes\n",
        encoding="utf-8",
    )

    result = drift_report([project_dir], output_format="json")
    entry = result["projects"][0]

    assert "intentional" in entry
    assert len(entry["intentional"]) == 1
    assert any("session modes" in item["section"] for item in entry["intentional"])


def test_intentional_shown_in_text_output(tmp_path: Path) -> None:
    """Text output must include the INTENTIONAL line with count for declared overrides."""
    from click.testing import CliRunner
    from skills.pairmode.scripts.pairmode_drift_report import main

    canonical = _canonical_build_md("testproj")

    import re
    drifted = re.sub(
        r"(## Session modes\n\n)(.*?)(\n\n---|\n\n##)",
        r"\g<1>INTENTIONAL TEXT OUTPUT CONTENT\g<3>",
        canonical,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )

    project_dir = _make_project(tmp_path, "testproj", claude_build_content=drifted)
    (project_dir / ".pairmode-overrides").write_text(
        "CLAUDE.build.md: ## Session modes\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    invoke_result = runner.invoke(
        main, ["--projects", str(project_dir), "--output", "text"]
    )

    assert invoke_result.exit_code == 0, f"CLI failed: {invoke_result.output}"
    assert "INTENTIONAL" in invoke_result.output
    assert ".pairmode-overrides" in invoke_result.output


def test_undeclared_drift_not_reclassified(tmp_path: Path) -> None:
    """A DRIFT section NOT in .pairmode-overrides must remain classified as DRIFT."""
    canonical = _canonical_build_md("testproj")

    import re
    drifted = re.sub(
        r"(## Session modes\n\n)(.*?)(\n\n---|\n\n##)",
        r"\g<1>UNDECLARED DRIFT CONTENT\g<3>",
        canonical,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )

    project_dir = _make_project(tmp_path, "testproj", claude_build_content=drifted)
    # Write an overrides file that does NOT include the drifted section
    (project_dir / ".pairmode-overrides").write_text(
        "# No relevant overrides here\n"
        "CLAUDE.build.md: ## some other section\n",
        encoding="utf-8",
    )

    result = drift_report([project_dir])
    project_data = result["projects"][0]

    drift_sections = {item["section"] for item in project_data["drift"]}
    assert any(
        "session modes" in s for s in drift_sections
    ), f"Undeclared drift must remain DRIFT; drift={project_data['drift']}"

    intentional_sections = {item["section"] for item in project_data["intentional"]}
    assert not any(
        "session modes" in s for s in intentional_sections
    ), f"Undeclared section must not appear in intentional; intentional={project_data['intentional']}"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_projects_list() -> None:
    """Passing an empty projects list returns empty results."""
    result = drift_report([], convergent=True)
    assert result["projects"] == []
    assert result["convergence_candidates"] == []


def test_invalid_project_dir_is_skipped(tmp_path: Path) -> None:
    """A non-existent project directory is skipped with a warning, not a crash."""
    missing = tmp_path / "does_not_exist"
    canonical = _canonical_build_md("testproj")
    valid_proj = _make_project(tmp_path, "valid_proj", claude_build_content=canonical)

    result = drift_report([missing, valid_proj])
    # Only the valid project should appear
    assert len(result["projects"]) == 1
    assert result["projects"][0]["project"] == "valid_proj"


def test_project_result_convenience_views() -> None:
    """ProjectDriftResult.missing / .extra / .drift / .intentional filter correctly."""
    items = [
        DriftItem(file="f", section="s1", classification="MISSING"),
        DriftItem(file="f", section="s2", classification="EXTRA"),
        DriftItem(file="f", section="s3", classification="DRIFT"),
        DriftItem(file="f", section="s4", classification="INTENTIONAL"),
    ]
    r = ProjectDriftResult("p", Path("/tmp/p"), items=items)
    assert len(r.missing) == 1
    assert len(r.extra) == 1
    assert len(r.drift) == 1
    assert len(r.intentional) == 1
