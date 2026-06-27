"""
tests/pairmode/resolver_fixtures.py

Synthetic durable-state fixture-tree builder for next-action resolver tests.

Provides ``make_resolver_project`` — a single entry point that constructs a
fully-wired synthetic project tree in a tmp dir, parameterised by a declarative
config dict that can realise any of the 9 DP2 resolver states.

The helper is designed as test infrastructure only.  It has no imports from
production code beyond what is needed to construct the on-disk artifacts it
creates.

Usage example
-------------
    from resolver_fixtures import make_resolver_project

    def test_something(tmp_path):
        project = make_resolver_project(tmp_path, {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": [],       # no commits yet
            "stub_story": False,
            "auth_gated": False,
            "schema_introduces": False,
        })
        # project is the Path to the synthetic project root

Config keys
-----------
phase_status    : str         "active" | "complete" — phase index status
stories         : list of (story_id, table_status, story_class, primary_files)
                  If empty the phase has no stories.
attempt_count   : int         Counter to write into attempt_counter.json (for
                               the *first* story in the list).
git_commits     : list[str]   Commit messages to inject (as empty commits in a
                               seeded git repo).  Use "story-<ID>" patterns to
                               simulate reviewer commits.
stub_story      : bool        If True, the first story body uses delegation
                               language ("See phase doc for details").
auth_gated      : bool        auth_gated: true in the first story's frontmatter.
schema_introduces: bool       schema_introduces: true in the first story's
                               frontmatter.
state_json      : dict | None Extra keys to merge into .companion/state.json.
                               If None a minimal state.json is written.
phase_ref       : str         Phase identifier string (default "1").
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def make_resolver_project(tmp_path: Path, cfg: dict) -> Path:
    """Build a synthetic project tree rooted at ``tmp_path`` and return it.

    The function seeds a git repo, writes docs/phases/index.md,
    docs/phases/phase-{ref}.md, story files, .companion/attempt_counter.json,
    and .companion/state.json — exactly the durable-state surfaces that
    ``infer_position`` reads.
    """
    project = tmp_path / "project"
    project.mkdir()

    phase_ref: str = cfg.get("phase_ref", "1")
    phase_status: str = cfg.get("phase_status", "active")
    stories: list = cfg.get("stories", [])
    attempt_count: int = cfg.get("attempt_count", 0)
    git_commits: list[str] = cfg.get("git_commits", [])
    stub_story: bool = cfg.get("stub_story", False)
    auth_gated: bool = cfg.get("auth_gated", False)
    schema_introduces: bool = cfg.get("schema_introduces", False)
    state_extra: dict = cfg.get("state_json") or {}

    # ------------------------------------------------------------------
    # Git repo initialisation (matching test_next_story.py pattern)
    # ------------------------------------------------------------------
    subprocess.run(["git", "init", "-q"], cwd=str(project), check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(project), check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(project), check=True,
    )
    # Initial commit so git log is functional
    (project / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(project), check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "initial"],
        cwd=str(project), check=True,
    )

    # ------------------------------------------------------------------
    # Inject any additional commits
    # ------------------------------------------------------------------
    for msg in git_commits:
        subprocess.run(
            ["git", "commit", "-q", "--allow-empty", "-m", msg],
            cwd=str(project), check=True,
        )

    # ------------------------------------------------------------------
    # Phase index
    # ------------------------------------------------------------------
    phases_dir = project / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)

    index_lines = [
        "# Phase Index\n\n",
        "| Phase | Title | Status | Tag |\n",
        "|-------|-------|--------|-----|\n",
        f"| {phase_ref} | Test Phase | {phase_status} | |\n",
    ]
    (phases_dir / "index.md").write_text("".join(index_lines), encoding="utf-8")

    # ------------------------------------------------------------------
    # Phase manifest (Stories table)
    # ------------------------------------------------------------------
    phase_lines = [
        f"# Phase {phase_ref}\n\n",
        "## Stories\n\n",
        "| ID | Title | Status |\n",
        "|----|-------|--------|\n",
    ]
    for story_id, table_status, _sc, _pf in stories:
        phase_lines.append(f"| {story_id} | A story | {table_status} |\n")
    (phases_dir / f"phase-{phase_ref}.md").write_text(
        "".join(phase_lines), encoding="utf-8"
    )

    # ------------------------------------------------------------------
    # Story files
    # ------------------------------------------------------------------
    for i, (story_id, _table_status, story_class, primary_files) in enumerate(stories):
        rail = story_id.split("-", 1)[0]
        story_dir = project / "docs" / "stories" / rail
        story_dir.mkdir(parents=True, exist_ok=True)

        # Only the first story gets the auth/schema/stub overrides
        is_first = i == 0
        story_auth_gated = auth_gated if is_first else False
        story_schema_introduces = schema_introduces if is_first else False
        story_stub = stub_story if is_first else False

        if primary_files:
            pf_yaml = "primary_files:\n" + "".join(
                f"  - {f}\n" for f in primary_files
            )
        else:
            pf_yaml = "primary_files: []\n"

        if story_stub:
            body = "See phase doc for details.\n"
        else:
            body = "## Ensures\n\n- It works.\n"

        content = (
            f"---\n"
            f"id: {story_id}\n"
            f"rail: {rail}\n"
            f"status: planned\n"
            f"phase: '{phase_ref}'\n"
            f"story_class: {story_class}\n"
            f"{pf_yaml}"
            f"auth_gated: {'true' if story_auth_gated else 'false'}\n"
            f"schema_introduces: {'true' if story_schema_introduces else 'false'}\n"
            f"---\n\n"
            f"{body}"
        )
        (story_dir / f"{story_id}.md").write_text(content, encoding="utf-8")

    # ------------------------------------------------------------------
    # .companion directory
    # ------------------------------------------------------------------
    companion = project / ".companion"
    companion.mkdir(exist_ok=True)

    # attempt_counter.json — write only if there are stories and count > 0
    if stories and attempt_count > 0:
        first_story_id = stories[0][0]
        (companion / "attempt_counter.json").write_text(
            json.dumps({"story_id": first_story_id, "attempt_count": attempt_count}),
            encoding="utf-8",
        )

    # state.json
    state: dict = {"pairmode_version": "1.0"}
    state.update(state_extra)
    (companion / "state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )

    return project
