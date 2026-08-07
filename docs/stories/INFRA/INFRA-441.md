---
id: INFRA-441
rail: INFRA
title: Repoint flex build loop at marketplace install; retire release-channel docs
status: draft
phase: "145"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - CLAUDE.build.md
  - docs/architecture.md
touches:
  - docs/harness-cutover-runbook.md
  - docs/phases/phase-proposed-retire-harness-release-channel-20260804-001.md
  - tests/pairmode/test_harness_path_audit.py
narrative_roles: []
---

## Context

flex's own build loop still resolves `pairmode_scripts_dir` to
`/mnt/work/flex-harness/skills/pairmode/scripts`, and `checkpoint-tag` still
promotes into that clone with a `merge --ff-only`. The release channel existed
to decouple flex's orchestrator from the working tree it is editing (the
RESOLVER-012..017 self-reference incidents). Phase 120/CER-159's
marketplace-installed plugin copy now provides that same decoupling from a
version-keyed, read-only install, so the channel is redundant machinery with an
ongoing promotion cost. This story is the tooling/docs half of Phase 145: repoint
flex's own dogfooding at the marketplace install and retire the release-channel
documentation. Sibling INFRA-440 handles the repo/branch merge-down and clone
disposition.

## Requires

- INFRA-440 landed or landing concurrently (the fold-prep merge-down must not be
  stranded behind docs that already declare the channel retired).
- `~/flex-marketplace-cache/flex-0.3.1/skills/pairmode/scripts/flex_build.py`
  exists on the build host (verified live at spec time).


## Scope widenings

| path | reason | widened_at |
| --- | --- | --- |
| tests/pairmode/test_harness_path_audit.py | Removing CLAUDE.build.md's flex-harness references (this story's Ensures) leaves the CLAUDE.build.md allowlist entry in this CER-160 audit test stale; the story's own test-suite-green Ensures requires updating it. | 2026-08-07T18:16:48Z |

## Ensures

- `grep -n 'flex-harness' CLAUDE.build.md` returns no matches: no
  `pairmode_scripts_dir` value, no orchestrator call site, and no checkpoint-tag
  promotion step references the flex-harness clone.
- `CLAUDE.build.md`'s `pairmode_scripts_dir` is
  `~/flex-marketplace-cache/flex-0.3.1/skills/pairmode/scripts`, and every call
  site in that file that spells the scripts directory spells that same path.
- Live check, not a string check:
  `PATH=$HOME/.local/bin:$PATH uv run python ~/flex-marketplace-cache/flex-0.3.1/skills/pairmode/scripts/flex_build.py next-action --help`
  exits 0. Forbidden proxy: the path string appears in `CLAUDE.build.md` but does
  not resolve to a runnable `flex_build.py`.
- The `checkpoint-tag` sequence in `CLAUDE.build.md` ends at the git tag and push;
  it contains no `git -C /mnt/work/flex-harness merge` step and no successor
  promotion step of any kind.
- `docs/architecture.md` § "Release channel — flex-harness" no longer claims the
  channel is permanent, and its replacement text names (a) the marketplace-cache
  install as the current self-reference-decoupling mechanism, (b) Phase 120/
  CER-159 as its origin, and (c) the RESOLVER-012..017 incident history the old
  channel protected against, with an explanation of how the marketplace install
  protects against that same failure. Forbidden proxy: the "permanent" warning is
  deleted without the incident rationale being carried forward.
- `docs/harness-cutover-runbook.md` carries a final status note naming Phase 145
  as the point of retirement; its body is otherwise unchanged.
- `docs/phases/phase-proposed-retire-harness-release-channel-20260804-001.md` does
  not exist.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` is green.

## Instructions

1. Confirm the install path before editing:
   `ls ~/flex-marketplace-cache/flex-0.3.1/skills/pairmode/scripts/flex_build.py`.
   The cache is version-keyed; if `flex-0.3.1` is not the live directory, use the
   directory that is and say so in the story completion note.
2. In `CLAUDE.build.md`, find every occurrence with
   `grep -n 'flex-harness' CLAUDE.build.md` and repoint each to the marketplace
   path. This includes the `pairmode_scripts_dir` definition and all orchestrator
   call sites that spell the path literally.
3. In the same file, remove the flex-harness promotion step from the
   `checkpoint-tag` sequence. Do not replace it with an equivalent step against
   another clone — after this story the sequence terminates at tag + push.
4. Rewrite `docs/architecture.md` § "Release channel — flex-harness" per the
   Ensures above. Read
   `docs/phases/phase-proposed-retire-harness-release-channel-20260804-001.md`'s
   Background section first and carry its RESOLVER-012..017 reasoning into the new
   text — the section is being *superseded*, not erased. Retitle the section to
   reflect the current mechanism (e.g. "Self-reference decoupling — marketplace
   install") and keep a short "formerly the flex-harness release channel"
   sentence so existing cross-references still land.
5. Append a dated final-status line to `docs/harness-cutover-runbook.md` stating
   the release channel was retired in Phase 145 and the runbook is closed history.
6. Delete
   `docs/phases/phase-proposed-retire-harness-release-channel-20260804-001.md`
   with `git rm`. **This story owns the deletion; INFRA-440 must not delete it.**
   If the file is already gone (INFRA-440 landed it early), that is not a failure —
   verify its content is present in the phase-145 doc and this story's
   architecture.md rewrite, and move on.
7. Frontmatter note: the stub declared no `primary_files`/`touches`; both were
   populated at spec time from the enumerated edit surface (Step 7 scope rule) so
   the story's declared scope matches what it changes.

## Tests

```bash
grep -n 'flex-harness' CLAUDE.build.md; test $? -eq 1
PATH=$HOME/.local/bin:$PATH uv run python ~/flex-marketplace-cache/flex-0.3.1/skills/pairmode/scripts/flex_build.py next-action --help
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: the grep finds nothing in `CLAUDE.build.md`, `next-action --help`
exits 0 from the marketplace path, and the suite is green. No new test file is
expected — this story changes documentation and orchestrator configuration only.

## Out of scope

- `pairmode_scripts_dir` references in the 17 sibling consuming repos under
  `/mnt/work/` — that is the 0.4.1 cleanup-script / config-canon / final-sync-all
  phase (`docs/release-0-4-1-findings-20260807.md`), not this story.
- The fold-prep merge-down, stale remote branch removal, and disposition of the
  `/mnt/work/flex-harness` clone itself — INFRA-440.
- Changing which marketplace version flex pins to, or automating cache-version
  discovery. This story hardcodes the live version-keyed path; a resolver is a
  separate concern.
