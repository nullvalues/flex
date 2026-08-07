---
era: "005"
phase_class: production
---

# project — Phase 142: Durable oracle-based fix for story_new.py frontmatter round-trip (CER-214/215/216)

← [Phase 141: Fix story_new.py writer/reader escaping mismatch (CER-213)](phase-141.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Close CER-214/215/216 with a single durable fix, not another narrow patch: story_new.py's _yaml_block_scalar has now had three narrow patches (CER-167, CER-211, CER-213), each fixing exactly what a security audit found and each leaving a new gap in the same function -- most recently a str.splitlines()-boundary-character injection primitive (CER-214, CRITICAL), an incomplete unicode-whitespace-before-# check (CER-215), and a bare '---'-suffix that truncates the entire frontmatter block, silently dropping later keys (CER-216, CRITICAL). Replace the hand-maintained denylist approach with an oracle-based design: build each candidate rendering (bare, double-quoted, single-quoted) and verify it round-trips byte-identically through the real schema_validator._parse_frontmatter reader (embedded with a trailing sentinel key to detect frontmatter truncation) before emitting it; raise only when no candidate round-trips. This makes the writer's guarantee structurally unable to drift from the reader's actual behavior again, closing the whole failure class rather than one more character. Pair with a regression test suite built from Python's actual line-boundary/whitespace character sets (str.splitlines() detection, re.search(r'\s', ...) detection) rather than hand-picked examples, so a future reader change or missed character is caught automatically.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-412 | Durable oracle-based fix for story_new.py frontmatter round-trip (CER-214/215/216) | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-142 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
