---
id: BUILD-010
rail: BUILD
title: STORY SPEC completeness check in reviewer.md.j2
status: complete
phase: "51"
story_class: methodology
primary_files:
  - skills/pairmode/templates/agents/reviewer.md.j2
  - .claude/agents/reviewer.md
---

# BUILD-010 — STORY SPEC completeness check in reviewer.md.j2

## Background

The reviewer currently checks RAIL SCOPE (check 6) — whether the story file
exists and whether touched files are in declared scope. It does NOT check whether
the story file itself is a complete spec.

A stub story that passes the pre-story stub gate (BUILD-009) should not have
been built in the first place, but the reviewer is a second enforcement layer.
More concretely: a story file might have an Ensures section but still contain
"See phase doc" delegation language. The builder will have read the phase doc;
the reviewer should surface this as a methodology violation.

## Acceptance criterion

A new check is added to `reviewer.md.j2` between check **2 (STORY SCOPE)** and
check **3 (BUILD GATE)** — making it check **2.5 STORY SPEC**:

```
**2.5 STORY SPEC**
Read docs/stories/<RAIL>/<RAIL>-NNN.md (the story file for this story).

Check:
a. Does the story file contain delegation language — "See phase doc",
   "See docs/phases/", or "See phase-"? If yes: FAIL — STORY SPEC (HIGH).
   The story file must be the builder's complete contract; phase doc references
   in the story spec are a methodology violation.
b. Does the story file have no ## Ensures AND no ## Acceptance criterion AND
   no ## Acceptance criteria section? If yes: FAIL — STORY SPEC (HIGH).
   A story without an acceptance surface cannot be verified.
c. If the story file is not found (legacy story predating the story-file
   convention): PASS with LOW note ("legacy story — no story file").

Severity: HIGH for (a) and (b). Blocks story completion until resolved.
```

The rendered `.claude/agents/reviewer.md` in the flex project must also be
updated to match the template.

## Out of scope

- Do not change any other check in reviewer.md.j2.
- Do not update downstream project reviewer.md files — they pick up on next sync.
- Do not change the check numbering for items 3–6 (they stay as-is even though
  the new check is 2.5 — numbering is human-readable labels, not an enforcement
  contract).
