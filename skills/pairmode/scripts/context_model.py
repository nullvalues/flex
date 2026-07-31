"""Thin-harness context growth model constants.

The thin dispatch loop's per-step context growth is the JSON return block from
flex_build.py next-action plus the leaf-worker's return summary and <usage> block.
This is fundamentally different from a builder's per-story cost (effort.db).

THIN_HARNESS_STEP_TOKENS is a deliberate, documented constant — not derived from
effort.db. It is the seed value for expected_step_tokens in the context budget.
The SPA display provenance label is tracked in OBS-003 (Phase G).

INFRA-254: expected_step_tokens is now derived live from observed orchestrator
window-growth deltas (never from effort.db — DP7/CER-053), recorded in a
bounded ring buffer in state.json (key CONTEXT_STEP_GROWTH_SAMPLES_KEY, capped
at CONTEXT_STEP_GROWTH_SAMPLES_CAP entries). THIN_HARNESS_STEP_TOKENS remains
the cold-start tier-3 fallback when both the ring buffer (< tier-2 minimum
sample count) and the state.json seed are unavailable. See
skills/pairmode/scripts/context_budget.py::derive_expected_step_tokens.
"""

THIN_HARNESS_STEP_TOKENS: int = 5000

# INFRA-254: bounded ring buffer of observed orchestrator step-growth deltas
# (context_current_tokens deltas between consecutive PostToolUse Task/Agent
# observations). State.json key name, cap, and the minimum sample count
# required before the live (ring-buffer-median) tier takes over from the
# stored seed.
CONTEXT_STEP_GROWTH_SAMPLES_KEY: str = "context_step_growth_samples"
CONTEXT_STEP_GROWTH_SAMPLES_CAP: int = 20
CONTEXT_STEP_GROWTH_SAMPLES_MIN_FOR_LIVE: int = 5


# ---------------------------------------------------------------------------
# INFRA-321 — the two-track context accounting model.
#
# flex has two token quantities. This module is where a reader looking for
# "what is a token here" should land — see docs/architecture.md § (c) effort.db
# ≠ context-control invariant (DP7) for the full narrative.
#
# Boundary rule (both directions, never violate either):
#   - A story-spend quantity (effort.db attempts.tokens_*) may NEVER be
#     compared against an orchestrator-track threshold (context_budget_threshold
#     and friends).
#   - A subagent/story-spend token count may NEVER be summed into an
#     orchestrator-track state.json key (context_current_tokens and friends).
# ---------------------------------------------------------------------------

#: Live occupancy of the orchestrator's own context window. The only quantity
#: that can overflow a window, and therefore the only one a pause decision may
#: ever be computed from.
TRACK_ORCHESTRATOR: str = "orchestrator-window"

#: Retrospective cost of subagent (builder/reviewer/auditor) work, recorded in
#: effort.db. Burned in a subagent's own disposable context window; never
#: entered the orchestrator's window (DP7).
TRACK_STORY_SPEND: str = "story-spend"

#: state.json keys that belong to the orchestrator track. A story-spend
#: quantity must never be compared against, or summed into, any of these.
ORCHESTRATOR_TRACK_KEYS: "tuple[str, ...]" = (
    "context_current_tokens",
    "context_current_tokens_recorded_at",
    "context_step_growth_samples",
    "expected_step_tokens",
    "context_budget_threshold",
    "context_budget_overrun_pct",
    "context_budget_reprompt_margin",
    "context_budget_acknowledged_at",
    "context_budget_user_turn_seq",
    "context_budget_acknowledged_user_turn_seq",
    "context_session_reset_at",
)

#: effort.db columns that belong to the story-spend track. Never an input to
#: a context-headroom or clear-seam decision (DP7).
STORY_SPEND_SOURCES: "tuple[str, ...]" = (
    "attempts.tokens_total",
    "attempts.tokens_out",
    "attempts.tokens_in",
)

#: The key that records which writer most recently stamped
#: context_current_tokens (INFRA-321 § C6). Additive, observability/audit only
#: — decide() does not gate on it. Absence means "unknown" (legacy state).
CONTEXT_CURRENT_TOKENS_SOURCE_KEY: str = "context_current_tokens_source"

#: The three known writer identities for CONTEXT_CURRENT_TOKENS_SOURCE_KEY.
#: NOTE (INFRA-321): only "user-prompt-submit" (user_turn_seq.record_user_turn)
#: and "manual" (flex_build.py set-context-tokens / bump-context-tokens) have
#: a live writer today. "post-tool-use" is reserved for hooks/post_tool_use.py's
#: Task/Agent branch, which is a protected path (hooks/**) — stamping it there
#: is deferred to a follow-up story (see docs/cer/backlog.md). Do not read the
#: presence of this tuple as a claim that all three writers exist.
CONTEXT_CURRENT_TOKENS_SOURCES: "tuple[str, ...]" = (
    "post-tool-use",
    "user-prompt-submit",
    "manual",
)

#: A dedicated story-spend threshold key (§ A3). Resolution order for
#: story-spend consumers: explicit CLI --threshold > state[this key] > the
#: module default. Never falls back to context_budget_threshold — that key is
#: orchestrator-track and a silent fallback is exactly the conflation this
#: story exists to remove.
STORY_SPEND_THRESHOLD_KEY: str = "story_spend_threshold"
STORY_SPEND_THRESHOLD_DEFAULT: int = 120000

_TRACK_LABELS: "dict[str, str]" = {
    TRACK_ORCHESTRATOR: "orchestrator window",
    TRACK_STORY_SPEND: "story spend (subagent cost — not headroom)",
}


def track_label(track: str) -> str:
    """Return the operator-facing caption for *track*.

    Every Python surface that prints either the orchestrator-window number or
    the story-spend number must label it through this helper rather than
    hand-writing a caption, so the two captions cannot drift apart. Unknown
    values return ``"unlabelled"`` rather than raising — this function is
    total.
    """
    return _TRACK_LABELS.get(track, "unlabelled")
