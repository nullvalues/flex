"""
model_selector.py — Deterministic model selection for reviewer-class agents.

Public API:

  select_reviewer_model(story_class, attempt_number, phase_id=None,
                        project_dir=None) -> str

    Returns "sonnet" or "opus" for the reviewer agent given the story's class
    and the current attempt number.

    Selection table:

      story_class   attempt=1   attempt>=2
      -----------   ---------   ----------
      code          sonnet      opus
      doc           sonnet      sonnet
      lesson        sonnet      sonnet
      methodology   sonnet      sonnet (upgrade to opus if a same-phase code
                                        story exists — requires phase_id and
                                        project_dir)

    For methodology stories on attempt >= 2: the helper checks the phase
    manifest for any code story (story_class="code", or absent which defaults
    to "code"). If found, returns "opus"; otherwise "sonnet".

  Unknown story_class values default to the "code" rules (conservative).

  select_intent_reviewer_model(phase_class) -> str

    Returns "sonnet" or "opus" for the intent-reviewer checkpoint agent given
    the phase's class.

    Selection table:

      phase_class   model
      -----------   -----
      production    sonnet
      docs-only     sonnet
      pre-pr        opus

    Unknown/absent phase_class values default to "production" (sonnet).

  select_security_auditor_model(phase_class) -> str

    Returns "sonnet" or "opus" for the security-auditor checkpoint agent given
    the phase's class.

    Selection table:

      phase_class   model
      -----------   -----
      production    opus
      docs-only     sonnet
      pre-pr        opus

    Unknown/absent phase_class values default to "production" (opus).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow sibling imports when run directly or via sys.path insertion.
_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from schema_validator import DEFAULT_STORY_CLASS  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_SONNET = "sonnet"
MODEL_OPUS = "opus"

# story_class values that never upgrade to opus on retry
_ALWAYS_SONNET_CLASSES = frozenset({"doc", "lesson"})


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------


def select_reviewer_model(
    story_class: str,
    attempt_number: int,
    phase_id: str | None = None,
    project_dir: Path | str | None = None,
) -> str:
    """Return "sonnet" or "opus" for the reviewer agent.

    Args:
        story_class:    The story's class ("code", "doc", "lesson",
                        "methodology").  Unknown values are treated as "code".
        attempt_number: 1 for the first attempt, >=2 for retries.
        phase_id:       Optional phase identifier (e.g. "24").  Required for
                        the methodology same-phase-code-story check.
        project_dir:    Optional path to the project root.  Required when
                        phase_id is supplied and story files must be resolved.

    Returns:
        "sonnet" or "opus".
    """
    # Normalise / apply default
    if not story_class or story_class not in {"code", "doc", "lesson", "methodology"}:
        story_class = DEFAULT_STORY_CLASS  # "code"

    # Attempt 1 is always sonnet regardless of class
    if attempt_number <= 1:
        return MODEL_SONNET

    # attempt >= 2 — apply per-class rules
    if story_class in _ALWAYS_SONNET_CLASSES:
        return MODEL_SONNET

    if story_class == "code":
        return MODEL_OPUS

    # story_class == "methodology"
    # Stays sonnet unless a same-phase code story exists
    if phase_id is not None and project_dir is not None:
        if _phase_has_code_story(phase_id, Path(project_dir)):
            return MODEL_OPUS

    return MODEL_SONNET


# ---------------------------------------------------------------------------
# Checkpoint-agent model selection (phase_class-driven)
# ---------------------------------------------------------------------------

# Default phase_class when the field is absent from a phase manifest.
DEFAULT_PHASE_CLASS = "production"

# phase_class values
_VALID_PHASE_CLASSES = frozenset({"production", "docs-only", "pre-pr"})


def select_intent_reviewer_model(phase_class: str) -> str:
    """Return "sonnet" or "opus" for the intent-reviewer checkpoint agent.

    Selection table:

      phase_class   model
      -----------   -----
      production    sonnet
      docs-only     sonnet
      pre-pr        opus

    Unknown/absent values default to "production" (sonnet).
    """
    if not phase_class or phase_class not in _VALID_PHASE_CLASSES:
        phase_class = DEFAULT_PHASE_CLASS

    if phase_class == "pre-pr":
        return MODEL_OPUS
    # production and docs-only both use sonnet
    return MODEL_SONNET


def select_security_auditor_model(phase_class: str) -> str:
    """Return "sonnet" or "opus" for the security-auditor checkpoint agent.

    Selection table:

      phase_class   model
      -----------   -----
      production    opus
      docs-only     sonnet
      pre-pr        opus

    Unknown/absent values default to "production" (opus).
    """
    if not phase_class or phase_class not in _VALID_PHASE_CLASSES:
        phase_class = DEFAULT_PHASE_CLASS

    if phase_class == "docs-only":
        return MODEL_SONNET
    # production and pre-pr both use opus
    return MODEL_OPUS


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _phase_has_code_story(phase_id: str, project_dir: Path) -> bool:
    """Return True if any story in the phase has story_class "code" (or absent).

    Looks up the phase manifest at docs/phases/phase-{phase_id}.md (or
    docs/phases/{phase_id}.md if the canonical path does not exist).
    Reads each story file's frontmatter to check story_class.

    Returns False on any I/O or parse error (fail-safe: no upgrade).
    """
    # Import here to avoid circular-import risk; both are sibling modules.
    try:
        import story_resolver as _sr
        import schema_validator as _sv
    except ImportError:
        # sys.path should already include _SCRIPTS_DIR; this is a safety net.
        return False

    # Locate the phase manifest
    phase_path = _find_phase_file(phase_id, project_dir)
    if phase_path is None:
        return False

    try:
        story_ids = _sr.list_phase_stories(phase_path)
    except Exception:
        return False

    for story_id in story_ids:
        try:
            story = _sr.resolve_story(story_id, project_dir)
        except Exception:
            continue

        # Read story_class from the story file's raw frontmatter
        story_path = (
            project_dir
            / "docs"
            / "stories"
            / story["rail"]
            / f"{story_id}.md"
        )
        try:
            text = story_path.read_text(encoding="utf-8")
            fm = _sv._parse_frontmatter(text)
            sc = (fm or {}).get("story_class", DEFAULT_STORY_CLASS)
        except Exception:
            sc = DEFAULT_STORY_CLASS

        if sc == "code":
            return True

    return False


def _find_phase_file(phase_id: str, project_dir: Path) -> Path | None:
    """Return the path to the phase manifest, or None if not found."""
    # Canonical naming: docs/phases/phase-{phase_id}.md
    canonical = project_dir / "docs" / "phases" / f"phase-{phase_id}.md"
    if canonical.exists():
        return canonical

    # Fallback: docs/phases/{phase_id}.md
    fallback = project_dir / "docs" / "phases" / f"{phase_id}.md"
    if fallback.exists():
        return fallback

    return None
