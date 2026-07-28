"""Tests for skills/pairmode/scripts/hook_view.py (INFRA-288, CER-104).

Covers B2 (source constants), B3 (merged view shape/order/provenance),
B4 (tolerant plugin discovery), B5 (basename grouping across sources),
B6 (duplicate group shape) and C3 (settings-only parity with the
pre-INFRA-288 detectors).

Every fixture is a tmpdir tree with a fake home — never the real
``~/.claude/``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skills.pairmode.scripts import hook_view


@pytest.fixture(autouse=True)
def _no_env_plugin_hooks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the operator's own FLEX_PLUGIN_HOOKS out of every test."""
    monkeypatch.delenv(hook_view.FLEX_PLUGIN_HOOKS_ENV, raising=False)


def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def _hooks_doc(command: str, event: str = "PostToolUse", matcher: "str | None" = "Task|Agent") -> dict:
    block: dict = {"hooks": [{"type": "command", "command": command}]}
    if matcher is not None:
        block["matcher"] = matcher
    return {"hooks": {event: [block]}}


# ---------------------------------------------------------------------------
# B2 — source constants
# ---------------------------------------------------------------------------


class TestSourceConstants:
    def test_values(self) -> None:
        assert hook_view.HOOK_SOURCE_SETTINGS == "settings"
        assert hook_view.HOOK_SOURCE_SETTINGS_LOCAL == "settings.local"
        assert hook_view.HOOK_SOURCE_PLUGIN == "plugin"
        assert hook_view.FLEX_PLUGIN_HOOKS_ENV == "FLEX_PLUGIN_HOOKS"


# ---------------------------------------------------------------------------
# B4 — plugin_hook_files
# ---------------------------------------------------------------------------


class TestPluginHookFiles:
    def test_finds_nested_plugin_hooks_json(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        plugin_file = _write_json(
            home / ".claude" / "plugins" / "x" / "y" / "hooks" / "hooks.json",
            _hooks_doc("python3 ${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.py"),
        )
        assert plugin_file in hook_view.plugin_hook_files(home)

    def test_empty_home_returns_empty(self, tmp_path: Path) -> None:
        assert hook_view.plugin_hook_files(tmp_path / "empty-home") == []

    def test_no_plugins_dir_returns_empty(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        (home / ".claude").mkdir(parents=True)
        assert hook_view.plugin_hook_files(home) == []

    def test_env_override_adds_absolute_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = tmp_path / "home"
        home.mkdir()
        extra = _write_json(
            tmp_path / "elsewhere" / "hooks.json",
            _hooks_doc("python3 ${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.py"),
        )
        monkeypatch.setenv(hook_view.FLEX_PLUGIN_HOOKS_ENV, str(extra))
        assert extra in hook_view.plugin_hook_files(home)

    def test_env_override_relative_paths_are_ignored(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv(hook_view.FLEX_PLUGIN_HOOKS_ENV, "relative/hooks.json")
        assert hook_view.plugin_hook_files(home) == []

    def test_glob_depth_is_bounded(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        too_deep = (
            home / ".claude" / "plugins" / "a" / "b" / "c" / "d" / "e"
            / "hooks" / "hooks.json"
        )
        _write_json(too_deep, _hooks_doc("python3 x/hook.py"))
        assert hook_view.plugin_hook_files(home) == []

    def test_never_raises_on_file_shaped_plugins_dir(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        (home / ".claude").mkdir(parents=True)
        (home / ".claude" / "plugins").write_text("not a dir", encoding="utf-8")
        assert hook_view.plugin_hook_files(home) == []


# ---------------------------------------------------------------------------
# B3 — merged_hook_view / hook_sources
# ---------------------------------------------------------------------------


class TestMergedHookView:
    def _project(self, tmp_path: Path) -> Path:
        project = tmp_path / "project"
        project.mkdir(parents=True, exist_ok=True)
        return project

    def test_flattens_all_three_sources_in_order(self, tmp_path: Path) -> None:
        project = self._project(tmp_path)
        home = tmp_path / "home"
        _write_json(
            project / ".claude" / "settings.json",
            _hooks_doc("uv run python /abs/hooks/post_tool_use.py"),
        )
        _write_json(
            project / ".claude" / "settings.local.json",
            _hooks_doc("uv run python /local/hooks/other_hook.py", matcher=None),
        )
        _write_json(
            home / ".claude" / "plugins" / "flex" / "hooks" / "hooks.json",
            _hooks_doc("python3 ${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.py"),
        )

        view = hook_view.merged_hook_view(project, home=home)
        assert [entry["source"] for entry in view] == [
            hook_view.HOOK_SOURCE_SETTINGS,
            hook_view.HOOK_SOURCE_SETTINGS_LOCAL,
            hook_view.HOOK_SOURCE_PLUGIN,
        ]
        first = view[0]
        assert first["event"] == "PostToolUse"
        assert first["matcher"] == "Task|Agent"
        assert first["command"] == "uv run python /abs/hooks/post_tool_use.py"
        assert first["basename"] == "post_tool_use.py"
        assert first["path"] == str(project / ".claude" / "settings.json")
        # settings.local entry has no matcher key -> None
        assert view[1]["matcher"] is None
        # Plugin command is recorded verbatim — never expanded (B5).
        assert view[2]["command"] == (
            "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.py"
        )
        assert view[2]["basename"] == "post_tool_use.py"

    def test_missing_and_malformed_files_contribute_nothing(
        self, tmp_path: Path
    ) -> None:
        project = self._project(tmp_path)
        home = tmp_path / "home"
        # settings.json malformed JSON; settings.local malformed shape; no plugins.
        settings = project / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text("{not json", encoding="utf-8")
        _write_json(
            project / ".claude" / "settings.local.json",
            {"hooks": {"PostToolUse": "not-a-list"}},
        )
        assert hook_view.merged_hook_view(project, home=home) == []

    def test_hook_sources_orders_and_labels(self, tmp_path: Path) -> None:
        project = self._project(tmp_path)
        home = tmp_path / "home"
        plugin_file = _write_json(
            home / ".claude" / "plugins" / "flex" / "hooks" / "hooks.json",
            _hooks_doc("python3 ${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.py"),
        )
        sources = hook_view.hook_sources(project, home=home)
        assert [s["source"] for s in sources] == [
            hook_view.HOOK_SOURCE_SETTINGS,
            hook_view.HOOK_SOURCE_SETTINGS_LOCAL,
            hook_view.HOOK_SOURCE_PLUGIN,
        ]
        assert sources[2]["path"] == str(plugin_file)


# ---------------------------------------------------------------------------
# B5 / B6 — duplicate_hook_groups
# ---------------------------------------------------------------------------


class TestDuplicateHookGroups:
    def test_settings_vs_plugin_pair_groups_by_basename(self, tmp_path: Path) -> None:
        """B5: an absolute settings path and an unexpanded
        ${CLAUDE_PLUGIN_ROOT} plugin command group together by basename."""
        project = tmp_path / "project"
        home = tmp_path / "home"
        settings_command = "uv run python /mnt/work/flex/hooks/post_tool_use.py"
        plugin_command = "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.py"
        _write_json(
            project / ".claude" / "settings.json", _hooks_doc(settings_command)
        )
        _write_json(
            home / ".claude" / "plugins" / "flex" / "hooks" / "hooks.json",
            _hooks_doc(plugin_command),
        )

        groups = hook_view.duplicate_hook_groups(
            hook_view.merged_hook_view(project, home=home)
        )
        assert len(groups) == 1
        group = groups[0]
        assert group["event"] == "PostToolUse"
        assert group["basename"] == "post_tool_use.py"
        assert group["commands"] == [settings_command, plugin_command]
        assert group["sources"] == [
            hook_view.HOOK_SOURCE_SETTINGS,
            hook_view.HOOK_SOURCE_PLUGIN,
        ]

    def test_distinct_basenames_do_not_group(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        home = tmp_path / "home"
        _write_json(
            project / ".claude" / "settings.json",
            _hooks_doc("uv run python /a/hooks/post_tool_use.py"),
        )
        _write_json(
            home / ".claude" / "plugins" / "flex" / "hooks" / "hooks.json",
            _hooks_doc("python3 ${CLAUDE_PLUGIN_ROOT}/hooks/session_start.py"),
        )
        assert hook_view.duplicate_hook_groups(
            hook_view.merged_hook_view(project, home=home)
        ) == []

    def test_same_basename_different_events_do_not_group(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        _write_json(
            project / ".claude" / "settings.json",
            {
                "hooks": {
                    "PostToolUse": [
                        {"matcher": "Task", "hooks": [
                            {"type": "command", "command": "uv run python /a/x.py"},
                        ]},
                    ],
                    "PreToolUse": [
                        {"matcher": "Task", "hooks": [
                            {"type": "command", "command": "uv run python /b/x.py"},
                        ]},
                    ],
                }
            },
        )
        assert hook_view.duplicate_hook_groups(
            hook_view.merged_hook_view(project, home=tmp_path / "home")
        ) == []

    def test_malformed_view_yields_empty(self) -> None:
        assert hook_view.duplicate_hook_groups(None) == []
        assert hook_view.duplicate_hook_groups([{"nonsense": True}, 42]) == []


# ---------------------------------------------------------------------------
# C3 — settings-only parity with the pre-INFRA-288 detectors
# ---------------------------------------------------------------------------


class TestSettingsOnlyParity:
    def test_settings_only_project_matches_legacy_shape(self, tmp_path: Path) -> None:
        """A project with no settings.local.json and no plugin install
        produces exactly the pre-INFRA-288 settings-only result (first three
        keys unchanged; sources is the only addition)."""
        project = tmp_path / "project"
        _write_json(
            project / ".claude" / "settings.json",
            {
                "hooks": {
                    "PreToolUse": [
                        {"matcher": "Task", "hooks": [
                            {"type": "command", "command": "uv run python /a/hooks/pre_tool_use.py"},
                        ]},
                        {"matcher": "Task", "hooks": [
                            {"type": "command", "command": "uv run python /b/hooks/pre_tool_use.py"},
                        ]},
                    ]
                }
            },
        )
        groups = hook_view.duplicate_hook_groups(
            hook_view.merged_hook_view(project, home=tmp_path / "home")
        )
        assert len(groups) == 1
        assert groups[0]["event"] == "PreToolUse"
        assert groups[0]["basename"] == "pre_tool_use.py"
        assert groups[0]["commands"] == [
            "uv run python /a/hooks/pre_tool_use.py",
            "uv run python /b/hooks/pre_tool_use.py",
        ]
        assert groups[0]["sources"] == [
            hook_view.HOOK_SOURCE_SETTINGS,
            hook_view.HOOK_SOURCE_SETTINGS,
        ]

    def test_clean_settings_only_project_reports_no_duplicates(
        self, tmp_path: Path
    ) -> None:
        project = tmp_path / "project"
        _write_json(
            project / ".claude" / "settings.json",
            _hooks_doc("uv run python /a/hooks/post_tool_use.py"),
        )
        assert hook_view.duplicate_hook_groups(
            hook_view.merged_hook_view(project, home=tmp_path / "home")
        ) == []
