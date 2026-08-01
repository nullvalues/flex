"""
schema_validator.py — Validate story, era, and phase manifest files.

All three formats use YAML frontmatter (delimited by ---) followed by Markdown body.
This module parses frontmatter with stdlib only (re + a minimal YAML subset via
the standard `re` module and simple key/value extraction). Full YAML parsing is not
needed because the frontmatter schemas are shallow key/value structures.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(
    r"^\s*---\s*\n(.*?)\n?---\s*(\n|$)",
    re.DOTALL,
)

_YAML_SCALAR_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$')
_YAML_LIST_ITEM_RE = re.compile(r'^\s+-\s+(.+)$')

# Matches a '#' that starts an inline comment: preceded by whitespace (or at
# the very start of the string). A '#' glued to non-whitespace content is not
# a comment start (real-YAML-like semantics).
_INLINE_COMMENT_RE = re.compile(r'(?:^|\s)#.*$')


class FrontmatterError(ValueError):
    """Raised when frontmatter contains a value this parser refuses to guess at.

    Derives from ``ValueError`` deliberately (INFRA-296): several existing
    callers already funnel parse problems through ``ValueError``
    (``model_selector.py`` raises a bare ``ValueError`` for missing
    frontmatter) or through a broad ``except Exception``
    (``flex_build.generate_permissions_artifact``,
    ``flex_build.cmd_check_story_scope``, ``model_selector``). Keeping the base
    class inside that family means every existing loud handler stays loud and
    no caller silently swallows this as an unrelated type.
    """


def _strip_inline_comment(value: str) -> str:
    """
    Apply quote-handling then inline-comment-stripping to a raw scalar value
    or block-sequence list item value.

    Quoted values (start and end with matching quotes) are treated as
    literal — a '#' inside quotes is data, not a comment, and is never
    stripped. Unquoted values have a trailing inline comment removed, but
    only when the '#' is preceded by whitespace (or starts the value); a '#'
    glued to non-whitespace content is left alone.

    Shared by both the scalar-value branch and the block-sequence list-item
    branch of ``_parse_frontmatter`` (INFRA-211 introduced the list-item
    behaviour; CER-092 / INFRA-262 extended it to scalars).
    """
    trimmed = value.strip()
    if (trimmed.startswith('"') and trimmed.endswith('"') and len(trimmed) >= 2) or (
        trimmed.startswith("'") and trimmed.endswith("'") and len(trimmed) >= 2
    ):
        return trimmed[1:-1]

    match = _INLINE_COMMENT_RE.search(trimmed)
    if match:
        trimmed = trimmed[: match.start()]
    return trimmed.strip()


# Backwards-compatible alias — the list-item call site historically used this
# name; kept so any external caller importing it directly still works.
_strip_list_item_comment = _strip_inline_comment


def _parse_flow_sequence(value_raw: str, key: str | None = None) -> list[str] | None:
    """Parse a single-line YAML flow sequence into a list of strings.

    Returns None when *value_raw* is not a flow sequence at all (it does not
    begin with "["), so the caller falls through to its existing scalar
    handling unchanged. Raises FrontmatterError when it begins with "[" but
    is not a well-formed *flat* flow sequence — nesting is not supported, and
    guessing is worse than refusing (CER-115): the parser has ten callers and
    a silently-wrong type surfaces as a TypeError in whichever of them
    concatenates first.

    Elements are split on commas, stripped of surrounding whitespace, then of
    one matching pair of surrounding ``"`` or ``'``; empty elements are
    dropped. There is no escaping rule and none is invented here — a value
    containing a literal comma is not expressible in flow style and must be
    written as a block sequence instead.

    *key* is optional and used only to name the offending key in the error
    message; it does not change what is parsed or what is refused.
    """
    if not value_raw.startswith("["):
        return None

    where = f"key '{key}': " if key else ""
    text = value_raw.strip()

    # Nesting / flow mappings first, so the message names the real problem
    # rather than reporting a nested close bracket as trailing junk.
    if "[" in text[1:] or "{" in text or "}" in text:
        raise FrontmatterError(
            f"{where}nested flow sequences and flow mappings are not supported "
            f"by the minimal YAML subset; use a block sequence: {value_raw!r}"
        )

    close = text.find("]")
    if close == -1:
        raise FrontmatterError(
            f"{where}unterminated flow sequence (no closing ']'): {value_raw!r}"
        )
    if close != len(text) - 1:
        raise FrontmatterError(
            f"{where}trailing content after the closing ']' of a flow "
            f"sequence: {value_raw!r}"
        )

    items: list[str] = []
    for element in text[1:close].split(","):
        item = element.strip()
        if len(item) >= 2 and (
            (item.startswith('"') and item.endswith('"'))
            or (item.startswith("'") and item.endswith("'"))
        ):
            item = item[1:-1]
        if item:
            items.append(item)
    return items

# L018-style enforcement: detect pointer-only acceptance sections.
_POINTER_ONLY_RE = re.compile(
    r"^\s*See\s+(docs|phase)",
    re.IGNORECASE | re.MULTILINE,
)

_SECTION_BODY_RE = re.compile(
    r"^##\s+(?:Ensures|Acceptance criteria|Acceptance criterion|Acceptance)\s*\n(.*?)(?=^##|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)


def _parse_frontmatter(text: str) -> dict[str, Any] | None:
    """
    Extract and parse the YAML frontmatter block from *text*.

    Returns a dict of top-level keys, or None if no valid frontmatter block
    is found.  Only supports the subset of YAML used by our schemas:
      - scalar string values (quoted or unquoted)
      - block sequences (list items starting with '  - ')

    This is intentionally minimal — it is NOT a general YAML parser.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None

    raw = m.group(1)
    result: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    for line in raw.splitlines():
        # Skip blank lines inside frontmatter
        if not line.strip():
            continue

        # Check if this is a list item
        list_m = _YAML_LIST_ITEM_RE.match(line)
        if list_m and current_key is not None and current_list is not None:
            current_list.append(_strip_inline_comment(list_m.group(1)))
            continue

        # Check if this is a new scalar or list-start key
        scalar_m = _YAML_SCALAR_RE.match(line)
        if scalar_m:
            # Flush previous list if any
            if current_key is not None and current_list is not None:
                result[current_key] = current_list

            key = scalar_m.group(1)
            # CER-092: strip inline comments BEFORE the empty/block-sequence
            # test, so a scalar line whose value is only a comment (e.g.
            # `touches:  # note`) reduces to "" and is correctly parsed as a
            # block-sequence start. Do not reorder this — comment strip must
            # run first, or the trailing-comment bug (CER-092) comes back.
            value_raw = _strip_inline_comment(scalar_m.group(2))

            if value_raw in ("", "[]") or value_raw is None:
                # Start of a block sequence
                current_key = key
                current_list = []
                result[key] = current_list  # will be populated by list items
            else:
                current_key = key
                current_list = None
                # INFRA-296 / CER-115: a single-line flow sequence
                # (`key: [a, b]`) parses to a list. _parse_flow_sequence
                # returns None for anything that does not open with '[', so
                # every other scalar is byte-identical to before; a value that
                # opens with '[' but is not a well-formed flat flow sequence
                # raises FrontmatterError, which is deliberately NOT caught
                # here — refusing beats returning a string the caller will
                # later concatenate with a list.
                flow = _parse_flow_sequence(value_raw, key)
                if flow is not None:
                    result[key] = flow
                    continue
                # _strip_inline_comment already removed quotes (if any); do
                # not strip them again here (would double-strip "'x'").
                result[key] = value_raw

    return result


# ---------------------------------------------------------------------------
# Public validators
# ---------------------------------------------------------------------------

VALID_STORY_STATUSES = {"draft", "planned", "in-progress", "complete", "backlog"}
VALID_ERA_STATUSES = {"active", "complete"}
VALID_STORY_CLASSES = {"code", "doc", "lesson", "methodology"}
DEFAULT_STORY_CLASS = "code"
VALID_PHASE_CLASSES = {"production", "docs-only", "pre-pr"}
DEFAULT_PHASE_CLASS = "production"
VALID_TEST_GATES = {"story", "phase_checkpoint", "none"}
# INFRA-318: the shared model-tier vocabulary for the optional `model:` /
# `reviewer_model:` story frontmatter fields. Canonical names come from the
# live selection logic (model_selector.py's MODEL_HAIKU/MODEL_SONNET/
# MODEL_OPUS) — this is the ordinary three-rung builder/reviewer ladder only.
# `fable` (model_selector.MODEL_FABLE) is deliberately excluded: it is an
# escalation tier reserved for the loop-breaker rung
# (select_loop_breaker_model), never a spec-time declarable choice. One
# constant, shared by both fields, so neither is ever free-text (Requires 1).
VALID_MODEL_TIERS = {"haiku", "sonnet", "opus"}

REQUIRED_STORY_FIELDS = ("id", "rail", "title", "status", "phase", "primary_files")
REQUIRED_ERA_FIELDS = ("id", "name", "status")


def validate_story_file(path: Path) -> list[str]:
    """Return list of validation errors, empty if valid."""
    errors: list[str] = []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"Cannot read file: {exc}"]

    fm = _parse_frontmatter(text)
    if fm is None:
        return ["Missing or malformed YAML frontmatter block"]

    for field in REQUIRED_STORY_FIELDS:
        # primary_files presence and emptiness are checked separately with status awareness
        if field == "primary_files":
            pass  # handled below in the status-aware block
        else:
            if field not in fm or fm[field] in (None, "", []):
                errors.append(f"Missing required field: '{field}'")

    if "status" in fm and fm["status"] not in VALID_STORY_STATUSES:
        errors.append(
            f"Invalid status '{fm['status']}'; must be one of "
            f"{sorted(VALID_STORY_STATUSES)}"
        )

    if "story_class" in fm and fm["story_class"] not in VALID_STORY_CLASSES:
        errors.append(
            f"Invalid story_class '{fm['story_class']}'; must be one of "
            f"{sorted(VALID_STORY_CLASSES)}"
        )

    if "source" in fm and not (isinstance(fm["source"], str) and fm["source"]):
        errors.append("Field 'source' must be a non-empty string when present")

    if "auth_gated" in fm and fm["auth_gated"] not in ("true", "false", True, False):
        errors.append("Field 'auth_gated' must be a boolean (true/false)")

    if "schema_introduces" in fm and fm["schema_introduces"] not in ("true", "false", True, False):
        errors.append("Field 'schema_introduces' must be a boolean (true/false)")

    if "test_gate" in fm and fm["test_gate"] not in VALID_TEST_GATES:
        errors.append(
            f"Invalid test_gate '{fm['test_gate']}'; must be one of "
            f"{sorted(VALID_TEST_GATES)} when present"
        )

    # INFRA-318: `model:` / `reviewer_model:` are optional per-story overrides.
    # Same optional-field pattern as `test_gate` above — enum-checked only
    # when present; a story without either field validates exactly as today.
    if "model" in fm and fm["model"] not in VALID_MODEL_TIERS:
        errors.append(
            f"Invalid model '{fm['model']}'; must be one of "
            f"{sorted(VALID_MODEL_TIERS)} when present"
        )

    if "reviewer_model" in fm and fm["reviewer_model"] not in VALID_MODEL_TIERS:
        errors.append(
            f"Invalid reviewer_model '{fm['reviewer_model']}'; must be one of "
            f"{sorted(VALID_MODEL_TIERS)} when present"
        )

    status = fm.get("status", "")
    # The 'primary_files must be a list' check below is textually identical in
    # both arms. The duplication is known and deliberate for now (INFRA-296
    # B5): collapsing it — or adding the matching 'touches' check — changes
    # what validate-schema reports across every existing story file, and is a
    # validator-tightening story with its own full-tree re-validation evidence.
    if status in ("draft", "backlog"):
        # primary_files absent or empty is acceptable for draft/backlog stories
        if "primary_files" in fm and fm["primary_files"] is not None and not isinstance(fm["primary_files"], list):
            errors.append("Field 'primary_files' must be a list")
    else:
        if "primary_files" in fm and fm["primary_files"] is not None and not isinstance(fm["primary_files"], list):
            errors.append("Field 'primary_files' must be a list")
        if not fm.get("primary_files"):
            errors.append("primary_files must be non-empty for non-draft stories "
                          "(status is not 'draft' or 'backlog')")

    # Body-section contract validation:
    # Valid if: has '## Acceptance criterion' (legacy) OR has both '## Requires' AND '## Ensures'
    # A story with neither is invalid.
    has_acceptance_criterion = "## Acceptance criterion" in text
    has_requires = "## Requires" in text
    has_ensures = "## Ensures" in text
    if not has_acceptance_criterion and not (has_requires and has_ensures):
        errors.append(
            "Story body must contain either '## Acceptance criterion' (legacy) "
            "or both '## Requires' and '## Ensures' sections"
        )

    # Pointer-only enforcement for code and methodology stories (non-draft/backlog).
    # L018: exclude pointer-only acceptance sections — reviewer must see real assertions.
    story_class = fm.get("story_class") or DEFAULT_STORY_CLASS
    _ENFORCED_CLASSES = {"code", "methodology"}
    _EXEMPT_STATUSES = {"draft", "backlog"}

    if story_class in _ENFORCED_CLASSES and status not in _EXEMPT_STATUSES:
        has_body_section = any([
            "## Ensures" in text,
            "## Acceptance criteria" in text,
            "## Acceptance criterion" in text,
            "## Acceptance" in text,
        ])
        if not has_body_section:
            errors.append(
                f"Story class '{story_class}' requires at least one of "
                "## Ensures, ## Acceptance criteria, or ## Acceptance "
                "(body section missing for non-draft story)"
            )
        else:
            section_bodies = _SECTION_BODY_RE.findall(text)
            if section_bodies:
                all_pointer = all(
                    _POINTER_ONLY_RE.search(body) and not any(
                        line.strip() and not _POINTER_ONLY_RE.match(line)
                        for line in body.splitlines()
                    )
                    for body in section_bodies
                )
                if all_pointer:
                    errors.append(
                        f"Story class '{story_class}': ## Ensures / ## Acceptance "
                        "body section is pointer-only (contains only 'See docs/phase' "
                        "delegation). Add binary-verifiable assertions. "
                        "(pointer-only body section is not a valid acceptance surface)"
                    )

    return errors


def validate_era_file(path: Path) -> list[str]:
    """Return list of validation errors, empty if valid."""
    errors: list[str] = []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"Cannot read file: {exc}"]

    fm = _parse_frontmatter(text)
    if fm is None:
        return ["Missing or malformed YAML frontmatter block"]

    for field in REQUIRED_ERA_FIELDS:
        if field not in fm or fm[field] in (None, ""):
            errors.append(f"Missing required field: '{field}'")

    if "status" in fm and fm["status"] not in VALID_ERA_STATUSES:
        errors.append(
            f"Invalid status '{fm['status']}'; must be one of "
            f"{sorted(VALID_ERA_STATUSES)}"
        )

    return errors


def validate_phase_manifest(path: Path) -> list[str]:
    """Return list of validation errors, empty if valid."""
    errors: list[str] = []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"Cannot read file: {exc}"]

    fm = _parse_frontmatter(text)
    if fm is None:
        return ["Missing or malformed YAML frontmatter block"]

    if "era" not in fm or fm["era"] in (None, ""):
        errors.append("Missing required field: 'era'")

    if "phase_class" in fm and fm["phase_class"] not in VALID_PHASE_CLASSES:
        errors.append(
            f"Invalid phase_class '{fm['phase_class']}'; must be one of "
            f"{sorted(VALID_PHASE_CLASSES)}"
        )

    return errors
