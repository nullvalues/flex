# anchor — Cold-Eyes Review (CER) Backlog

*Last updated: 2026-05-07*

This file is the structured triage log for findings from external cold-eyes reviews.
Each finding is assigned to one quadrant. Findings are not deleted — resolved findings
remain in place with a resolution note.

---

## Do Now

Urgent and important. Blocks correctness, security, or the next phase.

| ID | Finding | Source | Date | Phase |
|----|---------|--------|------|-------|


| — | *(none)* | — | — | — |


---

## Do Later

Important, not urgent. Quality improvements, architectural refinements.

| ID | Finding | Source | Date | Phase |
|----|---------|--------|------|-------|
| CER-001 | reconstruct.py `parse_ideology()` compat wrapper uses NamedTemporaryFile round-trip; on SIGKILL leaves ideology.md copy in /tmp. Fix: add `parse_ideology_text(text: str)` to ideology_parser.py to eliminate temp file. reconstruct.py:33-50 | Security audit cp12 | 2026-04-24 | 12 | **RESOLVED** Phase 13 |
| CER-002 | bootstrap.py has no `--yes`/`--no-input` flag; non-interactive callers must use `input="y\n" * N` workaround. Limits CI/scripted use. Add `--yes` flag that auto-confirms all prompts. | Intent review cp13 | 2026-04-25 | 13 | **RESOLVED** Phase 18 BOOTSTRAP-001 |
| CER-003 | cer.py and phase_new.py call Path(project_dir).resolve() but do not apply the len(parts) < 3 suspicious-path depth check that all other pairmode scripts apply. Inconsistent guard discipline. | Security audit cp14 | 2026-04-25 | 14 | **RESOLVED** Phase 17 INFRA-009 |
| CER-004 | lesson_review.py uses str.startswith() for path containment instead of Path.relative_to(); vulnerable to prefix collision on unusual paths. lesson_review.py:149 | Security audit cp14 | 2026-04-25 | 14 |
| CER-005 | phase_new.py missing len(parts) < 3 depth guard; resolve() is called but shallow-path check absent. All other pairmode entry points apply this guard consistently (bootstrap, audit, sync, score, reconstruct, story_new, era_new). phase_new.py:286 | Security audit cp15 | 2026-04-27 | 15 | **RESOLVED** Phase 17 INFRA-009 |
| CER-006 | validate_story_file rejects empty primary_files list, but story_new.py writes primary_files: [] by default. Every new story file fails its own validator until primary_files is filled in. Either allow empty list for draft stories, or omit the field entirely when empty. schema_validator.py, story_new.py | Intent review cp15 | 2026-04-27 | 15 | **RESOLVED** Phase 17 INFRA-008 |
| CER-007 | era_new.py writes unquoted id field (id: 001 — YAML integer) while bootstrap.py writes quoted id (id: "001" — YAML string). Current regex-based parsers tolerate both, but a proper YAML parser (e.g., python-frontmatter, PyYAML) would return integer 1 from era_new output. Fix era_new.py to write id: "{era_id}" (quoted string). era_new.py | Intent review cp15 | 2026-04-27 | 15 | **RESOLVED** Phase 17 INFRA-008 |
| CER-008 | permission_scope.py: if settings.local.json contains valid non-object JSON (e.g., a bare array), _read_json returns it as-is and the subsequent .setdefault() call raises AttributeError. Add a guard: if the parsed value is not a dict, treat it as {}. permission_scope.py:75 | Security audit cp16 | 2026-04-28 | 16 | **RESOLVED** Phase 17 INFRA-009 |
| CER-009 | hooks/stop.py, post_tool_use.py, session_end.py: PIPE_PATH defaults to hardcoded "/tmp/companion.pipe" and is then conditionally overridden by reading pipe_path from .companion/state.json (relative path). A crafted state.json could redirect pipe writes to an arbitrary path. No secrets in payloads; write silently drops on ENXIO if no FIFO reader. LOW severity. exit_plan_mode.py correctly uses tempfile.gettempdir(). | Security audit cp17 | 2026-04-30 | 17 |
| CER-010 | story_new.py --rail input is .upper()'d but not validated against a regex before being used in path construction. A caller passing --rail "../../../etc" constructs a path that escapes project_dir. No containment check present. MEDIUM severity. story_new.py:183-185 | Security audit cp18 | 2026-04-30 | 18 | **RESOLVED** Phase 25 INFRA-052 |
| CER-011 | era_new.py _slugify() neutralizes "/" and "." in --name before path construction, providing effective (but informal) traversal prevention. No formal resolve().relative_to() containment check present. LOW severity — _slugify() is correct but not a formal guard. era_new.py:25-31, 114-116 | Security audit cp18 | 2026-04-30 | 18 | **PARTIALLY RESOLVED** Phase 25 INFRA-052 — formal resolve().relative_to() containment check added; _slugify() approach retained alongside guard |
| CER-012 | pairmode_status.py: ANCHOR_ROOT computed as `Path(__file__).resolve().parent.parent.parent` resolves to `<repo>/skills/`, not the anchor repo root. The constructed `start_sidebar.sh` path becomes `<repo>/skills/skills/companion/scripts/start_sidebar.sh` — a file that does not exist. Must be `parent.parent.parent.parent` (four levels up). HIGH severity — surfaced to user as broken instructions. pairmode_status.py:33 | Story review cp20 INFRA-019 | 2026-05-01 | 20 | **RESOLVED** Phase 20 INFRA-020 |
| CER-013 | INFRA-033 propagation gap: fallback-policy pointer was added to anchor's own CLAUDE.build.md but NOT to the canonical `skills/pairmode/templates/CLAUDE.build.md.j2` template. Future bootstraps will not inherit the orchestrator-level pointer to the fallback policy (the inline `# fallback:` template comments and architecture.md subsection still propagate via separate paths). LOW severity — anchor's own dogfood is correct; downstream effect contained. | Phase 21 intent review | 2026-05-04 | 21 | **RESOLVED** Phase 22 INFRA-041 |
| CER-014 | docs/architecture.md "Reviewer-class agent tool restriction (build-loop safety)" subsection asserts the existence of a "pre-reviewer commit discipline (committing story files and running `git checkout -- lessons/` before the reviewer fires)" as one of two layers protecting the working tree, but neither CLAUDE.build.md (project) nor CLAUDE.build.md.j2 (template) encodes this discipline. Either add the discipline to CLAUDE.build.md.j2 (preserving the architecture claim) or trim the claim (preserving truth). MEDIUM severity — defense-in-depth claim rests on aspirational orchestrator behaviour; the load-bearing tool-restriction layer remains in force regardless. | Phase 21 security audit + intent review | 2026-05-04 | 21 | **RESOLVED** Phase 22 INFRA-042 |
| CER-015 | INFRA-030's CLAUDE.build.md examples hardcode `--phase N --rail RAIL` and `--attempt-number 1` placeholder literals; the orchestrator has no plumbed source for phase/rail at record time and no per-story retry counter state. The cp22 cleanup commit clarified that phase and rail are read from the current story file's frontmatter, but a small helper (e.g. `record_attempt.py --story-file <path>` that auto-extracts phase/rail from frontmatter) would close the typo surface. Without it, retry attempts may be miscounted as fresh attempts and rollup reports may see NULL phase/rail rows. MEDIUM severity. CLAUDE.build.md:82-94. | Phase 22 intent review | 2026-05-05 | 22 | **RESOLVED** Phase 25 INFRA-051 |
| CER-016 | effort_db.py `resolve_effort_db_path` accepts an absolute or relative `effort_db_path` from .companion/state.json and applies only `_depth_guard` (rejects paths with fewer than 3 parts after resolution) — it does not assert containment under project_dir. Same shape mirrored in record_attempt.py and pairmode_effort.py. Strictly weaker guard than permission_scope.py's resolve().relative_to() containment check. State.json is treated as project-owned (consistent with existing trust boundary), so this is informational, not exploitable. LOW severity. effort_db.py:115-139. | Phase 22 security audit | 2026-05-05 | 22 |
| CER-017 | bootstrap.py `_record_state` auto-enables `effort_tracking: true` on every pairmode-bootstrapped project unless the user explicitly sets the key first. No data leaves the host (sqlite is local), but the behaviour is documented in architecture.md only — not surfaced to the user during bootstrap. Consider an interactive prompt or a one-line bootstrap-summary note. LOW severity (transparency, not security). bootstrap.py:267-268. | Phase 22 security audit | 2026-05-05 | 22 |
| CER-018 | `lesson.py` CLI (`capture_lesson()` and its argparse entry point) does not accept the `value_framing` or `validation_phase` fields introduced by L012 (Phase 24). These fields exist in `lessons/lessons.json` and are documented in `architecture.md`, but can only be written by direct JSON append — not through the canonical CLI writer. Schema drift: data model ahead of the writer. LOW severity (usable via direct edit; append-only policy and lessons integrity check are unaffected). lesson.py: CLI definition. | Phase 24 intent review | 2026-05-07 | 24 |
| CER-019 | `pairmode_sync.py` `_get_project_name` returns `state["project_name"]` with only `.strip()` applied before rendering into agent-file frontmatter. A `project_name` containing embedded newlines or YAML control characters could inject extra frontmatter keys (e.g. additional `tools:` or `model:` lines) when `sync-agents` writes agent files. A malicious or malformed `.companion/state.json` could silently elevate reviewer-class tool permissions or override model assignments. Realistic threat is low (state.json is local and user-owned, same trust boundary as bootstrap.py:582), but this is the first script to write project_name into security-sensitive frontmatter fields. Fix: strip `\n`/`\r` from project_name or YAML-quote the value before template substitution. LOW severity. pairmode_sync.py:55-63. | Phase 25 security audit | 2026-05-07 | 25 | **RESOLVED** Phase 28 INFRA-057 |


---

## Do Much Later

Not urgent, marginal value. Style, cosmetics, speculative improvements.

| ID | Finding | Source | Date | Phase |
|----|---------|--------|------|-------|


| — | *(none)* | — | — | — |


---

## Do Never

Rejected findings. Record the rejection reason so it is not re-raised.

| ID | Finding | Source | Date | Phase | Resolution |
|----|---------|--------|------|-------|------------|


| — | *(none)* | — | — | — | — |

