"""Tests for skills/pairmode/scripts/fleet_map.py.

All fixtures use fake placeholder repo names — never real fleet repo names.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "skills" / "pairmode" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import fleet_map as fm


def _write(root: Path, rel_path: str, content: str) -> Path:
    p = root / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# load_local_fleet_map — dict-shape validation (CER-198)
# ---------------------------------------------------------------------------

def test_load_local_fleet_map_missing_returns_empty_dict(tmp_path: Path) -> None:
    assert fm.load_local_fleet_map(tmp_path) == {}


def test_load_local_fleet_map_valid_dict_returns_it(tmp_path: Path) -> None:
    _write(tmp_path, fm.LOCAL_FLEET_CONFIG_FILENAME, json.dumps({"Repo-A": "/tmp/x"}))
    assert fm.load_local_fleet_map(tmp_path) == {"Repo-A": "/tmp/x"}


def test_load_local_fleet_map_malformed_json_raises(tmp_path: Path) -> None:
    _write(tmp_path, fm.LOCAL_FLEET_CONFIG_FILENAME, "{not valid json")
    with pytest.raises(fm.FleetMapConfigError):
        fm.load_local_fleet_map(tmp_path)


@pytest.mark.parametrize("top_level", [[], "a string", 3, None, True])
def test_load_local_fleet_map_non_dict_top_level_raises(
    tmp_path: Path, top_level
) -> None:
    """CER-198: valid JSON whose top-level value is not an object must raise
    FleetMapConfigError rather than being returned as-is or falling through
    to the same handling as an absent file. A list/string/number/null
    reaching `repo_entries()` (which calls `.items()`) previously either
    blew up with an unrelated AttributeError or, for a falsy value like `[]`
    or `None`, was silently treated by callers as "no fleet names
    configured" via the `if not fleet_map:` truthiness check — the same
    fail-open shape CER-196 closed for the unparseable case, reopened here
    for the wrong-shape case."""
    _write(tmp_path, fm.LOCAL_FLEET_CONFIG_FILENAME, json.dumps(top_level))
    with pytest.raises(fm.FleetMapConfigError):
        fm.load_local_fleet_map(tmp_path)


def test_load_local_fleet_map_non_dict_error_names_the_file(tmp_path: Path) -> None:
    _write(tmp_path, fm.LOCAL_FLEET_CONFIG_FILENAME, json.dumps([]))
    with pytest.raises(fm.FleetMapConfigError) as excinfo:
        fm.load_local_fleet_map(tmp_path)
    assert fm.LOCAL_FLEET_CONFIG_FILENAME in str(excinfo.value)


# ---------------------------------------------------------------------------
# normalize_name — shared case-fold (CER-205)
# ---------------------------------------------------------------------------

def test_normalize_name_lowercases() -> None:
    assert fm.normalize_name("Fakeproject-X") == "fakeproject-x"
    assert fm.normalize_name("FAKEPROJECT-X") == "fakeproject-x"
    assert fm.normalize_name("fakeproject-x") == "fakeproject-x"


# ---------------------------------------------------------------------------
# repo_entries / real_names_to_labels — sanity coverage
# ---------------------------------------------------------------------------

def test_repo_entries_filters_all_reserved_keys() -> None:
    fleet_map = {
        "_fleet_root": "/path/to/root",
        "_excluded": ["some-name"],
        "_comment": "guidance text",
        "Repo-X": "/path/to/repo-x",
    }
    assert fm.repo_entries(fleet_map) == {"Repo-X": "/path/to/repo-x"}


def test_real_names_to_labels_derives_from_basename() -> None:
    fleet_map = {"Repo-A": "/mnt/work/fakeproject-a"}
    assert fm.real_names_to_labels(fleet_map) == {"fakeproject-a": "Repo-A"}
