---
id: INFRA-088
rail: INFRA
title: "Filesystem paths and identifier rename (_ANCHOR_ROOT, ~/.anchor, /tmp/anchor_*, ANCHOR_PROJECT_*)"
status: planned
phase: "35"
story_class: code
primary_files:
  - .claude/settings.json
  - skills/seed/scripts/mine_sessions.py
  - skills/seed/scripts/reconcile.py
  - skills/pairmode/scripts/story_context.py
  - skills/pairmode/scripts/effort_recorder.py
  - skills/companion/scripts/sidebar.py
  - skills/companion/scripts/launch_sidebar.sh
  - skills/companion/scripts/launch_sidebar.command
  - skills/companion/scripts/start_sidebar.sh
  - skills/pairmode/scripts/lesson.py
  - skills/pairmode/scripts/lesson_review.py
  - skills/pairmode/scripts/pairmode_status.py
  - skills/pairmode/scripts/phase_new.py
  - skills/pairmode/scripts/cer.py
  - skills/pairmode/scripts/record_attempt.py
  - skills/pairmode/scripts/bootstrap.py
  - skills/pairmode/scripts/spec_exception.py
  - hooks/session_start.py
  - .claude/agents/security-auditor.md
  - skills/pairmode/templates/agents/security-auditor.md.j2
touches:
  - tests/pairmode/test_pairmode_status.py
  - tests/pairmode/test_sidebar_story_panel.py
  - tests/pairmode/test_pairmode_sync.py
  - tests/pairmode/test_drift_evidence.py
  - tests/pairmode/test_sync_agents.py
  - tests/pairmode/test_lesson_review.py
---

## Requires

See `docs/phases/phase-35.md` — Story INFRA-088.

## Ensures

See `docs/phases/phase-35.md` — Story INFRA-088.

## Instructions

See `docs/phases/phase-35.md` — Story INFRA-088.

## Tests

See `docs/phases/phase-35.md` — Story INFRA-088.
