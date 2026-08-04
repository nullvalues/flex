---
id: INFRA-381
rail: INFRA
title: Add drift/staleness tracking for bootstrap-seeded cold-start triad docs (CER-121)
status: complete
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/audit.py
touches:
  - tests/pairmode/test_audit.py
  - docs/cer/backlog.md
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-121 (HIGH): `docs/architecture.md` (item #2 of the mandatory cold-start triad) and
`docs/checkpoints.md` are bootstrap-seeded, deny-listed from writes, and tracked by nothing — no
body compare, no staleness check, no drift report — with observed downstream spread of 99-1568
lines across projects. INFRA-311 only landed the `bootstrap.SCAFFOLD_FILES ⊆ audit-tracked` parity
test; the actual body-tracking mechanism for these two seeded-doc families is this row's scope.
Gate: the next canon change to a seeded-doc template (`architecture.md`/`checkpoints.md` families)
or the first post-0.3.1 fleet sync campaign, whichever comes first — both conditions have now
arrived given Phase 119's own scope. Files: `docs/architecture.md`, `docs/checkpoints.md`, and the
tracking mechanism itself (likely `skills/pairmode/scripts/audit.py`, which already carries the
analogous staleness-check pattern for `docs/ideology.md`/`docs/reconstruction.md`). From the
2026-07-29 cold-eyes review (F3).

Picked up now as part of era 004's Phase 119 goal of draining the CER backlog to zero unresolved
operational findings.

## Requires

- `skills/pairmode/scripts/audit.py` exists and already contains the
  `_check_ideology_staleness` / `_check_reconstruction_staleness` pattern, the
  `_split_sections` / `_is_stale_placeholder` helpers, and `_load_overrides`.
- `skills/pairmode/templates/docs/architecture.md.j2` and
  `skills/pairmode/templates/docs/checkpoints.md.j2` exist (the seeding source of truth).
- INFRA-372 (CER-132) is not being built concurrently in the same working tree — both stories
  land in `audit.py`. Build serially (either order); this story never edits INFRA-372's regions
  (see `## Out of scope`).

## Ensures

1. `audit.py` declares a new module-level list of seeded cold-start docs that receive drift
   tracking, containing exactly `("docs/architecture.md", "docs/architecture.md.j2")` and
   `("docs/checkpoints.md", "docs/checkpoints.md.j2")`, and a new checker function that takes a
   project dir plus one such pair and returns one of: `None` (file missing), `"STALE"`,
   `"DRIFTED"`, or `"OK"`.
2. The checker performs an actual body compare: it renders/reads the template's top-level
   section headings via the existing `_read_template_sections` path and compares that heading
   set against the project file's headings via `_read_project_sections`. `"DRIFTED"` is returned
   when at least one template heading is absent from the project file.
   *Forbidden proxy:* returning `"OK"` on the basis of file existence, mtime, or list membership
   alone, with no heading comparison performed — a check that never reads either body is the
   exact "tracked by nothing" condition CER-121 reports.
3. `"STALE"` is returned when the file exists but every section body is placeholder-only,
   determined by the existing `_is_stale_placeholder` helper (not a new placeholder predicate).
4. Extra sections present in the project file but absent from the template are never reported
   for these two files — divergence in the customized direction is expected (observed 99-1568
   line spread) and must not produce findings.
5. `audit_project` runs the checker for each tracked pair and appends a finding for the
   `None`/`"STALE"`/`"DRIFTED"` outcomes only; each finding names the file path and states which
   template heading(s) are missing (for `"DRIFTED"`). `format_audit_output` renders these
   findings in human-readable form rather than dropping them.
6. A `"DRIFTED"` finding for a given `(file, section)` is suppressed when that pair is present in
   the set returned by the existing `_load_overrides(project_dir)` — read only; the function
   itself is unchanged.
7. `PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/audit.py --project-dir .`
   (or the equivalent existing entry point) exits without traceback on this repo.
8. `tests/pairmode/test_audit.py` gains tests covering, at minimum: the missing-file case, the
   `"STALE"` case, the `"DRIFTED"` case (template heading absent from project file), the `"OK"`
   case, the extra-section-is-not-a-finding case (Ensures 4), and the override-suppression case
   (Ensures 6).
9. Full `tests/pairmode/` suite green.

## Instructions

1. Mirror the existing `_check_ideology_staleness` / `_check_reconstruction_staleness` shape —
   a module-level constant, a private `_check_*` function returning a small string status, and a
   dedicated block in `audit_project` that converts the status into a finding. Do not reroute
   these two docs through `SCAFFOLD_FILES`: full section-level body comparison on a 1500-line
   customized `architecture.md` would emit noise proportional to legitimate customization, which
   is why they were excluded in the first place. Heading-set comparison is the deliberate bounded
   cut for this story.
2. Reuse `_read_template_sections`, `_read_project_sections`, `_split_sections`, and
   `_is_stale_placeholder` as-is. Adjustment note (Step 4a, "rationale-bearing decisions over bare
   rules"): the finding text must say *which* template heading is missing, not just "drifted" —
   a bare status gives the downstream operator no way to act.
3. Wire the override read at the finding site in `audit_project`, not inside `_load_overrides`.
4. Keep the diff out of `CANONICAL_FILES`, `SCAFFOLD_FILES`, and the body of `_load_overrides`
   so INFRA-372 (CER-132) can land in the same module without conflict.
5. Mark CER-121 RESOLVED in `docs/cer/backlog.md`, citing this story.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_audit.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: both green; the new `test_audit.py` cases named in Ensures 8 all present and passing.

## Out of scope

- Extending drift tracking to any seeded doc beyond `docs/architecture.md` and
  `docs/checkpoints.md` (e.g. `docs/phase-prompts.md`, `docs/phases/*`) — this is the first
  bounded cut; a general "every seeded doc is tracked" parity test is deliberately deferred.
- Any change to `CANONICAL_FILES`, `SCAFFOLD_FILES`, or `_load_overrides` — INFRA-372's surface.
- Auto-repair or sync of drifted docs (`sync.py` writing missing sections into a project's
  `architecture.md`). This story reports drift only.
- Line-level or paragraph-level body diffing of these two files.
- Editing `docs/architecture.md` or `docs/checkpoints.md` themselves. They are the *subjects*
  of the new check, not write targets, and are deliberately absent from `touches:` — the
  spec-preflight `scope:` finding on `docs/checkpoints.md` is intentional for this reason.
