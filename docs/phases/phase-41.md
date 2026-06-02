---
era: "001"
---

# flex — Phase 41: Re-frame docs around pairmode as the lead capability

← [Phase 40: Pre-story schema gate](phase-40.md)

## Goal

Flex's primary feature has become **pairmode** — the structured builder/reviewer
workflow with effort tracking, per-story schema gates, context budget checks, and
model selection per attempt. The companion layer (sidebar, state.json, lessons) still
exists, but it is now the plumbing that pairmode sits on top of, not the headline.

The four documents a reader hits first — `README.md`, `docs/brief.md`,
`docs/architecture.md`, and `CLAUDE.md` — still describe flex as a companion/memory
tool with pairmode as a secondary feature. `CLAUDE.md` even claims pairmode is still
being built, which has been false since Phase 16 and is dramatically false after 24
further phases of pairmode work.

This phase rewrites the lead framing in all four documents so pairmode is presented
as the primary capability and companion as the supporting infrastructure. No code
changes — documentation only.

**Story dependencies:** none (all four stories are independent).

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-106 | Re-frame `README.md` around pairmode as the lead capability | planned |
| INFRA-107 | Re-frame `docs/brief.md` around pairmode as the lead capability | planned |
| INFRA-108 | Re-frame `docs/architecture.md` around pairmode as the lead capability | planned |
| INFRA-109 | Update `CLAUDE.md` project context to reflect pairmode as shipped | planned |

---

### Story INFRA-106 — Re-frame `README.md` around pairmode as the lead capability

**Rail:** INFRA | **story_class:** doc

#### Requires

- `README.md` exists at repo root.
- The "What flex does" section currently presents the Memory layer first and
  the Process layer (pairmode) second.
- The "Reactive memory vs proactive process" comparison table has Companion in
  the second column and Pairmode in the third.
- The "Three skills" table lists `/flex:seed`, `/flex:companion`,
  `/flex:pairmode` in that row order.
- Scenario B in "Use case scenarios" treats the companion sidebar as the
  re-entry point rather than `/flex:pairmode audit`.

#### Ensures

1. In the opening "What flex does" section, the **Process layer (pairmode)**
   paragraph appears **before** the Memory layer paragraph. The pairmode
   paragraph leads with language such as: "Pairmode is the primary workflow:
   a structured builder/reviewer loop with effort tracking, per-story schema
   gates, context budget checks, and model selection per attempt." The memory
   layer paragraph is then introduced as supporting infrastructure ("The
   companion memory layer underneath pairmode captures decisions live and
   feeds them back into the build loop.").

2. The summary sentence under the two layers is updated from "Used together,
   the memory layer supplies the spec; the process layer enforces it." to a
   pairmode-leading sentence, e.g.: "Pairmode is the build loop. Companion is
   the memory it draws on."

3. The "Reactive memory vs proactive process" section is renamed to
   "Pairmode and companion: posture comparison" and the table column order is
   swapped so **Pairmode is the second column and Companion is the third**.
   The prose below the table is rewritten so the pairmode recommendation comes
   first.

4. The "Three skills" table row order is changed so pairmode-related rows
   appear first, companion next, seed last.

5. In "Use case scenarios", Scenario B is rewritten so the lead action is
   `/flex:pairmode audit` and the companion sidebar appears as a supporting
   step rather than the re-entry point.

6. The repo tagline, opening paragraph, "## Installation", "## The build loop",
   "## The canonical spec format", "## Known limitations", and
   "## Requirements and License" sections are preserved unchanged.

#### Instructions

**`README.md`**

- Swap the two paragraph blocks under "## What flex does" so the pairmode
  paragraph comes first. Rewrite the pairmode lead sentence per Ensures #1.
- Replace the "Used together" sentence per Ensures #2.
- Rename "### Reactive memory vs proactive process" to
  "### Pairmode and companion: posture comparison". Swap the second and
  third table columns (header row and every data row). Rewrite the prose
  paragraphs that follow the table so they lead with pairmode.
- In the "## The three skills" table, reorder rows: pairmode first,
  companion next, seed last.
- In "### Scenario B", rewrite step 1 to lead with `/flex:pairmode audit`,
  move the `/flex:companion` invocation to a later step framed as optional
  supporting capture.

Do **not** edit the tagline, opening paragraph, "## Installation",
"## The build loop", "## The canonical spec format", "## Known limitations",
or "## Requirements and License".

#### Tests

No test file expected for this documentation story.

The reviewer verifies:
1. In "## What flex does", the pairmode paragraph appears before the memory
   layer paragraph.
2. The comparison table's column order is: Dimension | Pairmode | Companion.
3. The "Three skills" table lists pairmode rows before companion and seed rows.
4. Scenario B's step 1 invokes `/flex:pairmode audit`, not `/flex:companion`.
5. Sections named in the "Do not edit" list are unchanged.
6. Full test suite passes: `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`.

`TEST RUN: documentation story — no test file expected`

---

### Story INFRA-107 — Re-frame `docs/brief.md` around pairmode as the lead capability

**Rail:** INFRA | **story_class:** doc

#### Requires

- `docs/brief.md` exists.
- The "## What this project produces" section lists `/flex:seed`,
  `/flex:companion`, `/flex:pairmode` in that order.
- The "## Why it exists" section frames flex primarily as
  "captures decisions as you work" — a memory-first framing.

#### Ensures

1. In "## What this project produces", the `/flex:pairmode` paragraph appears
   **first**, followed by `/flex:companion`, then `/flex:seed`. The pairmode
   paragraph leads with language that names pairmode as the primary surface —
   e.g., "**`/flex:pairmode`** — The primary flex workflow. Bootstraps and
   manages a structured builder/reviewer methodology…".

2. The "## Why it exists" section is rewritten so the first paragraph names
   the build-loop problem pairmode solves before the memory problem. Suggested
   opening: "Code is becoming cheap to generate. What's scarce is a build loop
   that holds intent steady from spec to commit. Pairmode is that loop: every
   story specced before code, every commit gated by a reviewer. The companion
   memory layer underneath records the decisions that pairmode needs to
   enforce."

3. The "## Core beliefs", "## Accepted tradeoffs", "## Constraints",
   "## Not in scope", and "## What a second implementation must preserve"
   sections are preserved unchanged.

#### Instructions

**`docs/brief.md`**

- Reorder the three skill paragraphs in "## What this project produces":
  pairmode first, companion second, seed third. Update the lead sentence of
  the pairmode paragraph per Ensures #1.
- Rewrite the first paragraph of "## Why it exists" per Ensures #2. Leave
  the remaining paragraphs intact, adjusting order only if needed so the
  pairmode framing reads first.

Do **not** edit anything from "## Core beliefs" onward.

#### Tests

No test file expected for this documentation story.

The reviewer verifies:
1. The first skill described in "## What this project produces" is
   `/flex:pairmode`.
2. The first paragraph of "## Why it exists" mentions pairmode and the
   build loop before mentioning persistent memory.
3. Sections "## Core beliefs" through "## What a second implementation must
   preserve" are unchanged.
4. Full test suite passes.

`TEST RUN: documentation story — no test file expected`

---

### Story INFRA-108 — Re-frame `docs/architecture.md` around pairmode as the lead capability

**Rail:** INFRA | **story_class:** doc

#### Requires

- `docs/architecture.md` exists.
- The "## What flex is" intro reads as a pure memory-first description
  ("gives Claude Code a persistent memory of architectural decisions…").
- The module structure block lists `seed/`, `companion/`, `pairmode/` under
  `skills/` in that order.
- There is no build-loop flow diagram or prose in the data-flow section.
- The "## Pairmode design" section is positioned after "## Hook architecture"
  and "## Companion data files".

#### Ensures

1. The "## What flex is" intro is rewritten to lead with pairmode. Suggested
   text: "Flex is a Claude Code plugin built around two layers. **Pairmode**
   is the primary workflow: a structured builder/reviewer build loop with
   effort tracking, per-story schema gates, context budget checks, and model
   selection per attempt. **Companion** is the memory layer underneath: a
   sidebar that captures decisions live and a canonical spec format
   (`spec.json`) that survives across sessions. Pairmode enforces intent at
   the build gate; companion records what was decided along the way."

2. The skills subtree of the module structure block is reordered so
   `pairmode/` appears first, then `companion/`, then `seed/`. Internal
   contents of each subtree are preserved unchanged.

3. A new "## Pairmode build loop" section is inserted immediately after
   "## Data flow" (before "## The canonical spec format"). It contains a
   prose description of the per-story flow: story spec → permission pre-write
   → builder spawn (with model selection) → tests → reviewer spawn (with model
   selection) → commit OR revert + retry → effort recording → loop-breaker on
   persistent fail → context budget check → checkpoint. Keep it under 30 lines.

4. The existing "## Pairmode design" section is moved so it appears
   **before** "## Hook architecture" and "## Companion data files". Its
   content is preserved unchanged except for the first sentence of
   "### Pairmode and companion: separation of concerns", which is rewritten to
   lead with pairmode: "Pairmode is flex's primary build workflow; companion
   is the memory layer it draws on."

5. "## Effort tracking", "## Layer rules", "## Phase documentation policy",
   "## Documentation currency policy", "## Build commands", and
   "## Protected files" are preserved unchanged.

#### Instructions

**`docs/architecture.md`**

- Rewrite the "## What flex is" paragraph per Ensures #1.
- In the module structure code block, reorder `skills/` children:
  `pairmode/` first, `companion/` second, `seed/` third.
- Insert a new "## Pairmode build loop" section after "## Data flow" per
  Ensures #3.
- Move the entire "## Pairmode design" section so it appears immediately
  after the new "## Pairmode build loop" section and before
  "## Hook architecture" and "## Companion data files".
- In "### Pairmode and companion: separation of concerns", rewrite the first
  sentence per Ensures #4.

Do **not** edit any subsection content under "## Pairmode design" beyond
that one sentence. Do **not** edit "## Effort tracking" or anything below it.

#### Tests

No test file expected for this documentation story.

The reviewer verifies:
1. "## What flex is" opens with a paragraph naming pairmode as the primary
   workflow before describing companion.
2. The `skills/` subtree order is `pairmode/`, `companion/`, `seed/`.
3. A "## Pairmode build loop" section exists between "## Data flow" and
   "## The canonical spec format".
4. "## Pairmode design" appears before "## Hook architecture" and
   "## Companion data files" in document order.
5. All subsection content under "## Pairmode design" (rails/eras, story
   classification, model selection, etc.) is unchanged.
6. "## Effort tracking" and all sections below it are unchanged.
7. Full test suite passes.

`TEST RUN: documentation story — no test file expected`

---

### Story INFRA-109 — Update `CLAUDE.md` project context to reflect pairmode as shipped

**Rail:** INFRA | **story_class:** doc

#### Requires

- `CLAUDE.md` exists at repo root.
- "## Project context" describes flex as giving Claude "persistent memory of
  architectural decisions, specs, and constraints across sessions" — memory-first.
- The same section ends with "This repo is currently building the `pairmode`
  feature — a structured builder/reviewer workflow that any project can adopt.
  See `/docs/phase-prompts.md` for the build plan." — factually incorrect since
  Phase 16; pairmode has been shipped for 24+ subsequent phases.

#### Ensures

1. The "## Project context" section is replaced with:

   ```
   ## Project context

   flex — a Claude Code plugin whose primary feature is **pairmode**: a
   structured builder/reviewer workflow with effort tracking, per-story schema
   gates, context budget checks, and model selection per attempt. The companion
   memory layer (sidebar, `spec.json`, lessons) is the supporting infrastructure
   that pairmode sits on top of.

   Stack: Python 3.11+ / uv / Rich (TUI) / Anthropic SDK.
   Read `/docs/brief.md` then `/docs/architecture.md` before any task. These are
   the source of truth.

   Pairmode is shipped and in continuous use on this repo. Current build activity
   lives in numbered phase files under `/docs/phases/`; see
   `/docs/phases/index.md` for the current phase.
   ```

2. The sentence "This repo is currently building the `pairmode` feature…" and
   the `/docs/phase-prompts.md` reference are removed entirely.

3. "## Session modes", "## Review checklist", "## Review output format",
   "## Story test verification", and "## Loop-breaker mode" are preserved
   byte-identical.

#### Instructions

**`CLAUDE.md`**

Replace the "## Project context" section in full with the text in Ensures #1.
Verify no other section is modified.

#### Tests

No test file expected for this documentation story.

The reviewer verifies:
1. "## Project context" does not contain "currently building the `pairmode`
   feature".
2. "## Project context" does not reference `/docs/phase-prompts.md`.
3. "## Project context" leads with pairmode as the primary feature.
4. "## Session modes" onward is byte-identical to the prior version.
5. Full test suite passes.

`TEST RUN: documentation story — no test file expected`

---

## Notes

- All four stories are `story_class: doc`. No code changes; no new test files.
  The build gate (`uv run pytest tests/pairmode/ -x -q`) must still pass at
  checkpoint.
- No template files (`skills/pairmode/templates/`) are modified in this phase.
  Whether newly-bootstrapped projects should also describe pairmode as primary
  is a separate question for a future phase.
- Stories are independent and may be built in any order.

---

Tag: `cp41-pairmode-as-lead-capability`
