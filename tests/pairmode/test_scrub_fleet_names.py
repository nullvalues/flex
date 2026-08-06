"""Tests for skills/pairmode/scripts/scrub_fleet_names.py.

All fixtures use fake placeholder repo names — never real fleet repo names.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "skills" / "pairmode" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import scrub_fleet_names as sfn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)


def _git_add(root: Path) -> None:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)


def _write(root: Path, rel_path: str, content: str) -> Path:
    p = root / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


FAKE_MAP = {
    "Repo-A": "/tmp/example-repo-a",
    "Repo-B": "/tmp/example-repo-b",
    # A pair where one name is a strict prefix of the other, mirroring the
    # real prefix/extended-name collision in the fleet map.
    "Repo-C": "/tmp/example-repo-c",
    "Repo-D": "/tmp/example-repo-c.help",
}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _init_git_repo(tmp_path)
    # INFRA-400: point `_fleet_root` at an empty, isolated directory (never
    # `tmp_path`'s real parent, which under pytest holds unrelated sibling
    # git repos from other tests in the same run) so the reconciliation step
    # `verify()` now performs never fires against tests that aren't
    # exercising it. Reconciliation itself is covered by its own dedicated
    # tests below.
    isolated_fleet_root = tmp_path / "_isolated_fleet_root"
    isolated_fleet_root.mkdir()
    fleet_map = {**FAKE_MAP, "_fleet_root": str(isolated_fleet_root)}
    _write(tmp_path, ".pairmode-fleet.local.json", json.dumps(fleet_map))
    return tmp_path


# ---------------------------------------------------------------------------
# _load_local_fleet_map
# ---------------------------------------------------------------------------

def test_load_local_fleet_map_present(repo: Path) -> None:
    loaded = sfn._load_local_fleet_map(repo)
    # The `repo` fixture adds a reserved `_fleet_root` key (INFRA-400) beyond
    # FAKE_MAP's plain repo entries; the loader must return it unfiltered
    # (filtering it out is `_real_names_to_labels`'s job, not the loader's).
    assert loaded["_fleet_root"] == str(repo / "_isolated_fleet_root")
    for k, v in FAKE_MAP.items():
        assert loaded[k] == v


def test_load_local_fleet_map_missing(tmp_path: Path) -> None:
    assert sfn._load_local_fleet_map(tmp_path) == {}


def test_load_local_fleet_map_malformed(tmp_path: Path) -> None:
    _write(tmp_path, ".pairmode-fleet.local.json", "{not valid json")
    assert sfn._load_local_fleet_map(tmp_path) == {}


# ---------------------------------------------------------------------------
# One-to-one validation
# ---------------------------------------------------------------------------

def test_one_to_one_validation_passes_for_distinct_map() -> None:
    names_to_labels = sfn._real_names_to_labels(FAKE_MAP)
    sfn._validate_one_to_one(names_to_labels)  # should not raise


def test_one_to_one_validation_rejects_duplicate_label() -> None:
    bad_map = {"Repo-A": "/tmp/example-repo-a", "Repo-B": "/tmp/example-repo-a"}
    names_to_labels = sfn._real_names_to_labels(bad_map)
    # Only one entry survives in the dict (same key "example-repo-a"), so
    # exercise the collapse check directly via a constructed collision.
    collision = {"example-repo-x": "Repo-A", "example-repo-y": "Repo-A"}
    with pytest.raises(ValueError):
        sfn._validate_one_to_one(collision)


# ---------------------------------------------------------------------------
# Apply: basic substitution, boundary, longest-match-first
# ---------------------------------------------------------------------------

def test_apply_replaces_basename_with_word_boundary(repo: Path) -> None:
    _write(repo, "docs/notes.md", "See /tmp/example-repo-a for details.")
    _git_add(repo)

    sfn.apply(repo)

    assert "example-repo-a" not in (repo / "docs/notes.md").read_text()
    assert "Repo-A" in (repo / "docs/notes.md").read_text()


def test_apply_does_not_match_substring_of_larger_token(repo: Path) -> None:
    # "example-repo-a" must not match inside an unrelated longer word.
    _write(repo, "docs/notes.md", "notexample-repo-astuff should be untouched.")
    _git_add(repo)

    sfn.apply(repo)

    text = (repo / "docs/notes.md").read_text()
    assert "Repo-A" not in text


def test_apply_prefers_longest_match(repo: Path) -> None:
    # "example-repo-c.help" must win over the shorter "example-repo-c" when
    # both are present at the same position.
    _write(repo, "docs/notes.md", "the example-repo-c.help project")
    _git_add(repo)

    sfn.apply(repo)

    text = (repo / "docs/notes.md").read_text()
    assert "Repo-D" in text
    assert "Repo-C" not in text
    assert "example-repo-c" not in text


def test_apply_replaces_bare_name_when_not_the_extended_form(repo: Path) -> None:
    _write(repo, "docs/notes.md", "the example-repo-c project, not the extended one")
    _git_add(repo)

    sfn.apply(repo)

    text = (repo / "docs/notes.md").read_text()
    assert "Repo-C" in text
    assert "example-repo-c" not in text


# ---------------------------------------------------------------------------
# Domain-context exclusion (INFRA-394 review finding)
# ---------------------------------------------------------------------------

def test_apply_skips_email_address_context(repo: Path) -> None:
    _write(
        repo,
        "README.md",
        "Contact: operator@example-repo-a.com\n"
        "Repo dir: /tmp/example-repo-a\n",
    )
    _git_add(repo)

    sfn.apply(repo)

    text = (repo / "README.md").read_text()
    assert "operator@example-repo-a.com" in text  # untouched
    assert "/tmp/Repo-A" in text  # genuine directory mention IS anonymized


def test_apply_skips_url_host_context(repo: Path) -> None:
    _write(
        repo,
        "tests/fixture.schema.json",
        '{"$id": "https://flex.example-repo-a.com/schemas/thing/v1"}\n',
    )
    _git_add(repo)

    sfn.apply(repo)

    text = (repo / "tests/fixture.schema.json").read_text()
    assert "flex.example-repo-a.com" in text  # untouched


def test_apply_collision_case_all_three_forms_in_one_file(repo: Path) -> None:
    """Regression for the exact collision the prior attempt got wrong: an
    email address and a schema-URL host containing the mapped repo's
    basename survive unchanged, while a genuine directory reference to the
    same basename IS anonymized, all in the same file.
    """
    _write(
        repo,
        "README.md",
        "Contact: david@example-repo-a.com\n"
        'Schema: "https://flex.example-repo-a.com/schemas/next_action/v6"\n'
        "Repo directory: /tmp/example-repo-a\n",
    )
    _git_add(repo)

    sfn.apply(repo)

    text = (repo / "README.md").read_text()
    assert "david@example-repo-a.com" in text
    assert "https://flex.example-repo-a.com/schemas/next_action/v6" in text
    assert "/tmp/Repo-A" in text
    # No leftover bare occurrence of the real name outside the two excluded
    # domain contexts.
    lines = text.splitlines()
    assert "example-repo-a" not in lines[2]


# ---------------------------------------------------------------------------
# Case-variant coverage (real-world regression: sentence-initial capitalized
# and ALL-CAPS-acronym mentions of a real name survived a lowercase-only
# case-sensitive scrub)
# ---------------------------------------------------------------------------

def test_apply_replaces_capitalized_sentence_initial_mention(repo: Path) -> None:
    _write(
        repo,
        "docs/notes.md",
        "Example-repo-a's CLAUDE.build.md is the main beneficiary.",
    )
    _git_add(repo)

    sfn.apply(repo)

    text = (repo / "docs/notes.md").read_text()
    assert "example-repo-a" not in text.lower() or "Repo-A" in text
    assert "Example-repo-a" not in text
    assert "Repo-A" in text


def test_apply_replaces_all_caps_acronym_mention(repo: Path) -> None:
    _write(repo, "docs/notes.md", "vocabulary in EXAMPLE-REPO-A/EXAMPLE-REPO-B")
    _git_add(repo)

    sfn.apply(repo)

    text = (repo / "docs/notes.md").read_text()
    assert "EXAMPLE-REPO-A" not in text
    assert "EXAMPLE-REPO-B" not in text
    assert "Repo-A" in text
    assert "Repo-B" in text


def test_verify_catches_leftover_capitalized_mention(repo: Path) -> None:
    _write(repo, "docs/notes.md", "Example-repo-a is great.")
    _git_add(repo)

    # Deliberately not applied — verify must catch the capitalized form too.
    assert sfn.verify(repo) == 1


# ---------------------------------------------------------------------------
# Vendored-path exclusion (real-world regression: a short real name like
# a short real name collided with an unrelated token inside checked-in
# node_modules)
# ---------------------------------------------------------------------------

def test_apply_skips_vendored_node_modules(repo: Path) -> None:
    _write(
        repo,
        "skills/observability/node_modules/some-pkg/fixture.js",
        "const x = { id: 'example-repo-a' }",
    )
    _git_add(repo)

    sfn.apply(repo)

    text = (repo / "skills/observability/node_modules/some-pkg/fixture.js").read_text()
    assert "example-repo-a" in text  # untouched — vendored content


def test_verify_skips_vendored_node_modules(repo: Path) -> None:
    _write(
        repo,
        "skills/observability/node_modules/some-pkg/fixture.js",
        "const x = { id: 'example-repo-a' }",
    )
    _git_add(repo)

    assert sfn.verify(repo) == 0


# ---------------------------------------------------------------------------
# Protected-path exclusion (real-world regression: the scrub mutated
# lessons/lessons.json, a protected_paths entry per CLAUDE.build.md, and its
# auto-generated lessons/LESSONS.md rendering)
# ---------------------------------------------------------------------------

def _write_build_md(root: Path, protected_paths: str) -> None:
    _write(
        root,
        "CLAUDE.build.md",
        "**Build standards**: "
        f"protected_paths=`{protected_paths}` | test_command=`pytest`\n",
    )


def test_apply_skips_protected_path_entry(repo: Path) -> None:
    _write_build_md(repo, "lessons/lessons.json, hooks/")
    _write(repo, "lessons/lessons.json", '{"trigger": "example-repo-a issue"}')
    _git_add(repo)

    sfn.apply(repo)

    text = (repo / "lessons/lessons.json").read_text()
    assert "example-repo-a" in text  # untouched — protected_paths entry


def test_apply_skips_protected_directory_prefix(repo: Path) -> None:
    _write_build_md(repo, "hooks/")
    _write(repo, "hooks/some_hook.py", "# example-repo-a reference\n")
    _git_add(repo)

    sfn.apply(repo)

    text = (repo / "hooks/some_hook.py").read_text()
    assert "example-repo-a" in text  # untouched — under protected hooks/


def test_apply_skips_generated_lessons_md(repo: Path) -> None:
    _write_build_md(repo, "lessons/lessons.json")
    _write(repo, "lessons/LESSONS.md", "## L001 — example-repo-a issue\n")
    _git_add(repo)

    sfn.apply(repo)

    text = (repo / "lessons/LESSONS.md").read_text()
    assert "example-repo-a" in text  # untouched — generated from protected json


def test_verify_skips_protected_paths(repo: Path) -> None:
    _write_build_md(repo, "lessons/lessons.json")
    _write(repo, "lessons/lessons.json", '{"trigger": "example-repo-a issue"}')
    _git_add(repo)

    assert sfn.verify(repo) == 0


def test_apply_scrubs_non_protected_files_normally_when_build_md_present(repo: Path) -> None:
    _write_build_md(repo, "hooks/")
    _write(repo, "docs/notes.md", "See /tmp/example-repo-a for details.")
    _git_add(repo)

    sfn.apply(repo)

    assert "Repo-A" in (repo / "docs/notes.md").read_text()


def test_read_protected_paths_absent_build_md_returns_empty(tmp_path: Path) -> None:
    assert sfn._read_protected_paths(tmp_path) == ()


def test_read_protected_paths_none_value_returns_empty(repo: Path) -> None:
    _write_build_md(repo, "(none)")
    assert sfn._read_protected_paths(repo) == ()


# ---------------------------------------------------------------------------
# Verify mode
# ---------------------------------------------------------------------------

def test_verify_clean_after_apply(repo: Path) -> None:
    _write(repo, "docs/notes.md", "See /tmp/example-repo-a for details.")
    _git_add(repo)

    sfn.apply(repo)
    _git_add(repo)

    assert sfn.verify(repo) == 0


def test_verify_reports_remaining_hits(repo: Path) -> None:
    _write(repo, "docs/notes.md", "See /tmp/example-repo-a for details.")
    _git_add(repo)

    # Deliberately do not apply — verify should catch the un-scrubbed name.
    assert sfn.verify(repo) == 1


def test_verify_skips_excluded_domain_context(repo: Path) -> None:
    _write(repo, "README.md", "Contact: david@example-repo-a.com\n")
    _git_add(repo)

    assert sfn.verify(repo) == 0


def test_verify_missing_local_config_exits_zero_with_message(tmp_path: Path, capsys) -> None:
    _init_git_repo(tmp_path)
    _write(tmp_path, "docs/notes.md", "nothing to scrub here")
    _git_add(tmp_path)

    assert sfn.verify(tmp_path) == 0
    captured = capsys.readouterr()
    assert "no local fleet config found" in captured.out


def test_apply_missing_local_config_is_noop(tmp_path: Path, capsys) -> None:
    _init_git_repo(tmp_path)
    p = _write(tmp_path, "docs/notes.md", "nothing to scrub here")
    _git_add(tmp_path)

    changed = sfn.apply(tmp_path)

    assert changed == 0
    assert p.read_text() == "nothing to scrub here"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_apply_is_idempotent(repo: Path) -> None:
    _write(repo, "docs/notes.md", "See /tmp/example-repo-a and /tmp/example-repo-c.help too.")
    _git_add(repo)

    first_changed = sfn.apply(repo)
    _git_add(repo)
    after_first = (repo / "docs/notes.md").read_text()

    second_changed = sfn.apply(repo)
    after_second = (repo / "docs/notes.md").read_text()

    assert first_changed == 1
    assert second_changed == 0
    assert after_first == after_second


def test_apply_idempotent_on_already_anonymized_text(repo: Path) -> None:
    # Re-running apply on text that already uses the anonymized labels
    # (never contains the real names) must make no further changes.
    already_scrubbed = "See Repo-A and Repo-D for details, contact david@example-repo-a.com."
    _write(repo, "docs/notes.md", already_scrubbed)
    _git_add(repo)

    changed = sfn.apply(repo)

    assert changed == 0
    assert (repo / "docs/notes.md").read_text() == already_scrubbed


# ---------------------------------------------------------------------------
# No real repo name literal in this test file or the script itself
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Lessons-scoped mode (CER-173)
# ---------------------------------------------------------------------------

FAKE_LESSONS_DATA = {
    "lessons": [
        {
            "id": "L001",
            "date": "2026-04-20",
            "source_project": "flex",
            "trigger": "Ran audit against example-repo-a — a project with pairmode scaffold",
            "problem": "Something went wrong in example-repo-a's config.",
            "learning": "Fix the config.",
            "methodology_change": {
                "affects": ["audit.py"],
                "description": "Add a warning referencing example-repo-a's setup.",
            },
            "applies_to": ["all"],
            "status": "applied",
            "enforced_by": "lint",
        },
        {
            "id": "L002",
            "date": "2026-04-21",
            "source_project": "flex",
            "trigger": "Unrelated trigger with no fleet name",
            "problem": "No mention here.",
            "learning": "Nothing to scrub in this entry.",
            "methodology_change": {
                "affects": ["other.py"],
                "description": "No name here either.",
            },
            "applies_to": ["all"],
            "status": "applied",
            "enforced_by": "lint",
            "value_framing": "efficiency ratio unaffected by example-repo-a mention? no.",
            "validation_phase": "3",
        },
    ]
}


def _write_lessons_fixture(root: Path, data: dict) -> None:
    _write(root, "lessons/lessons.json", json.dumps(data, indent=2) + "\n")


@pytest.fixture
def lessons_repo(tmp_path: Path) -> Path:
    _init_git_repo(tmp_path)
    _write(tmp_path, ".pairmode-fleet.local.json", json.dumps(FAKE_MAP))
    _write_lessons_fixture(tmp_path, json.loads(json.dumps(FAKE_LESSONS_DATA)))
    _git_add(tmp_path)
    return tmp_path


def test_apply_lessons_substitutes_matched_free_text_fields(lessons_repo: Path) -> None:
    sfn.apply_lessons(lessons_repo)

    data = json.loads((lessons_repo / "lessons/lessons.json").read_text())
    l001 = data["lessons"][0]
    assert "example-repo-a" not in l001["trigger"]
    assert "Repo-A" in l001["trigger"]
    assert "example-repo-a" not in l001["problem"]
    assert "Repo-A" in l001["problem"]
    assert "example-repo-a" not in l001["methodology_change"]["description"]
    assert "Repo-A" in l001["methodology_change"]["description"]


def test_apply_lessons_leaves_unmatched_entry_unchanged(lessons_repo: Path) -> None:
    sfn.apply_lessons(lessons_repo)

    data = json.loads((lessons_repo / "lessons/lessons.json").read_text())
    l002 = data["lessons"][1]
    assert l002["trigger"] == FAKE_LESSONS_DATA["lessons"][1]["trigger"]
    assert l002["learning"] == FAKE_LESSONS_DATA["lessons"][1]["learning"]


def test_apply_lessons_preserves_structural_fields(lessons_repo: Path) -> None:
    before = json.loads((lessons_repo / "lessons/lessons.json").read_text())

    sfn.apply_lessons(lessons_repo)

    after = json.loads((lessons_repo / "lessons/lessons.json").read_text())

    assert len(after["lessons"]) == len(before["lessons"])
    assert [e["id"] for e in after["lessons"]] == [e["id"] for e in before["lessons"]]
    for b, a in zip(before["lessons"], after["lessons"]):
        assert b["date"] == a["date"]
        assert b["status"] == a["status"]
        assert b["enforced_by"] == a["enforced_by"]
        assert b["applies_to"] == a["applies_to"]
        assert b["methodology_change"]["affects"] == a["methodology_change"]["affects"]
        assert b.get("validation_phase") == a.get("validation_phase")


def test_apply_lessons_regenerates_lessons_md(lessons_repo: Path) -> None:
    sfn.apply_lessons(lessons_repo)

    md_text = (lessons_repo / "lessons/LESSONS.md").read_text()
    assert "example-repo-a" not in md_text
    assert "Repo-A" in md_text


def test_verify_lessons_reports_zero_after_apply(lessons_repo: Path) -> None:
    sfn.apply_lessons(lessons_repo)

    assert sfn.verify_lessons(lessons_repo) == 0


def test_verify_lessons_reports_nonzero_before_apply(lessons_repo: Path) -> None:
    assert sfn.verify_lessons(lessons_repo) == 1


def test_apply_lessons_missing_local_config_is_noop(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_lessons_fixture(tmp_path, json.loads(json.dumps(FAKE_LESSONS_DATA)))
    _git_add(tmp_path)

    before = (tmp_path / "lessons/lessons.json").read_text()
    changed = sfn.apply_lessons(tmp_path)
    after = (tmp_path / "lessons/lessons.json").read_text()

    assert changed == 0
    assert before == after


def test_apply_lessons_general_apply_still_excludes_lessons_json(lessons_repo: Path) -> None:
    """The general apply()/verify() loop must remain unchanged by this
    story: lessons/lessons.json stays excluded from it (CLAUDE.build.md
    protected_paths), even though the repo fixture has no CLAUDE.build.md
    (falling back to the hardcoded _GENERATED_FROM_PROTECTED exclusion for
    LESSONS.md only) — so exercise the exclusion explicitly via a
    CLAUDE.build.md declaring lessons/lessons.json as protected.
    """
    _write(
        lessons_repo,
        "CLAUDE.build.md",
        "**Build standards**: protected_paths=`lessons/lessons.json` | test_command=`pytest`\n",
    )
    _git_add(lessons_repo)

    before = (lessons_repo / "lessons/lessons.json").read_text()
    sfn.apply(lessons_repo)
    after = (lessons_repo / "lessons/lessons.json").read_text()

    assert before == after


def test_script_source_contains_no_real_fleet_name() -> None:
    """Structural guard: the script must source all real names from the
    runtime-loaded local config, never as a hardcoded literal."""
    source = (_SCRIPTS_DIR / "scrub_fleet_names.py").read_text()
    # Sanity check that the loader pattern (mirrored from INFRA-393) is used
    # so real names are sourced only from the runtime-loaded local config.
    assert "_load_local_fleet_map" in source
    assert ".pairmode-fleet.local.json" in source


# ---------------------------------------------------------------------------
# Map/disk reconciliation (Ensures 1/2, INFRA-400)
# ---------------------------------------------------------------------------

def _write_map(root: Path, fleet_map: dict) -> None:
    _write(root, ".pairmode-fleet.local.json", json.dumps(fleet_map))


def _make_fake_repo_dir(root: Path, name: str) -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / ".git").mkdir()
    return d


def test_reconcile_fails_when_a_sibling_repo_is_unmapped(tmp_path: Path) -> None:
    fleet_root = tmp_path / "fleet"
    fleet_root.mkdir()
    _make_fake_repo_dir(fleet_root, "Fakeproject-X")
    _make_fake_repo_dir(fleet_root, "Fakeproject-Y")

    project_root = fleet_root / "flex"
    project_root.mkdir()
    _init_git_repo(project_root)
    _write_map(
        project_root,
        {
            "_fleet_root": str(fleet_root),
            "Repo-X": str(fleet_root / "Fakeproject-X"),
        },
    )
    _git_add(project_root)

    assert sfn.verify(project_root) == 1


def test_reconcile_passes_when_map_covers_every_sibling(tmp_path: Path) -> None:
    fleet_root = tmp_path / "fleet"
    fleet_root.mkdir()
    _make_fake_repo_dir(fleet_root, "Fakeproject-X")
    _make_fake_repo_dir(fleet_root, "Fakeproject-Y")

    project_root = fleet_root / "flex"
    project_root.mkdir()
    _init_git_repo(project_root)
    _write_map(
        project_root,
        {
            "_fleet_root": str(fleet_root),
            "Repo-X": str(fleet_root / "Fakeproject-X"),
            "Repo-Y": str(fleet_root / "Fakeproject-Y"),
        },
    )
    _git_add(project_root)

    assert sfn.verify(project_root) == 0


def test_reconcile_failure_names_count_and_unmapped_path_only(
    tmp_path: Path, capsys
) -> None:
    fleet_root = tmp_path / "fleet"
    fleet_root.mkdir()
    unmapped_dir = _make_fake_repo_dir(fleet_root, "Fakeproject-X")

    project_root = fleet_root / "flex"
    project_root.mkdir()
    _init_git_repo(project_root)
    _write_map(project_root, {"_fleet_root": str(fleet_root)})
    _git_add(project_root)

    assert sfn.verify(project_root) == 1
    captured = capsys.readouterr()
    assert "1 unmapped" in captured.err
    assert str(unmapped_dir) in captured.err


def test_reconcile_not_a_silent_warning_while_still_exiting_zero(
    tmp_path: Path,
) -> None:
    """Forbidden-proxy guard (Ensures 1): an unmapped sibling must fail the
    run, never just print a warning while still returning 0."""
    fleet_root = tmp_path / "fleet"
    fleet_root.mkdir()
    _make_fake_repo_dir(fleet_root, "Fakeproject-X")

    project_root = fleet_root / "flex"
    project_root.mkdir()
    _init_git_repo(project_root)
    _write_map(project_root, {"_fleet_root": str(fleet_root)})
    _git_add(project_root)

    result = sfn.verify(project_root)
    assert result != 0


def test_reconcile_skipped_with_stderr_notice_when_map_absent(
    tmp_path: Path, capsys
) -> None:
    fleet_root = tmp_path / "fleet"
    fleet_root.mkdir()
    _make_fake_repo_dir(fleet_root, "Fakeproject-X")

    project_root = fleet_root / "flex"
    project_root.mkdir()
    _init_git_repo(project_root)
    _write(project_root, "docs/notes.md", "nothing to scrub")
    _git_add(project_root)

    # No .pairmode-fleet.local.json at all — a clean clone. Must still exit 0.
    assert sfn.verify(project_root) == 0


# ---------------------------------------------------------------------------
# Leak-free hit reporting (Ensures 5, INFRA-400)
# ---------------------------------------------------------------------------

def test_verify_hit_report_never_embeds_the_matched_literal(
    repo: Path, capsys
) -> None:
    _write(repo, "docs/notes.md", "See /tmp/example-repo-a for details.")
    _git_add(repo)

    exit_code = sfn.verify(repo)

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert exit_code == 1
    assert "example-repo-a" not in combined
    assert "Repo-A" in combined
    assert "docs/notes.md" in combined


def test_validate_one_to_one_error_never_embeds_either_real_name() -> None:
    collision = {"example-repo-x": "Repo-A", "example-repo-y": "Repo-A"}
    with pytest.raises(ValueError) as excinfo:
        sfn._validate_one_to_one(collision)
    message = str(excinfo.value)
    assert "example-repo-x" not in message
    assert "example-repo-y" not in message
    assert "Repo-A" in message


def test_verify_lessons_hit_report_never_embeds_the_matched_literal(
    lessons_repo: Path, capsys
) -> None:
    exit_code = sfn.verify_lessons(lessons_repo)

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert exit_code == 1
    assert "example-repo-a" not in combined
    assert "Repo-A" in combined


# ---------------------------------------------------------------------------
# Mechanical gate: git pre-commit hook (Ensures 6, INFRA-400)
# ---------------------------------------------------------------------------

def _run_hook(hook_path: Path, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(hook_path)], cwd=cwd, capture_output=True, text=True
    )


def test_install_hook_writes_executable_pre_commit(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    hook_path = sfn.install_hook(tmp_path)

    assert hook_path == tmp_path / ".git" / "hooks" / "pre-commit"
    assert hook_path.exists()
    assert hook_path.stat().st_mode & 0o111  # some execute bit set


def test_installed_hook_blocks_commit_on_failing_verify(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write(tmp_path, "docs/notes.md", "See /tmp/example-repo-a for details.")
    _write_map(tmp_path, FAKE_MAP)
    _git_add(tmp_path)

    hook_path = sfn.install_hook(tmp_path)
    result = _run_hook(hook_path, tmp_path)

    assert result.returncode != 0


def test_installed_hook_allows_commit_on_passing_verify(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    isolated_fleet_root = tmp_path / "_isolated_fleet_root"
    isolated_fleet_root.mkdir()
    _write(tmp_path, "docs/notes.md", "nothing to scrub here")
    _write_map(tmp_path, {**FAKE_MAP, "_fleet_root": str(isolated_fleet_root)})
    _git_add(tmp_path)

    hook_path = sfn.install_hook(tmp_path)
    result = _run_hook(hook_path, tmp_path)

    assert result.returncode == 0


def test_install_hook_is_not_a_silent_warning(tmp_path: Path) -> None:
    """Forbidden-proxy guard (Ensures 6): the generated hook must actually
    fail the commit, never just print a warning while exiting 0."""
    _init_git_repo(tmp_path)
    _write(tmp_path, "docs/notes.md", "See /tmp/example-repo-a for details.")
    _write_map(tmp_path, FAKE_MAP)
    _git_add(tmp_path)

    hook_path = sfn.install_hook(tmp_path)
    result = _run_hook(hook_path, tmp_path)

    assert result.returncode != 0
