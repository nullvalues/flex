# Findings — path to 0.4.1 (stabilization release for local-marketplace use)

**Date:** 2026-08-07
**Source:** external deep-dive (Devin CLI session) at operator request; reconciled
against the CER backlog, the phase index (through Phase 144), and the era-scaffold
handoff (`docs/Flex 0.4 roadmap decision memo.zip` — untracked at time of writing).
**Purpose:** input for orchestrator review. The recommended phases below are
**not specs** — each requires a phase doc + story specs written in-process before
any build (spec-before-build policy). New defect findings in § 4 must be filed
as CER rows before the remediation phase is specced.

**Operator intent being served:**
- Get the current tooling "good enough" for consuming repos to continue on,
  working around known defects → release as **0.4.1** so local-marketplace
  consumers get an upgrade signal.
- flex itself must **dogfood its own 0.4.1 marketplace install** and use it to
  build 0.5.x (songline) until 0.5.0 is itself dogfood-ready.
- All sibling repos convert from direct path links to local-marketplace
  consumption; stale pairmode references are fully scrubbed and configs
  verified against a working canon.
- `fold-prep` and `harness` merge down to main; main becomes both the stable
  marketplace source and the jumping-off point for the 0.5.x hard fork.
- Because 0.4.1 is the daily driver during the songline build, build-speed
  items (shadow-reviewer efficiency) and build-blocking state defects are
  in scope, not deferred.

---

## 1. Current release/branch/consumption state (verified)

### Versions and marketplace

- Plugin version is **0.3.1** in both `.claude-plugin/plugin.json` and
  `.claude-plugin/marketplace.json`. (`pyproject.toml` says `0.1.0` — cosmetic
  drift, should be aligned at release.)
- Local marketplace `nullvalues-flex` exists as a **directory source** at
  `~/flex-marketplace-cache/flex-0.3.1` — a clone of this repo pinned at
  `cp-119` — installed at **user scope**, cache at
  `~/.claude/plugins/cache/nullvalues-flex/flex/0.3.1/`.
- Per `docs/architecture.md` § INFRA-384: the install cache is version-keyed
  and a same-version reinstall **silently no-ops**. A version bump to 0.4.1 is
  therefore the upgrade signal *and* the mechanism that forces a re-copy.

### Branch state

- `harness` is **fully contained in main** (0 commits ahead; main is 868
  ahead of it). Nothing to merge; delete/archive only.
- `fold-prep` (tracked by the `/mnt/work/flex-harness` sibling clone) is
  main + a long chain of `cp-NNN` promotion merges + **exactly one real
  commit**: INFRA-332's agent-shell backfill (`.claude/agents/docs-reviewer.md`,
  `gate-worker.md`, `spec-writer.md` — 3 files, 6 lines of diff vs main).
  Content merge-down is trivial; the real work is the architectural
  retirement of the release channel, already drafted (goal, background,
  open questions, doc-impact list; **no stories yet**) in
  `docs/phases/phase-proposed-retire-harness-release-channel-20260804-001.md`.
- Remote branches `era2`, `era3-methodology`, `pairmode`, `pr-squashed` are
  historical; disposition can be decided in the same retirement phase.

### Sibling repo consumption (the stale-link inventory)

Scan of `/mnt/work/*` (17 consuming repos):

| Reference shape | Where found |
|---|---|
| `pairmode_scripts_dir = /mnt/work/flex-harness/...` in `CLAUDE.build.md` | 16 repos (aab, asp, caddy, coherra, forqsite, forqsite.help, halfhorse, lumin, meander, pokus, radar, rockue, stackabid, ud, …) |
| `pairmode_scripts_dir = /mnt/work/flex/...` (second stale canon) | cora |
| Hooks invoking `/mnt/work/flex-harness/hooks/*.py` in `.claude/settings.json` | ~14 repos |
| Hooks invoking `/mnt/work/flex/hooks/*.py` | cora, pokus |
| `PYTHONPATH="/mnt/work/flex"` Bash allows in `settings.local.json` | aab |
| flex-path permission prose in `settings.local.json` | forqsite (line 213), caddy (settings.json line 10) |
| Full pre-rename `skills/pairmode` copy vendored in-repo | anchor |

Two different stale canons coexist (`/mnt/work/flex-harness` vs
`/mnt/work/flex`), which is the confusion source the operator reported.

### flex's own dogfood inconsistency

- Hooks: **correct** — `flex@inline: false` in `.claude/settings.json`; hooks
  fire via the marketplace install (Phase 120 / CER-159 fix).
- Scripts: **stale** — flex's own `CLAUDE.build.md` hardcodes
  `pairmode_scripts_dir = /mnt/work/flex-harness/skills/pairmode/scripts` and
  every orchestrator call site spells that path. Dogfooding 0.4.1 requires
  repointing these at the marketplace-install path.

### Handoff scaffold status

`docs/Flex 0.4 roadmap decision memo.zip` (untracked) contains the 0.4.1/0.5.x
decision memo, 13 proposed phase docs, 2 design notes, era/narrative docs, and
~80 story stubs (INFRA-420..439, KERNEL, BUS, OSPA, PROSE, SONG rails). It must
be unpacked and committed before its phases can be sequenced. Memo W-phase
status against the built record:

| Memo phase | Status |
|---|---|
| W1 — shadow-reviewer dispatch wiring (INFRA-358/359, CER-164) | **built** (Phases 118, 122, 126–127, 138) |
| W2 — measurement columns + gate-worker retirement | **not built** (proposed: `phase-proposed-measurement-columns-20260807-001`) |
| W3 — sync repair | **built** (Phase 121); **final sync-all not run** (proposed: `phase-proposed-final-sync-all-20260807-004`, resumes INFRA-387) |
| W4 — fork prep, expunge gate, 0.4.1 tag | **not built** (proposed: `phase-proposed-fork-prep-20260807-005`) |
| shadow-handshake (ruled 2026-08-07) | **not built** (proposed: `phase-proposed-shadow-handshake-20260807-003`, INFRA-438) |
| completeness gate / dark-feature scan (ruling 15) | **not built** (proposed: `phase-proposed-completeness-gate-20260807-002`, INFRA-434/435) — memo makes a green scan a 0.4.1 **tag precondition** |

---

## 2. Shadow reviewer — audited operational state

**Verdict: dispatch fully wired and provably running; consumption half-open;
one structural inefficiency; one open CER.**

- **Wired end-to-end:** `shadow_review=concurrent` set in `CLAUDE.build.md`
  (line 52); concurrent spawn at the `spawn-builder` branch (line 28);
  `model_selector.select_shadow_reviewer_model` wired; agent definition +
  procedure present; security hardening complete through Phase 138
  (CER-174/175/176/177/201 all RESOLVED).
- **Proof of live execution:** CER-218's incident narrative (suggestions file
  observed mid-build during INFRA-412) — the mechanism runs in real builds.
- **Half-open loop:** the builder's read of `.pairmode-suggestions.md` is
  advisory prose only (`builder/procedure.md` § INFRA-358) — no
  adoption/decline record, no reviewer visibility of the exchange, and the
  shadow's `SHADOW-RESULT` JSON is consumed by **no code path** (the
  orchestrator waits for completion and discards the result).
- **Structural inefficiency (the build-speed cost):** the shadow's stop
  condition is "story commit appears," so its highest-value pass — the
  complete diff — lands at/after the moment the attempt is sealed. Final-pass
  findings can only save attempt N+1, never attempt N. This is precisely what
  the ruled three-artifact handshake design fixes
  (`docs/design/shadow-handshake-and-warm-attempts.md` in the scaffold:
  `.pairmode-review-request` builder marker, `.pairmode-review.lck` OPEN/CLOSED
  liveness ack, typed findings, builder dispositions, structural dead-shadow
  detection).
- **Open CER:** **CER-218** (MEDIUM) — worktree teardown/`git clean`-shaped
  step destroyed the suggestions file mid-run. **Prerequisite** for the
  handshake: the exchange record is worthless if teardown can eat it.
- Out of scope for 0.4.1 (per the design note's own sequencing): warm
  attempts / salvage manifest — lands in the era-5 TS kernel (KERNEL-007),
  not in Python. Note the dependency: measurement-columns' cause-class column
  is the salvage-manifest trigger data, another reason W2 should land as
  specced.

---

## 3. Context/state lifecycle — CER reconciliation

All previously-known CERs in this problem class are **RESOLVED**: CER-080
(stale current_story), CER-083 (phase-stamped checkpoint state), CER-095
(single-slot coordination state), CER-097 (cross-session state corruption),
CER-056 (inactive phases treated active), CER-077 (ambiguous active phase).

The operator's recurring symptoms — builds blocked by lingering stale context
values; index drift confusing next-action after a context clear — are
therefore **not covered by any open CER row**. The findings in § 4 are new.

The consistent shape: state cleanup is solid on **success paths**
(merge/discard clear their stamps correctly) and absent on **failure paths**
(session crash, orphaned worktrees, manual edits) — exactly the paths a
context clear exposes.

---

## 4. New cold-eyes findings (file as CERs before speccing remediation)

| # | Severity | Finding | Evidence |
|---|---|---|---|
| F1 | HIGH | **Session death mid-story leaves a permanent stale claim.** Orphaned `.pairmode-worktrees/<ID>/`, `state.json["current_stories"][ID]`, the `current_story` mirror, and `docs/phases/permissions/<ID>.json` all persist with no automatic recovery; `claimed_story_ids()` (flex_build.py ~1320–1327) then treats the story as claimed on the next session — the exact "build blocked after context clear" shape. Manual `clear-stale-stories --apply` + hand cleanup required. | flex_build.py ~484–516, ~5062–5138 |
| F2 | MEDIUM | **`clear-stale-stories` is a partial repair.** It clears state.json stamps only — not the orphaned worktree directory, not the permissions artifact — so the next `create-story-worktree` fails "worktree already exists" (~4828–4830) and requires manual git surgery. No unified doctor/repair command exists. | flex_build.py ~2440–2541 |
| F3 | MEDIUM | **Story frontmatter `status:` vs phase-table status is never cross-checked.** `infer_position` reads only the phase-doc Stories table; INFRA-347 synced the two on merge/discard paths, but manual edits or partial writes diverge silently and misroute next-action after a context clear. | next_action.py ~1174–1240 |
| F4 | MEDIUM | **Stale gate verdict survives spec revision.** `_clear_gate_verdict` fires only on merge and discard; a story re-attempted after its spec was revised can route on a verdict recorded against the old spec. | flex_build.py ~5118–5121 |
| F5 | LOW | **Era ledger is write-only.** `_mark_phase_complete_in_era_ledger` never validates the ledger against `docs/phases/index.md`; manual drift persists indefinitely. | flex_build.py ~1920–1980 |

Suggested remediation shape (for the spec writer, not binding): a unified
`doctor-state` command (stamps + worktrees + permissions artifacts + era
ledger + frontmatter/table cross-check), session-start orphan detection,
gate-verdict invalidation on story-file modification, and optionally a
`next-action --diagnose` provenance mode.

---

## 5. Recommended 0.4.1 phase sequence

Ruled in scope by operator (2026-08-07 session): shadow-reviewer efficiency
and state-lifecycle relief ride in 0.4.1, since 0.4.1 is the daily driver for
both the 0.3.1-repo closeouts and the songline build.

| Order | Phase | Content | Spec source |
|---|---|---|---|
| 1 | Harness retirement + merge-down | Merge `fold-prep` → main (preserving INFRA-332's 3 agent files); retire the release channel; rewrite `architecture.md` § Release channel; repoint flex's own `CLAUDE.build.md` `pairmode_scripts_dir` + call sites at the marketplace install (dogfood requirement); disposition of the `flex-harness` clone, `fold-prep`/`harness` branches, and historical remote branches | existing `phase-proposed-retire-harness-release-channel-20260804-001.md` — **needs stories** |
| 2 | State-lifecycle relief | F1–F4 (F5 optional): doctor-state, session-start orphan detection, frontmatter↔table cross-check, verdict-on-revision clear | **new spec** — file § 4 as CERs first |
| 3 | Shadow handshake | CER-218 teardown fix **first**, then the three-artifact handshake, typed findings, builder dispositions (INFRA-438), reviewer consumption of the exchange record | scaffold `phase-proposed-shadow-handshake-20260807-003` + design note |
| 4 | Measurement columns + dead code (memo W2) | cause-class column, silent-deviation marking, gate-worker retirement; cause-class is also era-5 salvage-manifest trigger data — "land exactly as specced" | scaffold `phase-proposed-measurement-columns-20260807-001` |
| 5 | Cleanup script + config canon | Canonical sibling config defined (marketplace-path hooks, canonical `pairmode_scripts_dir`); scan/rewrite/verify for every stale-reference shape in § 1's inventory (both stale canons, PYTHONPATH allows, permission prose, vendored skills copies); verify mode green = canon conformance | **new spec** — likely extends `pairmode_sync.py`/`to-030` migration rather than greenfield |
| 6 | Final sync-all + fleet conversion (memo W3 tail) | INFRA-423/424 across the 17 repos using the phase-5 tooling; every repo clean or explicitly pinned at 0.3.x | scaffold `phase-proposed-final-sync-all-20260807-004` |
| 7 | Completeness gate + fork prep + release (memo W4) | Dark-feature scan green (tag precondition, ruling 15/INFRA-434/435); fleet expunge + grep gate; version bump (`plugin.json`, `marketplace.json`, `pyproject.toml`) to 0.4.1; new `~/flex-marketplace-cache/flex-0.4.1` clone at the tag (avoids the INFRA-384 same-version no-op trap); reinstall + hook-fire verification via `.companion/effort_recording.log`; 0.4.1 tag → hard fork per ruling 12 | scaffold `phase-proposed-completeness-gate-20260807-002` + `phase-proposed-fork-prep-20260807-005` |

Deliberately **excluded** from 0.4.1: warm attempts (era 5, KERNEL-007),
event bus, and everything in the memo's E1–E8 sequence.

### Preconditions before phase 1 builds

1. Unpack and commit the era-scaffold zip (the memo, design notes, and three
   of the seven phases above live in it; the zip itself is untracked).
2. File F1–F5 via `cer.py` so the backlog remains the source of truth.
3. Write stories for phase 1 (the retirement phase doc has none) and full
   specs for phases 2 and 5 (new).

### Open questions for the orchestrator/operator

- Phase 1: archive vs delete the `flex-harness` clone and remote branches
  (`era2`, `era3-methodology`, `pairmode`, `pr-squashed`) — the retirement
  phase doc's own open questions apply.
- Phase 5/6 ordering vs phase 7: the fork-prep grep gate (fleet expunge) and
  the sibling-conversion pass both touch fleet-name surfaces; sequence so the
  scrub gate (`scrub_fleet_names.py --verify`) stays green throughout.
- Whether F5 (era ledger reconciliation) rides in phase 2 or goes to the
  Do-Later backlog.
