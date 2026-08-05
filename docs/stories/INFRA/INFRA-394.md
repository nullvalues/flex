---
id: INFRA-394
rail: INFRA
title: Scrub real fleet repo names from committed docs via stable Repo-A..Repo-O mapping (CER-172)
status: draft
phase: "125"
story_class: doc
auth_gated: false
schema_introduces: false
touches: []
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

Roughly 150 already-committed files (phase docs, story specs,
`docs/architecture.md`, the CER backlog, etc., across this project's whole
history) mention real sibling-repo names in prose — the same public-repo leak
CER-172 tracks, but in committed docs rather than source code. INFRA-393 gave
this project a local, gitignored real→anonymized-label mapping
(`.pairmode-fleet.local.json`). This story mechanically scrubs every
already-committed doc so each real name is replaced by its stable anonymized
label from that mapping, preserving meaning where a passage compares multiple
distinct repos by name.

## Requires

- INFRA-393 complete and merged: `.pairmode-fleet.local.json` (the local,
  gitignored real→label mapping) and its loader (`_load_local_fleet_map()`)
  exist in the working tree.
- The operator has populated their own `.pairmode-fleet.local.json` locally
  with the real fleet mapping before this story is built — without it there is
  no mapping to apply, and the builder must not re-derive or re-list real
  names from memory or from grepping the docs themselves to invent one.

## Ensures

- A committed script (`skills/pairmode/scripts/scrub_fleet_names.py`) loads
  the real→label mapping from `.pairmode-fleet.local.json` at runtime and
  contains no real repo name as a source-code literal anywhere in the file.
- Running the script in apply mode replaces every occurrence of a real repo
  name in every git-tracked file (via `git ls-files`, not a `docs/`-only glob
  — forbidden proxy: a verify pass that reports clean because it only scanned
  `docs/` while a real name remained in a tracked file elsewhere) with that
  repo's mapped label, consistently within and across files.
- No two distinct real names collapse to the same label, and no single real
  name maps to two different labels — verified by the script itself
  (one-to-one mapping check) before it writes any file.
- Passages that compare multiple distinct repos by name in the same paragraph
  (e.g. `docs/architecture.md`'s design-rationale sections, `phase-47.md`,
  the flagged `RELEASE-*.md` stories) retain distinct, readable anonymized
  labels after substitution — spot-checked manually by the builder against a
  sample of these passages.
- Running the script in verify mode (`--verify`) after the apply pass exits 0
  and reports zero remaining hits for every real name loaded from the local
  config, scanning the full `git ls-files` tree.
- When `.pairmode-fleet.local.json` is absent (e.g. CI, a fresh clone without
  a populated local copy), `--verify` exits 0 with a clear
  "no local fleet config found, skipping verification" message rather than
  failing — mirrors INFRA-393's graceful-degrade contract for a missing local
  config, so this story's own regression check never breaks a consumer who
  has not populated their own mapping.
- `tests/pairmode/test_scrub_fleet_names.py` exists and is green, exercising
  the substitution logic against fixture files using fake placeholder names
  (never real repo names) — including an idempotency case (re-running the
  apply pass on already-anonymized fixture text makes no further changes).
- Neither `skills/pairmode/scripts/scrub_fleet_names.py`,
  `tests/pairmode/test_scrub_fleet_names.py`, nor this story file itself
  contains a real fleet repo name literal — all real-name data is sourced
  from the runtime-loaded local config, never hardcoded.

## Instructions

1. In `skills/pairmode/scripts/scrub_fleet_names.py` (new file), reuse or
   mirror INFRA-393's `_load_local_fleet_map()`-style loader to read
   `.pairmode-fleet.local.json` from the repo root. If the file is absent,
   both the apply and verify code paths must degrade gracefully (apply: no-op
   with a clear message; verify: exit 0 with the skip message from Ensures) —
   never invent, re-list, or hardcode a real name to fall back on.
2. Implement an apply mode that: enumerates tracked files via
   `git ls-files` (repo-wide, not `docs/`-scoped, so a real name in a
   non-`docs/` tracked file is not missed); for each file, for each
   `(label, real_path)` pair in the loaded mapping, derives the real *name*
   to match (the leaf/basename of `real_path`, and any other real-name forms
   already used in prose per the mapping — judgment call on exact match
   patterns belongs to the builder, informed only by the runtime-loaded
   mapping, never by re-deriving names from the docs); performs a literal,
   case-sensitive substring replacement of each real name with its label;
   writes the file back only if changed.
3. Implement a verify mode (`--verify`) that re-scans the same `git ls-files`
   tree for any remaining occurrence of any real name from the loaded mapping
   and exits non-zero (listing file:line) if any are found, or exits 0 (with
   the absent-config skip message when the local config itself is missing).
4. Run the script's apply mode once across the repository as this story's
   actual scrub. Do not hand-edit files one at a time — this is a scripted,
   repo-wide substitution, not a manual per-file pass.
5. After applying, manually spot-check the passages named in Ensures
   (`docs/architecture.md` design-rationale sections, `phase-47.md`, the
   flagged `RELEASE-*.md` stories) to confirm multi-repo comparisons still
   read coherently with distinct labels, not a collapsed generic term.
6. Run the script's verify mode and confirm a clean (zero-hit) result before
   considering the story done.
7. Add `tests/pairmode/test_scrub_fleet_names.py` covering the substitution
   and idempotency logic against fixture files that use fake placeholder
   names (e.g. `"repo-a": "/tmp/example-repo-a"`-style fixtures) written
   directly in the test — never real names.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_scrub_fleet_names.py -q
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/scrub_fleet_names.py --verify
```
Acceptance: the pytest suite is green; the verify command exits 0 and reports
zero remaining real-name hits (or the clean skip message when no local config
is present).

## Out of scope

- Re-deriving or re-verifying INFRA-393's local-config shape or loader —
  assumed correct and already covered by that story's own tests.
- Anonymizing untracked files (scratch notes, ephemeral local files) — this
  story only scrubs git-tracked, already-committed content.
- Renaming real directories on disk under `/mnt/work/` — this story edits
  only the text content of committed docs/source, never filesystem layout
  outside the repo.
