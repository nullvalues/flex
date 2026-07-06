---
id: INFRA-197
rail: INFRA
title: Architecture doc stale claims
status: draft
phase: "HARNESS011-main"
story_class: documentation
auth_gated: false
schema_introduces: false
primary_files:
  - docs/architecture.md
touches:
  - skills/pairmode/templates/CLAUDE.build.md.j2
---

## Acceptance criterion

- **CER-014** — `docs/architecture.md` § "Reviewer-class agent tool restriction
  (build-loop safety)" is updated to accurately describe the current protection model.
  The claim about a "pre-reviewer commit discipline" is either:
  (a) removed if it no longer exists in the build loop, or
  (b) added to `CLAUDE.build.md.j2` if it should exist.
  After this story, the architecture doc and the template are consistent.
- **CER-035** — `docs/architecture.md` § Agent definitions no longer states that
  `security-auditor` has no `Bash`. The section reflects that all reviewer-class agents
  share `tools: [Read, Bash, Glob, Grep]` (as established by Phase 53 BUILD-020).
- `TEST RUN: documentation story — no test file expected`.

## Instructions

### CER-014 — pre-reviewer commit discipline

Read the current `docs/architecture.md` subsection on reviewer-class agent tool
restriction. Read the current `CLAUDE.build.md` (harness) and `CLAUDE.build.md.j2`
template. Determine which of these is true:
- (a) The pre-reviewer commit discipline (committing story files + `git checkout -- lessons/`)
  is not encoded anywhere → remove the claim from architecture.md.
- (b) The discipline should be encoded → add it to `CLAUDE.build.md.j2` and note it in
  architecture.md.

Apply whichever fix is accurate. Do not invent a discipline that isn't there.

### CER-035 — security-auditor Bash claim

Find the stale line in `docs/architecture.md` (around line 248) that claims
`security-auditor` has no `Bash`. Replace with accurate text: all reviewer-class agents
(reviewer, security-auditor, intent-reviewer) share `tools: [Read, Bash, Glob, Grep]`.
