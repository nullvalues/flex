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
