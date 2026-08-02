"""Tests for documentation file existence and constraints."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_readme_exists_and_under_400_lines() -> None:
    readme = Path(__file__).resolve().parent.parent.parent / "README.md"
    assert readme.exists(), "README.md does not exist at repo root"
    lines = readme.read_text(encoding="utf-8").splitlines()
    assert len(lines) < 400, f"README.md has {len(lines)} lines, must be under 400"


def test_pipe_architecture_doc_exists() -> None:
    pipe_doc = Path(__file__).resolve().parent.parent.parent / "docs" / "pipe-architecture.md"
    assert pipe_doc.exists(), "docs/pipe-architecture.md does not exist"


def test_pairmode_contribution_guide_exists() -> None:
    pairmode_doc = Path(__file__).resolve().parent.parent.parent / "docs" / "pairmode" / "PAIRMODE.md"
    assert pairmode_doc.exists(), "docs/pairmode/PAIRMODE.md does not exist"


def test_changelog_exists_and_under_200_lines() -> None:
    changelog = Path(__file__).resolve().parent.parent.parent / "CHANGELOG.md"
    assert changelog.exists(), "CHANGELOG.md does not exist at repo root"
    lines = changelog.read_text(encoding="utf-8").splitlines()
    assert len(lines) < 200, f"CHANGELOG.md has {len(lines)} lines, must be under 200"


def test_contributing_exists_and_under_200_lines() -> None:
    contributing = Path(__file__).resolve().parent.parent.parent / "CONTRIBUTING.md"
    assert contributing.exists(), "CONTRIBUTING.md does not exist at repo root"
    lines = contributing.read_text(encoding="utf-8").splitlines()
    assert len(lines) < 200, f"CONTRIBUTING.md has {len(lines)} lines, must be under 200"


def test_readme_contains_reactive_and_proactive_positioning() -> None:
    readme = Path(__file__).resolve().parent.parent.parent / "README.md"
    text = readme.read_text(encoding="utf-8").lower()
    assert "reactive" in text, "README.md must mention 'reactive' for companion/pairmode positioning"
    assert "proactive" in text, "README.md must mention 'proactive' for companion/pairmode positioning"


def test_readme_skills_table_has_posture_column() -> None:
    readme = Path(__file__).resolve().parent.parent.parent / "README.md"
    text = readme.read_text(encoding="utf-8")
    assert "Posture" in text, "README.md skills table must contain a 'Posture' column header"


def test_readme_under_400_lines() -> None:
    readme = Path(__file__).resolve().parent.parent.parent / "README.md"
    lines = readme.read_text(encoding="utf-8").splitlines()
    assert len(lines) < 400, f"README.md has {len(lines)} lines, must be under 400"


def test_pairmode_doc_contains_relation_to_companion_section() -> None:
    pairmode_doc = Path(__file__).resolve().parent.parent.parent / "docs" / "pairmode" / "PAIRMODE.md"
    text = pairmode_doc.read_text(encoding="utf-8").lower()
    assert "in relation to companion" in text, (
        "PAIRMODE.md must contain a 'Pairmode in relation to companion' section"
    )


# ---------------------------------------------------------------------------
# INFRA-305 Ensures 10 (CER-112) — durable skill-count parity.
#
# docs/brief.md and docs/reconstruction.md's "Flex is a Claude Code plugin
# with N skills:" prose must match the live skills/*/SKILL.md count so it
# cannot silently drift again (as it did when /flex:observability landed).
# ---------------------------------------------------------------------------

_SKILL_COUNT_WORDS = {3: "three", 4: "four", 5: "five", 6: "six"}


def test_skill_count_prose_matches_skill_dirs() -> None:
    skill_dirs = sorted(p.parent.name for p in (REPO_ROOT / "skills").glob("*/SKILL.md"))
    n = len(skill_dirs)
    # Anti-vacuity floor: a glob that matches nothing must fail this test,
    # not pass it vacuously.
    assert n >= 4, (
        f"expected at least 4 skill directories with a SKILL.md, found {n}: {skill_dirs} "
        "-- a glob matching nothing must fail, not pass"
    )
    assert n in _SKILL_COUNT_WORDS, f"no number-word mapping for skill count {n}"
    word = _SKILL_COUNT_WORDS[n]
    phrase = f"plugin with {word} skills"
    for doc_name in ("brief.md", "reconstruction.md"):
        doc_path = REPO_ROOT / "docs" / doc_name
        text = doc_path.read_text(encoding="utf-8").lower()
        assert phrase in text, (
            f"{doc_path} must contain the phrase {phrase!r} matching the live "
            f"skill count ({n} skills: {skill_dirs}) (CER-112)"
        )
        for skill_dir in skill_dirs:
            assert skill_dir in text, (
                f"{doc_path} must mention skill directory {skill_dir!r} at least once"
            )


# ---------------------------------------------------------------------------
# INFRA-349 — Docstring currency guard tests (CER-156)
#
# Prevents recurrence of misdescribed wiring claims in harness docstrings
# and comments. The guard tests assert the absence of specific stale phrases
# that were corrected, so a future re-introduction is caught immediately.
# ---------------------------------------------------------------------------

_STALE_WIRING_PHRASES: dict[str, tuple[str, ...]] = {
    "skills/pairmode/scripts/flex_build.py": (
        "Advisory only",
        "not wired into the live",
        "_is_fresh_phase",
    ),
    ".claude/agents/spec-writer.md": ("select_spec_writer_model tier exists yet",),
    ".claude/agents/docs-reviewer.md": (
        "select_docs_reviewer_model exists yet",
        "checkpoint-docs currently resolves with model=None",
    ),
}


def test_harness_docstrings_have_no_stale_wiring_claims() -> None:
    for rel_path, phrases in _STALE_WIRING_PHRASES.items():
        text = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        for phrase in phrases:
            assert phrase not in text, (
                f"{rel_path} contains stale wiring claim {phrase!r} (CER-156, INFRA-349) — "
                "the comment describes a prior or aspirational state, not the shipped one"
            )


def test_model_selector_functions_named_in_agent_shells_exist() -> None:
    # Extract select_*_model identifiers from agent shell files
    agent_files = [
        REPO_ROOT / ".claude/agents/spec-writer.md",
        REPO_ROOT / ".claude/agents/docs-reviewer.md",
    ]

    extracted_selectors = set()
    for agent_file in agent_files:
        text = agent_file.read_text(encoding="utf-8")
        matches = re.findall(r"select_\w+_model", text)
        extracted_selectors.update(matches)

    # Verify each extracted selector exists in model_selector.py
    model_selector_path = REPO_ROOT / "skills/pairmode/scripts/model_selector.py"
    model_selector_text = model_selector_path.read_text(encoding="utf-8")

    for selector_name in extracted_selectors:
        def_pattern = f"def {selector_name}("
        assert def_pattern in model_selector_text, (
            f"Agent shell files reference {selector_name!r} but it is not defined in "
            f"skills/pairmode/scripts/model_selector.py — update the agent shell comment "
            f"or wire the missing function"
        )
