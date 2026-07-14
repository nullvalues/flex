---
era: "003"
---

# flex — Phase 87: checklist-item-level override granularity for sync/audit

← [Phase 86: permissions-create idempotency](phase-86.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->

## Goal

Close a methodology bug found via an external report from another
pairmode-run project (coherra): `sync.py`'s section-level diffing silently
reverted a legitimate, previously-committed project customization.

Coherra's `.claude/agents/reviewer.md` had its BUILD GATE checklist item
(and the matching "## Test run" block) hand-fixed in story INFRA-009 to run
`pnpm -r --if-present build && pnpm -r --if-present test` instead of the
canonical single `{{ test_command }}`. Running `pairmode sync` afterward
silently reverted both back to the single-command canonical form — dropping
the build step entirely — because:

- `audit.py::_split_sections` keys sections on `_SECTION_RE = r"^(##+ .+|---)$"`
  — i.e. `##`/`###`+ headers or bare `---` lines. Canonical checklist items
  (in `reviewer.md.j2`, `builder.md.j2`, `security-auditor.md.j2`,
  `intent-reviewer.md.j2`) are not headers — they're bold markers like
  `**3. BUILD GATE**`, `**2.5 STORY SPEC**`, `**5a. Conviction consistency**`
  living inside one large `## Review checklist` H2 section.
- Because BUILD GATE isn't independently addressable, coherra's customized
  checklist body as a whole differs from canonical and audits as
  INCONSISTENT for the entire `## Review checklist` section (10 items).
  `.pairmode-overrides` can only declare the override at that same
  granularity — pinning it would silently opt the whole checklist out of
  future canonical improvements (e.g. this run's legitimate `test_gate`
  frontmatter delivery), not just the one customized bullet.
- Net effect: there is no way today for a project to pin one checklist
  bullet against canonical drift while still receiving updates to the rest
  of the section. Any project that hand-fixes a single checklist item is
  silently exposed to having that fix reverted by the next `sync` run.

The fix: extend section-boundary recognition to also split on the bold
numbered-item marker convention already in universal use across the
canonical checklist templates (`**N[.letter][.sub]. LABEL**` — covers `1.`,
`2.5`, `5a.`, etc.), so each checklist item becomes its own addressable
section key for both audit's INCONSISTENT detection and sync's
override/replace/append logic. Projects can then declare
`.claude/agents/reviewer.md:**3. build gate**` in `.pairmode-overrides` and
get exactly that one item pinned, with the rest of the checklist still
tracking canonical.

A second, unrelated methodology bug found via the same external report chain
(caddy project, same session that reported the coherra issue): the
orchestrator itself repeatedly violated the build loop's cold-read contract
— `CLAUDE.build.md` says the builder gets "the story ID only... Do not pass
story text, file contents, or git history" and the reviewer "reads its own
story spec cold" — by directly `Read`-ing `docs/stories/**` and
`.claude/agents/**` files into its own context and hand-inlining that
content into Agent prompts, instead of passing the story ID and a role-file
pointer and letting the subagent read cold. This happened three times in a
row (two `/clear` + identical-prompt retries) on a one-line-diff story,
burning the context budget on orchestrator overhead the prose contract was
supposed to prevent. The contract already existed in prose; prose alone did
not hold under repetition.

No hook currently gates `Read` at all — `hooks/pre_tool_use.py` only
dispatches `Task`/`Agent` (context budget) and `Edit`/`Write` (scope guard).
Verified empirically (live probe against a temporary debug hook, reverted
immediately after): the PreToolUse hook payload gains an `agent_type` key
(alongside `agent_id`) precisely when the triggering tool call originates
from inside a spawned subagent's own tool-use loop — absent when the
top-level orchestrator makes the call itself. This is not documented in
Claude Code's hooks reference, but is a real, non-spoofable runtime signal:
the orchestrator cannot fake `agent_type` being present without actually
being a subagent.

The fix: a new `Read`-matched branch in `hooks/pre_tool_use.py`, delegating
to a new `cold_read_guard.py` module (matching the existing thin-dispatcher
pattern), blocks `Read` calls to `docs/stories/**` or `.claude/agents/**`
whenever `agent_type` is absent from the payload. Scope is deliberately
narrower than the full set of files the caddy incident touched: it excludes
`docs/phases/**` and `docs/architecture.md`, because `CLAUDE.build.md`
already has legitimate, documented orchestrator-level reads of those paths
(the "3.5 Phase doc boundary scan" step, phase-completion Stories-table
check, and checkpoint-time intent-review doc updates) — blocking those would
break sanctioned behavior, not just the violation. `docs/stories/**` and
`.claude/agents/**` have zero such precedent anywhere in `CLAUDE.build.md`;
every documented interaction with them is either a subagent's own cold read
or an orchestrator-side CLI/`git add` call that never opens their content.

A third, unrelated finding, surfaced via an external report from the radar
project (fable-orchestrated): `story_new.py --phase MU020` failed to
auto-register the new story into the phase's Stories table. `_append_to_phase`
(`skills/pairmode/scripts/story_new.py:127-137`) only recognizes two filename
shapes for the target phase manifest — `{phase}-*.md` (phase arg as filename
prefix) and exact `phase-{phase}.md`. Suffixed phase manifests, of the form
`phase-<phase_id>-<suffix>.md` (the convention `phase_new.py --phase-id
--suffix` produces — see CER-038), match neither glob. `_append_to_phase`
falls through to `return False` with no error surfaced to the caller, so the
story file is still created correctly but the phase manifest's Stories table
silently fails to get the new row — the radar operator had to add the row by
hand. Logged as CER-062 (Do Later) and pulled forward into this phase since
it's a low-effort, directly-related tooling fix alongside the other two
stories in this phase.

A fourth finding, surfaced live on story EDGE-001 (pre-Phase-87): the
builder refused to run `flex_build.py permissions-create` via `Bash`,
reporting it as blocked by "an explicit Edit/Write deny rule protecting
`docs/phases/permissions/**`." Investigation (this session) confirmed no
such rule exists in `.claude/settings.json` or `.claude/settings.local.json`
— the only configured deny entries are `skills/companion/**`, `lessons/**`,
`.claude-plugin/**`, `skills/seed/**`. `docs/phases/permissions/**` is also
absent from CLAUDE.md's Protected Files list (item 7). The block was the
model's own permission classifier self-enforcing prose in
`docs/stories/INFRA/INFRA-194.md`, which describes the path as "a Layer 1
protected path under the orchestrator's auto-mode deny rules" — a design
narrative, not a machine-enforced rule — and treating the trusted script's
`Bash` invocation as equivalent to a raw `Write` to that path.

Separately (and compounding it): `CLAUDE.build.md` invokes
`permissions-create` unconditionally at Step 1 of every build-loop entry
(lines ~427-430), with no check for whether the story's declared scope
(`primary_files`/`touches`) has changed since the permissions file was last
generated. The script itself is already idempotent (Phase 86/INFRA-194 —
`cmd_permissions_create` reads the existing file and returns before writing
if `allowed_paths` is unchanged), but that idempotency never gets a chance
to prove itself when the invocation is blocked before the script runs, and
the orchestrator has no reason to skip the call in the first place even
when nothing changed.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-195 | Checklist-item-level section granularity in audit/sync | planned |
| INFRA-196 | Cold-read enforcement hook — block orchestrator Read of story/agent files | planned |
| INFRA-197 | `story_new.py` phase-manifest glob — support suffixed phase filenames (CER-062) | planned |
| INFRA-198 | Stop self-blocking `permissions-create` — clarify it's not a protected-path write, add orchestrator skip-check | planned |

## Schema delivery

No new persistent schema objects introduced in this phase. INFRA-195 changes
section-boundary detection and the section-replace/append logic used by
`audit.py` and `sync.py`. INFRA-196 adds a new hook-dispatch branch and a
new stateless guard module; it introduces no persistent schema — the
`agent_type` field it reads is a runtime hook-payload field, not project
state. INFRA-197 changes a glob pattern in `story_new.py`'s existing
phase-manifest lookup; no new schema, no new files. INFRA-198 changes
prose (`INFRA-194.md`, `architecture.md`) and orchestrator instructions
(`CLAUDE.build.md`), plus a permissions config entry; no schema change.
