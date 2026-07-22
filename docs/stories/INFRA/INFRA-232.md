---
id: INFRA-232
rail: INFRA
title: Fix README era-status and production-readiness contradictions; remove stale duplicate readme.md
status: draft
phase: "97"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - README.md
touches: []
---

## Context

A cold-eyes review this session found `README.md` internally contradictory
in two ways, plus a stale duplicate file:

1. **Era status**: README.md lists "Era 001 — pairmode foundation (complete)"
   and "Era 002 — build loop and observability (**active**)", but
   `docs/eras/002-flex-build-loop-and-observability.md` has
   `status: complete` and `docs/eras/003-flex-orchestrator-as-harness.md`
   (`status: active`) — the actual active era, "Orchestrator as harness" —
   isn't mentioned in README.md at all.
2. **Status section**: README.md's `## Status` section says "Production-ready
   for solo developers... Core workflows are stable" in one line, then later
   states "Alpha software. Internal APIs and scaffold formats may change
   without notice." under Known Limitations — directly contradictory framing.
   Operator direction (2026-07-22): the project is better described as
   **beta, production-adjacent** — neither "production-ready" nor "alpha."
3. **Duplicate stale file**: a lowercase `readme.md` (ASCII-art header,
   last touched 2026-06-26 during the anchor→flex rename) coexists with the
   actively-maintained `README.md` (last touched 2026-07-21). It is fully
   superseded content and a real hazard on case-insensitive filesystems
   (macOS/Windows) where the two could silently collide or shadow each
   other.

## Requires

- `docs/eras/002-flex-build-loop-and-observability.md` (`status: complete`)
  and `docs/eras/003-flex-orchestrator-as-harness.md` (`status: active`,
  "Orchestrator as harness" — the Era 3 thin-dispatch-loop work this whole
  phase's fold effort is part of) as the authoritative source for the
  corrected era summary.

## Ensures

- README.md's era summary lists all three eras with correct status: Era 001
  (complete), Era 002 (complete), Era 003 (active) — "Orchestrator as
  harness," with a one- or two-sentence description drawn from
  `docs/eras/003-flex-orchestrator-as-harness.md`'s own "Strategic intent"
  section (the orchestrator-as-thin-dispatch-loop / `next-action` resolver
  concept), not invented independently.
- README.md's `## Status` section no longer contains the word
  "Production-ready" or the phrase "Alpha software" in contradiction with
  each other — reworded to a single consistent characterization: beta,
  production-adjacent (e.g. "Beta — approaching production-readiness for
  solo developers. Core workflows are stable and self-hosted on this repo;
  internal APIs and scaffold formats may still change without notice.").
  The Known Limitations section's existing bullet is reconciled with this
  (either merged into the Status section or reworded so it no longer reads
  as a flat contradiction — no two sections should assert conflicting
  maturity claims).
- The lowercase `readme.md` file is removed (`git rm`) — confirmed superseded
  content, not merged or preserved elsewhere (its content is fully
  redundant with README.md's own introduction).
- No other content in README.md is changed beyond these two corrections.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` passes (run
  without `-x`; report every failure, confirm only the known CER-070
  environmental one remains) — this is a doc-only change, so no test should
  be affected, but confirm nothing references the removed `readme.md`.

## Instructions

1. In `README.md`, update the era summary section: keep "Era 001 — pairmode
   foundation (complete)" as-is, change "Era 002 — build loop and
   observability (active)" to "(complete)", and add a new "Era 003 —
   orchestrator as harness (active)" entry with a brief description drawn
   from `docs/eras/003-flex-orchestrator-as-harness.md`'s Strategic Intent
   section.
2. In `README.md`'s `## Status` section, reword to a single consistent
   "beta, production-adjacent" characterization (see Ensures for suggested
   phrasing) that doesn't contradict the Known Limitations "Alpha software"
   bullet — either remove/reword that Known Limitations bullet to match, or
   fold the maturity claim into one place. Keep the edit minimal.
3. Run `grep -rn "readme.md" .` (case-sensitive, excluding `.git/`) to
   confirm nothing else in the repo references the lowercase file by name
   before removing it (a broken link would be a regression).
4. `git rm readme.md`.
5. Run the full test suite without `-x` and confirm the only failure is the
   known CER-070 environmental one.

## Out of scope

- Any other content change to README.md beyond the two corrections named
  above (e.g. do not rewrite the "What flex does" section, installation
  instructions, or any other part).
- Updating `docs/eras/*.md` themselves — those are already correct; this
  story only brings README.md into agreement with them.
- Any change to CHANGELOG.md or other doc-currency surfaces beyond
  README.md and the readme.md removal.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental
failure — run without `-x` and report every failure seen, not just the
first.
