---
id: INFRA-376
rail: INFRA
title: Close shadow-reviewer Bash-bypass and bootstrap operator-note escaping gaps (CER-163)
status: complete
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/bootstrap.py
touches:
  - skills/pairmode/templates/agents/shadow-reviewer.md.j2
  - .claude/agents/shadow-reviewer.md
  - tests/pairmode/test_bootstrap.py
  - tests/pairmode/test_sync_agents.py
  - tests/pairmode/test_harness_path_audit.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-163 (LOW): three sub-HIGH observations from the Phase-118 checkpoint-security re-audit, after
INFRA-365/366 closed the two HIGH findings: (1) flex's own `.claude/agents/shadow-reviewer.md` was
never synced via `sync-agents`, so the shadow-reviewer role INFRA-358/359 built is currently
unreachable in this repo's own checkout — a dogfood gap, not a downstream-project issue; (2) the
shadow-reviewer's agent-shell template (`skills/pairmode/templates/agents/shadow-reviewer.md.j2`)
grants `tools: [Read, Bash]`, so a real dispatched shadow-reviewer could append to
`.pairmode-suggestions.md` via a `Bash` heredoc/append instead of `Edit`/`Write`, bypassing
`scope_guard.py`'s `pre_tool_use.py` enforcement entirely — INFRA-365 only closed the `Edit`/`Write`
route; (3) `bootstrap.py` interpolates the free-text `--operator-note` CLI value into a
frontmatter-bearing markdown file (`OPERATOR-010-project.md`) unescaped, so a note containing `---`
or YAML-special characters could corrupt that file's frontmatter block. Files:
`.claude/agents/shadow-reviewer.md` (missing), `skills/pairmode/templates/agents/shadow-reviewer.md.j2`,
`skills/pairmode/scripts/bootstrap.py`.

Picked up now as part of era 004's Phase 119 goal of draining the CER backlog to zero unresolved
operational findings.

## Requires

- INFRA-358/INFRA-359 complete — they introduced the shadow-reviewer role and its agent-shell
  template, which sub-findings (1) and (2) correct.
- INFRA-365 complete — it closed the `Edit`/`Write` route into `.pairmode-suggestions.md` through
  `scope_guard.py`/`pre_tool_use.py`. This story closes the remaining `Bash` route.
- INFRA-366 complete — it routed the `OPERATOR-010-project.md` write through `_write_file`. This
  story hardens what that write emits, not how it is guarded.

## Ensures

1. `skills/pairmode/templates/agents/shadow-reviewer.md.j2` no longer grants `Bash`: the template's
   `tools:` list contains `Read` and does not contain `Bash`, and no other tool capable of writing
   files (`Write`, `Edit`, `NotebookEdit`) is added in its place.
   **Forbidden proxy:** prose in the template body telling the shadow reviewer not to use Bash while
   `Bash` remains in the `tools:` list — the assertion is on the declared grant, not on advisory text.
2. `.claude/agents/shadow-reviewer.md` exists in this repo and is byte-identical to what the
   project's own agent-sync step renders from the corrected template; re-running that sync produces
   no diff on the file.
   **Forbidden proxy:** a hand-written `.claude/agents/shadow-reviewer.md` that reads correctly but
   does not round-trip through the sync path — the assertion is on the re-sync being a no-op.
3. Bootstrapping with an `--operator-note` whose text contains a line consisting of `---`, a leading
   `#`, and YAML-special characters (`:`, `"`, a newline) produces an
   `OPERATOR-010-project.md` whose YAML frontmatter block still parses (e.g. via `yaml.safe_load` on
   the leading block) to the same field set and values as a blank-note run of the same bootstrap.
   **Forbidden proxy:** stripping or rejecting the offending characters so the file parses — the
   operator's note text must still be recoverable from the rendered file, only its placement/quoting
   made safe.
4. Blank-note and ordinary-note bootstrap behaviour is unchanged: a blank note still writes no
   extension content, and a plain-text note renders the same as before this story.
5. Full `tests/pairmode/` suite green.

## Instructions

1. Fix the template before syncing, so the rendered file inherits the corrected grant. In
   `skills/pairmode/templates/agents/shadow-reviewer.md.j2`, remove `Bash` from the `tools:` list,
   leaving `Read` (plus any non-write tool already present). The shadow reviewer's job is to read and
   suggest; the suggestion write is performed by the orchestrator/harness, not by the agent. Do not
   attempt to keep `Bash` and filter its command strings in `pre_tool_use.py` — removing the
   capability is the fix; a Bash-command parser is a new attack surface, not a guard.
2. Render `.claude/agents/shadow-reviewer.md` for this repo using the project's own agent-sync path
   (the same `sync-agents` step that produces the other files in `.claude/agents/`), not by hand.
   Verify the round-trip by running the sync a second time and confirming no diff.
3. In `skills/pairmode/scripts/bootstrap.py`, find where the `--operator-note` value is interpolated
   into `OPERATOR-010-project.md`. Determine which side of the frontmatter fence it lands on and fix
   accordingly:
   - if it lands in a YAML frontmatter field, serialise it with the YAML library already in use
     rather than string-interpolating it, so quoting/escaping is the serialiser's job;
   - if it lands in the markdown body, ensure the frontmatter block is emitted and closed
     independently of the note, so no line of the note can open or close a frontmatter fence.
   Either way, the note text must survive intact — do not sanitise by deletion.
4. Tests: extend `tests/pairmode/test_bootstrap.py` for Ensures 3-4 with an adversarial-note case
   (assert on `yaml.safe_load` of the rendered file's frontmatter block and on the note text being
   present in the file), plus a blank-note and plain-note regression case. For Ensures 1-2, add
   assertions in the existing agent-template/sync test module (create `tests/pairmode/` coverage
   there if the module does not already exist) that the rendered
   `.claude/agents/shadow-reviewer.md` declares `Read` and does not declare `Bash`. Assert on file
   contents, not on captured stdout.

Ideology note: sub-finding (2) is resolved by narrowing the capability rather than by adding
inspection logic to `pre_tool_use.py`, preserving the "hooks are thin relays only" constraint — a
hook that parses Bash command strings to decide whether a write is permitted is exactly the blocking
logic that constraint forbids.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_bootstrap.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: both green, including the new adversarial-operator-note test and the shadow-reviewer
tool-grant assertions.

## Out of scope

- Auditing every other agent template in `skills/pairmode/templates/agents/` for over-broad `Bash`
  grants. CER-163 names only the shadow reviewer; any further over-grant found while working here is
  a new CER, not an inline fix.
- Teaching `scope_guard.py`/`pre_tool_use.py` to inspect `Bash` command strings for writes to
  protected paths. Explicitly rejected above.
- Re-syncing downstream projects' already-installed `.claude/agents/shadow-reviewer.md`; they pick
  the corrected template up on their next plugin sync.
- Auditing `bootstrap.py`'s other free-text CLI values for the same escaping gap — only
  `--operator-note` is in scope.

## Scope widenings

| path | reason | widened_at |
| --- | --- | --- |
| tests/pairmode/test_harness_path_audit.py | new .claude/agents/shadow-reviewer.md entry (INFRA-376's sync-agents render) trips test_harness_path_audit.py's flex-harness-path allowlist; the allowlist row must be added alongside the shell | 2026-08-04T01:10:39Z |
