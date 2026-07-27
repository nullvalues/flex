"""Tests for skills/pairmode/scripts/story_context.py."""

from __future__ import annotations

import json
import pathlib

import pytest
from click.testing import CliRunner

from skills.pairmode.scripts.story_context import (
    CURRENT_STORIES_KEY,
    clear_current_story,
    cli,
    get_current_stories,
    get_current_story,
    is_pairmode_active,
    match_file_to_module,
    read_state,
    set_current_story,
    write_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_companion_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    companion = tmp_path / ".companion"
    companion.mkdir()
    return companion


# ---------------------------------------------------------------------------
# is_pairmode_active
# ---------------------------------------------------------------------------

class TestIsPairmodeActive:
    def test_returns_false_when_deny_rationale_missing(self, tmp_path):
        assert is_pairmode_active(tmp_path) is False

    def test_returns_true_when_deny_rationale_present(self, tmp_path):
        dot_claude = tmp_path / ".claude"
        dot_claude.mkdir()
        (dot_claude / "settings.deny-rationale.json").write_text("{}")
        assert is_pairmode_active(tmp_path) is True

    def test_returns_false_when_dot_claude_missing(self, tmp_path):
        # No .claude directory at all
        assert is_pairmode_active(tmp_path) is False

    def test_returns_false_when_dot_claude_exists_but_file_absent(self, tmp_path):
        (tmp_path / ".claude").mkdir()
        assert is_pairmode_active(tmp_path) is False


# ---------------------------------------------------------------------------
# read_state / write_state
# ---------------------------------------------------------------------------

class TestReadWriteState:
    def test_read_returns_empty_dict_when_no_state_json(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        result = read_state(companion)
        assert result == {}

    def test_read_returns_empty_dict_on_malformed_json(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        (companion / "state.json").write_text("not valid json {{{")
        result = read_state(companion)
        assert result == {}

    def test_write_creates_state_json(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        write_state(companion, {"pairmode_version": "1.0"})
        state_path = companion / "state.json"
        assert state_path.exists()
        data = json.loads(state_path.read_text())
        assert data["pairmode_version"] == "1.0"

    def test_read_after_write_round_trip(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        original = {"last_loaded_modules": ["auth", "billing"], "pairmode_version": "2.0"}
        write_state(companion, original)
        result = read_state(companion)
        assert result == original

    def test_write_pretty_prints_json(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        write_state(companion, {"k": "v"})
        raw = (companion / "state.json").read_text()
        # Pretty-printed JSON contains newlines
        assert "\n" in raw


# ---------------------------------------------------------------------------
# set_current_story
# ---------------------------------------------------------------------------

class TestSetCurrentStory:
    def test_writes_current_story_with_id(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        state = set_current_story(companion, "2.3")
        assert state["current_story"]["id"] == "2.3"

    def test_writes_current_story_with_title(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        state = set_current_story(companion, "2.3", title="Add denylist deriver")
        assert state["current_story"]["title"] == "Add denylist deriver"

    def test_current_story_without_title_has_no_title_key(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        state = set_current_story(companion, "1.1")
        assert "title" not in state["current_story"]

    def test_set_at_is_iso_timestamp(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        state = set_current_story(companion, "3.0")
        set_at = state["current_story"]["set_at"]
        # Should be parseable as ISO 8601
        from datetime import datetime
        dt = datetime.fromisoformat(set_at)
        assert dt.year >= 2024

    def test_persists_to_disk(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "4.1", title="Some story")
        # Read raw from disk
        raw = json.loads((companion / "state.json").read_text())
        assert raw["current_story"]["id"] == "4.1"
        assert raw["current_story"]["title"] == "Some story"

    def test_preserves_existing_state_keys(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        # Pre-populate state.json with existing data
        write_state(companion, {"last_loaded_modules": ["auth"], "pairmode_version": "1.0"})
        state = set_current_story(companion, "2.1")
        assert state["last_loaded_modules"] == ["auth"]
        assert state["pairmode_version"] == "1.0"
        assert state["current_story"]["id"] == "2.1"

    def test_overwrites_previous_current_story(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "1.0")
        state = set_current_story(companion, "2.0", title="New story")
        assert state["current_story"]["id"] == "2.0"
        assert state["current_story"]["title"] == "New story"

    def test_creates_companion_dir_state_when_no_prior_state_json(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        # No state.json yet
        assert not (companion / "state.json").exists()
        set_current_story(companion, "5.1")
        assert (companion / "state.json").exists()


# ---------------------------------------------------------------------------
# get_current_story
# ---------------------------------------------------------------------------

class TestGetCurrentStory:
    def test_returns_none_when_no_state_json(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        assert get_current_story(companion) is None

    def test_returns_none_when_current_story_not_set(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        write_state(companion, {"last_loaded_modules": ["auth"]})
        assert get_current_story(companion) is None

    def test_returns_current_story_when_set(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "3.2", title="A story")
        result = get_current_story(companion)
        assert result is not None
        assert result["id"] == "3.2"
        assert result["title"] == "A story"


# ---------------------------------------------------------------------------
# clear_current_story (state.json not modified when story is skipped)
# ---------------------------------------------------------------------------

class TestClearCurrentStory:
    def test_removes_current_story_when_present(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "2.3")
        state = clear_current_story(companion)
        assert "current_story" not in state

    def test_noop_when_current_story_not_set(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        write_state(companion, {"last_loaded_modules": ["auth"]})
        state = clear_current_story(companion)
        assert "current_story" not in state
        # Other keys preserved
        assert state["last_loaded_modules"] == ["auth"]

    def test_state_on_disk_has_no_current_story_after_clear(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "1.0")
        clear_current_story(companion)
        raw = json.loads((companion / "state.json").read_text())
        assert "current_story" not in raw

    def test_skip_does_not_modify_story_field(self, tmp_path):
        """Simulates user skipping story prompt — state.json must not have current_story."""
        companion = make_companion_dir(tmp_path)
        write_state(companion, {"last_loaded_modules": ["billing"]})
        # Simulate skip: do not call set_current_story at all
        raw = json.loads((companion / "state.json").read_text())
        assert "current_story" not in raw
        assert raw["last_loaded_modules"] == ["billing"]

    def test_clear_retains_context_tokens(self, tmp_path):
        """--clear must NOT remove context_current_tokens or recorded_at.

        Token accumulation must survive story transitions within a session;
        cross-session staleness is handled by the TTL in
        read_context_tokens_from_state (INFRA-170).
        """
        companion = make_companion_dir(tmp_path)
        write_state(
            companion,
            {
                "current_story": {"id": "INFRA-151", "set_at": "2026-01-01T00:00:00+00:00"},
                "context_current_tokens": 50_000,
                "context_current_tokens_recorded_at": "2026-01-01T00:00:00+00:00",
            },
        )
        state = clear_current_story(companion)
        assert state["context_current_tokens"] == 50_000
        assert state["context_current_tokens_recorded_at"] == "2026-01-01T00:00:00+00:00"
        # current_story must still be gone.
        assert "current_story" not in state
        # Verify on-disk state matches.
        raw = json.loads((companion / "state.json").read_text())
        assert raw["context_current_tokens"] == 50_000
        assert raw["context_current_tokens_recorded_at"] == "2026-01-01T00:00:00+00:00"
        assert "current_story" not in raw

    def test_clear_retains_token_accumulation(self, tmp_path):
        """State with context_current_tokens: 78000 retains that value after --clear."""
        companion = make_companion_dir(tmp_path)
        write_state(
            companion,
            {
                "current_story": {"id": "INFRA-170", "set_at": "2026-06-11T10:00:00+00:00"},
                "context_current_tokens": 78_000,
                "context_current_tokens_recorded_at": "2026-06-11T10:00:00+00:00",
            },
        )
        state = clear_current_story(companion)
        assert state["context_current_tokens"] == 78_000
        assert state["context_current_tokens_recorded_at"] == "2026-06-11T10:00:00+00:00"


# ---------------------------------------------------------------------------
# Schema round-trip (full current_story schema)
# ---------------------------------------------------------------------------

class TestCurrentStorySchemaRoundTrip:
    def test_full_schema_round_trip(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        state = set_current_story(companion, "2.3", title="Add denylist deriver")
        # Re-read from disk
        reread = read_state(companion)
        story = reread["current_story"]
        assert story["id"] == "2.3"
        assert story["title"] == "Add denylist deriver"
        assert "set_at" in story
        # Verify it can be serialised back to JSON without error
        assert json.dumps(reread)

# ---------------------------------------------------------------------------
# match_file_to_module
# ---------------------------------------------------------------------------

class TestMatchFileToModule:
    def _modules(self):
        return [
            {"name": "auth-and-security", "description": "Auth", "paths": ["src/auth/"]},
            {"name": "decision-ledger", "description": "Ledger", "paths": ["src/ledger/", "lib/ledger/"]},
            {"name": "billing", "description": "Billing", "paths": ["src/billing/"]},
        ]

    def test_returns_module_name_for_exact_prefix_match(self):
        modules = self._modules()
        assert match_file_to_module("src/auth/views.py", modules) == "auth-and-security"

    def test_returns_module_name_for_nested_path(self):
        modules = self._modules()
        assert match_file_to_module("src/ledger/models/account.py", modules) == "decision-ledger"

    def test_returns_module_name_for_second_path_entry(self):
        modules = self._modules()
        assert match_file_to_module("lib/ledger/util.py", modules) == "decision-ledger"

    def test_returns_none_when_no_module_matches(self):
        modules = self._modules()
        assert match_file_to_module("src/unrelated/file.py", modules) is None

    def test_returns_none_for_empty_modules_list(self):
        assert match_file_to_module("src/auth/views.py", []) is None

    def test_returns_none_for_empty_file_path(self):
        modules = self._modules()
        assert match_file_to_module("", modules) is None

    def test_does_not_match_partial_directory_name(self):
        # "src/auth" should NOT match "src/authorize/views.py" if module path is "src/auth/"
        modules = [{"name": "auth-and-security", "paths": ["src/auth/"]}]
        # "src/authorize/views.py" does not start with "src/auth/" — no match
        assert match_file_to_module("src/authorize/views.py", modules) is None

    def test_matches_first_module_when_multiple_could_match(self):
        # Module list order determines which wins — first match wins
        modules = [
            {"name": "first", "paths": ["src/"]},
            {"name": "second", "paths": ["src/auth/"]},
        ]
        assert match_file_to_module("src/auth/views.py", modules) == "first"

    def test_module_with_no_paths_key_is_skipped(self):
        modules = [
            {"name": "no-paths"},
            {"name": "auth-and-security", "paths": ["src/auth/"]},
        ]
        assert match_file_to_module("src/auth/views.py", modules) == "auth-and-security"


    def test_state_json_schema_includes_last_loaded_modules(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        write_state(companion, {
            "last_loaded_modules": ["auth", "billing"],
            "current_story": {
                "id": "2.3",
                "title": "optional title",
                "set_at": "2026-04-20T00:00:00+00:00",
            },
        })
        state = read_state(companion)
        assert state["last_loaded_modules"] == ["auth", "billing"]
        assert state["current_story"]["id"] == "2.3"


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def _make_story_file(project_dir: pathlib.Path, story_id: str, title: str = "Test story", status: str = "planned") -> pathlib.Path:
    """Create a minimal story file at docs/stories/<RAIL>/<RAIL>-NNN.md."""
    parts = story_id.split("-")
    rail = parts[0].upper()
    story_dir = project_dir / "docs" / "stories" / rail
    story_dir.mkdir(parents=True, exist_ok=True)
    story_path = story_dir / f"{story_id}.md"
    story_path.write_text(
        f"---\nid: {story_id}\nrail: {rail}\ntitle: {title}\nstatus: {status}\nphase: \"32\"\nprimary_files:\n---\n\n## Ensures\n\n- Done.\n"
    )
    return story_path


class TestCLI:
    def test_set_writes_current_story_to_state_json(self, tmp_path):
        """--set INFRA-001 with a fixture story file writes current_story to state.json."""
        (tmp_path / ".companion").mkdir()
        _make_story_file(tmp_path, "INFRA-001", title="Add CLI entry point")

        runner = CliRunner()
        result = runner.invoke(cli, ["--set", "INFRA-001", "--project-dir", str(tmp_path)])

        assert result.exit_code == 0, result.output
        assert "Story set: INFRA-001" in result.output

        state = json.loads((tmp_path / ".companion" / "state.json").read_text())
        assert state["current_story"]["id"] == "INFRA-001"
        assert state["current_story"]["title"] == "Add CLI entry point"

    def test_get_returns_story_id_when_set(self, tmp_path):
        """--get returns the current story ID when one is set."""
        companion = tmp_path / ".companion"
        companion.mkdir()
        set_current_story(companion, "INFRA-002", title="Some story")

        runner = CliRunner()
        result = runner.invoke(cli, ["--get", "--project-dir", str(tmp_path)])

        assert result.exit_code == 0, result.output
        assert "INFRA-002" in result.output

    def test_get_returns_no_story_set_when_absent(self, tmp_path):
        """--get returns 'No story set.' when no current story is in state.json."""
        (tmp_path / ".companion").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["--get", "--project-dir", str(tmp_path)])

        assert result.exit_code == 0, result.output
        assert "No story set." in result.output

    def test_clear_removes_current_story(self, tmp_path):
        """--clear removes current_story from state.json."""
        companion = tmp_path / ".companion"
        companion.mkdir()
        set_current_story(companion, "INFRA-003", title="Old story")

        runner = CliRunner()
        result = runner.invoke(cli, ["--clear", "--project-dir", str(tmp_path)])

        assert result.exit_code == 0, result.output
        assert "Story cleared." in result.output

        state = json.loads((companion / "state.json").read_text())
        assert "current_story" not in state

    def test_get_after_clear_returns_no_story_set(self, tmp_path):
        """After --clear, --get returns 'No story set.'."""
        companion = tmp_path / ".companion"
        companion.mkdir()
        set_current_story(companion, "INFRA-004")

        runner = CliRunner()
        runner.invoke(cli, ["--clear", "--project-dir", str(tmp_path)])
        result = runner.invoke(cli, ["--get", "--project-dir", str(tmp_path)])

        assert result.exit_code == 0, result.output
        assert "No story set." in result.output

    def test_set_with_missing_story_file_exits_with_error(self, tmp_path):
        """--set with a story ID whose file does not exist exits with an error message."""
        (tmp_path / ".companion").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["--set", "INFRA-999", "--project-dir", str(tmp_path)])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "Story file not found" in result.output

    def test_no_option_provided_exits_with_usage_error(self, tmp_path):
        """Providing none of --set/--get/--clear exits with a usage error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--project-dir", str(tmp_path)])

        assert result.exit_code != 0

    def test_set_creates_companion_dir_state_when_absent(self, tmp_path):
        """--set creates state.json in .companion/ even when state.json is absent."""
        companion = tmp_path / ".companion"
        companion.mkdir()
        _make_story_file(tmp_path, "INFRA-005")

        runner = CliRunner()
        result = runner.invoke(cli, ["--set", "INFRA-005", "--project-dir", str(tmp_path)])

        assert result.exit_code == 0, result.output
        assert (companion / "state.json").exists()

    def test_set_rejects_traversal_story_id(self, tmp_path):
        """--set with a traversal story ID (e.g. ../../../etc-001) exits non-zero.

        The containment guard in _resolve_story_file must catch paths that escape
        docs/stories/ even if the raw string looks like a valid story ID.
        """
        (tmp_path / ".companion").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["--set", "../../../etc-001", "--project-dir", str(tmp_path)])

        assert result.exit_code != 0
        # Should report a file-not-found or similar error
        assert result.output.strip() != ""

    def test_shallow_project_dir_rejected_by_depth_guard(self, tmp_path):
        """--project-dir /tmp exits non-zero because the path has fewer than 3 components."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--get", "--project-dir", "/tmp"])

        assert result.exit_code != 0
        assert "suspiciously shallow" in result.output


# ---------------------------------------------------------------------------
# INFRA-281 (CER-095.2): current_stories keyed record
# ---------------------------------------------------------------------------


class TestCurrentStoriesKeyedRecord:
    """B1, B2: set_current_story writes both the keyed record and the mirror."""

    def test_set_current_story_writes_keyed_entry(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        state = set_current_story(companion, "A-001", title="Story A")
        assert state[CURRENT_STORIES_KEY]["A-001"]["id"] == "A-001"
        assert state[CURRENT_STORIES_KEY]["A-001"]["title"] == "Story A"

    def test_second_stamp_preserves_first_entry_byte_identical(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "A-001", title="Story A")
        first_entry = read_state(companion)[CURRENT_STORIES_KEY]["A-001"]

        state = set_current_story(companion, "B-002", title="Story B")

        assert state[CURRENT_STORIES_KEY]["A-001"] == first_entry
        assert state[CURRENT_STORIES_KEY]["B-002"]["id"] == "B-002"

    def test_mirror_equals_latest_keyed_entry(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "A-001", title="Story A")
        state = set_current_story(companion, "B-002", title="Story B")
        assert state["current_story"] == state[CURRENT_STORIES_KEY]["B-002"]

    def test_get_current_stories_returns_keyed_dict(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "A-001")
        set_current_story(companion, "B-002")
        result = get_current_stories(companion)
        assert set(result) == {"A-001", "B-002"}

    def test_get_current_stories_empty_dict_when_absent(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        assert get_current_stories(companion) == {}

    def test_get_current_stories_derives_single_entry_from_legacy_state(self, tmp_path):
        """B4: pre-INFRA-281 state.json (flat current_story, no current_stories key)."""
        companion = make_companion_dir(tmp_path)
        write_state(
            companion,
            {"current_story": {"id": "LEGACY-001", "set_at": "2026-01-01T00:00:00+00:00"}},
        )
        result = get_current_stories(companion)
        assert set(result) == {"LEGACY-001"}
        assert result["LEGACY-001"]["id"] == "LEGACY-001"

    def test_get_current_stories_no_write_on_legacy_state(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        write_state(
            companion,
            {"current_story": {"id": "LEGACY-001", "set_at": "2026-01-01T00:00:00+00:00"}},
        )
        state_path = companion / "state.json"
        before_mtime = state_path.stat().st_mtime_ns
        before_bytes = state_path.read_bytes()

        get_current_stories(companion)

        assert state_path.stat().st_mtime_ns == before_mtime
        assert state_path.read_bytes() == before_bytes

    def test_get_current_stories_empty_dict_when_neither_key_present(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        write_state(companion, {"last_loaded_modules": ["auth"]})
        assert get_current_stories(companion) == {}

    def test_get_current_story_unchanged_signature_and_shape(self, tmp_path):
        """B2: get_current_story is unchanged — still returns the flat entry."""
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "A-001", title="Story A")
        result = get_current_story(companion)
        assert result == {"id": "A-001", "title": "Story A", "set_at": result["set_at"]}


class TestClearCurrentStoryScoped:
    """B3: scoped clear_current_story(companion_dir, story_id)."""

    def test_scoped_clear_removes_only_named_story(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "A-001", title="Story A")
        set_current_story(companion, "B-002", title="Story B")

        state = clear_current_story(companion, "A-001")

        assert "A-001" not in state[CURRENT_STORIES_KEY]
        assert "B-002" in state[CURRENT_STORIES_KEY]

    def test_scoped_clear_leaves_other_entries_byte_identical(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "A-001", title="Story A")
        set_current_story(companion, "B-002", title="Story B")
        b_entry_before = read_state(companion)[CURRENT_STORIES_KEY]["B-002"]

        state = clear_current_story(companion, "A-001")

        assert state[CURRENT_STORIES_KEY]["B-002"] == b_entry_before

    def test_scoped_clear_repoints_mirror_when_mirrored_story_removed(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "A-001", title="Story A")
        set_current_story(companion, "B-002", title="Story B")
        # B-002 is the mirror (stamped last).
        state = clear_current_story(companion, "B-002")
        assert state["current_story"]["id"] == "A-001"

    def test_scoped_clear_repoint_ties_broken_by_ascending_story_id(self, tmp_path):
        """Deterministic re-point: identical set_at, tie-break by story ID ascending."""
        companion = make_companion_dir(tmp_path)
        same_ts = "2026-01-01T00:00:00+00:00"
        write_state(
            companion,
            {
                CURRENT_STORIES_KEY: {
                    "B-002": {"id": "B-002", "set_at": same_ts},
                    "A-001": {"id": "A-001", "set_at": same_ts},
                    "C-003": {"id": "C-003", "set_at": same_ts},
                },
                "current_story": {"id": "C-003", "set_at": same_ts},
            },
        )
        state = clear_current_story(companion, "C-003")
        assert state["current_story"]["id"] == "A-001"

    def test_scoped_clear_leaves_mirror_unchanged_when_not_mirrored_story(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "A-001", title="Story A")
        set_current_story(companion, "B-002", title="Story B")
        # Mirror currently points at B-002; clear A-001 instead.
        state = clear_current_story(companion, "A-001")
        assert state["current_story"]["id"] == "B-002"

    def test_scoped_clear_removes_mirror_entirely_when_no_entries_remain(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "A-001", title="Story A")
        state = clear_current_story(companion, "A-001")
        assert "current_story" not in state
        assert CURRENT_STORIES_KEY not in state or state[CURRENT_STORIES_KEY] == {}

    def test_unscoped_clear_still_clears_the_whole_slate(self, tmp_path):
        """The legacy call shape (story_id defaulted to None) keeps its old behaviour."""
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "A-001", title="Story A")
        set_current_story(companion, "B-002", title="Story B")
        state = clear_current_story(companion)
        assert "current_story" not in state
        assert CURRENT_STORIES_KEY not in state

    def test_scoped_clear_retains_context_tokens(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        write_state(
            companion,
            {
                CURRENT_STORIES_KEY: {
                    "A-001": {"id": "A-001", "set_at": "2026-01-01T00:00:00+00:00"},
                },
                "current_story": {"id": "A-001", "set_at": "2026-01-01T00:00:00+00:00"},
                "context_current_tokens": 50_000,
                "context_current_tokens_recorded_at": "2026-01-01T00:00:00+00:00",
            },
        )
        state = clear_current_story(companion, "A-001")
        assert state["context_current_tokens"] == 50_000
        assert state["context_current_tokens_recorded_at"] == "2026-01-01T00:00:00+00:00"

    def test_scoped_clear_of_unknown_story_is_a_noop(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "A-001", title="Story A")
        state = clear_current_story(companion, "NOT-A-REAL-STORY")
        assert state[CURRENT_STORIES_KEY]["A-001"]["id"] == "A-001"
        assert state["current_story"]["id"] == "A-001"
