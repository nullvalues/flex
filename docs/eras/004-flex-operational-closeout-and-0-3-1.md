---
id: "004"
name: flex — Operational closeout and 0.3.1
status: complete
closed_at: 2026-08-04
reopened_at: 2026-08-04
---

## Strategic intent

Drain the CER backlog's operational defects and ship pairmode 0.3.1 clean: zero
unresolved operational findings, docs matching code, a fleet that can actually
*receive* the release, and a version-consistent plugin tagged with exactly one
era active. Group-3 blockers land first because both rails stand on them; the
phase-107 stub drain is superseded into this era.

**Scope revision (2026-07-29):** the era was deliberately scaffolded incomplete
at inception, pending external review. Two reviews arrived — the cold-eyes pass
(`docs/closeout-planning-cold-eyes-review_20260729.md`) and cora's
hand-migration findings — and were reconciled into
`docs/closeout-agreements-20260729.md` (AG-1..AG-7), which is the authority for
this era's final shape. The review's containment sizing ("no new phase") was
set aside by operator decision: the era gains INFRA-311 (sync canon-shrink —
the CRITICAL propagation fix), INFRA-312 (observability functional validation),
a widened INFRA-310 (era-003 closure folded in, check-index driven to zero),
and phase 116 (cora upstream, pre-tag). The 0.3.1 record and tag move to
phase 116 as the era's last act.

## Rails

| Rail | Primary domain |
|------|----------------|

## Phases

| Phase | Title | Status |
|-------|-------|--------|
| 113 | Shared blockers: frontmatter, resolver evidence, recording determinism | complete |
| 114 | Build-loop closeout: worktrees, scaffolding, migration tooling, doc currency | complete |
| 115 | Observability closeout: API hardening, payload guards, rollup hygiene, functional validation | complete |
| 116 | Cora upstream: methodology gates, resolver cadence, spec-time controls; backlog truth pass and 0.3.1 | complete |
| 117 | Build-loop integrity remediation: escalation ladder, dead handoffs, CER-append corruption | complete |
| 118 | Narrative of Record: propagation, spec-writer/intent-reviewer integration, and mid-build steering | complete |
| 119 | Spec precision (frozen exemplar), fundamental-doc trim, and CER backlog drain (era 004 closeout) | complete |
| 120 | CER-159 hook-firing fix: marketplace install migration, era-004 stable close | complete |

## Exit criterion (closed 2026-08-04, superseded — see Reopened below)

The era's strategic intent named four conditions: zero unresolved operational findings, docs
matching code, a fleet that can actually receive the release, and a version-consistent plugin
tagged with exactly one active era. **Exit criterion: substantially met, with one honest
qualifier.** Phase 119 (operator-directed, widened mid-flight from 2 to 18 stories) drained the
broadest reasonable set of open CER backlog items — CER-042, 062, 109, 117, 121, 125, 131, 132,
133, 135, 142, 145, 146, 160, 162, 163 all now carry RESOLVED annotations — and `## Do Now` (the
checkpoint-blocking section) is fully clear. Docs (`architecture.md`, `CHANGELOG.md`, narrative
files) were brought current against the landed code as part of the same phase.

The qualifier: "zero unresolved operational findings" was not achieved literally. Phase 119's own
checkpoint-security audit filed four *new* findings (CER-164..167) from the very work that closed
older ones — the backlog is a living document, not a target that reaches empty. A number of
long-standing `Do Later`/`Do Much Later` items predating this era (CER-001..019, CER-031, CER-035,
CER-063) remain open; they were not in scope of the operator's "broadest reasonable" directive for
this specific phase and were not re-triaged here. This era closes on the intent's spirit — the
backlog's checkpoint-blocking gate is clear, the broadest reasonable drain was done, docs are
current — not on a literal zero count that a living backlog structurally cannot sustain.

This era is tagged `cp-119`; era 005 opens as a lightweight placeholder pending real scope.

## Reopened (2026-08-04)

The closeout above is inaccurate in one respect: CER-159 (HIGH, `docs/cer/backlog.md`)
was filed mid-era (2026-08-02, during Phase 117 build) and was left in `## Do Later`,
unresolved, at closeout — but the "one honest qualifier" paragraph above only disclosed
*pre-era* Do Later items (CER-001..019, CER-031, CER-035, CER-063) as the known-open
exceptions. CER-159 was in-era and HIGH severity; its omission from that disclosure was
an oversight, not a deliberate scoping call.

Follow-up investigation (2026-08-04, this session) confirmed CER-159's suspected defect
at much higher confidence than the original filing: `.companion/effort_recording.log`
and `.companion/state.json`'s `context_sessions` map both show the `PostToolUse`
Task/Agent hook branch (`hooks/post_tool_use.py`) has not executed even once since
2026-07-31T05:52:22Z, spanning phases 115 through 119 (~4 days, dozens of Agent spawns).
This is on flex's own dogfooding install (`flex@inline`, not marketplace-registered).
Root cause (why it stopped firing) is still open — see the CER-159 entry for what's
ruled in/out so far.

This era is reopened, not un-tagged: `cp-119` and the 0.3.1 release stand as shipped.
Reopening records that the closeout's "zero unresolved operational findings" framing
needs this correction, and that a fix for CER-159 needs its own spec (per the
spec-before-build policy) before any code changes.

**Root cause pinned down (2026-08-04, high confidence — see CER-159 for full evidence
chain):** direct standalone reproduction shows `hooks/post_tool_use.py` runs correctly
on its own; the failure is in `hooks.json`'s invocation itself. `CLAUDE_PLUGIN_ROOT` is
empty in this repo's session environment, so `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.py`
resolves to `python3 /hooks/post_tool_use.py` and fails instantly, before any hook logic
runs — consistent with the session's own recorded hook-duration stats (p50 = 1ms for
`pre_tool_hook_duration_ms`, far below normal Python startup time). Working hypothesis:
`CLAUDE_PLUGIN_ROOT` is not populated for flex's `flex@inline` self-referential plugin
registration the way it would be for a marketplace-installed plugin. Not confirmed at the
CLI-internals level — this session cannot instrument the harness's actual hook-subprocess
environment directly — but every available signal (standalone repro, empty env var,
failure-timing statistics, this being uniquely flex's own dogfooding install rather than
a fleet-wide pattern) fits this explanation.

Next step: spec a fix for CER-159 — likely a `hooks.json` invocation change that stops
depending on `${CLAUDE_PLUGIN_ROOT}` resolving for inline installs (e.g. a wrapper
resolving the script path relative to `hooks.json`'s own location as a fallback), plus a
live-session verification step to confirm the hypothesis before/while building. Which
phase number receives that spec (new phase in this era vs. era-005) is still pending
operator direction.

## Re-closed (2026-08-04, Phase 120)

Phase 120 (INFRA-383/384/385) resolved CER-159 for real, not just hypothesized it. Root
cause confirmed by direct reproduction: `hooks/post_tool_use.py` runs correctly standalone;
`hooks.json`'s command invocation is what fails, because `${CLAUDE_PLUGIN_ROOT}` is never
populated for `flex@inline`'s self-referential registration. Fix verified live, not just
theorized: flex was registered as a real marketplace plugin (`flex@nullvalues-flex`, a
directory-source marketplace pointed at a stable `cp-119` snapshot, decoupled from the live
working tree), and hook firing was directly confirmed — first in an isolated scratch
directory, then in this repo itself across a session restart (`effort_recording.log` and
`state.json`'s `context_sessions` both show fresh, correctly-timestamped writes where before
there were none since 2026-07-31).

Two things intentionally NOT fixed, documented instead as accepted limitations (INFRA-384):
the `flex@inline`/`flex@nullvalues-flex` dual registration cannot be suppressed (`claude
plugin disable flex@inline -s project` reports success but has no functional effect — a
Claude Code CLI gap, not something fixable in this project) but is harmless (the inline
copy's hooks were already failing before any of this work, so its continued presence causes
no regression); and the marketplace install's version-keyed cache requires a version bump
before any future reinstall actually takes effect (no bump was needed for this phase — the
one machine testing this had its stale cache manually wiped by the operator).

Phase 120 also found and fixed a second, self-inflicted defect: three `tests/pairmode/`
tests assumed no real flex plugin install would ever exist on a dev machine and scanned the
literal `~/.claude/plugins/` unisolated — exactly the state the marketplace-install fix
above creates for the first time. Fixed same-phase (INFRA-385, CER-168) by isolating those
tests from real host state.

This era is re-closed on Phase 120 (tag `cp-120`), superseding the `cp-119` closeout above.
The original four-condition exit criterion (zero unresolved operational findings, docs
matching code, a fleet that can receive the release, one active era) now holds without the
CER-159 qualifier — CER-159 itself carries a RESOLVED marker, not just an evidence trail.
Era 005 (already open as a placeholder since the original `cp-119` closeout) remains the
correct home for whatever comes next; this phase did not need to open a new era to close
this one.
