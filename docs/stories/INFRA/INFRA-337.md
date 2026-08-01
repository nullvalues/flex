---
id: INFRA-337
rail: INFRA
title: Fix JSON-verdict parser: parse_worker_outcome must handle braces inside BUILD-RESULT/REVIEW-RESULT string fields
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

HIGH finding F6 of `docs/build-loop-cold-eyes-review-20260801.md`, corroborated independently at
the identical line by both reviewers: `subagent_transcript.py`'s `parse_worker_outcome` extracts a
candidate JSON object with the non-nesting regex `\{[^{}]*\}`. A BUILD-RESULT/REVIEW-RESULT whose
`reason`/`findings`/`fail_cause` string field quotes a code snippet containing a literal `{...}`
(routine reviewer prose in this codebase — e.g. "the guard `if (x) { revert() }` is unreachable")
fails to match as a single balanced object; only an unparseable inner fragment matches. The whole
outcome then stays `None` — no effort outcome, no FAIL bump, no escalation — directly feeding
INFRA-336's F1 symptom. Reconcile re-runs the same parser on retry, so a once-malformed row never
self-heals.

Fix direction: replace the regex with a proper balanced-brace scan (or attempt sequential
`json.JSONDecoder.raw_decode` calls starting at each `{` in the text) so nested/quoted braces inside
string values don't truncate the match.

## Requires
<!-- Prior stories, system state, or file conditions that must hold before building. -->

## Ensures
<!-- Binary assertions the reviewer checks independently. One per line.
     Each must be verifiable without interpretation: file exists, command output
     contains X, function Y returns Z. -->
<!-- State the correct signal AND the forbidden proxy (INFRA-314): e.g. "the
     write is absent after refusal; forbidden proxy: a warning line while the
     write happens anyway." -->

## Instructions

## Tests
