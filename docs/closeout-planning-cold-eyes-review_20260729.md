# Cold-Eyes Review — Era 004 Closeout Planning (phases 113/114/115 → 0.3.1)

**Date:** 2026-07-29
**Reviewed at:** `main` @ `3b84947d`
**Reviewer:** external cold-eyes pass (Cascade), pre-build, against the working tree and the live fleet
**Subject:** era 004 (`docs/eras/004-flex-operational-closeout-and-0-3-1.md`), phases 113/114/115, stories `INFRA-296`..`INFRA-310`
**Stated goal under review:** tooling production-ready, observability UI good enough to dogfood, tagged `0.3.1` as a beta for the Claude Code plugin marketplace

---

## 1. Scope and method

Four axes were requested and all four were run:

1. 1:1 CER coverage audit — every undispositioned backlog row mapped against the 15 era-004 stories
2. Story-spec quality pass — `INFRA-296`..`INFRA-310` against buildability by a thin builder
3. Code-truth review against the three README intentions
4. Release-mechanics review of the `0.3.1` bump and marketplace cache invalidation

Sequencing of phases 106/107/108 and the deferred fold (97 / `HARNESS016-main`) was treated
as an open question to be derived from the artifacts, per operator instruction, with two
operator-supplied constraints: **106 is to be considered effectively closed** (outlier projects
hand-migrated, unverifiable from this repo), and **108 should be folded into this era** in effect
or literally if not already complete.

Evidence is first-hand: predicates run against `docs/cer/backlog.md`, the full test suite,
`check-index`, and six live fleet projects under `/mnt/work/`. Every claim below carries a
reproduction command in § 9.

**Method correction, recorded for honesty.** An initial glob (`INFRA-3*`) led this review to
conclude that `INFRA-296`..`299` had no specs. That was wrong — they are committed in `7f696c71`
and were simply outside the glob. All coverage findings below reflect the corrected 15-story set.
A second correction, on the definition of "system of record," is recorded in § 4.

---

## 2. Verdict

**The specs are strong. The plan is not sufficient to reach a clean `0.3.1`, and would ship a
fleet that does not receive `0.3.1`'s behaviour.**

Backlog coverage is genuinely complete and the spec quality is high — higher than typical for
this kind of closeout. The problems are not in the story bodies; they are in what the era does
not contain:

- one **CRITICAL** downstream-propagation defect that no story addresses and that no `sync` run can fix
- three **HIGH** release-gating gaps (a failing index check the closing story requires to pass, an era that never closes, and a UI that is never functionally validated)
- a **MEDIUM** public-doc defect in the most-read artifact of a beta release

None require a new phase. They require roughly two added stories and a widened `INFRA-310`.

### Findings summary

| ID | Severity | Finding |
|---|---|---|
| F1 | **CRITICAL** | Thin-agent canon reduction never propagated downstream; `sync` structurally cannot shrink canon |
| F2 | **HIGH** | `audit` reports the stale downstream contract as healthy (`✓ project-specific`) |
| F3 | **HIGH** | `docs/architecture.md` has no currency mechanism in any consuming repo |
| F4 | **HIGH** | `check-index` fails with 48 violations; `INFRA-310` Ensures 14 requires exit 0 |
| F5 | **HIGH** | Era 003 never closes; phases 106 and 108 left undispositioned; two eras simultaneously active |
| F6 | **HIGH** | The observability UI is never functionally validated before the tag |
| F7 | **MEDIUM** | Agent templates emit a procedure path that does not resolve in any consuming repo |
| F8 | **MEDIUM** | `README.md` misdescribes the build loop it ships |
| F9 | LOW | `INFRA-310` Requires 2's undispositioned count is already stale (50 vs 52) |
| F10 | LOW | `INFRA-310` Requires 3's duplicate-ID map is imprecise in two ways |
| F11 | LOW | After the bump, flex's own `state.json` reports "behind canon" |
| F12 | LOW | `phase-64.md`'s Stories table contradicts its own story files |

---

## 3. What is verified sound

Stated plainly, because it is the larger part of the picture and it is load-bearing for the
recommendations.

**Backlog coverage is complete — zero orphans.** Running `INFRA-310`'s own Ensures-6 predicate
returns **52 undispositioned rows**. Every one has an owner:

- 33 rows referenced by name in one or more of the 15 story specs
- 19 rows in `INFRA-310`'s `OBSOLETE` annotation set (`CER-001`..`012`, `014`, `017`, `018`, `019`, `035`, `044`, `063`)
- `CER-031` and `CER-118` given explicit `BACKLOG-RETAIN` dispositions

The set difference is empty. The five rows that looked orphaned before the method correction
(`CER-105`, `106`, `113`, `114`, `116`) are owned by `INFRA-297`/`298`/`299`.

**Test baseline is exactly as claimed.** `4116 passed, 211 skipped` — matches `INFRA-310`
Requires 16 precisely. No drift between the spec's stated baseline and reality.

**Version plumbing is correct and the marketplace-cache requirement is satisfied.** All four
version-bearing surfaces sit at `0.3.0` (`skills/pairmode/scripts/_version.py:3`,
`.claude-plugin/plugin.json:4`, `.claude-plugin/marketplace.json:14`,
`skills/pairmode/SKILL.md:5`). Ensures 17 bumps all four. Claude Code invalidates its plugin
cache on the `plugin.json` / `marketplace.json` version, so the increment does what is needed.
An independent sweep for other `0.3.0` pins found no surface the story missed.

**Spec quality is high, and the specs found real things.** `INFRA-310` independently identified
the duplicate CER IDs, three distinct disposition formats, `CER-118` as a forward-reference from
a sibling story, the fourth version surface, the hard version pin in
`tests/pairmode/test_fold_preparation.py:28-32` that breaks on bump, and the fact that
`_mark_phase_complete_in_era_ledger` only writes the highest active era. It correctly excludes
`pairmode_migrate.py:938`'s `to-030` seed as a migration target rather than a version surface.
Requires sections are re-verified with line-number drift called out. **This spec set does not
need a quality intervention.**

**Deferred Phase 64 observability work was genuinely absorbed, not dropped.** All five stories
(`INFRA-164`..`168`) are `status: complete` under `phase: "HARNESS007-main"`.

**Context control is honestly implemented.** `hooks/pre_tool_use.py:71-76` gates exactly four
subagent types, with `reviewer` exempt for a stated and correct reason (`INFRA-246`: it is the
mandatory deterministic next step, so blocking it preserves nothing). The README describes this
accurately.

---

## 4. Correction: which system of record

This review initially evaluated the "refocus on the system of record" intention against *flex's
own* bookkeeping — its CER backlog, phase index, era ledgers. That was a conflation, and it
concealed the most serious finding in this document.

The system of record named by the README is the one **consuming repos depend on**, seeded and
maintained by flex tooling. `README.md:8` — *"makes that record the source of truth for every
agent and every session"*; `README.md:12` — *"persistent refocus to the system of record."*

`skills/pairmode/templates/CLAUDE.md.j2:7-11` defines it as the mandatory cold-start triad:

> 1. `docs/brief.md` — what and why (operator intent)
> 2. `docs/architecture.md` — how and architectural decisions
> 3. Current phase file from `docs/phases/` […]
>
> These three documents should be sufficient for any model or toolchain to cold-start this
> project and reproduce a valid variant without prior session context.

Plus `docs/ideology.md` as the policy surface, and the role `procedure.md` files as the
grading/build contracts. The refocus is *enforced* by `cold_read_guard.py`, which forbids the
orchestrator from reading stories cold — it must hand a story ID to a worker that reads the
record itself.

That last mechanism is why F1–F3 matter so much: **the leaf workers are thin precisely because
the procedure and the architecture doc are the source of truth.** A thin worker with a stale or
unreachable record does not degrade gracefully — it grades against recalled rules, which is the
exact failure mode the intention exists to prevent.

### Downstream record coverage matrix

`bootstrap.py:50-60` seeds nine files. `audit.py` tracks a different set.

| Downstream record file | Seeded | Audit/sync coverage |
|---|---|---|
| `CLAUDE.md` | yes | full body (`CANONICAL_FILES`) |
| `CLAUDE.build.md` | yes | full body + `drift-report` |
| `.claude/agents/*` (7 shells) | yes | full body + `drift-report` |
| `docs/brief.md` | yes | section-level, placeholder-only |
| `docs/phases/index.md` | (phase tooling) | section-level, placeholder-only |
| `docs/cer/backlog.md` | yes | section-level, placeholder-only |
| `docs/ideology.md` | yes | staleness only |
| `docs/reconstruction.md` | yes | staleness only |
| **`docs/architecture.md`** | yes | **none** |
| **`docs/checkpoints.md`** | yes | **none** |

---

## 5. Findings

### F1 — CRITICAL: the thin-agent canon reduction never propagated, and `sync` cannot deliver it

`INFRA-241` / `HARNESS-002` reduced the agent shells to thin pointers: no role logic inline,
the procedure skill is the single source of truth. flex itself is thin. **The fleet is not.**

| | `reviewer.md` lines | `git clean -fd` | procedure path resolves |
|---|---|---|---|
| flex (canon) | **47** | 0 | yes |
| `templates/agents/reviewer.md.j2` | 47 | 0 | — |
| coherra | 293 | 1 | no |
| caddy | 321 | 1 | no |
| asp | 311 | 1 | no |
| forqsite | **639** | **3** | no |
| radar | 282 | 1 | no |
| meander | 314 | 1 | no |

Every downstream project carries **6×–13× canon**, retaining the full pre-`INFRA-241` inline
review checklist. `sync` *appended* the new thin shell without removing the fat body, so
downstream `reviewer.md` now holds two contradictory contracts: a stale inline checklist,
followed by an instruction reading *"Read that file in full before doing anything else […] Do
not infer review rules from memory or prior context."*

The stale bodies also still carry `git clean -fd` fleet-wide — the live subject of the open
`CER-065` (Do Later) row. Canon has moved on: the template carries 0 occurrences, flex's own
shell 0, and the only legitimate remaining surface is
`skills/pairmode/skills/reviewer/procedure.md` (2, in the FAIL-revert block).

**Root cause is structural, not a bug.** `sync_project`'s contract at
`skills/pairmode/scripts/sync.py:344` is *"Never modifies EXTRA items."* The stale fat sections
are classified EXTRA (present in project, absent from canonical). Therefore:

- `sync` can **add** canon — missing sections are appended (`sync.py:450-455`)
- `sync` can never **remove** canon
- the thin-agent shift was a canon *reduction*
- **`sync` is built for canon growth and structurally cannot deliver canon shrinkage**

**Consequence for the release.** This is not fixable by hand-migration, which bears directly on
the instruction to treat phase 106 as effectively closed: no `sync` run at any version removes
these bodies. They require deletion or a shrink-capable sync mode. As it stands, `0.3.1` ships
to a fleet whose reviewers grade against 0.2-era inline rules while being told not to.

No story in era 004 addresses this. `CER-065` covers a fragment of it (the `git clean -fd`
residue) and `INFRA-304` owns that row, but the propagation mechanism itself is unowned.

### F2 — HIGH: `audit` reports the stale contract as healthy

`audit` does see the stale sections. It renders them with a checkmark:

```
✓ .claude/agents/reviewer.md: Section '## review checklist' is project-specific (not in canonical template)
✓ .claude/agents/reviewer.md: Section '**1. protected files**' is project-specific (not in canonical template)
✓ .claude/agents/reviewer.md: Section '**3. build gate**' is project-specific (not in canonical template)
```

On a file class whose entire design contract is *"thin shell, no inline role logic,"* an
unexpected section is a **finding**, not a project prerogative. The EXTRA classification is
correct and useful for project-authored docs; applying it unqualified to `CANONICAL_FILES`
is what let F1 persist unnoticed across the whole fleet. This is the cheap fix that would have
surfaced F1 months ago.

### F3 — HIGH: `docs/architecture.md` has no currency mechanism downstream

Item #2 of the mandatory cold-start triad is absent from `CANONICAL_FILES` (`audit.py:41-51`),
absent from `SCAFFOLD_FILES` (`audit.py:56-60`), absent from the staleness checks that do cover
`ideology.md` and `reconstruction.md` (`audit.py:608-652`), and absent from
`pairmode_drift_report.py`. It is seeded once at `bootstrap.py:57` and never checked again —
while `bootstrap.py:112-113` simultaneously deny-lists it from writes. Seeded, protected, and
unmaintained: it ossifies.

Observed divergence: coherra 365 lines, caddy 99, asp 1568, forqsite 1493.

This is the same defect class `INFRA-305` is fixing *inside flex* (`CER-078`/`084`/`100` — a
stale grading contract that produced a false CRITICAL and cost a phase's time). `INFRA-305`
fixes flex's copy. Nothing detects the identical decay in any consuming repo.

**A guard of the right shape already exists and was not generalised.**
`tests/pairmode/test_audit.py:2209` enforces `AGENT_FILES ⊆ CANONICAL_FILES` so agent shells
cannot be seeded-but-untracked. There is **no equivalent assertion for
`bootstrap.SCAFFOLD_FILES` ⊆ the audit-tracked set**. That omission is why `architecture.md`
and `checkpoints.md` fell through, and closing it is a one-test change.

### F4 — HIGH: `check-index` fails, and the closing story requires it to pass

`INFRA-310` Ensures 14 requires `check-index` → **exit 0, no output**. It currently exits 1 with
**48 violations**:

| Category | Count | Notes |
|---|---|---|
| `orphan-story` | 21 | story files in no phase Stories table |
| `deferred-without-section` | 13 | all `phase-97.md` (the unmerged fold) |
| `cross-link` | 12 | incl. **5 era-001 ledger/index status mismatches**, 7 dangling phase refs |
| `status-drift` | 2 | `OBS-006`, `RELEASE-058` |

No era-004 story addresses these. `INFRA-301` mentions `check-index` only as a reconciliation
tool for a warning path; `INFRA-310` merely consumes it. And `INFRA-310`'s `touches:` list
excludes `docs/eras/001-initial.md`, `docs/phases/phase-97.md`, and the orphan story files —
so `scope_guard` will actively **block** its builder from fixing them.

The last story of the era therefore carries an acceptance criterion it structurally cannot
satisfy. The likely outcomes are all bad: the story fails; or the assertion is quietly weakened
at build time; or the builder scope-creeps and is blocked.

Note the specific irony: 5 of the 12 `cross-link` violations are check 2c era/index mismatches —
the *same check* Ensures 10/14/15 rely on to prove the phase-107 supersession landed in lockstep.

### F5 — HIGH: era 003 never closes; 106 and 108 are left undispositioned

Two eras are simultaneously `status: active`:

```
docs/eras/003-flex-orchestrator-as-harness.md:status: active
docs/eras/004-flex-operational-closeout-and-0-3-1.md:status: active
```

Era 003's phase ledger still reads:

```
| 97  | Fold resume — pre-fold gate, fleet migration, merge to main, re-sync | deferred |
| 106 | Fleet migration campaign (driven from flex)                          | planned  |
| 107 | CER backlog drain to zero                                            | planned  |
| 108 | Era 003 close (gated on observability delivery)                       | planned  |
```

`INFRA-310` dispositions **only 107** — one of the three open phases. After cp-115 and the tag,
era 003 remains active with 106 and 108 still `planned`, and `RELEASE-072`
(`era_transition.py`, close 003) never runs. The two-active-era state is anomalous enough that
`INFRA-310` Requires 8 has to document a tooling workaround for it
(`_mark_phase_complete_in_era_ledger` only writes the highest active era, so era 003's ledger
must be edited by hand).

Per operator instruction 106 may be dispositioned as effectively closed rather than built — but
it still needs a *disposition*, exactly as 107 gets one, or the ledger and index stay
inconsistent permanently. **Caveat: see F1 — the premise that hand-migration completed the
fleet's move to 0.3.x does not hold for the agent shells.**

### F6 — HIGH: the observability UI is never functionally validated before the tag

This is the stated beta deliverable, and the only story anywhere that validates it sits in the
orphaned phase 108:

> `INFRA-278` — Observability validation: SPA over the post-campaign fleet, effort-db integrity
> audit on campaign data, evidence record

`phase-108.md` states the gate explicitly: *"Does not checkpoint until validation passes"* and
*"The era does not close on unvalidated observability."*

Era 004 has no equivalent. Phase 115's five stories are CORS and path-disclosure hardening
(`INFRA-306`), vendored-payload guards (`307`), a manifest glob guard (`308`), rollup role
hygiene (`309`), and the backlog/version record (`310`). **None of them renders the SPA or
exercises a route.**

Compounding: there is **no TypeScript test runner in the repo at all**. `INFRA-306` states it
directly — observability tests are Python structural assertions over `.ts` source text plus one
`subprocess.run(["pnpm","build"])` compile gate. For a UI being shipped as the beta headline,
the verification surface is a compile check and substring greps. That is also the reason UI
defects in this project have historically arrived via cold-eyes review rather than via tests.

### F7 — MEDIUM: the downstream procedure pointer does not resolve

All six agent templates emit a **bare relative path** with no `{{ pairmode_scripts_dir }}`
prefix — unlike `CLAUDE.build.md.j2`, which correctly renders absolute paths:

```
skills/pairmode/skills/reviewer/procedure.md
```

In flex this resolves, because flex *is* the plugin repo. In a consuming repo there is no
`skills/` directory. Verified absent in all six fleet projects checked, with no `FLEX_DIR` or
absolute-path fallback anywhere in their `.claude/agents/`.

So each downstream worker is instructed to read its grading contract "in full before doing
anything else" from a path that does not exist — and, per F1, has a stale copy of that contract
inline immediately above.

**Confidence note:** it is possible that Claude Code resolves these through plugin skill loading
rather than the filesystem, which the phrase "plugin-versioned skill" may be relying on. This
review cannot verify runtime resolution. Either way the action is the same: make it absolute, or
confirm and document the resolution mechanism. The `CER-067` precedent — `bootstrap` registering
only the `PreToolUse` hook downstream, rendering the entire context gate decorative fleet-wide —
shows this flex-works/fleet-doesn't class is real and recurring here.

### F8 — MEDIUM: `README.md` misdescribes the build loop

`README.md:222` and Scenario A step 7 (`README.md:193`) both state that `next-action` resolves to
`spawn-reviewer`; `README.md:223-224` says the orchestrator's job is to dispatch whatever comes
back; and `README.md:183` (step 4) says it drives a while-loop "dispatching whatever action the
resolver returns."

The actual contract, from `CLAUDE.build.md:11` and `next_action.py:209-210`:

> `# (spawn-reviewer membership is for orchestrator dispatch only — the resolver`
> `#  never emits it; see the CER-074 note at its declaration above.)`

Under `CER-074`'s one-iteration-per-story design, the reviewer dispatch and the PASS/FAIL
merge/discard branch are held by the orchestrator in prose, not by the resolver. `INFRA-305`
explicitly scopes README to the `CER-085` deny-list sentences only ("README is touched only for
the CER-085 deny-list sentences"), and no CER row exists for this divergence. The most-read
artifact of a beta release describes a loop that was deliberately changed.

### F9 — LOW: `INFRA-310` Requires 2's count is already stale

Requires 2 states that a naive bold-token scan returns **50** undispositioned rows. It returns
**52** today: `CER-114`/`115` were filed 2026-07-28 and `CER-116`/`117` on 2026-07-29, after the
closeout plan was written. The backlog is a live intake surface; any asserted count decays.
Ensures 6 already has the right shape (predicate + explicit survivor list) — Requires 2 should
derive the number, not assert it.

### F10 — LOW: `INFRA-310` Requires 3's duplicate-ID map is imprecise

Requires 3 states that `CER-062`, `063`, `064`, `065`, `066` "each appear **twice** in
`## Do Later`." Measured:

| ID | Occurrences |
|---|---|
| `CER-062` | **1** (Do Later, line 98) — not duplicated |
| `CER-063` | 2 — both Do Later (96 open, 104 dispositioned) |
| `CER-064` | 2 — **Do Now** (26, dispositioned) + Do Later (106, open) |
| `CER-065` | 2 — **Do Now** (24, dispositioned) + Do Later (108, open) |
| `CER-066` | 2 — Do Now (22) + Do Later (92), both dispositioned |

So there are **four** duplicate IDs, not five, and two of the pairs span quadrants rather than
sitting within Do Later. The story's own per-ID breakdown *does* place `064`/`065` correctly in
Do Now, so only the summary sentence is wrong — but a builder following the summary would search
the wrong section, which is exactly the failure Requires 3 exists to prevent.

### F11 — LOW: flex reports itself "behind canon" after the bump

`global_session_check.py:187-198` compares `skills/pairmode/SKILL.md`'s `pairmode_version` to the
project's `.companion/state.json`. flex's own state records `0.3.0`, and `INFRA-310` Ensures 21
forbids touching anything outside its named file list — `.companion/state.json` is not among
them. After cp-115 every project including flex reports `behind canon — run /flex:pairmode sync`.
Advisory only (non-blocking), but noisy for a release. `INFRA-249` set the precedent for
self-syncing flex's own state.

### F12 — LOW: `phase-64.md` contradicts its own story files

`docs/phases/phase-64.md:68-72` lists `INFRA-164`..`168` as `backlog`. All five are `complete`
under `phase: "HARNESS007-main"`. Because `story_update.py` scopes to the story's declared
`phase:` frontmatter (correctly, per `CER-064`), phase-64's rows can never be updated by tooling.
Harmless historically, but it is a phase manifest that misreports.

---

## 6. Sequencing verdict

Derived from the artifacts, as requested.

**What the artifacts imply.** Era 003 was designed to close via phase 108, gated on
observability validation, with `RELEASE-072` running the era transition and scaffolding era 004.
That never happened: era 004 was scaffolded directly (`5b585a86`) while era 003 stayed active.
Era 004's own closing story then had to encode a workaround for the resulting two-active-era
state. So the current structure is not a designed sequence — it is the residue of an era
transition that was skipped.

**Recommended resolution.** Fold 108's obligations into era 004 rather than reviving the phase:

- `INFRA-278`'s validation → a new phase-115 story (F6). This is the operative gate, not paperwork.
- `INFRA-279`'s exit criterion + `RELEASE-072`'s transition → widen `INFRA-310`, which already does exactly this shape of work for phase 107.
- 106 → disposition as complete-by-hand-migration with a stated evidence limitation, **but not before F1 is resolved**, since the premise that the fleet migrated does not hold for agent shells.
- 97 / `HARNESS016-main` → leave `deferred`; it is the unmerged fold and is correctly inactive. Its 13 `deferred-without-section` violations should be resolved as part of F4 rather than by reviving the phase.

---

## 7. The three intentions, assessed against code

### Control drift by controlling context — sound

The strongest of the three. `hooks/pre_tool_use.py:71-76` gates four build-cycle subagent types
mechanically, hook-side, with the `reviewer` exemption justified rather than incidental. State is
session-scoped after `INFRA-285`. The README describes it accurately. Only nit: `docs-reviewer`
is ungated and that is not written down anywhere.

### Refocus on the system of record — the weakest, and this era papers over it

Assessed correctly (per § 4), the mechanism is **sound in flex and unenforced in every repo that
consumes it**. `INFRA-305` is a genuinely good story that fixes flex's own grading contract; F1,
F2, F3 and F7 show the same class is unaddressed and largely undetectable downstream. The
architecture doc has no currency check, the agent shells never received the canon reduction, and
`audit` reports the stale state with a checkmark.

There is a real structural asymmetry worth naming: **`sync` is a monotonic mechanism applied to a
non-monotonic canon.** It propagates additions and is contractually forbidden from propagating
removals. Every future simplification of the methodology will fail to reach the fleet the same
way this one did, silently, unless that is fixed once.

The one genuine strength of the harness model here: the `procedure.md` files are read from the
shared checkout, not bootstrapped per project — so `INFRA-305`'s corrections propagate fleet-wide
with no sync at all. That is the right design. F7 is what currently prevents it from working.

### Shift deterministic processes to code — real residue, partly by design

Under `CER-074`, the reviewer dispatch, the PASS/FAIL branch, and the merge/discard decision
moved *out* of the resolver into orchestrator prose. That was a deliberate trade (avoiding a
wasteful second builder on a mid-story re-poll), but it means two of the loop's most consequential
decisions are LLM-held, and F8 shows the README still describes the pre-`CER-074` design.

Separately, `CER-114` establishes that spawn completion has **no deterministic signal**: no
`SubagentStop` hook is registered, `post_tool_use.py` fires at *launch* for async spawns, the
quiescence sweep can never promote the driving session's own spawns, and ~18% of transcripts end
`stop_reason: None`. `INFRA-298` fixes this and is correctly placed as a shared blocker in phase
113 — good call, and the highest-value code story in the era.

One dependency worth flagging: per `CER-102`, the escalation ladder's insert-time bump is
*structurally dead* on async spawns, so the entire retry/model-upgrade ladder now depends on
reconciliation working. That is a single point of failure for the "build whole phases unattended"
claim, and `INFRA-298` is what protects it.

---

## 8. Recommendations

Ordered by what gates the tag. None requires a new phase.

**Phase 113 (shared blockers) — add:**

1. **A canon-reduction path in `sync`** (F1). An opt-in `--prune-extra`, or a `retired_sections`
   manifest, so canon *shrinkage* can land downstream. Pair it with an EXTRA-on-`CANONICAL_FILES`
   severity change (F2) so an unexpected section in a thin shell reads as a finding, not a `✓`.
   This is the highest-value story available and it unblocks the fleet actually receiving 0.3.1.
2. **Absolute-path the procedure pointer** in the six agent templates (F7), or verify and document
   plugin-skill resolution. Cheap, and it decides whether downstream workers can reach their
   contract at all.

**Phase 114 (build-loop) — add or widen:**

3. **`check-index` to zero** (F4), sequenced before `INFRA-310`. Alternative: downgrade Ensures 14
   to "no new violations against a recorded baseline of 48." The first is materially better —
   it converts the index from convention into mechanism, which is the same argument `INFRA-305`
   makes for the procedure docs.
4. **Track `docs/architecture.md` in `audit`** (F3), at minimum as a staleness-checked file, plus
   the `bootstrap.SCAFFOLD_FILES ⊆ audit-tracked` parity test mirroring `test_audit.py:2209`.
5. **Add the README build-loop correction to `INFRA-305`** (F8) and file a CER row so it is
   tracked rather than remembered.

**Phase 115 (observability + 0.3.1) — add or widen:**

6. **A real UI validation story** absorbing `INFRA-278` (F6): the SPA served against ≥2 registered
   repos, each route exercised, evidence pasted. If a TS test runner is out of scope for 0.3.1,
   a documented manual dogfood checklist with pasted output is an acceptable beta floor — but
   "compiles" is not.
7. **Widen `INFRA-310`** to disposition phases 106 and 108 and run the era-003 transition (F5),
   mirroring what it already does for 107. Fix Requires 2's stale count (F9) and Requires 3's
   duplicate map (F10) while in the file. Consider the flex self-sync (F11).

**Beta signalling.** Ensures 17's ban on a pre-release suffix is correct for cache behaviour —
keep it. If the UI's beta status should be legible, put it in `README.md` § Status and the
`0.3.1` CHANGELOG entry, not the version string.

---

## 9. Reproduction

Every command below is read-only and was run from the repo root at `3b84947d`.

**Undispositioned row count (52).** `INFRA-310` Ensures 6's own predicate:

```bash
python3 - <<'PY'
import re, pathlib
MARK = re.compile(r'\*\*(RESOLVED|SUPERSEDED|OBSOLETE|REJECTED|AMENDED|BACKLOG-RETAIN)\b')
ROW  = re.compile(r'^\|\s*(CER-\d+[a-z]?)\s*\|')
sec = None; und = []
for n, line in enumerate(pathlib.Path('docs/cer/backlog.md').read_text().splitlines(), 1):
    if line.startswith('## '): sec = line[3:].strip()
    m = ROW.match(line)
    if m and not MARK.search(line): und.append((n, sec, m.group(1)))
print(f"undispositioned rows: {len(und)}")
PY
```

**Coverage / orphan check (empty result).** Cross-references the 52 rows against all 15 story
specs plus `INFRA-310`'s obsolete set. Note the glob must be `INFRA-29[6-9]` **and**
`INFRA-3[01][0-9]` — `INFRA-3*` alone silently drops four stories.

**Duplicate-ID map (F10).** `/tmp/cer_dupcheck.py` in this session; regenerate by grouping
`^\| (CER-\d+) \|` matches by ID with line number and section.

**Test baseline (4116 / 211):**

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -q --tb=no
# → 4116 passed, 211 skipped, 14 warnings in 176.76s
```

**`check-index` violations (48):**

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/flex_build.py check-index --project-dir .
# → exit 1
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/flex_build.py check-index --project-dir . 2>&1 \
  | sed 's/ .*//' | sort | uniq -c | sort -rn
#   21 orphan-story / 13 deferred-without-section / 12 cross-link / 2 status-drift
```

**Era statuses (two active):**

```bash
grep -H '^status:' docs/eras/*.md
```

**Fleet canon divergence (F1, F7):**

```bash
for p in coherra caddy asp forqsite radar meander; do d=/mnt/work/$p
  printf "%-10s reviewer_lines:%-5s git_clean_fd:%-3s procedure:%s\n" "$p" \
    "$(wc -l < $d/.claude/agents/reviewer.md)" \
    "$(grep -c 'git clean -fd' $d/.claude/agents/reviewer.md)" \
    "$([ -f $d/skills/pairmode/skills/reviewer/procedure.md ] && echo YES || echo DANGLING)"
done
wc -l < .claude/agents/reviewer.md                              # 47 (canon)
wc -l < skills/pairmode/templates/agents/reviewer.md.j2         # 47
grep -c 'git clean -fd' skills/pairmode/skills/reviewer/procedure.md   # 2 (legitimate surface)
```

**`audit` greenlighting stale sections (F2):**

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/audit.py --project-dir /mnt/work/caddy
```

**Version surfaces (all `0.3.0`):**

```bash
grep -n 'PAIRMODE_VERSION' skills/pairmode/scripts/_version.py
python3 -c "import json;print(json.load(open('.claude-plugin/plugin.json'))['version'])"
python3 -c "import json;d=json.load(open('.claude-plugin/marketplace.json'));print([p['version'] for p in d['plugins']])"
grep -n '^pairmode_version:' skills/pairmode/SKILL.md
```

---

## 10. Proposed CER rows

Offered in backlog voice for intake. `CER-118` is already reserved by `INFRA-305`, so these are
numbered from `119`.

**Do Now:**

- **CER-119 — CRITICAL:** the `INFRA-241` thin-agent canon reduction never propagated to any
  bootstrapped project. flex's `.claude/agents/reviewer.md` is 47 lines (== template); coherra
  293, caddy 321, asp 311, forqsite 639, radar 282, meander 314 — all retaining the full
  pre-`INFRA-241` inline review checklist, and all still carrying `git clean -fd` (canon carries
  it only in `skills/pairmode/skills/reviewer/procedure.md`). `sync` appended the thin shell
  without removing the fat body, so every downstream shell holds two contradictory contracts.
  Root cause is structural: the stale sections classify as EXTRA and `sync_project` "Never
  modifies EXTRA items" (`sync.py:344`) — `sync` propagates canon *growth* only and cannot
  deliver canon *shrinkage*. Not fixable by hand-migration. Fix: an opt-in prune/`retired_sections`
  path for canonical files. `skills/pairmode/scripts/sync.py`, `audit.py`.

**Do Later:**

- **CER-120 — HIGH:** EXTRA sections on `CANONICAL_FILES` are rendered with a `✓` and the label
  "project-specific," including on thin-shell agent files whose design contract forbids inline
  role logic. This is why CER-119 persisted fleet-wide undetected. Fix: treat EXTRA on
  `CANONICAL_FILES` as a finding; keep current behaviour for project-authored docs.
  `skills/pairmode/scripts/audit.py`.
- **CER-121 — HIGH:** `docs/architecture.md` (and `docs/checkpoints.md`) are seeded by
  `bootstrap.py:57-58` but appear in no audit-tracked list — no body comparison, no staleness
  check, no drift-report — while being deny-listed from writes (`bootstrap.py:112-113`). Item #2
  of `CLAUDE.md`'s mandatory cold-start triad has no currency mechanism in any consuming repo;
  observed spread 99–1568 lines. `test_audit.py:2209` guards `AGENT_FILES ⊆ CANONICAL_FILES` but
  no equivalent guards `bootstrap.SCAFFOLD_FILES`. Fix: track it, and add the parity test.
- **CER-122 — MEDIUM:** the six agent templates emit a bare relative procedure path
  (`skills/pairmode/skills/<role>/procedure.md`) with no `{{ pairmode_scripts_dir }}` prefix,
  unlike `CLAUDE.build.md.j2`. Verified non-resolving in six fleet projects with no `FLEX_DIR`
  fallback. Workers are told to read their contract "in full before doing anything else" from a
  path that does not exist. Verify plugin-skill resolution first; if it does not apply, render
  absolute.
- **CER-123 — MEDIUM:** `README.md:183`, `:193`, `:222`, `:223-224` describe `next-action`
  emitting `spawn-reviewer` and the orchestrator dispatching only resolver output. `CER-074` made the
  reviewer dispatch and PASS/FAIL branch orchestrator-held; `next_action.py:209-210` states the
  resolver never emits it. `INFRA-305` scopes README to deny-list sentences only.
- **CER-124 — MEDIUM:** `check-index` exits 1 with 48 pre-existing violations (21 orphan-story,
  13 deferred-without-section in `phase-97.md`, 12 cross-link incl. 5 era-001 ledger mismatches,
  2 status-drift). `INFRA-310` Ensures 14 requires exit 0 but cannot touch the offending files
  under its declared scope.

**Do Much Later:**

- **CER-125 — LOW:** `docs/phases/phase-64.md:68-72` lists `INFRA-164`..`168` as `backlog`; all
  five are `complete` under `phase: "HARNESS007-main"`. Unreachable by `story_update.py` because
  it scopes to declared `phase:` frontmatter.
- **CER-126 — LOW:** after the `0.3.1` bump, flex's own `.companion/state.json` retains `0.3.0`,
  so `global_session_check.py:198` reports flex itself "behind canon". `INFRA-249` set the
  self-sync precedent.

---

*End of review.*
