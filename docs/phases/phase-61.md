---
era: "002"
---

# project — Phase 61: Scope-Miss Capture & Pre-Story Scope Checks

← [Phase 60: Checkpoint report intelligence — phase-key fix and next-phase detection](phase-60.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Close the scope-miss feedback loop by making both detection and prevention mechanical. The companion sidebar gains a new capture type that recognizes the scope_guard-block-then-elevate pattern in transcripts and writes a scope_miss lesson automatically, surfacing previously invisible friction without orchestrator recall. In parallel, a new flex_build.py check-story-scope subcommand applies co-dependency heuristics to a story's declared primary_files and touches, flagging likely-missing declarations (companion tests, rendered template counterparts) before the builder is spawned. Wiring the check into the pre-story step of CLAUDE.build.md and its Jinja2 template ensures every story in the build loop gets the informational warning, advancing Era 002's theme of surfacing scope issues at capture time and at gate time.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-154 | companion sidebar scope_miss capture from scope_guard elevation pattern | complete |
| INFRA-155 | `flex_build.py check-story-scope RAIL-NNN` — co-dependency heuristic warnings | planned |
| BUILD-025 | wire `check-story-scope` into CLAUDE.build.md pre-story step (live + template) | planned |

**Story dependency:** BUILD-025 depends on the `check-story-scope` subcommand introduced in INFRA-155. Build INFRA-155 before BUILD-025. INFRA-154 is independent of the other two and may be built in any order.

## Schema delivery

| Object | Management surface | Exception |
|---|---|---|
| — | — | No new persistent schema objects (scope_miss lessons reuse the existing `lessons.json` schema; no new fields) |

---

### CP-61 Cold-eyes checklist

— developer fills in after phase completion —
