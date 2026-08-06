---
era: "005"
phase_class: production
---

# project — Phase 124: Scaffold EXEMPLAR-000.md for downstream projects (CER-171)

← [Phase 123: Fix audit.py override-key normalisation mismatch (CER-170)](phase-123.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Add docs/exemplars/EXEMPLAR-000.md to bootstrap.py's SCAFFOLD_FILES and sync.py/audit.py's canonical-file handling so every flex-bootstrapped project (not just flex itself) gets the frozen spec-writer format exemplar scaffolded and audited, closing the silent-degrade gap the spec-writer procedure currently hits on any downstream project.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-392 | Scaffold EXEMPLAR-000.md into downstream projects via bootstrap/sync/audit (CER-171) | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-124 Cold-eyes checklist

- [x] written-never-read — does anything this phase persists have no reader? No. `docs/exemplars/EXEMPLAR-000.md` is scaffolded by `bootstrap.py`'s `EXEMPLAR_FILES`, read by the spec-writer procedure, and compared by both `audit.py`'s `CANONICAL_FILES` and `sync.py`'s backfill path — all three paths verified reachable end-to-end by the checkpoint's security-auditor.
- [x] required-never-written — does any read path depend on a value no writer produces? No new required-read path was introduced; the spec-writer's pre-existing graceful fallback (built-in section-list) still covers the case where the file is absent for any reason.
- [x] duplicate state — is any fact now stored twice with independent writers? Yes, but reconciled: the canonical content lives at both `docs/exemplars/EXEMPLAR-000.md` and `skills/pairmode/templates/docs/exemplars/EXEMPLAR-000.md.j2`, kept in sync by `test_exemplar_file_content_matches_source` (fails CI on drift) rather than a single writer — a deliberate, test-enforced duplication, same pattern as every other `CANONICAL_FILES` template pair.
- [x] half-implementation — is any branch unreachable, or any producer without its consumer? One real gap found and filed (CER-186, Do Later): the file's YAML frontmatter falls under `_split_sections`' skipped separator key, so both `audit.py` and `sync.py` are structurally blind to frontmatter drift (proven empirically — an `id:` edit produced zero audit findings and survived a sync run). The file-absent case CER-171 set out to fix is closed; the file-present-and-frontmatter-drifted case is a known, tracked residual, not a silent one.

Filled at Phase 124 checkpoint per the security-auditor's first-pass report (PASS, zero CRITICAL/HIGH; CER-186/CER-187 filed to Do Later for the two non-blocking findings above and the `--force-agents` docs staleness).
