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

  select_loop_breaker_model() -> tuple[str, str]

    Returns the (model, reason) tuple for the loop-breaker rung.  Deterministic
    and parameter-free: always ``("fable", "escalation-upgrade")``.  This rung
    is only reached at the double-fail point (next_action.py Row 6), after the
    ordinary top tier (opus) has already failed twice.

  select_gate_worker_model(phase_class) -> tuple[str, str]

    Returns a (model, reason) tuple for the gate-worker judged-gate agent
    (WORKER-002 — schema/auth verdict evaluation) given the phase's class.
    Checkpoint/gate-shaped, keyed by ``phase_class`` like
    ``select_intent_reviewer_model``/``select_security_auditor_model``, not
    ``story_class`` (INFRA-333 Requires 1) — gate-worker judges a single
    story's schema/auth conformance, but that judgment carries the same
    correctness weight regardless of which story is in front of it, so this
    table reuses ``select_security_auditor_model``'s tier assignment rather
    than the lighter-weight ``select_intent_reviewer_model`` one: a missed
    schema/auth violation is a correctness defect, not a documentation-
    currency miss.

    Selection table:

      phase_class   model   reason
      -----------   -----   ------
      production    opus    production-class
      docs-only     sonnet  non-production-class
      pre-pr        opus    production-class

    Unknown/absent phase_class values default to "production" (opus,
    production-class).

    Wiring note (INFRA-333 Ensures 1): the resolved value cannot ride
    ``next_action.py``'s ``spawn-gate-worker`` action's ``model`` field —
    ``validate_action`` requires ``model=null`` for any action outside
    ``_SPAWN_ACTIONS``, and ``spawn-gate-worker`` is deliberately not a
    member of that set (locked in by
    ``test_spawn_gate_worker_with_model_fails_validate`` in
    ``tests/pairmode/test_next_action.py``; promoting it would be an
    action-grammar redesign, out of this story's narrow "wire the missing
    selectors" scope). The "spawn-gate-worker carries no builder model"
    comment at ``next_action.py``'s ``SPAWN_GATE_WORKER`` declaration
    therefore remains accurate for the action's ``model`` field after this
    story. ``next_action.py``'s Row 4b instead calls this selector directly
    and surfaces its result as an advisory ``meta["gate_worker_model"]`` /
    ``meta["gate_worker_model_reason"]`` pair on the emitted action — a real
    call site, not an unused function, without changing the grammar.

  select_docs_reviewer_model(phase_class) -> tuple[str, str]

    Returns a (model, reason) tuple for the docs-reviewer checkpoint agent
    (WORKER-011 — documentation currency checklist) given the phase's class.
    Checkpoint/gate-shaped, keyed by ``phase_class``. docs-reviewer is an
    advisory, bounded-input checklist role much closer in weight to the
    intent-reviewer's phase-alignment judgment than to the security-
    auditor's correctness judgment, so this table reuses
    ``select_intent_reviewer_model``'s tier assignment.

    Selection table:

      phase_class   model   reason
      -----------   -----   ------
      production    sonnet  non-production-class
      docs-only     sonnet  non-production-class
      pre-pr        opus    production-class

    Unknown/absent phase_class values default to "production" (sonnet,
    non-production-class).

    Wiring note (INFRA-333 Ensures 2): unlike ``select_gate_worker_model``,
    ``checkpoint-docs`` already carries a non-null model in the action
    grammar (``CHECKPOINT_DOCS`` is a member of ``_SPAWN_ACTIONS``) —
    ``next_action.py`` Row 9 calls this selector directly and sets the
    result on the emitted action's ``model`` field whenever ``checkpoint-
    docs`` is the next uncompleted step, replacing the unconditional
    ``model=None`` the ``docs-reviewer.md.j2`` comment used to describe.

  select_spec_writer_model(story_class) -> tuple[str, str]

    Returns a (model, reason) tuple for the spec-writer agent given the
    stub story's declared class. spec-writer elaborates a bare story stub
    into a full spec (Ensures/Instructions/Tests) before any builder-model
    or story-class decision can be trusted — ``story_class`` on a stub is
    frequently still the schema default rather than a considered
    classification, since the story hasn't been fully written yet. Unlike
    ``select_builder_model``, this selector does not downgrade
    ``doc``/``lesson`` stories to haiku: the elaboration step carries the
    same judgment weight regardless of the class the finished story will
    end up in, because a bad elaboration corrupts every downstream attempt
    at whatever class is eventually assigned (INFRA-333 Requires 2
    evidence).

    Selection table:

      story_class   model   reason
      -----------   -----   ------
      code          opus    spec-elaboration-baseline
      doc           opus    spec-elaboration-baseline
      lesson        opus    spec-elaboration-baseline
      methodology   opus    spec-elaboration-baseline

    Unconditional opus regardless of ``story_class`` — a deliberate decision,
    not a placeholder: this refactors ``next_action.py``'s Row-2
    ``spawn-spec-writer`` emission (formerly a hardcoded ``model="opus"``
    literal) onto the shared ``model_selector`` mechanism without changing
    the one known production case's effective behavior (INFRA-333 Ensures
    3). No attempt-number parameter: ``resolve_next_action`` only ever
    emits ``spawn-spec-writer`` once, at Row 2 (``attempt_count == 0``); a
    retried/revised spec-writer pass is routed by ``SPEC-RESULT{revised}``
    handling in ``CLAUDE.build.md`` orchestrator prose, not by a second
    ``resolve_next_action`` emission at a higher attempt number, so there is
    no attempt ladder for this selector to encode.

  Model ladder note:

    The ordinary builder/reviewer attempt tables use the strict three-rung
    ladder haiku < sonnet < opus.  ``fable`` is an *escalation tier ranking
    above opus*, used only by the loop-breaker rung (select_loop_breaker_model)
    for escalation/loop-breaker situations — it is deliberately NOT inserted
    into the attempt-1/attempt-2 builder or reviewer tables above.
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
# Escalation tier — ranks *above* opus. Used only by the loop-breaker rung
# (see select_loop_breaker_model); never inserted into the ordinary
# builder/reviewer attempt-based tables, which stay haiku/sonnet/opus.
MODEL_FABLE = "fable"

# Model selection reason values (used by the effort DB schema).
REASON_AUTO_DOWNGRADE = "auto-downgrade"
REASON_AUTO_BASELINE = "auto-baseline"
REASON_PROMPTED_UPGRADE = "prompted-upgrade"
REASON_USER_OVERRIDE = "user-override"
REASON_RETRY_UPGRADE = "retry-upgrade"
REASON_ESCALATION_UPGRADE = "escalation-upgrade"

# Rank of the ordinary three-rung ladder (haiku < sonnet < opus), used only to
# compare a story-declared model floor against an auto-selected model.
# ``fable`` is deliberately absent — it is the loop-breaker's escalation tier,
# never a declarable floor (see schema_validator.VALID_MODEL_TIERS).
MODEL_RANK = {MODEL_HAIKU: 0, MODEL_SONNET: 1, MODEL_OPUS: 2}

# Reason value for an attempt-1 dispatch that carries a story-declared model.
REASON_STORY_DECLARED = "story-declared"

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


def apply_declared_model_floor(
    model: str,
    reason: str,
    declared_model: "str | None",
    attempt_number: int,
) -> tuple[str, str]:
    """Apply a story-declared ``model:``/``reviewer_model:`` floor (INFRA-318)
    to an already-auto-selected ``(model, reason)`` pair.

    Asymmetric by design (Cora item A#7 / AG-6):

    - ``attempt_number <= 1``: a declared model is an outright *override* —
      the spec-writer's already-approved choice (raise or lower) replaces the
      auto-selected baseline entirely. Reason becomes ``REASON_STORY_DECLARED``.
    - ``attempt_number >= 2``: the auto-selected retry tier still applies, but
      never drops below the declared floor's rank on the ordinary
      haiku < sonnet < opus ladder — a *floor*, not an override, so
      retry-upgrade keeps working unchanged whenever it is already at or
      above the floor.

    ``declared_model=None`` is a no-op: returns ``(model, reason)`` unchanged
    — undeclared stories get byte-identical output to before this helper
    existed (Ensures 2/5).
    """
    if declared_model is None:
        return model, reason

    if attempt_number <= 1:
        return declared_model, REASON_STORY_DECLARED

    if MODEL_RANK.get(model, 0) < MODEL_RANK.get(declared_model, 0):
        return declared_model, reason

    return model, reason


# ---------------------------------------------------------------------------
# Builder model selection (story_class + complexity-signal-driven)
# ---------------------------------------------------------------------------


def select_builder_model(
    story_class: str,
    primary_files: list[str],
    protected_files: list[str],
    attempt_number: int = 1,
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
        attempt_number:  1 for the first attempt, >=2 for retries.  Code
                         stories on attempt >=2 are always escalated to opus.

    Returns:
        A ``(model, reason)`` tuple where:
        - ``model``  is one of ``"haiku"``, ``"sonnet"``, ``"opus"``
        - ``reason`` is one of ``"auto-downgrade"``, ``"auto-baseline"``,
          ``"prompted-upgrade"``, ``"retry-upgrade"``

    Decision table:

      story_class   attempt   complexity signal                         model   reason
      -----------   -------   -----------------                         -----   ------
      doc           any       any                                       haiku   auto-downgrade
      lesson        any       any                                       haiku   auto-downgrade
      methodology   any       any                                       sonnet  auto-baseline
      code          1         <5 primary_files AND no protected file    sonnet  auto-baseline
      code          1         >=5 primary_files OR protected file       opus    prompted-upgrade
      code          >=2       any                                       opus    retry-upgrade
    """
    # Normalise / apply default
    if not story_class or story_class not in {"code", "doc", "lesson", "methodology"}:
        story_class = DEFAULT_STORY_CLASS  # "code"

    # Retry escalation: code stories on attempt >= 2 always use opus.
    # doc/lesson/methodology classes never escalate (mirrors reviewer behaviour).
    if attempt_number >= 2 and story_class == "code":
        return (MODEL_OPUS, REASON_RETRY_UPGRADE)

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
# Loop-breaker / escalation-tier model selection
# ---------------------------------------------------------------------------


def select_loop_breaker_model() -> tuple[str, str]:
    """Return (model, reason) for the loop-breaker rung.

    The loop-breaker rung is only ever reached at the double-fail point
    (next_action.py Row 6: attempt_count == 2 and the last outcome was FAIL),
    i.e. after the harness's ordinary top tier (opus) has already failed twice.
    It therefore escalates unconditionally to the ``fable`` tier, which ranks
    above ``opus`` for escalation/loop-breaker situations only — it is not part
    of the ordinary builder/reviewer attempt-based tables.

    Deterministic and parameter-free (mirrors the intent-reviewer /
    security-auditor selector pattern).

    Returns:
        The tuple ``("fable", "escalation-upgrade")``.
    """
    return MODEL_FABLE, REASON_ESCALATION_UPGRADE


# ---------------------------------------------------------------------------
# Gate-worker / docs-reviewer / spec-writer model selection (INFRA-333)
# ---------------------------------------------------------------------------


def select_gate_worker_model(phase_class: str) -> tuple[str, str]:
    """Return (model, reason) for the gate-worker judged-gate agent.

    See the module docstring's ``select_gate_worker_model`` entry for the
    full selection table and the wiring-note explaining why this result
    cannot ride ``next_action.py``'s ``spawn-gate-worker`` action's ``model``
    field.

    Unknown/absent phase_class values default to "production" (opus,
    production-class).
    """
    if not phase_class or phase_class not in _VALID_PHASE_CLASSES:
        phase_class = DEFAULT_PHASE_CLASS

    if phase_class == "docs-only":
        return MODEL_SONNET, "non-production-class"
    # production and pre-pr both use opus (mirrors select_security_auditor_model)
    return MODEL_OPUS, "production-class"


def select_docs_reviewer_model(phase_class: str) -> tuple[str, str]:
    """Return (model, reason) for the docs-reviewer checkpoint agent.

    See the module docstring's ``select_docs_reviewer_model`` entry for the
    full selection table.

    Unknown/absent phase_class values default to "production" (sonnet,
    non-production-class).
    """
    if not phase_class or phase_class not in _VALID_PHASE_CLASSES:
        phase_class = DEFAULT_PHASE_CLASS

    if phase_class == "pre-pr":
        return MODEL_OPUS, "production-class"
    # production and docs-only both use sonnet (mirrors select_intent_reviewer_model)
    return MODEL_SONNET, "non-production-class"


def select_spec_writer_model(story_class: str) -> tuple[str, str]:
    """Return (model, reason) for the spec-writer agent.

    See the module docstring's ``select_spec_writer_model`` entry for the
    full selection table and the reasoning for its unconditional-opus,
    no-attempt-ladder shape.

    Unknown story_class values default to "code" (still opus — this
    selector's table has no per-class variation).
    """
    if not story_class or story_class not in {"code", "doc", "lesson", "methodology"}:
        story_class = DEFAULT_STORY_CLASS

    return MODEL_OPUS, "spec-elaboration-baseline"


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


# ---------------------------------------------------------------------------
# CLI — __main__ entry point
# ---------------------------------------------------------------------------


def _read_story_frontmatter(story_file: Path) -> dict:
    """Parse YAML frontmatter from a story file using schema_validator.

    Returns the frontmatter dict, or raises ValueError on parse failure.
    Raises FileNotFoundError if the file does not exist.

    Uses the canonical `_parse_frontmatter` from schema_validator rather than
    re-implementing the parser inline (architecture.md non-negotiable).
    """
    # schema_validator is a sibling module; _SCRIPTS_DIR is already on sys.path.
    from schema_validator import _parse_frontmatter  # noqa: PLC0415

    text = story_file.read_text(encoding="utf-8")
    data = _parse_frontmatter(text)

    if data is None:
        raise ValueError(f"No YAML frontmatter found in {story_file}")

    return data


def _read_protected_files(project_dir: Path) -> list[str]:
    """Read the deny list from .claude/settings.json in project_dir.

    Returns a list of raw deny patterns (e.g. "Edit(hooks/**)").  When the
    file is absent or unreadable, returns an empty list (fail-safe).
    """
    import json
    import re

    settings_path = project_dir / ".claude" / "settings.json"
    if not settings_path.exists():
        return []

    try:
        with settings_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []

    deny_rules: list[str] = (
        data.get("permissions", {}).get("deny", [])
    )

    # Extract the path portion from patterns like "Edit(hooks/**)" or
    # "Write(skills/companion/**)" so callers can compare against plain paths.
    extracted: list[str] = []
    for rule in deny_rules:
        m = re.match(r"^\w+\((.+)\)$", rule)
        if m:
            extracted.append(m.group(1))
        else:
            extracted.append(rule)

    return extracted


def _read_phase_class(phase_id: str, project_dir: Path) -> str:
    """Read the phase_class field from the phase manifest.

    Returns "production" (the default) when the file or field is absent.
    """
    phase_path = _find_phase_file(phase_id, project_dir)
    if phase_path is None:
        return DEFAULT_PHASE_CLASS

    try:
        fm = _read_story_frontmatter(phase_path)
        return str(fm.get("phase_class") or DEFAULT_PHASE_CLASS)
    except Exception:
        return DEFAULT_PHASE_CLASS


if __name__ == "__main__":
    import argparse
    import sys as _sys

    parser = argparse.ArgumentParser(
        prog="model_selector.py",
        description=(
            "Determine the Claude model for a given role by reading a story file."
        ),
    )
    parser.add_argument(
        "--story-file",
        required=True,
        metavar="PATH",
        help="Path to the story file (YAML frontmatter required).",
    )
    parser.add_argument(
        "--role",
        default="builder",
        choices=["builder", "reviewer", "intent-reviewer", "security-auditor"],
        help="Agent role.  Default: builder.",
    )
    parser.add_argument(
        "--attempt",
        type=int,
        default=1,
        metavar="N",
        help="Attempt number (1 = first attempt).  Default: 1.",
    )
    parser.add_argument(
        "--project-dir",
        default=None,
        metavar="DIR",
        help=(
            "Project root directory.  Used to locate .claude/settings.json and "
            "phase manifests.  Defaults to the directory containing the story file."
        ),
    )

    args = parser.parse_args()

    story_path = Path(args.story_file)

    # --- Validate story file exists ---
    if not story_path.exists():
        _sys.stderr.write(f"error: story file not found: {story_path}\n")
        _sys.exit(1)

    # --- Parse frontmatter ---
    try:
        fm = _read_story_frontmatter(story_path)
    except (ValueError, OSError) as exc:
        _sys.stderr.write(f"error: {exc}\n")
        _sys.exit(1)

    # --- Extract fields from frontmatter ---
    story_class: str = fm.get("story_class") or DEFAULT_STORY_CLASS
    primary_files: list[str] = fm.get("primary_files") or []
    phase_id: str | None = str(fm["phase"]) if "phase" in fm else None

    # --- Resolve project_dir ---
    if args.project_dir is not None:
        project_dir = Path(args.project_dir).resolve()
    else:
        # Default: directory containing the story file
        project_dir = story_path.resolve().parent

    # --- Dispatch to the appropriate selection function ---
    role = args.role
    attempt = args.attempt

    if role == "builder":
        protected = _read_protected_files(project_dir)
        model, reason = select_builder_model(
            story_class,
            primary_files,
            protected,
            attempt_number=attempt,
        )

    elif role == "reviewer":
        model, reason = select_reviewer_model(
            story_class,
            attempt,
            phase_id=phase_id,
            project_dir=project_dir,
        )

    elif role == "intent-reviewer":
        # intent-reviewer uses phase_class, not story_class.
        # Read phase_class from the phase manifest when possible; fall back to
        # "production" (which is also the default inside the selector).
        phase_class = _read_phase_class(phase_id, project_dir) if phase_id else "production"
        model, reason = select_intent_reviewer_model(phase_class)

    elif role == "security-auditor":
        phase_class = _read_phase_class(phase_id, project_dir) if phase_id else "production"
        model, reason = select_security_auditor_model(phase_class)

    else:
        # Should never reach here due to argparse choices constraint.
        _sys.stderr.write(f"error: unknown role: {role}\n")
        _sys.exit(1)

    # --- Two-line output: model on line 1, reason on line 2 ---
    print(model)
    print(reason)
    _sys.exit(0)
