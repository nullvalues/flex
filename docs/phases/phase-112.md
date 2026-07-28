---
era: "003"
phase_class: production
---

# project — Phase 112: Campaign unblockers: worker result-grammar reconciliation, CER-guard placeholder fix, snapshot write targeting

← [Phase 111: Plugin packaging repair: local marketplace source and skill-name de-namespacing](phase-111.md)

**Parent phase:** Phase 106 (fleet migration campaign, re-blocked after
RELEASE-065 on evidence: E6b FAIL). RELEASE-066..070 resume after cp-112.

## Findings dossier (RELEASE-065 evidence, 2026-07-28; all verified live)

**Defect 1 — E6b grammar skew (INFRA-293).** Caddy's proving cycle
(PAIRMODE-002) left effort.db rows 33/34 permanently pending: `tokens_total`
and `model` parse from the spawn transcripts, but `outcome` is None because
the workers returned the 0.2-era plain-text grammar (`BUILD-RESULT: DONE`,
`REVIEW-RESULT: PASS`) instead of the WORKER-004 JSON grammar
`subagent_transcript.parse_worker_outcome` reads (it recognises only the JSON
block; verdicts PASS/FAIL/ALIGNED per RECOGNISED_REVIEW_VERDICTS, ~line 308).
The sweep's CER-091 defect-2 branch then correctly refuses to commit a partial
row. Root cause: `pairmode_sync.py sync-agents` merges frontmatter and appends
new template sections but preserves stale 0.2-era body content — caddy's
`.claude/agents/builder.md:106` carries the literal `BUILD-RESULT: DONE`
example alongside the newly merged JSON-schema reference, and workers followed
the old example. Canary playbook note 4's agent-cleanup WARN ("content differs
from known 0.2.x template … manual porting required") has flagged this on all
three migrations and was twice adjudicated noise (reclassified in RELEASE-065
E12 note 4). Every 0.2-era fleet project (forqsite.help, halfhorse, pokus,
base56, cora at minimum) will reproduce this. Fix direction (both ends, like
phase 110's CER-104 treatment): (a) parser tolerance — `parse_worker_outcome`
additionally accepts a legacy plain-text verdict line, mapping recognised
verdicts and handling `DONE` explicitly (map or reject-with-reason, decide in
spec; note caddy's PAIRMODE-002 rows should become reconcilable after the fix
— an acceptance test candidate); (b) sync-side — the agent-file sync replaces
the return-format section of stale bodies (or the to-030 agent-cleanup step
ports it), so consumer workers stop emitting the legacy grammar in the first
place.

**Defect 2 — CER-guard placeholder false positive (INFRA-294).** Caddy's first
0.3.0 checkpoint was blocked by `next_action._check_cer_do_now` reading the
scaffolded CER-backlog placeholder row `| — | *(none)* | — | — |` as an
unresolved Do Now item; the caddy operator deleted the row by hand (caddy
commit f234915, filed there as CER-C004). Every repo whose CER backlog was
scaffolded with the placeholder hits this on its first checkpoint. Fix in
`next_action.py`'s `_check_cer_do_now` (and check the backlog template under
`skills/pairmode/templates/` for the placeholder shape it emits); a regression
test with the scaffolded placeholder row belongs alongside.

**Defect 3 — snapshot writes into the scripts checkout (INFRA-295).** Caddy's
native session ran `fleet_discovery.py` (channel scripts) without
`--no-snapshot`; the `--snapshot` default (`docs/fleet-snapshot.md`, resolved
relative to the flex checkout the script derives, see `fleet_discovery.py`)
wrote into `/mnt/work/flex-harness` — a migration-story E11 violation caught
and reverted in RELEASE-065. The scripts checkout is a read-only release
channel; the default should target the invoking project (or require an
explicit path / refuse to write into the scripts checkout). Decide the exact
rule in spec; keep `--no-snapshot` and explicit `--snapshot PATH` behaviour.

Related CERs already filed: CER-110 (plugin-sourced duplicate-hook signal,
fleet-wide — NOT in this phase's scope), CER-111 (to-030 expected_step_tokens
rewrite — three-way data now recorded in RELEASE-065; not in scope unless the
spec-writer finds it cheap), CER-C001..C004 live in caddy's backlog (C004 is
defect 2 upstream).

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Fix the three defects RELEASE-065 surfaced that block RELEASE-066..070: consumer workers returning the 0.2-era plain-text result grammar that parse_worker_outcome cannot read (E6b), the _check_cer_do_now placeholder-row false positive that blocks every migrated repo's first checkpoint, and fleet_discovery's default snapshot path writing into the channel checkout.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-293 | Worker result-grammar reconciliation: parser tolerance for legacy plain-text verdicts + sync-agents replaces stale return-format sections (E6b, CER-101 downstream) | draft |
| INFRA-294 | _check_cer_do_now: stop reading the scaffolded (none) placeholder row as an unresolved Do Now item | draft |
| INFRA-295 | fleet_discovery snapshot targeting: default snapshot must not write into the scripts checkout | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-112 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
