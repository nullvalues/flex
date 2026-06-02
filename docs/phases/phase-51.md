# flex — Phase 51: Stub gate and phase-doc scan enforcement

← [Phase 50: Phase/story spec boundary policy](phase-50.md)

## Goal

Make the phase/story boundary mechanically enforced, not just policy. Two
failure modes diagnosed across downstream projects require two gates:

1. **Delegation** (forqsite pattern): story files route the builder to the
   phase doc for the "full spec." The story file is a digest, not a contract.
   Fix: pre-story stub gate — block before spawning the builder if the story
   file contains "See phase doc" language or has no acceptance criterion.

2. **Duplication** (radar pattern): phase doc contains full story specs inline
   alongside self-contained story files. The story is authoritative but the
   phase bloats. Fix: phase doc boundary scan at build-loop start — report
   embedded story sections in the phase doc and block until they are moved.

The third story adds a `check-stubs` CLI that lets operators audit any
downstream project before a build, seeing the full scope of stub stories
upfront rather than discovering them one at a time during builds.

## Stories

| ID | Title | Status |
|----|-------|--------|
| BUILD-009 | Phase doc boundary scan + pre-story stub gate in CLAUDE.build.md.j2 | complete |
| BUILD-010 | STORY SPEC completeness check in reviewer.md.j2 | complete |
| INFRA-134 | check-stubs CLI in flex_build.py | complete |

## Schema delivery

No new schema objects.

## Out of scope

- Automatic migration of existing stubs — the gate forces migration story-by-story
  at build time; no bulk migration script is in scope
- Backfilling forqsite phase docs to remove embedded story sections — out of scope;
  the phase doc boundary scan reports them at build time and the orchestrator migrates
- Downstream project CLAUDE.build.md / reviewer.md files — they pick up both gates
  on next `pairmode sync`

Tag (on ship): `cp51-stub-gate-enforcement`
