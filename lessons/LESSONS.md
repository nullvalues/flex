# Anchor Methodology Lessons

This file is auto-generated from `lessons.json`. Edit `lessons.json` directly
or use `/anchor:pairmode lesson` to capture a new lesson.

## L001 — Ran audit against cora — a project with pairmode scaffold but no pairmode_context.json
**Date:** 2026-04-20
**Status:** captured
**Learning:** When audit detects no pairmode_context.json, it should emit a prominent warning: 'No pairmode_context.json found — template body comparison will show false INCONSISTENT for all variable-bearing sections. Bootstrap this project with /anchor:pairmode to fix.' MISSING and EXTRA findings remain reliable; INCONSISTENT findings require a context file to be meaningful.

## L002 — Ran audit against radar and forqsite — projects with pairmode scaffold
**Date:** 2026-04-20
**Status:** captured
**Learning:** The _split_sections output uses '---' as section keys in audit output. These entries are hard to interpret. Either: (a) skip separator-keyed sections from INCONSISTENT comparison since --- separators carry no semantic content, or (b) display the surrounding context (what section comes before/after) when reporting --- inconsistencies.
