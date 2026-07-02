---
era: "003"
phase_class: production
---

# project — Phase HARNESS008-main: Housekeeper consolidation

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->

## Goal

Fold scattered index-integrity logic into the resolver's read-model as a first-class graph-invariant
checker: a pure-read `index_integrity.py` module exposed via an additive `flex_build.py check-index`
CLI. Detects the four classes of drift found in practice: (1) status drift — a built story still
marked `planned`; (2) cross-link consistency — missing phase files, mismatched era tables, broken
story `phase` frontmatter; (3) orphan story files not referenced in any phase doc; (4) deferred
stories without a `## Deferred stories` section in their phase doc. Also fixes CER-056 by
implementing the deferred-as-inactive rule once in `index_integrity.py` and sharing it with
`infer_position` (the resolver previously treated `deferred`/`backlog` phases as active).
Forcing function: the status-drift + stale-era-table mess found during the Era 002 close-out.
Advisory CLI only — no hard checkpoint gating. Agreements input:
`docs/agreements/HARNESS008-main.md` (all 5 DPs AGREED).

## Stories

| ID | Title | Status |
|----|-------|--------|
| RESOLVER-010 | `check-index` graph-invariant checker (`index_integrity.py` + CLI) | complete |
| RESOLVER-011 | Resolver read-model integration + housekeeper isolation suite | complete |

## Schema delivery

| Object | Management surface | Exception |
|---|---|---|
| _(none)_ | — | HARNESS008 introduces no new persistent schema objects. |

---

### CP-HARNESS008-main Cold-eyes checklist

— developer fills in after phase completion —
