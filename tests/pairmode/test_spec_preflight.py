"""Tests for skills/pairmode/scripts/spec_preflight.py — INFRA-190."""
from __future__ import annotations
import sys
from pathlib import Path
import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"))
import spec_preflight as sp


def test_extract_sections_returns_ensures_and_instructions():
    text = "---\nid: X\n---\n## Ensures\n- foo bar\n\n## Instructions\nbaz\n"
    body = sp._extract_body_sections(text)
    assert "foo bar" in body
    assert "baz" in body


def test_extract_sections_ignores_requires():
    text = "---\nid: X\n---\n## Requires\nprecondition\n\n## Ensures\n- assertion\n"
    body = sp._extract_body_sections(text)
    assert "assertion" in body
    assert "precondition" not in body


def test_check_routes_warns_when_route_not_in_source(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.ts").write_text("// no routes here\n")
    warnings = sp._check_routes("Call /api/nonexistent-zzz9 to fetch data.", tmp_path)
    assert any("/api/nonexistent-zzz9" in w for w in warnings)


def test_check_routes_clean_when_route_found(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "routes.ts").write_text('router.get("/api/health", handler)\n')
    warnings = sp._check_routes("Call /api/health to check status.", tmp_path)
    assert not warnings


def test_check_routes_empty_body_no_warnings(tmp_path):
    warnings = sp._check_routes("No routes mentioned here.", tmp_path)
    assert not warnings


def test_check_constants_warns_when_constant_not_in_source(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n")
    warnings = sp._check_constants("Use `FAKE_CONSTANT_ZZZ9` in the config.", tmp_path)
    assert any("FAKE_CONSTANT_ZZZ9" in w for w in warnings)


def test_check_constants_clean_when_constant_found(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "config.py").write_text("REAL_CONST = 42\n")
    warnings = sp._check_constants("Set `REAL_CONST` to configure.", tmp_path)
    assert not warnings


def test_check_constants_excludes_http_methods(tmp_path):
    warnings = sp._check_constants("Use `GET` and `POST`.", tmp_path)
    assert not warnings


def test_check_constants_excludes_null_true_false(tmp_path):
    warnings = sp._check_constants("Value should be `NULL` or `TRUE` or `FALSE`.", tmp_path)
    assert not warnings


def test_run_preflight_returns_empty_for_clean_story(tmp_path):
    story = tmp_path / "docs" / "stories" / "INFRA"
    story.mkdir(parents=True)
    (story / "INFRA-190.md").write_text(
        "---\nid: INFRA-190\nrail: INFRA\n---\n## Ensures\n- The file exists.\n"
    )
    (tmp_path / "src").mkdir()
    assert sp.run_preflight(story / "INFRA-190.md", tmp_path) == []


def test_run_preflight_warns_on_missing_route(tmp_path):
    story = tmp_path / "docs" / "stories" / "INFRA"
    story.mkdir(parents=True)
    (story / "INFRA-191.md").write_text(
        "---\nid: INFRA-191\nrail: INFRA\n---\n## Ensures\n- Call /api/ghost-route-zzz.\n"
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("# nothing\n")
    warnings = sp.run_preflight(story / "INFRA-191.md", tmp_path)
    assert any("/api/ghost-route-zzz" in w for w in warnings)


def test_spec_preflight_surfaces_scope_warnings(tmp_path):
    """INFRA-320 § C4: run_preflight folds check-story-scope's rule-3
    (body-named undeclared path) warnings into its own output, prefixed
    `scope: ` so their origin is legible."""
    story = tmp_path / "docs" / "stories" / "INFRA"
    story.mkdir(parents=True)
    story_file = story / "INFRA-320.md"
    story_file.write_text(
        "---\nid: INFRA-320\nrail: INFRA\nphase: \"99\"\n"
        "primary_files: []\ntouches: []\n---\n\n"
        "## Ensures\n\n- Update `docs/architecture.md` and "
        "`skills/pairmode/scripts/undeclared.py`.\n"
    )
    (tmp_path / "skills" / "pairmode" / "scripts").mkdir(parents=True)
    (tmp_path / "skills" / "pairmode" / "scripts" / "undeclared.py").write_text("# x\n")

    warnings = sp.run_preflight(story_file, tmp_path)
    scope_warnings = [w for w in warnings if w.startswith("scope: ")]
    assert len(scope_warnings) == 1
    assert "skills/pairmode/scripts/undeclared.py" in scope_warnings[0]
    # docs/architecture.md is a standing surface — never warned on.
    assert not any("docs/architecture.md" in w for w in scope_warnings)


def test_run_preflight_cli_exits_0(tmp_path):
    story = tmp_path / "docs" / "stories" / "INFRA"
    story.mkdir(parents=True)
    (story / "INFRA-190.md").write_text(
        "---\nid: INFRA-190\nrail: INFRA\n---\n## Ensures\n- plain assertion.\n"
    )
    runner = CliRunner()
    result = runner.invoke(
        sp.spec_preflight,
        ["--story-id", "INFRA-190", "--project-dir", str(tmp_path)],
    )
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# INFRA-304 (CER-064) — parity between the two spec-preflight entry points.
#
# spec_preflight.spec_preflight (this module's standalone command) and
# flex_build's `spec-preflight` subcommand must reject a malformed/escaping
# --story-id identically: same exit code, same stderr text, no filesystem
# read of the offending payload. Both now route through flex_build's single
# story_path_checked helper (E2/E3).
# ---------------------------------------------------------------------------

import flex_build as fb  # noqa: E402


_CER_064_PAYLOADS = [
    "../../../etc/passwd",
    "INFRA-190/../../../../etc/passwd",
    "../INFRA-190",
    "infra-190",
    "INFRA-19",
]


@pytest.mark.parametrize("payload", _CER_064_PAYLOADS)
def test_cer_064_both_entry_points_reject_malformed_story_id_identically(payload):
    runner = CliRunner()
    standalone_result = runner.invoke(
        sp.spec_preflight, ["--story-id", payload, "--project-dir", "."]
    )
    flex_build_result = runner.invoke(
        fb.flex_build, ["spec-preflight", "--story-id", payload, "--project-dir", "."]
    )

    # Equality first — both must agree with each other...
    assert standalone_result.exit_code == flex_build_result.exit_code
    assert standalone_result.output == flex_build_result.output

    # ...then the absolute values, so this test cannot pass by both entry
    # points being broken the same (wrong) way.
    assert standalone_result.exit_code == 2
    assert payload in standalone_result.output
    assert "invalid story ID" in standalone_result.output


def test_cer_064_both_entry_points_still_exit_0_for_wellformed_missing_story(tmp_path):
    """A well-formed ID for a story that does not exist is not a shape/escape
    failure — both entry points must still exit 0 (E4), so this test cannot
    pass by making every payload fail."""
    runner = CliRunner()
    standalone_result = runner.invoke(
        sp.spec_preflight, ["--story-id", "INFRA-999", "--project-dir", str(tmp_path)]
    )
    flex_build_result = runner.invoke(
        fb.flex_build,
        ["spec-preflight", "--story-id", "INFRA-999", "--project-dir", str(tmp_path)],
    )
    assert standalone_result.exit_code == 0
    assert flex_build_result.exit_code == 0
