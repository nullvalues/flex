---
id: INFRA-317
rail: INFRA
title: Covered-contracts gate — Build standards covered_contracts pairs; builder pre-build read gate on scope intersection; doc wins on conflict
status: draft
phase: "116"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/builder/procedure.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - CLAUDE.build.md
  - skills/pairmode/scripts/bootstrap.py
  - skills/pairmode/scripts/pairmode_sync.py
  - tests/pairmode/test_procedure_skills.py
  - tests/pairmode/test_templates.py
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Cora item A#5 (AG-6): structured payloads whose shape no database enforces —
JSON blobs, markdown tables read by parsers, wire formats between scripts —
are "covered contracts": a canonical doc section describes the shape, code
reflects it. "Without the gate, the doc becomes aspirational and the code
file silently becomes the only truth … the load-bearing piece of doc-first
development." The cold-eyes review's § 4 diagnosis (architecture.md
ossifying, README describing a retired loop) is the same disease on flex's
own surfaces; INFRA-311 fixed the *fleet* propagation half — this story
gives projects the *builder-side* half.

Two pieces, both methodology surfaces (procedure + template), one small
tooling touch:

1. **Build standards gains `covered_contracts:`** — a list of
   `doc-section ↔ source-file` pairs, declared per project in
   `CLAUDE.build.md`'s Build standards block (template
   `CLAUDE.build.md.j2:50`, the INFRA-240 per-project-facts pattern).
2. **Builder procedure gains a pre-build read gate:** before writing code,
   the builder intersects the story's `primary_files`/`touches` with the
   declared pairs; on any hit it must read **both** the doc section and the
   source file, and **the doc wins on conflict** — a mismatch is either
   fixed doc-first or surfaced as a finding, never silently resolved
   code-first.

**Correct signal: a builder touching a covered file demonstrably read the
paired doc section (the procedure requires quoting the contract line(s)
relied on in the story evidence) and any divergence is surfaced. Forbidden
proxy: a procedure sentence saying "be aware of covered contracts" with no
intersection step and no evidence requirement — awareness prose is exactly
the aspirational-doc failure this gate exists to end.**

## Requires

1. The Build standards block is a single rendered line
   (`CLAUDE.build.md.j2:50`) with `key=`value`` segments joined by `|`;
   `bootstrap.py:1145` notes skills read from it (INFRA-240). List-valued
   keys need a segment-safe encoding — follow `protected_paths`'s existing
   `join(', ')` pattern; pairs encode as `doc-section↔source-file`
   (choose and document an unambiguous separator that cannot appear in
   paths; `↔` or `::`).
2. The builder procedure (`skills/pairmode/skills/builder/procedure.md`) —
   locate the pre-build/recon step to host the gate; the reviewer procedure
   references builder evidence obligations, so the evidence-quoting
   requirement must name where in the story file it lands (`## Evidence`).
3. Flex's own first pairs are the seed (declare, minimally: the CER backlog
   row format ↔ `cer.py` parsers; the next-action JSON grammar ↔
   `next_action.py`). A gate shipped with an empty registry is the vacuity
   failure INFRA-308 just fixed elsewhere — ship ≥ 2 live pairs.
   **Flex's live `CLAUDE.build.md` (52 lines) currently contains NO Build
   standards block at all** — the block exists only in the downstream
   template (`CLAUDE.build.md.j2:50`). Declaring flex's pairs is therefore
   a structural addition of the whole Build standards line to
   `CLAUDE.build.md`, not a one-key tweak; add the full INFRA-240 block
   (test_command/test_dir/protected_paths/domain_isolation_rule populated
   with flex's real values) plus `covered_contracts`, so flex's own file
   finally matches the contract it ships downstream.
4. `bootstrap.py`/`sync` render the template downstream; the new key must
   default to empty-and-harmless for projects that declare nothing.
5. Baseline 4116/211.

## Ensures

1. **Template key exists and renders.** `covered_contracts` appears in
   `CLAUDE.build.md.j2`'s Build standards line with the documented pair
   encoding; unset → `(none)`, and rendered output for a no-pairs project
   is otherwise byte-identical to today's.
2. **Builder procedure gate is a numbered step with an evidence
   obligation.** The procedure's pre-build sequence gains: compute the
   intersection; for each hit read doc section + source file; quote the
   contract line(s) relied on into the story's `## Evidence`; on
   divergence, doc wins — fix doc-first in-scope if trivial, else file a
   CER row and stop. **The forbidden proxy (advisory prose without the
   intersection/evidence steps) must not be what lands.**
3. **Flex declares ≥ 2 live pairs** (Requires 3) in its own
   `CLAUDE.build.md`, and `docs/architecture.md` documents the mechanism
   (what qualifies as a covered contract, the doc-wins rule, the pair
   encoding) in ≤ 25 lines.
4. **Tests pin the surface.** `test_templates.py` asserts the template key
   and its unset default; `test_procedure_skills.py` asserts the builder
   procedure contains the intersection step, the doc-wins rule, and the
   evidence-quoting requirement (text-presence pins, the same style those
   suites already use for procedure contracts).
5. **Suite green** without `-x`; baseline + added tests.

## Instructions

1. Choose the pair separator first and pin it in one place (template
   comment + architecture doc); path-safety justification in one line.
2. Write the procedure step to be executable by a thin worker: concrete
   commands (grep the intersection), not judgment prose.
3. Seed flex's pairs and verify each named doc section actually exists
   (a dangling pair at spec time would be born-aspirational).

**Do not:** build a runtime enforcement hook (this is a procedure gate;
mechanical enforcement is a future story if the procedure proves
insufficient); resolve any existing doc/code divergence beyond the seed
pairs' verification (INFRA-305 owns the sweep); let "doc wins" mean
silently editing code to match a stale doc — divergence surfaces, a human
dispositions.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_templates.py tests/pairmode/test_procedure_skills.py -q 2>&1 | tail -10
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -5
```

Acceptance: green; baseline held. Reviewer negative checks: (a) both seed
pairs' doc sections exist at the named locations; (b) the procedure step
includes the evidence-quoting obligation, not just a read instruction;
(c) unset-key rendering is byte-identical for a no-pairs project.

## Out of scope

- Mechanical (hook-level) enforcement of the read gate.
- TypeScript-reflection tooling from cora's original (their compiled-TS
  half is project-specific; the flex mechanism is language-neutral pairs).
- Sweeping existing divergences (INFRA-305; CER rows for the rest).
