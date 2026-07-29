"""context_budget.py — Pure logic for the per-step context budget hook.

This module owns the decision logic for when to alert the orchestrator that
its context window is about to overflow. It is a library of pure (or
read-only) functions with no side effects on import.

Write/read split (INFRA-182):
- ``post_tool_use.py`` calls ``read_current_tokens()`` after each Task/Agent
  completion to read the live JSONL token count, then writes
  ``context_current_tokens`` + ``context_current_tokens_recorded_at`` to
  state.json.
- ``decide()`` reads ``context_current_tokens`` from state.json only (written
  by PostToolUse or by the SessionStart baseline on /clear). If absent or stale
  (recorded before the last session reset), ``decide()`` blocks with CONTEXT
  CHECK REQUIRED.
- ``set-context-tokens`` CLI remains available as a manual override /
  debugging escape hatch; it writes the scalar ``context_current_tokens``
  only.

Design boundary (D11):
- ``decide()`` MUST NOT write to state.json, effort.db, or the transcript.
- The hook (``hooks/pre_tool_use.py``) is the sole decision writer; it makes
  one delegated call: ``decide(project_dir)`` — reads
  ``context_current_tokens`` from state.json; the hook writes
  ``context_budget_acknowledged_at`` to state.json when the result has
  ``block=True``.

The hook is the sole state.json writer for context budget state. This
function (``decide``) is strictly read-only (D11).

INFRA-182: PostToolUse is now the writer of context_current_tokens.
PreToolUse reads state.json only — no JSONL reading in PreToolUse. No
per-story dict. No stale fallback (absent or stale = hard block).
Restored _derive_transcript_path, compute_context_tokens, read_current_tokens
bounded to last 500 lines (INFRA-183).

The companion phase-spend CLI ``context_budget_check.py`` is unrelated and
remains untouched.
"""

from __future__ import annotations

import json
import math
import sqlite3
import statistics
from datetime import datetime, timezone
from pathlib import Path

try:
    from skills.pairmode.scripts.context_model import (
        CONTEXT_STEP_GROWTH_SAMPLES_CAP,
        CONTEXT_STEP_GROWTH_SAMPLES_KEY,
        CONTEXT_STEP_GROWTH_SAMPLES_MIN_FOR_LIVE,
        THIN_HARNESS_STEP_TOKENS,
    )
except ImportError:
    # flat import via hook sys.path
    from context_model import (  # type: ignore[no-redef]
        CONTEXT_STEP_GROWTH_SAMPLES_CAP,
        CONTEXT_STEP_GROWTH_SAMPLES_KEY,
        CONTEXT_STEP_GROWTH_SAMPLES_MIN_FOR_LIVE,
        THIN_HARNESS_STEP_TOKENS,
    )


# ---------------------------------------------------------------------------
# Fixture location — shared with tests and the future INFRA-129 template work.
# ---------------------------------------------------------------------------

_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "tests"
    / "pairmode"
    / "fixtures"
    / "context_budget_prompt.txt"
)


# ---------------------------------------------------------------------------
# Module-level message constants
# ---------------------------------------------------------------------------

_FLEX_BUILD_PATH = Path(__file__).resolve().parent / "flex_build.py"

_CONTEXT_CHECK_REQUIRED_MSG = (
    "CONTEXT CHECK REQUIRED\n"
    "Context token count is missing or stale. This blocks the exact\n"
    "build-cycle agent spawn (builder/loop-breaker/security-\n"
    "auditor/intent-reviewer) that would normally refresh it, so it will\n"
    "NOT clear on its own. To proceed, do one of:\n"
    "1. Run /context to see the current token count, then run:\n"
    "     set-context-tokens --tokens N\n"
    "   (N = the token count /context reports). Then retry the spawn.\n"
    "2. Run /clear to reset the session; this writes a fresh baseline\n"
    "   automatically. Then resume with: \"Continue building Phase X\n"
    "   from story RAIL-NNN\".\n"
    "3. Spawn a non-build-cycle agent (general-purpose / Plan / Explore) —\n"
    "   these are not gated by this check.\n"
)

# CER-040: the prefix every fail-open (pass-through-while-not-enforcing)
# branch prints to stderr before continuing.
_FAIL_OPEN_PREFIX = "context_budget: gate not enforced — "


def _warn_fail_open(reason: str) -> None:
    """Print one line to stderr recording that the gate is passing through
    without having actually enforced anything (CER-040).

    A gate that fails open *silently* is indistinguishable from a gate that
    genuinely decided you were within budget — that false confidence is
    exactly what ``docs/ideology.md`` § *Never silently pass contradictions*
    forbids. This function exists so every such branch says so instead of
    staying quiet. Modeled on the ``flex_factor`` clamp warnings above
    (same "print to stderr and carry on" posture): it never raises (wrapped
    so a closed/replaced stderr cannot propagate an exception into the hook
    path), never writes state, and never blocks.
    """
    try:
        import sys as _sys

        print(_FAIL_OPEN_PREFIX + reason, file=_sys.stderr)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 0. JSONL transcript reading (PostToolUse writer path)
# ---------------------------------------------------------------------------


def _derive_transcript_path(
    cwd: Path,
    session_id: str,
    home: "Path | None" = None,
) -> "Path | None":
    """Derive the Claude Code session JSONL transcript path.

    ``home`` defaults to ``Path.home()`` when ``None``; callers (including
    tests) can inject an alternative root to avoid touching ``~/.claude/``.

    Constructs:
        home / ".claude" / "projects" / str(cwd.resolve()).replace("/", "-")
        / f"{session_id}.jsonl"

    Returns ``None`` if:
    - ``session_id`` is empty, None, or not a non-empty string.
    - The constructed path does not exist on disk (fail-open).
    - Any exception is caught.

    Pure function; no side effects.
    """
    try:
        if not session_id or not isinstance(session_id, str):
            return None
        # CER-051: reject session_id values that could escape the transcript dir.
        if "/" in session_id or ".." in session_id:
            return None
        if home is None:
            home = Path.home()
        cwd_key = str(Path(cwd).resolve()).replace("/", "-")
        candidate = home / ".claude" / "projects" / cwd_key / f"{session_id}.jsonl"
        resolved = candidate.resolve()
        if not resolved.is_relative_to((home / ".claude").resolve()):
            return None
        if not candidate.exists():
            return None
        return candidate
    except Exception:
        return None


def compute_context_tokens(transcript_path: Path) -> "int | None":
    """Bounded reverse scan of ``transcript_path``; return the live context token count.

    Reads the last 500 lines of the file (bounded tail) and walks them in
    reverse to find the last **non-sidechain** (``isSidechain`` falsy)
    ``type: "assistant"`` entry with a ``message.usage`` block — sidechain
    entries (a spawned subagent's own turns, INFRA-251) are skipped; they
    measure the subagent's disposable context, not the orchestrator's own
    live window. Returns the sum of:
      ``input_tokens + cache_read_input_tokens + cache_creation_input_tokens``

    Returns ``None`` if:
    - File is missing or unreadable (OSError).
    - No valid non-sidechain assistant entry with a ``usage`` dict is found.
    - Any numeric value is non-numeric.
    - Any exception occurs.

    Never raises. No TTL is applied — the JSONL value always reflects the
    most recent completed response.
    """
    try:
        try:
            lines = transcript_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return None
        tail = lines[-500:] if len(lines) > 500 else lines
        for line in reversed(tail):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            if entry.get("isSidechain"):
                # INFRA-251 (writer-liveness root cause): a spawned
                # subagent's own turns are appended to the SAME session
                # JSONL as ``isSidechain: True`` entries, each carrying its
                # own ``usage`` block for the subagent's disposable context
                # — not the orchestrator's own live window. PostToolUse
                # fires immediately after a Task/Agent tool call completes,
                # i.e. immediately after the subagent's sidechain entries
                # were appended and before the orchestrator emits its own
                # next turn — so an un-filtered reverse scan matched the
                # subagent's last sidechain entry here, not the
                # orchestrator's own growth, reproducing the "writer dead
                # in-session" symptom (quoting byte-identical/wrong numbers
                # after every spawn). ``subagent_transcript.py`` already
                # scans the sidechain-only side of this same split for its
                # own (correct) purpose — see its module docstring and
                # ``extract_subagent_usage`` — and § effort.db ≠
                # context-control invariant (DP7): a subagent's own cost
                # must never substitute for the orchestrator's own window
                # occupancy. Skip sidechain entries; only the orchestrator's
                # own non-sidechain turns count toward context_current_tokens.
                continue
            if entry.get("type") != "assistant":
                continue
            message = entry.get("message")
            if not isinstance(message, dict):
                continue
            usage = message.get("usage")
            if not isinstance(usage, dict):
                continue
            try:
                input_tokens = int(usage.get("input_tokens", 0) or 0)
                cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
                cache_create = int(usage.get("cache_creation_input_tokens", 0) or 0)
            except (TypeError, ValueError):
                continue
            total = input_tokens + cache_read + cache_create
            if total < 0:
                continue
            return total
        return None
    except Exception:
        return None


def read_current_tokens(
    project_dir: Path,
    session_id: str = "",
    home: "Path | None" = None,
) -> "int | None":
    """JSONL-only read of the live context token count.

    No state.json fallback. This function is the PostToolUse hook's source
    for the live count it writes back to state.json. Keeping it JSONL-only
    avoids re-arming the CER-041 staleness TTL with a stale state.json value.

    Logic:
    1. If ``session_id`` is non-empty: derive the transcript path and call
       ``compute_context_tokens()``. Return the count if positive.
    2. Return ``None`` in all other cases.

    ``home`` is passed through to ``_derive_transcript_path`` for testability.
    """
    if not session_id:
        return None
    transcript_path = _derive_transcript_path(project_dir, session_id, home)
    if transcript_path is None:
        return None
    count = compute_context_tokens(transcript_path)
    if count is not None and count > 0:
        return count
    return None


# ---------------------------------------------------------------------------
# 1. Read the current context-window count from state.json
# ---------------------------------------------------------------------------


def read_context_tokens_from_state(state: dict) -> int | None:
    """Return the recorded scalar token count from state.json.

    Reads ``state["context_current_tokens"]`` and returns it as a positive
    integer, or ``None`` when the key is absent, or the value is zero,
    negative, or non-numeric.

    CER-041 → CER-047: this function does **not** decide staleness. A
    60-minute TTL used to live here (Phase 59, INFRA-151); it was retired
    (this story, INFRA-272) because CER-047 demonstrated in production that
    a TTL cannot answer the cross-session question — an operator who clears
    within the TTL window still gets the phantom pre-clear number. The
    single staleness authority is ``_is_stale()``, which compares
    ``context_current_tokens_recorded_at`` against the session-invalidation
    anchor ``context_session_reset_at`` (Phase 68/74, INFRA-175/182) — that
    is the check ``decide()`` actually gates on. Do not re-add a staleness
    check here; the next reader who wants one should look at ``_is_stale``
    first.
    """
    if not isinstance(state, dict):
        return None

    if "context_current_tokens" not in state:
        return None
    raw = state.get("context_current_tokens")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return value


# ---------------------------------------------------------------------------
# 2. Estimate the cost of the next step from historical attempts
# ---------------------------------------------------------------------------


def estimate_next_step_tokens(
    db_path: Path | None,
    phase: str | None,
    seeded_default: int,
) -> int:
    """Waterfall estimation of the cost of the next step from historical data.

    Tier 1 — per-phase median: if ``db_path`` exists AND ``phase`` is set AND
    the attempts table has >=5 rows for that phase with non-null
    ``tokens_total``, return the median.

    Tier 2 — global median: if per-phase rows < 5 but total rows across all
    phases >= 5, return the global median (INFRA-171).

    Tier 3 — seeded default: if global rows < 5, return ``seeded_default``.
    """
    if db_path is None:
        return seeded_default
    if not isinstance(db_path, Path):
        db_path = Path(db_path)
    if not db_path.exists():
        return seeded_default

    try:
        conn = sqlite3.connect(str(db_path))
    except sqlite3.Error:
        return seeded_default

    try:
        cur = conn.cursor()

        # Tier 1: per-phase query (requires phase to be set).
        if phase is not None:
            try:
                cur.execute(
                    "SELECT tokens_total FROM attempts "
                    "WHERE phase = ? AND tokens_total IS NOT NULL",
                    (phase,),
                )
                phase_rows = cur.fetchall()
            except sqlite3.Error:
                phase_rows = []
            phase_values = [int(r[0]) for r in phase_rows if r and r[0] is not None]
            if len(phase_values) >= 5:
                return int(statistics.median(phase_values))

        # Tier 2: global all-phases fallback.
        try:
            cur.execute(
                "SELECT tokens_total FROM attempts WHERE tokens_total IS NOT NULL"
            )
            global_rows = cur.fetchall()
        except sqlite3.Error:
            return seeded_default
        global_values = [int(r[0]) for r in global_rows if r and r[0] is not None]
        if len(global_values) >= 5:
            return int(statistics.median(global_values))
    finally:
        conn.close()

    # Tier 3: seeded default.
    return seeded_default


# ---------------------------------------------------------------------------
# 2.5 Live expected_step_tokens derivation from observed orchestrator growth
#     (INFRA-254 — restores the INFRA-127 live-estimate intent with a DP7-
#     clean source; CER-053 severed the effort.db-derived path entirely
#     rather than re-sourcing it, leaving a static state.json value).
# ---------------------------------------------------------------------------


def derive_expected_step_tokens(state: dict) -> "tuple[int, str]":
    """Derive ``expected_step_tokens`` live from observed orchestrator growth.

    Tiers (never reads effort.db — DP7/CER-053 boundary preserved):

    1. Live — the ``context_step_growth_samples`` ring buffer
       (``state[CONTEXT_STEP_GROWTH_SAMPLES_KEY]``) holds
       ``>= CONTEXT_STEP_GROWTH_SAMPLES_MIN_FOR_LIVE`` numeric entries: return
       the median of those entries.
    2. Seed — otherwise, the stored ``state["expected_step_tokens"]`` value
       (bootstrap seed or a hand-edited override) when present and positive.
    3. Default — otherwise, ``THIN_HARNESS_STEP_TOKENS``.

    Returns ``(value, provenance)`` where ``provenance`` is a short
    human-readable string for the block message (Ensures #5):
    ``"live (N samples, median M)"``, ``"seed"``, or ``"default"``.

    Pure function; no I/O, no effort.db read anywhere in this path.
    """
    if not isinstance(state, dict):
        state = {}

    samples = state.get(CONTEXT_STEP_GROWTH_SAMPLES_KEY)
    numeric_samples: list[int] = []
    if isinstance(samples, list):
        for sample in samples:
            try:
                numeric_samples.append(int(sample))
            except (TypeError, ValueError):
                continue

    if len(numeric_samples) >= CONTEXT_STEP_GROWTH_SAMPLES_MIN_FOR_LIVE:
        median_value = int(statistics.median(numeric_samples))
        provenance = f"live ({len(numeric_samples)} samples, median {median_value:,})"
        return median_value, provenance

    seed_raw = state.get("expected_step_tokens")
    if seed_raw is not None:
        try:
            seed_value = int(seed_raw)
            if seed_value > 0:
                return seed_value, "seed"
        except (TypeError, ValueError):
            pass

    return THIN_HARNESS_STEP_TOKENS, "default"


def record_step_growth(
    state: dict,
    previous_tokens: "int | None",
    new_tokens: "int | None",
) -> None:
    """Append an observed orchestrator step-growth delta and re-derive
    ``expected_step_tokens`` in place.

    Called from ``hooks/post_tool_use.py``'s existing thin Task/Agent
    delegation (no new inline hook logic) immediately before it overwrites
    ``state["context_current_tokens"]`` with the freshly-read live count —
    the caller passes the OLD value as ``previous_tokens`` and the new live
    read as ``new_tokens``.

    Appends ``new_tokens - previous_tokens`` to the bounded ring buffer
    (``state[CONTEXT_STEP_GROWTH_SAMPLES_KEY]``, capped at
    ``CONTEXT_STEP_GROWTH_SAMPLES_CAP`` entries, oldest evicted) only when
    both values are valid positive integers AND the delta is strictly
    positive (a non-positive delta — e.g. a fresh ``/clear`` baseline, or a
    same-value re-read — is not genuine step growth and would corrupt the
    median with zero/negative noise).

    Always re-derives and writes back ``state["expected_step_tokens"]`` via
    ``derive_expected_step_tokens()`` (Ensures #2) — this is the "gate
    evaluation" write path: it fires on every PostToolUse Task/Agent
    observation (once per build-cycle step), immediately upstream of the
    next PreToolUse ``decide()`` call that will read it. ``decide()`` itself
    remains strictly read-only (D11) — this function is the sole writer,
    mutating ``state`` in place; the caller is responsible for persisting it.
    """
    try:
        prev = int(previous_tokens) if previous_tokens is not None else None
    except (TypeError, ValueError):
        prev = None
    try:
        new = int(new_tokens) if new_tokens is not None else None
    except (TypeError, ValueError):
        new = None

    if prev is not None and prev > 0 and new is not None and new > 0:
        delta = new - prev
        if delta > 0:
            existing = state.get(CONTEXT_STEP_GROWTH_SAMPLES_KEY)
            samples = list(existing) if isinstance(existing, list) else []
            samples.append(delta)
            if len(samples) > CONTEXT_STEP_GROWTH_SAMPLES_CAP:
                samples = samples[-CONTEXT_STEP_GROWTH_SAMPLES_CAP:]
            state[CONTEXT_STEP_GROWTH_SAMPLES_KEY] = samples

    derived_value, _provenance = derive_expected_step_tokens(state)
    state["expected_step_tokens"] = derived_value


# ---------------------------------------------------------------------------
# 3. Pure decision: should we block and prompt?
# ---------------------------------------------------------------------------


def should_block(
    current_tokens: int,
    expected_next: int,
    threshold: int,
    overrun_pct: float,
    acknowledged_at: int | None,
    reprompt_margin: int = 0,
    user_turn_seq: int = 0,
    acknowledged_user_turn_seq: int | None = None,
) -> bool:
    """Pure decision. Block iff the ceiling is exceeded AND acknowledgment does
    not clear the gate. Acknowledgment clearing has three distinct branches
    (INFRA-193; sign-corrected INFRA-251 — see below):

      - ``acknowledged_at is None``: no prior acknowledgment — always block.
      - ``acknowledged_user_turn_seq is None`` (pre-INFRA-192 state.json,
        one-time upgrade grace period): no turn tracking is available for
        this acknowledgment, so behave exactly as the pre-INFRA-193
        contract — re-block once real token growth crosses the margin
        (``current_tokens >= acknowledged_at + reprompt_margin``),
        turn-blind.
      - ``acknowledged_user_turn_seq`` is set but no ``UserPromptSubmit``
        event has occurred since the block (``user_turn_seq <=
        acknowledged_user_turn_seq``): always block. This closes the
        self-clearing bug — a bare identical retry with no human
        involvement (``current_tokens == acknowledged_at`` on a blocked
        call that never completed) must not silently clear the gate.
      - ``acknowledged_user_turn_seq`` is set and a genuine turn has
        occurred (``user_turn_seq > acknowledged_user_turn_seq``): clear
        (suppress) the block — the operator has now had a turn to see and
        respond to the prompt — UNLESS tokens have ALSO genuinely advanced
        past the reprompt margin since the acknowledgment
        (``current_tokens >= acknowledged_at + reprompt_margin``), in which
        case re-block (Ensures #2 of INFRA-251: re-block only on real
        growth, now actually reachable).

    INFRA-251: this last branch previously returned ``not token_ok`` — the
    opposite of the two branches above it. Every live-observed repro (block
    → genuine operator turn → retry, with ``context_current_tokens``
    unchanged from ``acknowledged_at`` because nothing had run since the
    block to grow it) hit exactly this branch with ``token_ok is False``
    (no growth), and the inverted sign turned that into ``True`` (still
    blocked) — the reported "acknowledgment never clears" defect. The fix
    makes all three token-margin branches agree: block on crossed margin,
    clear otherwise.

    Collapsing the last two branches into a single boolean (`turn happened
    or turn-tracking absent`) is intentionally avoided — the "no turn yet"
    branch and the "no turn tracking at all" branch require opposite
    outcomes when the token margin has not yet been crossed, so they must
    be evaluated as separate branches, not merged.
    """
    ceiling = threshold * (1.0 + overrun_pct)
    if (current_tokens + expected_next) <= ceiling:
        return False
    if acknowledged_at is None:
        return True
    # margin_crossed: real token growth since the acknowledgment has crossed
    # the reprompt margin — the signal that re-blocking is warranted.
    margin_crossed = current_tokens >= acknowledged_at + reprompt_margin
    if acknowledged_user_turn_seq is None:
        # Backward-compat upgrade path: no turn tracking recorded for this
        # acknowledgment — fall back to the pre-INFRA-193 token-only check
        # (block iff the token margin has been crossed since ack).
        return margin_crossed
    if user_turn_seq <= acknowledged_user_turn_seq:
        # No UserPromptSubmit event since the block was written — a human
        # has not yet had a turn to see and respond to the prompt.
        return True
    # A genuine turn has occurred since the block. Re-block only if tokens
    # have ALSO genuinely advanced past the reprompt margin (INFRA-251).
    return margin_crossed


# ---------------------------------------------------------------------------
# 4. Render the alert prompt body from the canonical fixture file
# ---------------------------------------------------------------------------


def render_alert_prompt(
    story_id: str | None,
    tokens: int,
    threshold: int,
    overrun_pct: float,
    expected_next: int,
    flex_factor: float = 1.0,
) -> str:
    """Template the verbatim prompt body from
    ``tests/pairmode/fixtures/context_budget_prompt.txt`` with
    ``[story RAIL-NNN]``, ``[N]``, ``[T]``, ``[O]``, ``[E]``, and ``[R]``
    substituted. ``story_id`` falls back to ``"current"`` when ``None``.

    ``[E]`` is ``expected_next``; ``[R]`` is ``ceiling - tokens`` where
    ``ceiling = int(threshold * (1 + overrun_pct) * flex_factor)`` (INFRA-165).
    """
    template = _FIXTURE_PATH.read_text(encoding="utf-8")
    story_label = story_id if story_id else "current"
    ceiling = int(threshold * (1.0 + overrun_pct) * flex_factor)
    remaining = ceiling - tokens
    rendered = template.replace("[story RAIL-NNN]", f"[story {story_label}]")
    rendered = rendered.replace("[N]", f"{tokens:,}")
    rendered = rendered.replace("[T]", f"{threshold:,}")
    rendered = rendered.replace("[O]", f"{overrun_pct:.0%}")
    rendered = rendered.replace("[E]", f"{expected_next:,}")
    rendered = rendered.replace("[R]", f"{remaining:,}")
    return rendered


# ---------------------------------------------------------------------------
# 5. End-to-end glue — read-only orchestration of the four functions above
# ---------------------------------------------------------------------------


def _read_state(project_dir: Path) -> dict | None:
    """Load .companion/state.json.

    Returns:
        None   — file is absent (non-pairmode project, fail-open).
        {}     — file exists but is malformed (JSON error, OSError, or
                 non-dict root); the caller treats this as a pairmode project
                 with a broken state, triggering CONTEXT CHECK REQUIRED.
        dict   — file exists and parsed successfully.
    """
    state_path = project_dir / ".companion" / "state.json"
    if not state_path.exists():
        return None
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _is_stale(state: dict) -> bool:
    """Return True when context_current_tokens_recorded_at < context_session_reset_at.

    Staleness rule (strict less-than): if recorded_at predates the last
    session reset, the value is stale. Equal timestamps are NOT stale —
    the SessionStart baseline sets both to the same timestamp, so equal
    means the baseline itself was just written.

    Returns False (not stale) when:
    - context_session_reset_at is absent from state (no reset recorded — fail-open).
    - Either timestamp is unparseable (fail-open for backwards compatibility).
    - recorded_at >= reset_at (fresh or equal to the reset instant).
    """
    reset_at_str = state.get("context_session_reset_at")
    if not reset_at_str:
        return False
    recorded_at_str = state.get("context_current_tokens_recorded_at", "")
    if not recorded_at_str:
        # No recorded_at means we cannot compare → treat as stale
        return True
    try:
        reset_dt = datetime.fromisoformat(reset_at_str)
        recorded_dt = datetime.fromisoformat(recorded_at_str)
    except (TypeError, ValueError, AttributeError):
        return False
    return recorded_dt < reset_dt


def _staleness_unverifiable_reason(state: dict) -> "str | None":
    """Return a human-readable reason when ``_is_stale()`` will fail open
    without having compared anything, or ``None`` when the comparison is
    genuinely performable.

    CER-040: ``_is_stale()`` itself must keep its existing signature and
    verdicts (A3) — this is a separate, pure helper that names *why* a
    fail-open branch was taken, without duplicating or calling ``_is_stale``'s
    verdict. It answers "can staleness even be judged here?", not "is it
    stale?".

    Returns a reason string for exactly the two ways ``_is_stale()`` fails
    open on an unanchored/unparseable comparison:
    - ``context_session_reset_at`` is absent entirely.
    - Either ``context_session_reset_at`` or
      ``context_current_tokens_recorded_at`` is present but not parseable by
      ``datetime.fromisoformat``.
    """
    reset_at_str = state.get("context_session_reset_at")
    if not reset_at_str:
        return (
            "context_session_reset_at is absent; staleness cannot be "
            "verified (mid-upgrade project or pre-INFRA-175 state.json)"
        )
    recorded_at_str = state.get("context_current_tokens_recorded_at", "")
    if not recorded_at_str:
        # A missing recorded_at is judged (True — stale) by _is_stale, not
        # unverifiable; nothing to report here.
        return None
    try:
        datetime.fromisoformat(reset_at_str)
        datetime.fromisoformat(recorded_at_str)
    except (TypeError, ValueError, AttributeError):
        return (
            "context_session_reset_at or context_current_tokens_recorded_at "
            "is not parseable as an ISO-8601 timestamp; staleness cannot be "
            "verified"
        )
    return None


def _import_session_state():
    """Import ``session_state`` under either import style.

    Imported lazily from inside :func:`decide` (rather than at module scope) to
    keep ``context_budget``'s import cost exactly where it is — this module is
    imported on the PreToolUse hook path.

    Returns ``None`` (CER-040) rather than propagating ``ImportError`` when
    neither import style resolves — a missing/renamed ``session_state``
    module must degrade the gate to its flat, project-global read, not kill
    it for the rest of the session.
    """
    try:
        from skills.pairmode.scripts import session_state  # type: ignore

        return session_state
    except ImportError:
        pass
    try:
        import session_state  # type: ignore[no-redef]

        return session_state
    except ImportError:
        return None


def decide(
    project_dir: Path,
    flex_factor: float = 1.0,
    *,
    session_id: "str | None" = None,
) -> "dict | None":
    """End-to-end glue. Reads ``state["context_current_tokens"]`` from state.json
    (written by ``post_tool_use.py`` after each Task/Agent completion, or by the
    SessionStart baseline on /clear), calls ``should_block``, and returns

        {"block": True, "reason": "<prompt>", "tokens": N,
         "acknowledged_at": N}

    when the next step would exceed the overrun ceiling, ``None`` when within
    budget, or a "CONTEXT CHECK REQUIRED" block dict when:
    - context_current_tokens is absent from state.json.
    - context_current_tokens_recorded_at < context_session_reset_at (stale).

    ``flex_factor`` scales the effective ceiling:
    ``ceiling = threshold * (1 + overrun_pct) * flex_factor``.
    Values <= 0 are clamped to 1.0; values > 5.0 are clamped to 5.0.
    The default of 1.0 preserves the pre-INFRA-160 behaviour exactly.

    ``session_id`` (INFRA-285 / CER-097) resolves the read through the calling
    session's own ``context_sessions`` record rather than the flat, project-
    global mirror. When it is falsy, behaviour is byte-for-byte what it was
    before that story — a single-session project is unaffected. When it is
    truthy but the session has **no** ``context_sessions`` entry and at least
    one *other* entry is live, this returns the existing CONTEXT CHECK REQUIRED
    block rather than reading the mirror: the mirror at that moment holds some
    other session's window, and gating this session's spawn against a window it
    is not in is precisely the under-blocking CER-097 reported. No new block
    reason string is introduced — the operator remedy is unchanged.

    The caller (the hook) is responsible for writing ``acknowledged_at`` back
    to state.json when blocking. ``post_tool_use.py`` is the sole writer of
    ``context_current_tokens`` (via read_current_tokens). This function is
    strictly read-only — it MUST NOT write to state.json or effort.db (D11).
    """
    import sys as _sys

    if not isinstance(project_dir, Path):
        project_dir = Path(project_dir)

    # Clamp flex_factor to a safe range (NaN check first — IEEE-754 NaN fails all comparisons).
    if math.isnan(flex_factor):
        print(
            "context_budget.decide: flex_factor is NaN; clamped to 1.0",
            file=_sys.stderr,
        )
        flex_factor = 1.0
    if flex_factor <= 0:
        print(
            f"context_budget.decide: flex_factor={flex_factor!r} is <= 0; clamped to 1.0",
            file=_sys.stderr,
        )
        flex_factor = 1.0
    elif flex_factor > 5.0:
        print(
            f"context_budget.decide: flex_factor={flex_factor!r} is > 5.0; clamped to 5.0",
            file=_sys.stderr,
        )
        flex_factor = 5.0

    state = _read_state(project_dir)
    if state is None:
        # _read_state returns None when state.json is absent.
        # CER-040: check whether this is a pairmode project (has .companion/ dir).
        # If .companion/ exists, state.json should be present → surface as needing attention.
        # If .companion/ is absent, this is a non-pairmode project → fail-open.
        if (project_dir / ".companion").is_dir():
            return {
                "block": True,
                "reason": _CONTEXT_CHECK_REQUIRED_MSG,
                "tokens": 0,
                "acknowledged_at": 0,
            }
        return None

    # INFRA-285 (CER-097): resolve through this session's own keyed record.
    if session_id:
        session_state = _import_session_state()
        if session_state is None:
            # CER-040 / A5: a missing/renamed session_state module must not
            # kill the gate for the rest of the session — warn and fall
            # through to the flat, project-global read exactly as if
            # session_id had been falsy.
            _warn_fail_open(
                "session_state module could not be imported; the "
                "session-keyed read was skipped and the flat project-global "
                "state.json mirror was used instead"
            )
        else:
            sessions = state.get(session_state.CONTEXT_SESSIONS_KEY)
            if isinstance(sessions, dict) and session_id not in sessions:
                # Unregistered session with live siblings: the flat mirror
                # belongs to someone else's window. Fail safe rather than
                # gate against it.
                if session_state.live_session_ids(state, exclude=session_id):
                    return {
                        "block": True,
                        "reason": _CONTEXT_CHECK_REQUIRED_MSG,
                        "tokens": 0,
                        "acknowledged_at": 0,
                    }
            state = session_state.session_view(state, session_id)

    # Read context_current_tokens directly (bypass TTL; session-reset check below).
    current_tokens: int | None = None
    raw = state.get("context_current_tokens")
    if raw is not None:
        try:
            v = int(raw)
            if v > 0:
                current_tokens = v
        except (TypeError, ValueError):
            pass

    # Absent → block hard.
    if current_tokens is None:
        return {
            "block": True,
            "reason": _CONTEXT_CHECK_REQUIRED_MSG,
            "tokens": 0,
            "acknowledged_at": 0,
        }

    # Staleness check: if recorded_at < reset_at (strict less-than), block hard.
    if _is_stale(state):
        return {
            "block": True,
            "reason": _CONTEXT_CHECK_REQUIRED_MSG,
            "tokens": 0,
            "acknowledged_at": 0,
        }

    # CER-040 / A4: _is_stale() returned False on the pass-through path — but
    # two of its branches are fail-opens rather than a genuine "fresh"
    # verdict (absent context_session_reset_at, or an unparseable
    # timestamp). Warn when that's what happened; a state that produced the
    # CONTEXT CHECK REQUIRED block above does not additionally warn (the
    # block is already the signal).
    unverifiable_reason = _staleness_unverifiable_reason(state)
    if unverifiable_reason is not None:
        _warn_fail_open(unverifiable_reason)

    threshold = int(state.get("context_budget_threshold", 130000) or 130000)
    overrun_pct = float(state.get("context_budget_overrun_pct", 0.10) or 0.10)
    # INFRA-254: live derivation from observed orchestrator growth (ring-buffer
    # median tier, falling back to the stored seed / THIN_HARNESS_STEP_TOKENS).
    # This is strictly a read of state — decide() remains read-only (D11);
    # the ring buffer and expected_step_tokens are written by
    # record_step_growth() from hooks/post_tool_use.py, never from here.
    seeded_default, expected_tokens_provenance = derive_expected_step_tokens(state)
    reprompt_margin = int(state.get("context_budget_reprompt_margin", 10000) or 10000)
    # CER-106 (INFRA-299): despite its `_at` suffix, this key holds a
    # token count, not a timestamp — it is the `context_current_tokens`
    # value at the moment hooks/pre_tool_use.py last wrote a block, which
    # should_block() compares against `current_tokens + reprompt_margin`.
    # Hence the int() coercion below rather than any date parsing. The
    # misnomer is retained deliberately; renaming it is a fleet-wide
    # state.json migration. See docs/architecture.md § Companion data files.
    acknowledged_at_raw = state.get("context_budget_acknowledged_at")
    acknowledged_at: int | None
    if acknowledged_at_raw is None:
        acknowledged_at = None
    else:
        try:
            acknowledged_at = int(acknowledged_at_raw)
        except (TypeError, ValueError):
            acknowledged_at = None

    # CER-053: window-growth constant must not be effort-derived.
    # Pass db_path=None to skip the effort.db median lookup entirely.
    user_turn_seq = int(state.get("context_budget_user_turn_seq", 0) or 0)
    ack_turn_seq_raw = state.get("context_budget_acknowledged_user_turn_seq")
    acknowledged_user_turn_seq = (
        int(ack_turn_seq_raw) if ack_turn_seq_raw is not None else None
    )

    expected_next = estimate_next_step_tokens(
        None,
        None,
        seeded_default,
    )

    # Apply flex_factor to the effective threshold, then delegate to the
    # pure should_block() decision (which applies the overrun_pct itself).
    blocked = should_block(
        current_tokens=current_tokens,
        expected_next=expected_next,
        threshold=threshold * flex_factor,
        overrun_pct=overrun_pct,
        acknowledged_at=acknowledged_at,
        reprompt_margin=reprompt_margin,
        user_turn_seq=user_turn_seq,
        acknowledged_user_turn_seq=acknowledged_user_turn_seq,
    )
    if not blocked:
        return None

    state_story_id = state.get("current_story") or state.get("story_id")
    prompt = render_alert_prompt(
        story_id=str(state_story_id) if state_story_id else None,
        tokens=current_tokens,
        threshold=threshold,
        overrun_pct=overrun_pct,
        expected_next=expected_next,
        flex_factor=flex_factor,
    )
    # INFRA-254 Ensures #5: report the estimate's provenance so an operator
    # can see at a glance whether the number is live (ring-buffer-derived) or
    # cold-start (seed / default).
    prompt = f"{prompt}\n[expected_step_tokens estimate: {expected_tokens_provenance}]\n"
    return {
        "block": True,
        "reason": prompt,
        "tokens": current_tokens,
        "acknowledged_at": current_tokens,
        "user_turn_seq_at_block": user_turn_seq,
    }
