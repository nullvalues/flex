---
id: INFRA-383
rail: INFRA
title: Migrate flex's own build sessions from @inline to marketplace-installed plugin (CER-159)
status: draft
phase: "120"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - docs/architecture.md
  - CLAUDE.build.md
touches:
  - docs/cer/backlog.md
narrative_roles: []
---

## Context

CER-159 tracked `hooks/hooks.json`'s hook commands silently never firing in flex's own
dogfooding sessions. Root cause, confirmed by direct reproduction this session: flex is
registered in this repo as `flex@inline` — an implicit Claude Code CLI behaviour where a
project whose cwd contains its own `.claude-plugin/plugin.json` is auto-loaded as a plugin
without a marketplace install. That path never populates `${CLAUDE_PLUGIN_ROOT}`, so every
command in `hooks/hooks.json` (all of the form `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/<name>.py`)
expands to `python3 /hooks/<name>.py` and dies with FileNotFoundError before any hook code
runs — silently, because the CLI does not surface hook-invocation failures. Evidence:
`.companion/effort_recording.log` had zero entries between 2026-07-31T05:52:22Z and
2026-08-04 despite phases 115-119 spawning dozens of Agents. Installing flex as a real
marketplace plugin from a cloned tag snapshot was verified live to fix this — fresh,
correctly-timestamped writes appeared in both `effort_recording.log` and `state.json`'s
`context_sessions` map, in an isolated scratch dir and (after session restart) in
`/mnt/work/flex` itself. This story turns that ad hoc one-off into the repo's documented,
repeatable setup procedure, so it survives to a new machine or checkout, and marks CER-159
resolved.

## Requires

None. The marketplace install itself was already performed by the operator out of band;
this story records the procedure and the CER resolution, it does not re-run the install.

## Ensures

`docs/architecture.md` contains a self-hosted-plugin-install section whose command block
reproduces the verified clone-tag → `marketplace add` → `plugin install flex@nullvalues-flex`
sequence and names the verification signal (`claude plugin list` shows
`flex@nullvalues-flex` enabled AND `.companion/effort_recording.log` gains a fresh entry
after a session restart); `CLAUDE.build.md` points a build session at that section as a
precondition; and CER-159's entry in `docs/cer/backlog.md` carries a
`**RESOLVED 120 — ...**` marker appended after its existing evidence. Forbidden proxy: a
prose note that flex "should be installed from the marketplace" without the exact,
copy-pasteable sequence, or a `claude plugin list` check alone treated as sufficient
verification — the inline registration also lists as present, so only the
`effort_recording.log` write proves hooks actually fire.

## Instructions

1. Add a section to `docs/architecture.md` (title it for self-hosted plugin installation;
   place it near the existing plugin/hooks material) covering:
   - The failure mode: `@inline` auto-load never sets `${CLAUDE_PLUGIN_ROOT}`, so every
     `hooks/hooks.json` command expands to `python3 /hooks/<name>.py` and fails silently.
   - The verified fix, as an exact command block:
     ```bash
     git clone /mnt/work/flex ~/flex-marketplace-cache/flex-0.3.1
     git -C ~/flex-marketplace-cache/flex-0.3.1 checkout cp-119
     claude plugin marketplace add ~/flex-marketplace-cache/flex-0.3.1
     claude plugin install flex@nullvalues-flex
     ```
     State why the clone is a tag snapshot rather than `/mnt/work/flex` itself: installing
     from the live working tree stays self-referential and re-creates the inline problem.
   - Verification: `claude plugin list` shows `flex@nullvalues-flex` enabled,
     `~/.claude/plugins/cache/nullvalues-flex/flex/0.3.1/` exists, and — the only
     load-bearing check — `.companion/effort_recording.log` gains a fresh entry after a
     session restart and an Agent spawn.
   - The stale-cache note: no version bump was needed for this migration only because the
     one machine involved had its `~/.claude/plugins/cache/nullvalues-flex/flex/0.3.1/`
     directory wiped by the operator before reinstall; reinstalling against an unchanged
     version string otherwise silently serves the stale cache. Cross-reference INFRA-384,
     which documents that discipline generally.
   - The accepted limitation, one short paragraph: `claude plugin disable flex@inline -s project`
     reports success and writes `"enabledPlugins": {"flex@inline": false}` to
     `.claude/settings.json` but has no functional effect (`~/.claude.json`'s `pluginUsage`
     count for `flex@inline` kept incrementing after a full restart). Harmless: the inline
     copy's hooks fail exactly as before (no regression), the marketplace copy's fire
     correctly, and no duplicate writes or corruption were observed in
     `effort_recording.log` or `state.json`. Suppression is not attempted here.
2. In `CLAUDE.build.md`, add a short precondition line to the build-session start
   material telling the session to confirm flex is running from the marketplace install
   (not `@inline`) and pointing at the architecture.md section by name.
3. In `docs/cer/backlog.md`, append to CER-159's existing entry — do not delete or rewrite
   the evidence trail already there — a resolution marker in the file's own documented
   form, `**RESOLVED 120 — <what landed>**`, positioned per that file's header comment
   (the marker must begin the annotation segment immediately after sentence-ending
   punctuation, or inside an emphasis/bracket opener) so the checkpoint guard matches it.
   The summary names the root cause (`@inline` leaves `${CLAUDE_PLUGIN_ROOT}` unset) and
   the fix (marketplace install from a cloned tag snapshot, procedure documented in
   architecture.md).

Documentation-only story: no new module and no plugin/marketplace version bump is in
scope (operator decision — stay on 0.3.1).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -5
```
Acceptance: suite green (unchanged — this story adds no code). Documentation story — no
test file expected. Additionally verify by inspection that `docs/architecture.md` contains
the four command lines above, `CLAUDE.build.md` references the new section, and
`docs/cer/backlog.md`'s CER-159 entry contains `**RESOLVED 120` with its prior text intact.

## Out of scope

- Actually suppressing or removing the `flex@inline` registration — no supported mechanism
  exists (verified: no CLI flag, no settings key that takes effect); it is recorded as an
  accepted limitation, and INFRA-384 owns the general discipline note.
- Any `plugin.json` / `marketplace.json` version bump, or re-tagging the cached snapshot.
- Changing `hooks/hooks.json` itself — the `${CLAUDE_PLUGIN_ROOT}` command form is correct
  and works under a real marketplace install; the registration path was the defect.
  (Spec-preflight reports `hooks/hooks.json` as outside declared scope; that is intended —
  it is referenced only as evidence, never edited, so it stays out of `touches:`.)
- Automating the clone/register/install sequence as a script under
  `skills/pairmode/scripts/` — the sequence is three commands run once per machine, and a
  wrapper would add a tested code surface for no reduction in ambiguity.
