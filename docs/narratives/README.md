# Narrative of Record — flex

A living documentation layer alongside `docs/architecture.md` (the how) and the
phase docs (the what): narratives describe **what a role in this build loop must
be able to do and expect, and why** — grounded in `docs/ideology.md` and
`docs/brief.md` — not implementation, not a technical spec. Their purpose is to
surface whole-loop gaps *before* they compound, the same way Repo-A/Repo-N's
narratives surface UX gaps before UAT.

flex's narrative roles are not end users of a product UI — they're the roles
inside the build loop itself (builder, reviewer, loop-breaker, the four
checkpoint-adjacent workers, spec-writer), plus the orchestrator that dispatches
them and the operator who depends on the whole thing. Precedent for a
non-human/system-role narrative already exists in the fleet (Repo-A's
PLATFORM-OPERATOR, Repo-N's ARTHUR); this project is the first to write
narratives for the harness's own internal roles, and the first anywhere in the
fleet to actually wire narrative-checking into a live spec-writer/reviewer
procedure rather than stating it as intent.

This README is orientation only — the narrative files are the authority.

## Structure

```
docs/narratives/<ROLE>/<ROLE>-NNN-<kebab-slug>.md
```

- One directory per role, uppercase.
- `<ROLE>-000-ideology.md` is always the role-level creed.
- Descendants are numbered in **steps of 10** so gaps discovered at cold-eyes
  review insert between neighbors without renumbering. Disk sort is the reading
  order; no index is required.
- Body sections: **Narrative** (the role's experience end-to-end) · **Always
  true** (invariants traced to ideology/architecture/the loop's own contract) ·
  **Never** (explicit anti-behaviors) · **Open gaps** (running list, the
  comparison against the actual harness that motivated this exercise).

### OPERATOR's seed-then-extend path (INFRA-353)

The other nine roles are plain template-and-sync: `OPERATOR-000` is instead a
**templated seed, not a finished narrative** — bootstrap scaffolds a generic
"typical operator" `OPERATOR-000-ideology.md` from
`skills/pairmode/templates/narratives/OPERATOR/OPERATOR-000-ideology.md.j2`
(project-agnostic, no reference to any one project's own findings), and
bootstrap's interactive flow asks one more free-text, blank-to-skip question
alongside "What does this project produce?"/"Why does this project exist?":
how this project's operator actually wants to work with the loop. A non-blank
answer becomes `OPERATOR-010-project.md` — a separate numbered extension file,
never a rewrite of the seed. A blank answer writes nothing; the seed alone is
still a complete, generic narrative. Further extension beyond bootstrap time
(`OPERATOR-020-*.md` and onward) is always available by hand-authoring a file
in the same directory — no tooling is required for that.

## Roles

| Role | Era | One line |
|------|-----|----------|
| BUILDER | 004 | Disposable and cold — implements exactly one story, completely, then stops |
| REVIEWER | 004 | The adversary the builder never argues with — verifies independently, PASS or FAIL, no middle path |
| LOOP-BREAKER | 004 | Cold-eyes on double failure — one alternative from first principles, never a retry |
| SECURITY-AUDITOR | 004 | Checkpoint-time judge of schema/auth/layer integrity, fixed checklist |
| INTENT-REVIEWER | 004 | The wide-angle lens — phase-level alignment, pre-build or post-build, never mid-story |
| DOCS-REVIEWER | 004 | Checkpoint-time judge of documentation currency |
| GATE-WORKER | 004 | A single per-story schema/auth verdict — currently a livelock with no consumer (Phase 117) |
| SPEC-WRITER | 004 | Elaborates a stub from five bounded inputs — the crux of this era's over-specification finding |
| ORCHESTRATOR | 004 | Stateless dispatcher, reconstructable from `next-action` alone — the operator's proxy inside the loop |
| OPERATOR | 004 | The person with a body and a calendar — final authority, and the role with the least standing visibility into loop health |

## Cross-cutting commitments

- **A spec that grows past what a story needs is a defect, not diligence.**
  Measured directly against this project's own history: early story specs
  averaged 14–36 lines; recent ones averaged 400–550+, peaking at 1317, with
  builder attempt counts rising roughly 50% in step. An external review
  (Devin/Windsurf) independently reached the same conclusion. The spec-writer's
  own procedure asks only for precision, never for proportion — this is the
  standing defect this era's remediation targets.
- **The loop's own health needs a signal the operator doesn't have to go
  looking for.** Every serious gap this era's cold-eyes review found (an
  escalation ladder failing ~50% of the time, two dead-on-arrival features, a
  data-corrupting bug) was invisible to the operator until a deliberate,
  expensive review was commissioned. A narrative can name this gap; closing it
  is a harness question, not a narrative-writing one.
- **A role's narrative and its actual wiring can diverge silently**, the same
  way code can drift from a technical spec — GATE-WORKER's verdict having zero
  consumers, or two Phase-116 features being reviewer-PASSed while
  structurally unreachable, are exactly this failure mode. Where a narrative's
  `Open gaps` names a divergence like this, treat it with the same weight
  `docs/build-loop-cold-eyes-review-20260801.md` gives a CRITICAL/HIGH finding
  — not a stylistic nit.

## Narrative-of-record wiring in spec-writer and intent-reviewer

The spec-writer draws on these narratives as its sixth bounded input (INFRA-355): when a
story's frontmatter lists `narrative_roles: [...]`, the spec-writer reads exactly those cited
`<ROLE>-000-ideology.md` files to ensure the drafted spec honors what each role needs to be
able to do. The intent-reviewer checks alignment against narratives post-build and pre-build
(INFRA-356): cited narrative `Always true`/`Never` sections are verified against the diff,
treating narrative violations with the same weight as ideology drift (CRITICAL/HIGH findings).

See `docs/architecture.md` § Narrative of Record and the cold-start quad for the complete
propagation mechanism (how narratives are synced, the OPERATOR seed-then-extend exception,
the input contract changes, and the phase-level relationship to the cold-start triad). The
procedure implementations are in `skills/pairmode/skills/spec-writer/procedure.md` (Step 2
bounded inputs + post-draft backfill) and `skills/pairmode/skills/intent-reviewer/procedure.md`
(post-build and pre-build narrative-alignment checks).
