---
id: INFRA-025
rail: INFRA
title: Add formal containment check to era_new.py path construction (CER-011)
status: complete
phase: "backlog-legacy"
primary_files:
  - skills/pairmode/scripts/era_new.py
touches: []
---

**Phase-frontmatter correction (INFRA-310, check-index cross-link fix, 2026-08-01):** the original phase: value named a bucket ("backlog" or empty), not a real phase doc. Re-anchored to `docs/phases/phase-backlog-legacy.md`, a legacy anchor doc created for exactly this class of pre-manifest stub. No behavior or status change.

## Acceptance criterion

`era_new.py` uses `resolve().relative_to(project_dir.resolve())` as a formal containment
check on the era file destination path, in addition to the existing `_slugify()` cleanse.
Test asserts containment failure raises ValueError on a crafted name.

## Background (CER-011)

Source: Security audit cp18 (2026-04-30). Severity: LOW. `_slugify()` neutralises "/" and
"." in `--name` before path construction, providing effective but informal traversal
prevention. No formal `resolve().relative_to()` containment check present.
`era_new.py:25-31, 114-116`.

## Instructions

After resolving the destination path, wrap a `relative_to()` call in try/except and
raise ValueError with a clear message on failure. Add containment test.
