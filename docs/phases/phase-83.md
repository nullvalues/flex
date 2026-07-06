---
era: "003"
---

# flex — Phase 83: Spec quality gates

← [Phase 82: security-auditor: document pairmode hook exceptions + audit scope rule](phase-82.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->

## Goal

Reduce the 18.5% fleet-wide retry rate by improving spec accuracy and completeness before the builder fires. Six targeted interventions: enable effort tracking on flex itself (closing the blind spot where the tool that built effort tracking has no data on itself), capture reviewer FAIL cause in the effort DB, add template prompts that steer authors toward architecture.md declarations, enforce body-section completeness in the schema validator, add an informational scope-budget count warning, and introduce a `test_gate` frontmatter field that lets story authors defer whole-suite green to phase checkpoints. None of these changes alter the builder/reviewer loop structure.

## Stories

| ID | Title | Status |
|----|-------|--------|
| BUILD-042 | Enable effort_tracking on flex itself | complete |
| BUILD-043 | Reviewer FAIL reason capture via --notes | complete |
| INFRA-186 | architecture.md template prompt in story_new.py and check-story-scope | complete |
| INFRA-187 | Body-section enforcement: non-pointer Ensures required for code and methodology stories | complete |
| INFRA-188 | Scope budget warning in check-story-scope | complete |
| INFRA-189 | test_gate frontmatter annotation | complete |

## Schema delivery

No new persistent schema objects introduced in this phase. The `notes` column referenced in BUILD-043 already exists in the `attempts` table in `effort.db` (added at schema init in `skills/pairmode/scripts/effort_db.py`).
