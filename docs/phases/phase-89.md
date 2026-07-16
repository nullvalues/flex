---
era: "003"
---

# flex — Phase 89: Remove flex-specific hook paragraph from canonical CLAUDE.md.j2 template

← [Phase 88: Scope context-budget gate to pairmode build-cycle agents](phase-88.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->

## Goal

A pairmode sync-attempt review on a downstream (non-flex) project surfaced that
its synced `CLAUDE.md` describes a "Documented thin-delegation exception" for
`hooks/pre_tool_use.py`'s `Read` dispatch to `skills/pairmode/scripts/cold_read_guard.py`
(INFRA-196) — naming a hook file path and an flex-internal story ID that have
no counterpart in that project's own repository. Confirmed the paragraph
originates in the canonical template itself
(`skills/pairmode/templates/CLAUDE.md.j2:35-42`), not a bad local edit: every
project bootstrapped from this template inherits the same paragraph verbatim.

Confirmed via `bootstrap.py`'s `SCAFFOLD_FILES` list that `hooks/` is never
among the files copied into a target project — hook scripts stay in the flex
plugin install and are wired into a bootstrapped project's
`.claude/settings.json` by absolute path (`_register_pretooluse_hook`), never
as a project-local file. So no bootstrapped project will ever have a local
`hooks/pre_tool_use.py` to point a reviewer at, regardless of any conditional
gating — the paragraph is not something to make conditional, it is flex-repo
dogfooding detail that does not belong in the generic template at all.

`/mnt/work/flex/CLAUDE.md` (this repo's own file) legitimately keeps the full
paragraph, expanded further (INFRA-199 scoping, `post_tool_use.py`,
`session_start.py`, `user_prompt_submit.py` dispatch descriptions) — those
hooks are real and version-controlled in this repo. This phase does not touch
`/mnt/work/flex/CLAUDE.md`; it only prevents the template from re-emitting a
version of this content into other projects' synced files.

The fix: remove the `hooks/pre_tool_use.py` / `cold_read_guard.py` /
INFRA-196 paragraph from `skills/pairmode/templates/CLAUDE.md.j2`'s PROTECTED
FILES checklist item, leaving that item's generic instruction ("Were any
protected files modified without a stated reason? Unexplained modification is
HIGH.") intact and unqualified for downstream projects.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-200 | Remove flex-specific hook exception paragraph from CLAUDE.md.j2 | planned |

## Schema delivery

No new persistent schema objects introduced in this phase. This phase edits
one template file's prose; no data model, state key, or file format changes.
