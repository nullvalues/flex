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
