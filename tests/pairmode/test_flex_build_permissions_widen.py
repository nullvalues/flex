"""Tests for flex_build.py permissions-widen subcommand (INFRA-320 § B)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from flex_build import (  # type: ignore[import]  # noqa: E402
    PermissionsWidenError,
    flex_build,
    widen_story_scope,
)
from schema_validator import _parse_frontmatter  # type: ignore[import]  # noqa: E402


def _make_story(
    tmp_path: Path,
    story_id: str,
    primary_files=None,
    touches=None,
    phase: str = "99",
    body: str = "## Requires\n\nNothing.\n\n## Ensures\n\n- Always true.\n",
) -> Path:
    rail = story_id.split("-")[0]
    story_dir = tmp_path / "docs" / "stories" / rail
    story_dir.mkdir(parents=True, exist_ok=True)
    story_file = story_dir / f"{story_id}.md"

    pf_yaml = ""
    if primary_files is not None:
        items = "\n".join(f"  - {p}" for p in primary_files)
        pf_yaml = f"primary_files:\n{items}\n"

    touches_yaml = ""
    if touches is not None:
        items = "\n".join(f"  - {p}" for p in touches)
        touches_yaml = f"touches:\n{items}\n"

    content = (
        "---\n"
        f"id: {story_id}\n"
        f"rail: {rail}\n"
        "title: Test story\n"
        "status: planned\n"
        f'phase: "{phase}"\n'
        f"{pf_yaml}"
        f"{touches_yaml}"
        "---\n\n"
        f"{body}"
    )
    story_file.write_text(content, encoding="utf-8")
    return story_file


# ---------------------------------------------------------------------------
# B2 — refusal policy
# ---------------------------------------------------------------------------


def test_permissions_widen_requires_reason(tmp_path):
    """B1: a missing/empty --reason is a usage error (exit 2)."""
    runner = CliRunner()
    _make_story(tmp_path, "INFRA-900", primary_files=["a.py"])
    result = runner.invoke(
        flex_build,
        [
            "permissions-widen",
            "INFRA-900",
            "--path",
            "b.py",
            "--reason",
            "",
            "--project-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 2

    result2 = runner.invoke(
        flex_build,
        ["permissions-widen", "INFRA-900", "--path", "b.py", "--project-dir", str(tmp_path)],
    )
    assert result2.exit_code == 2


def test_permissions_widen_refuses_protected_path_naming_the_glob(tmp_path):
    """B2: a PROTECTED_GLOBS path is refused, the message names the matched
    glob, and nothing is written."""
    runner = CliRunner()
    story = _make_story(tmp_path, "INFRA-900", primary_files=["a.py"])
    before = story.read_text(encoding="utf-8")

    result = runner.invoke(
        flex_build,
        [
            "permissions-widen",
            "INFRA-900",
            "--path",
            "hooks/pre_tool_use.py",
            "--reason",
            "need it",
            "--project-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code != 0
    assert "hooks/**" in result.output
    assert story.read_text(encoding="utf-8") == before
    assert not (tmp_path / "docs" / "phases" / "permissions" / "INFRA-900.json").exists()


def test_permissions_widen_refuses_out_of_root_path(tmp_path):
    """B2: a --path resolving outside the project root is refused via
    resolve-then-relative_to containment, never a string startswith."""
    _make_story(tmp_path, "INFRA-900", primary_files=["a.py"])
    with pytest.raises(PermissionsWidenError, match="outside the project root"):
        widen_story_scope("INFRA-900", "../../etc/passwd", "need it", tmp_path)


def test_permissions_widen_refuses_unknown_story(tmp_path):
    with pytest.raises(PermissionsWidenError, match="not found"):
        widen_story_scope("INFRA-901", "b.py", "need it", tmp_path)


def test_permissions_widen_refuses_invalid_story_id(tmp_path):
    with pytest.raises(PermissionsWidenError, match="invalid story_id"):
        widen_story_scope("not-an-id", "b.py", "need it", tmp_path)


# ---------------------------------------------------------------------------
# B3 — successful widening
# ---------------------------------------------------------------------------


def test_permissions_widen_appends_block_style_touches_and_widening_row(tmp_path):
    story = _make_story(tmp_path, "INFRA-900", primary_files=["a.py"], touches=["b.py"])
    widen_story_scope("INFRA-900", "c.py", "need c.py for the fix", tmp_path)

    text = story.read_text(encoding="utf-8")
    assert "touches:\n  - b.py\n  - c.py\n" in text
    assert "## Scope widenings" in text
    assert "| c.py | need c.py for the fix |" in text


def test_permissions_widen_creates_touches_key_after_primary_files_when_absent(tmp_path):
    story = _make_story(tmp_path, "INFRA-900", primary_files=["a.py"], touches=None)
    widen_story_scope("INFRA-900", "c.py", "need it", tmp_path)
    text = story.read_text(encoding="utf-8")
    assert "primary_files:\n  - a.py\ntouches:\n  - c.py\n" in text


def test_permissions_widen_creates_scope_widenings_after_requires(tmp_path):
    story = _make_story(tmp_path, "INFRA-900", primary_files=["a.py"])
    widen_story_scope("INFRA-900", "c.py", "need it", tmp_path)
    text = story.read_text(encoding="utf-8")
    requires_idx = text.index("## Requires")
    widenings_idx = text.index("## Scope widenings")
    ensures_idx = text.index("## Ensures")
    assert requires_idx < widenings_idx < ensures_idx


def test_permissions_widen_appends_second_row_to_existing_section(tmp_path):
    story = _make_story(tmp_path, "INFRA-900", primary_files=["a.py"])
    widen_story_scope("INFRA-900", "c.py", "first reason", tmp_path)
    widen_story_scope("INFRA-900", "d.py", "second reason", tmp_path)
    text = story.read_text(encoding="utf-8")
    assert text.count("## Scope widenings") == 1
    assert "| c.py | first reason |" in text
    assert "| d.py | second reason |" in text


def test_permissions_widen_regenerates_artifact(tmp_path):
    _make_story(tmp_path, "INFRA-900", primary_files=["a.py"])
    widen_story_scope("INFRA-900", "c.py", "need it", tmp_path)
    out_path = tmp_path / "docs" / "phases" / "permissions" / "INFRA-900.json"
    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert "c.py" in data["allowed_paths"]


def test_permissions_widen_preserves_existing_touches_order(tmp_path):
    story = _make_story(
        tmp_path, "INFRA-900", primary_files=["a.py"], touches=["z.py", "y.py"]
    )
    widen_story_scope("INFRA-900", "new.py", "need it", tmp_path)
    text = story.read_text(encoding="utf-8")
    assert "touches:\n  - z.py\n  - y.py\n  - new.py\n" in text


# ---------------------------------------------------------------------------
# B4 — idempotent
# ---------------------------------------------------------------------------


def test_permissions_widen_is_idempotent_for_declared_path(tmp_path):
    story = _make_story(tmp_path, "INFRA-900", primary_files=["a.py"], touches=["b.py"])
    before = story.read_text(encoding="utf-8")
    message = widen_story_scope("INFRA-900", "b.py", "already declared", tmp_path)
    after = story.read_text(encoding="utf-8")
    assert "no-op" in message
    assert before == after
    assert "## Scope widenings" not in after


def test_permissions_widen_idempotent_for_primary_files_path(tmp_path):
    story = _make_story(tmp_path, "INFRA-900", primary_files=["a.py"])
    before = story.read_text(encoding="utf-8")
    message = widen_story_scope("INFRA-900", "a.py", "already declared", tmp_path)
    after = story.read_text(encoding="utf-8")
    assert "no-op" in message
    assert before == after


# ---------------------------------------------------------------------------
# B6 — standing path is a no-op
# ---------------------------------------------------------------------------


def test_permissions_widen_noop_for_standing_path(tmp_path):
    story = _make_story(tmp_path, "INFRA-900", primary_files=["a.py"])
    before = story.read_text(encoding="utf-8")
    message = widen_story_scope(
        "INFRA-900", "docs/cer/backlog.md", "filing a finding", tmp_path
    )
    after = story.read_text(encoding="utf-8")
    assert "standing" in message
    assert before == after
    assert "touches:" not in after or "docs/cer/backlog.md" not in after


# ---------------------------------------------------------------------------
# B5 — dry run
# ---------------------------------------------------------------------------


def test_permissions_widen_dry_run_writes_nothing(tmp_path):
    story = _make_story(tmp_path, "INFRA-900", primary_files=["a.py"], touches=["b.py"])
    before = story.read_text(encoding="utf-8")
    perm_path = tmp_path / "docs" / "phases" / "permissions" / "INFRA-900.json"
    assert not perm_path.exists()

    message = widen_story_scope(
        "INFRA-900", "c.py", "need it", tmp_path, dry_run=True
    )
    assert "DRY RUN" in message
    assert story.read_text(encoding="utf-8") == before
    assert not perm_path.exists()


# ---------------------------------------------------------------------------
# CLI registration and end-to-end
# ---------------------------------------------------------------------------


def test_permissions_widen_registered_on_flex_build_cli():
    assert "permissions-widen" in flex_build.commands


def test_permissions_widen_cli_end_to_end(tmp_path):
    runner = CliRunner()
    story = _make_story(tmp_path, "INFRA-900", primary_files=["a.py"])
    result = runner.invoke(
        flex_build,
        [
            "permissions-widen",
            "INFRA-900",
            "--path",
            "c.py",
            "--reason",
            "discovered mid-build",
            "--project-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "c.py" in result.output
    assert "c.py" in story.read_text(encoding="utf-8")


def _make_linked_worktree(main_root: Path, story_id: str) -> Path:
    """Mirror test_pre_tool_use_scope_guard.py's linked-worktree fixture: a
    ``.git`` *file* pointing back at a ``<main>/.git/worktrees/<id>`` gitdir,
    the shape `scope_guard._resolve_main_project_root` recognises."""
    worktree_dir = main_root / ".pairmode-worktrees" / story_id
    worktree_dir.mkdir(parents=True)
    git_worktrees_dir = main_root / ".git" / "worktrees" / story_id
    git_worktrees_dir.mkdir(parents=True)
    (worktree_dir / ".git").write_text(f"gitdir: {git_worktrees_dir}\n")
    return worktree_dir


def test_permissions_widen_from_worktree_edits_worktree_spec_and_main_artifact(
    tmp_path,
):
    """A widen call made from inside a linked story worktree (the shape a
    real builder's cwd takes) must: (1) edit the story spec in the
    WORKTREE — that copy is what gets committed and merged; (2) write the
    regenerated permissions artifact under the MAIN checkout root — the only
    place `scope_guard.check_path` ever reads it from, regardless of the
    caller's cwd."""
    main_root = tmp_path / "main"
    main_root.mkdir()
    worktree_dir = _make_linked_worktree(main_root, "INFRA-950")
    # A real worktree checkout mirrors the whole repo tree, including the
    # story file, at the commit the worktree branch was cut from.
    story_in_worktree = _make_story(worktree_dir, "INFRA-950", primary_files=["a.py"])

    widen_story_scope("INFRA-950", "c.py", "discovered mid-build", worktree_dir)

    # The worktree's own story spec carries the widened touches: entry.
    assert "c.py" in story_in_worktree.read_text(encoding="utf-8")

    # The artifact lands under the MAIN root, not a stray worktree-local copy.
    main_artifact = main_root / "docs" / "phases" / "permissions" / "INFRA-950.json"
    assert main_artifact.exists()
    data = json.loads(main_artifact.read_text())
    assert "c.py" in data["allowed_paths"]

    stray_artifact = (
        worktree_dir / "docs" / "phases" / "permissions" / "INFRA-950.json"
    )
    assert not stray_artifact.exists()


def test_permissions_widen_never_touches_settings_files(tmp_path):
    """B7: permissions-widen never touches .claude/settings*.json or
    state.json — only the named story spec and its permissions artifact."""
    settings_dir = tmp_path / ".claude"
    settings_dir.mkdir()
    settings_path = settings_dir / "settings.local.json"
    settings_path.write_text("{}\n", encoding="utf-8")
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir()
    state_path = companion_dir / "state.json"
    state_path.write_text("{}\n", encoding="utf-8")

    _make_story(tmp_path, "INFRA-900", primary_files=["a.py"])
    widen_story_scope("INFRA-900", "c.py", "need it", tmp_path)

    assert settings_path.read_text(encoding="utf-8") == "{}\n"
    assert state_path.read_text(encoding="utf-8") == "{}\n"


# ---------------------------------------------------------------------------
# CER-222/INFRA-415 — oracle-verified touches: writes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "widened_path",
    [
        "skills/pairmode/scripts/foo.py",
        "docs/some dir/notes.md",
        "skills/pairmode/scripts/pkg#1.py",
    ],
    ids=["plain-path", "space-bearing-path", "non-comment-hash-path"],
)
def test_permissions_widen_representable_paths_round_trip_in_touches(
    tmp_path, widened_path
):
    """CER-222 Ensures 2: a normal path, a space-bearing path, and a
    non-comment `#`-bearing path are all still written into touches:
    exactly as before this story, and recoverable byte-identical via the
    real frontmatter reader — not a quoted or otherwise mangled form."""
    story = _make_story(tmp_path, "INFRA-900", primary_files=["a.py"])
    widen_story_scope("INFRA-900", widened_path, "need it", tmp_path)

    text = story.read_text(encoding="utf-8")
    parsed = _parse_frontmatter(text)
    assert parsed["touches"] == [widened_path]


def test_permissions_widen_refuses_unrepresentable_path_writes_nothing(tmp_path):
    """CER-222 Ensures 3/4: a path containing both '\"' and \"'\" cannot be
    wrapped by either quote form this reader's literal-strip scheme
    supports, and (having a literal ' #' as well) doesn't round-trip bare
    either — so widen_story_scope must raise PermissionsWidenError naming
    the path, and must not write anything — not the story spec (no partial
    touches: write, no Scope widenings row) and not the permissions
    artifact (INFRA-314 forbidden-proxy: a write that merely fails a later
    validation pass is not acceptable)."""
    unrepresentable = "docs/note \"x'y #1.md"
    story = _make_story(tmp_path, "INFRA-900", primary_files=["a.py"])
    before = story.read_text(encoding="utf-8")
    artifact_path = tmp_path / "docs" / "phases" / "permissions" / "INFRA-900.json"

    with pytest.raises(PermissionsWidenError) as excinfo:
        widen_story_scope("INFRA-900", unrepresentable, "need it", tmp_path)
    assert "docs/note" in str(excinfo.value)

    assert story.read_text(encoding="utf-8") == before
    assert not artifact_path.exists()


def test_permissions_widen_refuses_unrepresentable_path_with_embedded_newline(
    tmp_path,
):
    """CER-222 Ensures 3: an embedded real newline is also unrepresentable
    as a single block-sequence-item line."""
    unrepresentable = "docs/weird\nname.md"
    story = _make_story(tmp_path, "INFRA-900", primary_files=["a.py"])
    before = story.read_text(encoding="utf-8")

    with pytest.raises(PermissionsWidenError):
        widen_story_scope("INFRA-900", unrepresentable, "need it", tmp_path)

    assert story.read_text(encoding="utf-8") == before


def test_permissions_widen_cli_refuses_unrepresentable_path(tmp_path):
    """CER-222 Ensures 5: the CLI surfaces PermissionsWidenError for an
    unrepresentable widened path the same way it surfaces every other
    refusal on this path — non-zero exit, message on stderr/output naming
    the path, never an uncaught traceback."""
    runner = CliRunner()
    unrepresentable = "docs/note \"x'y #1.md"
    story = _make_story(tmp_path, "INFRA-900", primary_files=["a.py"])
    before = story.read_text(encoding="utf-8")

    result = runner.invoke(
        flex_build,
        [
            "permissions-widen",
            "INFRA-900",
            "--path",
            unrepresentable,
            "--reason",
            "need it",
            "--project-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "docs/note" in result.output
    assert story.read_text(encoding="utf-8") == before
    assert not (
        tmp_path / "docs" / "phases" / "permissions" / "INFRA-900.json"
    ).exists()
