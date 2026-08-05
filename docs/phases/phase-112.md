---
era: "003"
phase_class: production
---

# project — Phase 112: Campaign unblockers: worker result-grammar reconciliation, CER-guard placeholder fix, snapshot write targeting

← [Phase 111: Plugin packaging repair: local marketplace source and skill-name de-namespacing](phase-111.md)

**Parent phase:** Phase 106 (fleet migration campaign, re-blocked after
RELEASE-065 on evidence: E6b FAIL). RELEASE-066..070 resume after cp-112.

## Findings dossier (RELEASE-065 evidence, 2026-07-28; all verified live)

**Defect 1 — E6b grammar skew (INFRA-293).** Repo-C's proving cycle
(PAIRMODE-002) left effort.db rows 33/34 permanently pending: `tokens_total`
and `model` parse from the spawn transcripts, but `outcome` is None because
the workers returned the 0.2-era plain-text grammar (`BUILD-RESULT: DONE`,
`REVIEW-RESULT: PASS`) instead of the WORKER-004 JSON grammar
`subagent_transcript.parse_worker_outcome` reads (it recognises only the JSON
block; verdicts PASS/FAIL/ALIGNED per RECOGNISED_REVIEW_VERDICTS, ~line 308).
The sweep's CER-091 defect-2 branch then correctly refuses to commit a partial
row. Root cause: `pairmode_sync.py sync-agents` merges frontmatter and appends
new template sections but preserves stale 0.2-era body content — Repo-C's
`.claude/agents/builder.md:106` carries the literal `BUILD-RESULT: DONE`
example alongside the newly merged JSON-schema reference, and workers followed
the old example. Canary playbook note 4's agent-cleanup WARN ("content differs
from known 0.2.x template … manual porting required") has flagged this on all
three migrations and was twice adjudicated noise (reclassified in RELEASE-065
E12 note 4). Every 0.2-era fleet project (Repo-D, Repo-F, Repo-K,
base56, Repo-G at minimum) will reproduce this. Fix direction (both ends, like
phase 110's CER-104 treatment): (a) parser tolerance — `parse_worker_outcome`
additionally accepts a legacy plain-text verdict line, mapping recognised
verdicts and handling `DONE` explicitly (map or reject-with-reason, decide in
spec; note Repo-C's PAIRMODE-002 rows should become reconcilable after the fix
— an acceptance test candidate); (b) sync-side — the agent-file sync replaces
the return-format section of stale bodies (or the to-030 agent-cleanup step
ports it), so consumer workers stop emitting the legacy grammar in the first
place.

**Defect 2 — CER-guard placeholder false positive (INFRA-294).** Repo-C's first
0.3.0 checkpoint was blocked by `next_action._check_cer_do_now` reading the
scaffolded CER-backlog placeholder row `| — | *(none)* | — | — |` as an
unresolved Do Now item; the Repo-C operator deleted the row by hand (Repo-C
commit f234915, filed there as CER-C004). Every repo whose CER backlog was
scaffolded with the placeholder hits this on its first checkpoint. Fix in
`next_action.py`'s `_check_cer_do_now` (and check the backlog template under
`skills/pairmode/templates/` for the placeholder shape it emits); a regression
test with the scaffolded placeholder row belongs alongside.

**Defect 3 — snapshot writes into the scripts checkout (INFRA-295).** Repo-C's
native session ran `fleet_discovery.py` (channel scripts) without
`--no-snapshot`; the `--snapshot` default (`docs/fleet-snapshot.md`, resolved
relative to the flex checkout the script derives, see `fleet_discovery.py`)
wrote into `/mnt/work/flex-harness` — a migration-story E11 violation caught
and reverted in RELEASE-065. The scripts checkout is a read-only release
channel; the default should target the invoking project (or require an
explicit path / refuse to write into the scripts checkout). Decide the exact
rule in spec; keep `--no-snapshot` and explicit `--snapshot PATH` behaviour.

## Cold-eyes corrections (fable review, pre-spec — fold into specs)

1. **Pending-row shape (INFRA-293 acceptance):** Repo-C rows 33/34 are
   fully-NULL-except-`model` (`model` was set at insert; tokens are parseable
   at sweep time but the refuse-partial branch at `subagent_transcript.py:1711`
   skips the whole row). Do not spec an acceptance test asserting
   "tokens present, outcome NULL".
2. **Grammar asymmetry:** the 0.2-era builder has NO plain-text FAIL form —
   failure was prose (`BUILDER STUCK — …`), so legacy tolerance can only yield
   DONE for builders; reviewer legacy grammar is `REVIEW-RESULT: PASS|FAIL`.
   Also: JSON-path BUILD outcomes are accepted unvalidated
   (`subagent_transcript.py:339`) while REVIEW verdicts are enum-checked —
   decide whether plain-text BUILD verdicts get validated. `worker_result.py:50`
   BUILD enum is `{PASS, FAIL}` (no DONE).
3. **Sync-side fix needs a legacy-heading removal/aliasing mechanic
   (INFRA-293, HIGH):** the stale grammar lives under the legacy heading
   `## Final output to orchestrator`; `_merge_body_sections`
   (`pairmode_sync.py:321`) appends only missing concept keys and can never
   replace a heading the current template no longer uses — and the stale block
   sits EARLIER in the file than the appended `## return`, which is why workers
   follow it. Without removal/aliasing the sync half is unreachable. Also pick
   ONE owner (sync-agents vs to-030 agent-cleanup), not both — duplicate-writer
   risk.
4. **Fleet re-sweep is time-bounded and now owned by INFRA-293:**
   `RECONCILE_MAX_AGE_DAYS = 14` (`subagent_transcript.py:156`) — the fix must
   reach `/mnt/work/flex-harness` and a sweep must run in Repo-C before
   2026-08-11 or rows 33/34 leave the sweep window permanently. INFRA-293's
   Ensures must include: after channel release, the explicit sweep CLI run in
   Repo-C reconciles rows 33/34 (they are otherwise reconcilable today —
   predicate and target-allowlist verified).
5. **Placeholder skip-rule already exists (INFRA-294, avoid duplicate state):**
   `cer.py:119-120` (`cer_id == "—" or finding == "*(none)*"`) is the canonical
   rule — share or mirror it in `next_action.py:383-416`, don't write a third
   independent variant. Guard tolerance is the load-bearing half; a
   template-only fix would strand already-scaffolded repos. Template emits 5
   cols in Do Now (`templates/docs/cer/backlog.md.j2:23`), 6 in one section.
6. **INFRA-295 inverts a test-encoded design guarantee (HIGH):**
   `test_fleet_discovery.py:252,277` explicitly encode "snapshot goes to flex
   repo, NOT to any scanned project". The spec must resolve the collision
   deliberately (e.g. refuse-by-default when the scripts checkout is not the
   invoking repo — a "this is the read-only channel" predicate must be defined)
   and REWRITE those two tests, not extend them. Doc surface: module docstring
   "READ-ONLY" (`fleet_discovery.py:1`), `--snapshot` help (:473),
   `_write_snapshot` docstring (:384), `docs/architecture.md:3291,:3322`, and
   the runbook's Signal-1 verification command (~:409) which omits
   `--no-snapshot` and would default-write.
7. **Parser callers:** all four `parse_worker_outcome` call sites are internal
   to `subagent_transcript.py` (:1289, :1357, :1802, :1981) — single-file
   parser fix correctly scoped.

Test surface per story (builder must extend; from the review):
INFRA-293 — `test_subagent_transcript.py` (TestParseWorkerOutcome :100, sweep
classes), `test_effort_db.py`, `test_worker_result.py`, `test_sync_agents.py`,
`test_pairmode_sync.py`, `test_session_start_hook.py`.
INFRA-294 — `test_checkpoint_routing.py` (:254, :276),
`test_harness004_isolation.py` (:270), `test_cer.py`, `test_templates.py` /
`test_bootstrap.py`. (`test_next_action.py` has NO _check_cer_do_now coverage.)
INFRA-295 — `test_fleet_discovery.py` TestSnapshot :252-292 (rewrite).

## Backlog pulls (operator-approved at scaffold review, 2026-07-28)

Spec-writers must drain these into their stories (spec-time backlog pull):
- **CER-033 → INFRA-293**: legacy verbose `BUILT:`/`REVIEW PASS` template
  blocks — close or absorb inside the consumer agent-body porting work (flex's
  own templates verified clean already).
- **CER-099 → INFRA-293**: containment-guard parity gap in
  `classify_pending_reason` / `include_quiescent` raw `output_file` streaming —
  same function the story edits.
- **CER-059(a) → INFRA-295**: fleet_discovery Signal-2-only binding follow-ups
  — same file; spec the minimal slice that fits, defer the rest with a note.
- CER-111: NOT pulled unless the spec-writer routes the sync-side fix through
  to-030 agent-cleanup and it becomes cheap (operator declined the
  unconditional pull).

Related CERs already filed: CER-110 (plugin-sourced duplicate-hook signal,
fleet-wide — NOT in this phase's scope), CER-111 (to-030 expected_step_tokens
rewrite — three-way data now recorded in RELEASE-065; not in scope unless the
spec-writer finds it cheap), CER-C001..C004 live in Repo-C's backlog (C004 is
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
| INFRA-293 | Worker result-grammar reconciliation: parser tolerance for legacy plain-text verdicts + sync-agents replaces stale return-format sections (E6b, CER-101 downstream) | complete |
| INFRA-294 | _check_cer_do_now: stop reading the scaffolded (none) placeholder row as an unresolved Do Now item | complete |
| INFRA-295 | fleet_discovery snapshot targeting: default snapshot must not write into the scripts checkout | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-112 Cold-eyes checklist

- [x] written-never-read — no new persistent state introduced this phase (all three stories `schema_introduces: false`); the CER-099 fix closes an existing *read*-path containment gap rather than adding a writer.
- [x] required-never-written — the legacy plain-text verdict grammar is a read-side fallback only; no read path was added that depends on a value nothing produces. The pre-existing JSON-path outcome-validation asymmetry is filed as CER-113, not left implicit.
- [x] duplicate state — reduced, not added: the placeholder rule now has exactly one owner (`cer.is_placeholder_row`, consumed by both `_parse_entries_from_backlog` and `_check_cer_do_now`); the vestigial `cer.py` regex-guard dead code is recorded in INFRA-294's spec recon.
- [x] half-implementation — every new producer has its consumer (legacy grammar parser ← reconcile sweep; alias replacement ← sync-agents; refusal guard ← CLI default path, with `--snapshot`/`--no-snapshot` escape hatches tested). One deliberate outstanding item: INFRA-293 § Ensures F3 field acceptance, tracked below.

**F3/F4 record (INFRA-293 § Ensures, orchestrator-filled):** F3 **PASS**, run
2026-07-28 (operator-approved, well inside the 2026-08-11 deadline). The fix
was promoted to `/mnt/work/flex-harness` via ff-only merge to `df54fa06`, then
the explicit sweep `subagent_transcript.py reconcile --project-dir
/mnt/work/Repo-C --limit 200 --json` returned `{"reconciled": 3}`. Row check
before: rows 33/34 both `tokens_total=NULL, outcome=NULL`; after: row 33 =
`(sonnet, 7457, PASS)`, row 34 = `(sonnet, 9145, PASS)` — both non-NULL, the
E6b legacy plain-text verdict grammar reconciles in the field. F4 satisfied by
this record.
