---
era: "003"
phase_class: production
---

# project — Phase 111: Plugin packaging repair: local marketplace source and skill-name de-namespacing

← [Phase 110: Effort-recording data-flow remediation (CER-101..104)](phase-110.md)

**Parent phase:** Phase 106 (fleet migration campaign, held after RELEASE-064 —
see the phase-106 campaign hold; proving cycle deferred). This phase interposes
before 106 resumes: both defects surfaced during a fresh-machine plugin install
and would propagate through further fleet work.

## Findings dossier (operator-reported, 2026-07-28; verified in-repo)

**Defect 1 — local plugin install fails (INFRA-291).**
`.claude-plugin/marketplace.json` `plugins[0].source` is
`{"source": "github", "repo": "nullvalues/flex"}`. The actual install flow is
`claude plugin marketplace add ./flex` then `claude plugin install
flex@nullvalues-flex`; with a github source the install clones the published
repo instead of using the added local checkout. Fix: `"source": "./"`
(resolves relative to the marketplace root; correct for both local-path and
GitHub marketplace adds). An equivalent hotfix was applied uncommitted on the
operator's other machine and becomes redundant once this lands.
`README.md:88-95` documents a nonexistent command (`claude code plugin install
./flex` — no `code` subcommand; `plugin install` takes no path) and
`README.md:99-100` says "three skills" (there are four). CONTRIBUTING.md has
two related references to check.

**Defect 2 — doubled skill namespace `/flex:flex:*` (INFRA-292).**
All four `skills/*/SKILL.md` frontmatters bake the plugin prefix into the
skill name (`name: flex:seed`, `flex:companion`, `flex:pairmode`,
`flex:observability`). Claude Code namespaces installed plugin skills as
`<plugin-name>:<skill-name>` with the plugin already named `flex` in
`.claude-plugin/plugin.json`, so installs surface `/flex:flex:seed`. Fix: bare
names (`seed`, `companion`, `pairmode`, `observability`) — the installed form
then matches the `/flex:<skill>` shape every existing doc/script string
already uses (~40 references in audit.py, lesson_utils.py,
global_session_check.py, pairmode_status.py, sidebar.py, README, SKILL.md
section headers — all stay as-is). Known ripples: `pairmode_migrate.py:181`
anchor→flex rewrite rule stamps `name: flex:seed` into downstream repos and
must become bare; builder must verify no test asserts a literal
`name: flex:*` frontmatter value (tests/pairmode/test_skill_md.py hits are
body section headers, which remain correct).

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Make the flex plugin installable from a local checkout (marketplace source ./ instead of github) and fix the doubled /flex:flex:* skill namespace by de-prefixing SKILL.md names; correct the README/CONTRIBUTING install documentation that propagated the broken command.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-291 | Marketplace plugin source: local-relative ./ instead of github clone; README/CONTRIBUTING install-flow correction | complete |
| INFRA-292 | De-namespace SKILL.md skill names (flex:X -> X) to fix doubled /flex:flex:* plugin commands | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-111 Cold-eyes checklist

- [x] written-never-read — no persistent state introduced; `marketplace.json plugins[].source` and SKILL.md `name:` are read by the external Claude Code plugin loader (security audit check 7 traced consumers).
- [x] required-never-written — no read path added; `global_session_check.py` reads `pairmode_version:` only, not `name:`.
- [x] duplicate state — none; the plugin name lives solely in `plugin.json`, which is the fix (skill names no longer duplicate it).
- [x] half-implementation — rule 8 fixed for seed; the pre-existing rules-9/10 gap (anchor:pairmode/anchor:companion names not rewritten) is filed as CER-108, and the guard test's hardcoded skill list as CER-109, both Do Later.

Filled at checkpoint (cp-111): both stories single-attempt PASS; security audit
PASS (zero CRITICAL/HIGH, two LOW → CER-108/109); intent review ALIGNED; docs
gate PASS after CHANGELOG + architecture.md currency fixes; suite green 4083
passed / 0 failed.
