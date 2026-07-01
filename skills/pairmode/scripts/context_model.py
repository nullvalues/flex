"""Thin-harness context growth model constants.

The thin dispatch loop's per-step context growth is the JSON return block from
flex_build.py next-action plus the leaf-worker's return summary and <usage> block.
This is fundamentally different from a builder's per-story cost (effort.db).

THIN_HARNESS_STEP_TOKENS is a deliberate, documented constant — not derived from
effort.db. It is the seed value for expected_step_tokens in the context budget.
The SPA display provenance label is tracked in OBS-003 (Phase G).
"""

THIN_HARNESS_STEP_TOKENS: int = 5000
