"""
model_selector.py — Deterministic model selection for reviewer-class agents.

Public API:

  select_reviewer_model(story_class, attempt_number, phase_id=None,
                        project_dir=None) -> tuple[str, str]

    Returns a (model, reason) tuple for the reviewer agent given the story's
    class and the current attempt number.

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

    Reason values:
      "auto-baseline"        — attempt 1 (all classes)
      "doc-class-baseline"   — doc or lesson class, any attempt >= 2
      "retry-upgrade"        — code class, attempt >= 2
      "methodology-upgrade"  — methodology, attempt >= 2, same-phase code story exists
      "methodology-baseline" — methodology, attempt >= 2, no same-phase code story

  Unknown story_class values default to the "code" rules (conservative).

  select_builder_model(story_class, primary_files, protected_files) -> (str, str)

    Returns a (model, reason) tuple for the builder agent given the story's
    class, the list of primary file paths, and the list of protected file paths.

    Decision table:

      story_class   complexity signal                           model   reason
      -----------   -----------------                           -----   ------
      doc           any                                         haiku   auto-downgrade
      lesson        any                                         haiku   auto-downgrade
      methodology   any                                         sonnet  auto-baseline
      code          <5 primary_files AND no protected file      sonnet  auto-baseline
      code          >=5 primary_files OR protected file in      opus    prompted-upgrade
                    touches

    If the caller has already received a user-override decision, it should
    pass the overridden model back through this function by using the return
    tuple, but the ``user-override`` reason is a distinct value the orchestrator
    records after the user has spoken — the function itself never returns
    ``user-override``.  Callers that receive a ``prompted-upgrade`` result must
    prompt the user; if the user downgrades, record ``user-override`` reason in
    the DB.

  select_intent_reviewer_model(phase_class) -> tuple[str, str]

    Returns a (model, reason) tuple for the intent-reviewer checkpoint agent
    given the phase's class.

    Selection table:

      phase_class   model   reason
      -----------   -----   ------
      production    sonnet  non-production-class
      docs-only     sonnet  non-production-class
      pre-pr        opus    production-class

    Unknown/absent phase_class values default to "production" (sonnet,
    non-production-class).

  select_security_auditor_model(phase_class) -> tuple[str, str]

    Returns a (model, reason) tuple for the security-auditor checkpoint agent
    given the phase's class.

    Selection table:

      phase_class   model   reason
      -----------   -----   ------
      production    opus    production-class
      docs-only     sonnet  non-production-class
      pre-pr        opus    production-class

    Unknown/absent phase_class values default to "production" (opus,
    production-class).
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

MODEL_HAIKU = "haiku"
MODEL_SONNET = "sonnet"
MODEL_OPUS = "opus"

# Model selection reason values (used by the effort DB schema).
REASON_AUTO_DOWNGRADE = "auto-downgrade"
REASON_AUTO_BASELINE = "auto-baseline"
REASON_PROMPTED_UPGRADE = "prompted-upgrade"
REASON_USER_OVERRIDE = "user-override"

# story_class values that never upgrade to opus on retry
_ALWAYS_SONNET_CLASSES = frozenset({"doc", "lesson"})

# story_class values for builder that are auto-downgraded to haiku
_HAIKU_CLASSES = frozenset({"doc", "lesson"})

# Minimum primary_files count that triggers an upgrade signal for code stories
_CODE_UPGRADE_FILE_COUNT = 5


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------


def select_reviewer_model(
    story_class: str,
    attempt_number: int,
    phase_id: str | None = None,
    project_dir: Path | str | None = None,
) -> tuple[str, str]:
    """Return (model, reason) for the reviewer agent.

    Args:
        story_class:    The story's class ("code", "doc", "lesson",
                        "methodology").  Unknown values are treated as "code".
        attempt_number: 1 for the first attempt, >=2 for retries.
        phase_id:       Optional phase identifier (e.g. "24").  Required for
                        the methodology same-phase-code-story check.
        project_dir:    Optional path to the project root.  Required when
                        phase_id is supplied and story files must be resolved.

    Returns:
        A (model, reason) tuple where model is "sonnet" or "opus" and reason
        is one of "auto-baseline", "doc-class-baseline", "retry-upgrade",
        "methodology-upgrade", "methodology-baseline".
    """
    # Normalise / apply default
    if not story_class or story_class not in {"code", "doc", "lesson", "methodology"}:
        story_class = DEFAULT_STORY_CLASS  # "code"

    # Attempt 1 is always sonnet regardless of class
    if attempt_number <= 1:
        return MODEL_SONNET, "auto-baseline"

    # attempt >= 2 — apply per-class rules
    if story_class in _ALWAYS_SONNET_CLASSES:
        return MODEL_SONNET, "doc-class-baseline"

    if story_class == "code":
        return MODEL_OPUS, "retry-upgrade"

    # story_class == "methodology"
    # Stays sonnet unless a same-phase code story exists
    if phase_id is not None and project_dir is not None:
        if _phase_has_code_story(phase_id, Path(project_dir)):
            return MODEL_OPUS, "methodology-upgrade"

    return MODEL_SONNET, "methodology-baseline"


# ---------------------------------------------------------------------------
# Builder model selection (story_class + complexity-signal-driven)
# ---------------------------------------------------------------------------


def select_builder_model(
    story_class: str,
    primary_files: list[str],
    protected_files: list[str],
) -> tuple[str, str]:
    """Return ``(model, reason)`` for the builder agent.

    Args:
        story_class:     The story's class ("code", "doc", "lesson",
                         "methodology").  Unknown values are treated as
                         "code" (conservative).
        primary_files:   List of primary file path strings declared in the
                         story spec.  An empty list counts as zero files.
        protected_files: List of file path strings that are protected (from
                         CLAUDE.md § Protected files and
                         .claude/settings.json).  If any entry in
                         ``primary_files`` appears in ``protected_files``
                         the story is considered high-scope.

    Returns:
        A ``(model, reason)`` tuple where:
        - ``model``  is one of ``"haiku"``, ``"sonnet"``, ``"opus"``
        - ``reason`` is one of ``"auto-downgrade"``, ``"auto-baseline"``,
          ``"prompted-upgrade"``

    Decision table:

      story_class   complexity signal                         model   reason
      -----------   -----------------                         -----   ------
      doc           any                                       haiku   auto-downgrade
      lesson        any                                       haiku   auto-downgrade
      methodology   any                                       sonnet  auto-baseline
      code          <5 primary_files AND no protected file    sonnet  auto-baseline
      code          >=5 primary_files OR protected file       opus    prompted-upgrade
    """
    # Normalise / apply default
    if not story_class or story_class not in {"code", "doc", "lesson", "methodology"}:
        story_class = DEFAULT_STORY_CLASS  # "code"

    # doc and lesson → auto-downgrade to haiku
    if story_class in _HAIKU_CLASSES:
        return (MODEL_HAIKU, REASON_AUTO_DOWNGRADE)

    # methodology → sonnet baseline, no upgrade signal
    if story_class == "methodology":
        return (MODEL_SONNET, REASON_AUTO_BASELINE)

    # story_class == "code" — apply complexity signals
    protected_set = set(protected_files)
    touches_protected = any(f in protected_set for f in primary_files)
    has_broad_scope = len(primary_files) >= _CODE_UPGRADE_FILE_COUNT

    if touches_protected or has_broad_scope:
        return (MODEL_OPUS, REASON_PROMPTED_UPGRADE)

    return (MODEL_SONNET, REASON_AUTO_BASELINE)


# ---------------------------------------------------------------------------
# Checkpoint-agent model selection (phase_class-driven)
# ---------------------------------------------------------------------------

# Default phase_class when the field is absent from a phase manifest.
DEFAULT_PHASE_CLASS = "production"

# phase_class values
_VALID_PHASE_CLASSES = frozenset({"production", "docs-only", "pre-pr"})


def select_intent_reviewer_model(phase_class: str) -> tuple[str, str]:
    """Return (model, reason) for the intent-reviewer checkpoint agent.

    Selection table:

      phase_class   model   reason
      -----------   -----   ------
      production    sonnet  non-production-class
      docs-only     sonnet  non-production-class
      pre-pr        opus    production-class

    Unknown/absent values default to "production" (sonnet, non-production-class).
    """
    if not phase_class or phase_class not in _VALID_PHASE_CLASSES:
        phase_class = DEFAULT_PHASE_CLASS

    if phase_class == "pre-pr":
        return MODEL_OPUS, "production-class"
    # production and docs-only both use sonnet
    return MODEL_SONNET, "non-production-class"


def select_security_auditor_model(phase_class: str) -> tuple[str, str]:
    """Return (model, reason) for the security-auditor checkpoint agent.

    Selection table:

      phase_class   model   reason
      -----------   -----   ------
      production    opus    production-class
      docs-only     sonnet  non-production-class
      pre-pr        opus    production-class

    Unknown/absent values default to "production" (opus, production-class).
    """
    if not phase_class or phase_class not in _VALID_PHASE_CLASSES:
        phase_class = DEFAULT_PHASE_CLASS

    if phase_class == "docs-only":
        return MODEL_SONNET, "non-production-class"
    # production and pre-pr both use opus
    return MODEL_OPUS, "production-class"


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
