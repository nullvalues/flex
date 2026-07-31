---
id: INFRA-304
rail: INFRA
title: Containment parity for spec_preflight; reviewer-template revert-assertion residue
status: complete
phase: "114"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/spec_preflight.py
touches:
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/skills/spec-writer/procedure.md
  - skills/pairmode/templates/agents/builder.md.j2
  - skills/pairmode/templates/agents/reviewer.md.j2
  - skills/pairmode/templates/agents/intent-reviewer.md.j2
  - skills/pairmode/templates/agents/loop-breaker.md.j2
  - skills/pairmode/templates/agents/security-auditor.md.j2
  - skills/pairmode/templates/agents/gate-worker.md.j2
  - skills/pairmode/templates/agents/reconstruction-agent.md.j2
  - tests/pairmode/test_spec_preflight.py
  - tests/pairmode/test_flex_build.py
  - tests/pairmode/test_templates.py
  - tests/pairmode/test_procedure_skills.py
  - docs/architecture.md
  - docs/cer/backlog.md
  - skills/pairmode/scripts/bootstrap.py
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Two build-loop residues from the era-002 fold are still open on `main`, and both are
small enough that leaving them open costs more than closing them.

**CER-064 (main-branch row, `docs/cer/backlog.md:106`) is half-open.** The row asks
for a containment guard before any `story_path` I/O in *both* `spec-preflight` entry
points. Only one of the two got it: `flex_build.cmd_spec_preflight` (`flex_build.py:2107`)
routes through `_story_path` (`flex_build.py:129-144`), which resolves the path and
`relative_to`-checks it against `docs/stories/`, raising `ValueError` on escape — added
by RESOLVER-015, not by a CER-064 story. `spec_preflight.py:128-129` still builds
`project_path / "docs" / "stories" / rail / f"{story_id}.md"` inline, splits the ID on
`-` with no shape validation, and calls `.exists()` / `read_text` on whatever comes out.
Neither entry point validates the `--story-id` *shape*, so `_story_path`'s containment
check is the only thing standing between a malformed ID and a read outside the stories
tree, and in `flex_build` that check surfaces as an uncaught `ValueError` traceback
rather than a clean refusal. The row's own file:line anchors are stale (it names a
`spec_preflight.py:_story_path_for` that has never existed and `flex_build.py:65-71,138-139`,
which is `_stamp_active_story` / `_read_story_frontmatter` today); the defect it
describes is nonetheless real and reproducible. Severity is LOW — the input is trusted
orchestrator output and the I/O is read-only — so the value here is *parity*, not
exploit closure: two entry points to the same scan must not disagree about what a
story ID is.

**CER-065 (main-branch row, `docs/cer/backlog.md:108`) is obsolete in its premise and
wrong in its prescribed fix.** The row asks a follow-up story to (a) drop `git clean -fd`
from `skills/pairmode/templates/agents/reviewer.md.j2` and (b) *invert* the guardrail
assertion in `tests/pairmode/test_templates.py` so the line's absence is asserted. Both
halves have been overtaken:

- (a) is already satisfied, but not by a CER-065 story. HARNESS-002 (`9acb9145`, dogfood
  flip) rewrote `reviewer.md.j2` into a 47-line thin shell whose whole body is "load
  `skills/pairmode/skills/reviewer/procedure.md`". `grep -c 'git ' skills/pairmode/templates/agents/reviewer.md.j2`
  is `0` — there is no revert block in the template at all, so the bootstrap
  re-introduction vector the row names (`bootstrap.py:86-92` still renders the template
  into `.claude/agents/reviewer.md` for every fresh project) now re-introduces nothing.
- (b) must **not** be done as written. The revert logic moved to
  `skills/pairmode/skills/reviewer/procedure.md:511-523`, which is already correct: it
  reverts only the story's declared `primary_files` + `touches` paths via
  `git checkout -- <path>` / `git clean -fd -- <path>`, and keeps the whole-tree
  `git checkout . && git clean -fd` form **deliberately**, as the fallback for a legacy
  story with no declared scope — mirroring the `git add -A` fallback on the commit path.
  `docs/architecture.md:1057-1060` documents exactly that pair. A blanket
  "`git clean -fd` must be absent" assertion would be a false statement about the
  system's intended behaviour.

The actual residue is a *dead test*: `TestReviewerAgentTemplate`
(`tests/pairmode/test_templates.py:554-620`) carries a class-level
`@pytest.mark.skip(reason="HARNESS-002: legacy agent .md.j2 templates retired (agents/reviewer.md.j2 deleted)")`.
The reason is factually wrong — the template was retired to a thin shell, not deleted;
it is on disk and still rendered by `bootstrap.py` — and behind that skip sit
`test_revert_on_fail`'s assertions (`:611-612`) that `git checkout .` and `git clean -fd`
appear in the rendered reviewer agent, which is now false. So the current revert contract
has **no** executing test anywhere: not over the template (skipped, and asserting the old
shape) and not over the procedure skill (`tests/pairmode/test_procedure_skills.py` covers
build-standards references and data-flow labels, not the revert block). That gap — not the
literal string — is what this story closes.

This story therefore does one small code fix with a test, and one honest disposition of a
stale backlog row, and annotates both rows rather than deleting them
(`docs/cer/backlog.md:6`).

## Recon

Verified by reading the files at `HEAD` on `main`. Line numbers are anchors for the
builder, not assertions to preserve.

| Anchor | What is there now |
|---|---|
| `spec_preflight.py:114-136` | `@click.command()` `spec_preflight(story_id, project_dir)`. Docstring: "Always exits 0." Builds `rail = story_id.split("-", 1)[0]` and `story_path = project_path / "docs" / "stories" / rail / f"{story_id}.md"` with no shape or containment check; missing file → stderr message + `sys.exit(0)`. |
| `spec_preflight.py:15` | `sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))` — the **plugin root**, not the scripts dir. Sibling modules are not importable by bare name from a module-level import today. |
| `spec_preflight.py:97-111` | `run_preflight(story_path, project_dir)` — pure, takes a `Path`, already `OSError`-guarded. Imported by `flex_build.cmd_spec_preflight`. Unchanged by this story. |
| `flex_build.py:122` | `_STORY_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*-\d{3}$")`. |
| `flex_build.py:129-144` | `_story_path(story_id, project_dir)` — `rail = story_id.split("-", 1)[0]`, resolve, `relative_to(stories_root)`, `raise ValueError(f"story ID escapes stories root: {story_id}")` on failure. Added by RESOLVER-015 (`5cd343ac`). 12 call sites. |
| `flex_build.py:535-545` | `generate_permissions_artifact` — the existing precedent for pairing `_STORY_ID_RE.match` with a containment check; raises `PermissionsCreateError(f"invalid story_id format: {story_id!r}")`. |
| `flex_build.py:2091-2114` | `cmd_spec_preflight` — docstring "Always exits 0"; calls `_story_path` at `:2107` with **no** `try/except ValueError`, so an escaping ID exits via traceback; missing file → `sys.exit(0)`; lazily `import spec_preflight as _sp` at `:2104`. |
| `flex_build.py:30-31` | `sys.path.insert(0, str(Path(__file__).parent))` — the scripts-dir insert this story mirrors. `reconstruct.py:14-15` and `pairmode_status.py:22-23` are the two-insert precedent. |
| `tests/pairmode/test_spec_preflight.py:91-102` | `test_run_preflight_cli_exits_0` — the only CLI-level test on the standalone entry point. |
| `tests/pairmode/test_flex_build.py:1131-1156` | `spec-preflight (INFRA-191)` block: clean story exits 0, missing story exits 0, `--help` mentions `--story-id`. `_run` is the module's `CliRunner` helper. |
| `skills/pairmode/templates/agents/reviewer.md.j2` | 47 lines, thin shell (HARNESS-002 + INFRA-241 model note). Contains no `git` command; body delegates to `skills/pairmode/skills/reviewer/procedure.md`. |
| `tests/pairmode/test_templates.py:554-620` | `TestReviewerAgentTemplate`, class-level `@pytest.mark.skip(reason="HARNESS-002: legacy agent .md.j2 templates retired (agents/reviewer.md.j2 deleted)")`; `setup_method` renders `agents/reviewer.md.j2` with `AGENT_CONTEXT`; `test_revert_on_fail` at `:610-612` asserts `git checkout .` and `git clean -fd` present. `TestLoopBreakerAgentTemplate` (`:628`) carries the same skip pattern. |
| `skills/pairmode/skills/reviewer/procedure.md:511-523` | "On FAIL, revert:" — declared-scope revert, with the whole-tree block at `:520-523` explicitly gated on "Only when both `primary_files` and `touches` are empty or absent (a legacy story with no declared scope)". |
| `docs/architecture.md:1055-1060` | Documents the commit/revert scoping correctly, but attributes both paths to "the reviewer template" — stale since HARNESS-002 moved them into the procedure skill. |
| `docs/architecture.md:71`, `:303-306` | Both state `spec-preflight` "always exits 0". |
| `skills/pairmode/skills/spec-writer/procedure.md:188-203` | Step 7 — the only caller of `spec-preflight` in any procedure or build-loop doc; says "it always exits 0 and never blocks". |
| `tests/pairmode/test_procedure_skills.py:17,32` | `REVIEWER_PROCEDURE` constant and the builder/reviewer `procedure_text` fixture — the natural home for a revert-contract assertion. |
| `docs/cer/backlog.md:106` / `:108` | The two main-branch rows (CER-064 renumbered from main CER-061; CER-065 renumbered from main CER-060 at the RELEASE-008 fold). The rows at `:24` / `:26` are the *harness* CER-064/CER-065 and are already RESOLVED — do not touch them. |

## Requires

- `skills/pairmode/scripts/spec_preflight.py` exposes `run_preflight`,
  `_extract_body_sections`, `_check_routes`, `_check_constants`, and the `click`
  command `spec_preflight` with `--story-id` / `--project-dir`.
- `skills/pairmode/scripts/flex_build.py` exposes `_STORY_ID_RE` and
  `_story_path(story_id, project_dir)` with its `ValueError`-on-escape contract, and
  `cmd_spec_preflight` registered as the `spec-preflight` subcommand.
- `skills/pairmode/templates/agents/reviewer.md.j2` exists and contains no `git`
  command (HARNESS-002 thin shell). If a rebase has restored a fat template, stop and
  report — this story's CER-065 disposition assumes the thin shell.
- `skills/pairmode/skills/reviewer/procedure.md` contains the declared-scope revert
  block with the legacy whole-tree fallback at "On FAIL, revert:".
- `docs/cer/backlog.md` contains **two** rows numbered `CER-064` and **two** numbered
  `CER-065` (fold renumbering). This story annotates only the rows whose Finding cell
  opens with `[Renumbered from main-branch CER-061 …]` (CER-064) and
  `[Renumbered from main-branch CER-060 …]` (CER-065). Verify by matching that opening
  bracket text, not by row order.
- Baseline: `uv run pytest tests/pairmode/` on a clean `main` checkout is green
  (4116 passed / 211 skipped). Inside a fresh story worktree,
  `tests/pairmode/test_observability_ui.py::test_ui_build_emits_dist_index_html` fails
  for environmental reasons (CER-090 — incomplete vendored `node_modules`). The fix is
  to rsync the payload from the main checkout; **never** run `pnpm install`. That
  failure is not caused by this story.
- No dependency on any phase-113 story. INFRA-296/297/302 also edit `flex_build.py`, but
  in unrelated regions (`_parse_frontmatter` consumers, table splitting,
  `cmd_create_story_worktree`). Keep this story's `flex_build.py` diff to the few lines
  named in `## Ensures` so the overlap stays trivially rebasable.


## Scope widenings

| path | reason | widened_at |
| --- | --- | --- |
| skills/pairmode/scripts/bootstrap.py | E13 fix requires a new pairmode_pkg_dir context var so agent templates can render absolute procedure pointers | 2026-07-30T19:15:42Z |

## Ensures

Numbered assertions; the reviewer verifies each independently from the diff and the
test run.

**E1. One story-path resolver, not two — and no third variant.**
`spec_preflight.spec_preflight` no longer constructs a story path from string parts.
It obtains the path from `flex_build`'s existing helpers via a **lazy, function-scoped**
import (`from flex_build import ...` inside the command body, mirroring
`flex_build.py:2104`'s lazy `import spec_preflight as _sp`, so the two modules never
import each other at module scope). `grep -c 'docs" / "stories"' skills/pairmode/scripts/spec_preflight.py`
prints `0`, and `grep -c 'split("-"' skills/pairmode/scripts/spec_preflight.py` prints `0`.
No copy of the rail-split, the `resolve()`/`relative_to` guard, or the story-ID regex is
added to `spec_preflight.py`.

**E2. A single validated resolver serves both entry points.**
`flex_build.py` gains one public helper immediately after `_story_path`:

```python
def story_path_checked(story_id: str, project_dir: Path) -> Path:
```

which (a) rejects a `story_id` that `_STORY_ID_RE` does not match with
`ValueError(f"invalid story ID: {story_id!r}")`, then (b) returns `_story_path(story_id, project_dir)`,
letting that function's existing `ValueError("story ID escapes stories root: …")`
propagate unchanged. `_story_path` itself is **not** modified, and the other 11
`_story_path` call sites are **not** rewired — this story does not widen validation
across commands it does not own. The regex is `_STORY_ID_RE`, imported/used in place, not
re-spelled.

**E3. Both entry points reject the same payload identically.**
`spec_preflight.spec_preflight` and `flex_build`'s `spec-preflight` subcommand both call
`story_path_checked`, both wrap it in `except ValueError as exc`, and both emit to
**stderr** the single line `spec-preflight: {exc}` and exit with code **2**. For each of
the payloads `../../../etc/passwd`, `INFRA-190/../../../../etc/passwd`, `../INFRA-190`,
`infra-190`, and `INFRA-19` the two entry points produce the **same** exit code and the
**same** stderr text, and neither performs any filesystem read of the payload path
(asserted by the absence of any warning output and by the message text). Exit code 2 is
chosen to match the sibling gate convention already in this CLI family: `check-stub`
"exits 2 with a clear error message when the story file cannot be found" (its `--help`
text), so 2 already means "the command could not run against the named story" rather
than "the check failed".

**E4. The informational contract is narrowed, not abandoned — and it is written down.**
Exit code 0 still means "the scan ran" (clean or with warnings) **and** still covers the
well-formed-but-missing story file case (`spec-preflight: story file not found: …` →
exit 0, both entry points, unchanged). Exit 2 is reserved for a malformed `--story-id`,
which no build-loop caller produces. All four places that state the old blanket contract
are corrected in the same story: both docstrings (`spec_preflight.py:123-126`,
`flex_build.py:2100-2103`), `docs/architecture.md:71`, `docs/architecture.md:303-306`, and
`skills/pairmode/skills/spec-writer/procedure.md`'s Step 7 sentence "it always exits 0 and
never blocks". Each new wording states the exit-2 case **and its reason** — an ID the scan
cannot resolve must not report as a clean scan (`docs/ideology.md` § "Never silently pass
contradictions") — rather than only the rule.

**E5. The pre-existing spec-preflight tests pass unmodified.**
`tests/pairmode/test_spec_preflight.py::test_run_preflight_cli_exits_0` and the three
cases in `tests/pairmode/test_flex_build.py:1131-1156` (clean story exits 0, missing story
exits 0, `--help` mentions `--story-id`) are not edited, weakened, or deleted. They are
the backward-compatibility contract E4 promises.

**E6. A parity test pins E3.**
A new test in `tests/pairmode/test_spec_preflight.py`, named for CER-064, is parametrised
over the five payloads of E3 and invokes **both** entry points (the standalone
`sp.spec_preflight` command and `flex_build`'s `spec-preflight` subcommand) through
`CliRunner`, asserting for each payload that the two results have equal `exit_code`
(`== 2`) and equal output text. A separate case asserts that a well-formed ID for a
non-existent story still exits 0 from both, so the test cannot pass by making everything
fail.

**E7. CER-065's template half is recorded as satisfied, and the dead skip reason is
corrected.** `tests/pairmode/test_templates.py`'s `TestReviewerAgentTemplate` keeps its
class-level skip, but the reason string is corrected to state what actually happened:
the template was **retired to a thin shell by HARNESS-002 and is still rendered by
`bootstrap.py`**, not deleted, and its assertions describe the pre-HARNESS-002 fat
template. The reason string names `INFRA-304`. `test_revert_on_fail`'s two assertions at
`:611-612` are **not** inverted and **not** individually rewritten — inverting them would
assert a false statement about the system, because `git clean -fd` legitimately survives
in `skills/pairmode/skills/reviewer/procedure.md`'s legacy fallback. `TestLoopBreakerAgentTemplate`'s
identical skip is left alone (see `## Out of scope`).

**E8. The current revert contract gains an executing test.**
A new test class in `tests/pairmode/test_procedure_skills.py` (unskipped, reading
`REVIEWER_PROCEDURE`) asserts all of:
- the declared-scope form is present: the text contains `git checkout -- <path>` and
  `git clean -fd -- <path>`;
- the whole-tree form `git checkout .` / `git clean -fd` is present **and** is preceded
  by the legacy gate — the substring `Only when both` and the phrase naming
  `primary_files` and `touches` appear between "On FAIL, revert:" and the whole-tree code
  fence, so a future edit that promotes the fallback to the default fails this test;
- the FAIL-CAUSE line format (`FAIL-CAUSE:`) still precedes the revert block.

A second new test renders `agents/reviewer.md.j2` (no skip) and asserts the rendered
output contains **no** `git ` command at all and does contain the pointer
`skills/pairmode/skills/reviewer/procedure.md` — pinning the thin-shell property that
makes CER-065's bootstrap re-introduction vector inert.

**E9. Architecture stops attributing the revert to the template.**
`docs/architecture.md:1055-1060` is edited in place (no new `##` heading) so the
commit/revert scoping paragraph names
`skills/pairmode/skills/reviewer/procedure.md` as the location of both paths, notes that
the agent template is a thin shell that only points at it (HARNESS-002), and states that
the whole-tree revert survives *as the declared-scope-absent fallback* with its reason.
The documented behaviour is unchanged — only its stated location and rationale.

**E10. Both backlog rows are annotated, and both annotations are honest.**
`docs/cer/backlog.md` is edited only in the two main-branch rows identified in
`## Requires`; neither row is deleted, moved, re-numbered, nor is its `Phase` cell
changed (`84` and `79` respectively).
- The **CER-064** row gains an
  `**INFRA-304 (Phase 114) — RESOLVED:**` note recording that both entry points now route
  through `story_path_checked` (shape validation + `_story_path` containment), that the
  guard on the `flex_build` side pre-dated this story (RESOLVER-015), that the escape now
  produces exit 2 with a message instead of a traceback, and that the row's original
  file:line anchors (`spec_preflight.py:_story_path_for`, `flex_build.py:65-71,138-139`)
  were stale — the corrected anchors are named.
- The **CER-065** row gains an `**INFRA-304 (Phase 114) — RESOLVED (premise corrected):**`
  note recording all four facts: (i) `reviewer.md.j2` carries no revert block since
  HARNESS-002, so the bootstrap re-introduction vector is inert; (ii) the row's prescribed
  fix (b) — inverting `test_templates.py`'s assertion to require `git clean -fd`'s absence
  — was **rejected**, with the reason: the whole-tree revert is the intentional
  legacy-scope fallback in `reviewer/procedure.md:511-523` and `docs/architecture.md`;
  (iii) the real residue was a class-level skip whose reason claimed the template was
  deleted, and a revert contract with no executing test; (iv) what replaced it (E7, E8).
  The row's stale line references (`reviewer.md.j2:237`, `test_templates.py:677-679`) are
  named as stale with the current anchors given.

**E11. No new persistent schema object, no new module, no new dependency.**
`schema_introduces: false` stands and phase 114's § Schema delivery table stays empty.
No file is created under `skills/pairmode/scripts/`; no third-party import is added;
`spec_preflight.py` gains at most one `sys.path` insert (the scripts dir, mirroring
`flex_build.py:31`) and one function-scoped import.

**E12. The suite is green.** `uv run pytest tests/pairmode/` (run **without** `-x`)
passes, except the CER-090 environmental failure named in `## Requires` when the run
happens inside a fresh worktree. State in the build result whether that failure appeared
and that it reproduces on clean `HEAD`.

**E13. (F7, AG-5 item 1) The agent-shell procedure pointer is verified before it
is touched — and fixed only if it fails.** The templates emit a bare relative
procedure path (`skills/pairmode/skills/<role>/procedure.md` —
`builder.md.j2:34`, `reviewer.md.j2:34`, `intent-reviewer.md.j2:33`,
`loop-breaker.md.j2:38`, `security-auditor.md.j2:33`; check
`gate-worker.md.j2` / `reconstruction-agent.md.j2` for equivalents) which, as
written, resolves in **no consuming repo** — a downstream worker's cwd has no
`skills/pairmode/` tree. The cold-eyes caveat (CER-122) is that plugin-skill
loading **may** resolve it at runtime. Order is mandatory:

1. **Verify first.** In one consuming repo (or a bootstrapped fixture),
   determine whether a spawned worker reading its rendered agent shell can
   actually reach the procedure file at that path (plugin-root resolution,
   skill expansion, or any other runtime mechanism). Record the method and
   the verbatim result in `## Evidence`.
2. **If it resolves:** change **nothing** in the templates for this item;
   the fix is one clarifying comment line in each affected template stating
   *why* the bare path works (naming the resolution mechanism), so the next
   cold-eyes pass doesn't re-flag it.
3. **If it does not resolve:** render the path absolute (or
   plugin-root-anchored) at bootstrap/sync time via the templates' existing
   context variables, in all affected templates, with a
   `test_templates.py` assertion that rendered output contains a resolvable
   path shape.

**The correct signal is the recorded resolution experiment; the forbidden
proxy is rewriting the paths "to be safe" with no experiment — an untested
render change to six worker contracts is exactly the class of regression this
phase exists to end.**

**E14. CER-122 is annotated honestly per the E13 outcome.** The row gains
`**RESOLVED Phase 114 — INFRA-304: <verified-resolves + comment | rendered
absolute>, evidence in INFRA-304 § Evidence.**` — matching what actually
happened, in place, no row deleted or moved.

## Instructions

You are the builder. Work only in this repository, inside your story worktree. Do not
create a git tag, do not push, and run no command against `/mnt/work/flex-harness`.

1. **`flex_build.py` — one new helper, nothing else** (E2). Add `story_path_checked`
   immediately after `_story_path` (`:144`), with a docstring that says *why* it exists:
   `spec-preflight` has two entry points and they must not disagree about what a story ID
   is (CER-064). Reuse `_STORY_ID_RE` and `_story_path`; do not re-implement either, and
   do not touch `_story_path`'s body or its other call sites. Then, in
   `cmd_spec_preflight` (`:2099-2114`), replace the `_story_path(...)` call with a
   `try`/`except ValueError` around `story_path_checked(...)` that echoes
   `f"spec-preflight: {exc}"` with `err=True` and `sys.exit(2)`. Leave the
   missing-file branch exactly as it is (`sys.exit(0)`). Update the docstring per E4.
   Keep the whole `flex_build.py` diff under ~25 lines — INFRA-296/297/302 also edit this
   file.

2. **`spec_preflight.py` — delete the inline construction** (E1, E3). Add
   `sys.path.insert(0, str(Path(__file__).parent))` next to the existing plugin-root
   insert at `:15` (two inserts is the established shape — see `reconstruct.py:14-15`),
   with a one-line comment saying it makes sibling modules importable when this file is
   run as a script. Inside the `spec_preflight` command body, do the import lazily:
   `from flex_build import story_path_checked  # noqa: PLC0415` — a module-level import
   would make the pair mutually importable at load time, since `flex_build` imports this
   module. Replace `rail = …` / `story_path = …` with the guarded call in the same
   `try`/`except ValueError` shape as step 1, producing the **byte-identical** message and
   exit code. Update the module docstring and the command docstring per E4.

3. **Do not "fix" the informational contract further.** `run_preflight` keeps its
   signature, its `OSError` guard, and its return type; the route/constant scanners are
   untouched; no new warning classes. This story changes how the path is obtained and
   nothing about what the scan reports.

4. **Docs** (E4, E9). Correct the two "always exits 0" statements in
   `docs/architecture.md` (`:71`, `:303-306`), the Step 7 sentence in
   `skills/pairmode/skills/spec-writer/procedure.md`, and the commit/revert paragraph at
   `docs/architecture.md:1055-1060`. Every edit carries its reason, not just its rule
   (`docs/ideology.md` § "rationale-bearing decisions over bare rules").

5. **CER-065 — dispose, do not invert** (E7, E8). Read
   `skills/pairmode/skills/reviewer/procedure.md:511-523` before touching any test. The
   whole-tree `git checkout . && git clean -fd` block there is **intentional**: it is the
   fallback for a legacy story with no declared `primary_files`/`touches`, and
   `docs/architecture.md:1057-1060` documents it as such. The backlog row's instruction to
   assert its absence was written when the revert lived in a fat agent template that no
   longer exists. So:
   - in `tests/pairmode/test_templates.py`, change **only** the class-level skip reason on
     `TestReviewerAgentTemplate` (E7). Do not edit `test_revert_on_fail`'s assertions, do
     not unskip the class, and do not delete it — the class documents the retired shape,
     and mass-pruning retired skipped classes is a separate concern
     (`TestLoopBreakerAgentTemplate` carries the identical pattern).
   - add the two new tests to `tests/pairmode/test_procedure_skills.py` (E8). That file
     already owns `REVIEWER_PROCEDURE` (`:17`); for the template-render test, import
     `jinja2` the same way `test_templates.py` does, or add a small local `render` helper —
     do not import across test modules.

6. **Tests** (E5, E6, E8).
   - `tests/pairmode/test_spec_preflight.py` — the CER-064-named parity test of E6.
     Invoke `flex_build`'s subcommand through its `CliRunner` in the same way
     `tests/pairmode/test_flex_build.py:1131-1156` does (import `flex_build` and invoke
     the `flex_build` group with `["spec-preflight", …]`), so the two entry points are
     compared by their real CLI surfaces, not by calling the helper twice. Assert equality
     of `exit_code` and of output text between the two, then assert the absolute values
     (`2`, message contains the offending ID) — equality alone would pass if both were
     broken the same way.
   - Do not edit any pre-existing case in `tests/pairmode/test_spec_preflight.py` or the
     `spec-preflight (INFRA-191)` block of `tests/pairmode/test_flex_build.py` (E5).

7. **Backlog** (E10). Append the two annotations to the *Finding* cell of the two
   main-branch rows, matching the `**INFRA-NNN (Phase N) — …:**` style already used by
   neighbouring resolved rows. Confirm you have the right rows by grepping for the
   `[Renumbered from main-branch CER-061` and `[Renumbered from main-branch CER-060`
   opening text; the same-numbered harness rows at `:24`/`:26` are already RESOLVED and
   must not be touched. Refresh nothing else in the file — the backlog truth pass is
   INFRA-310.

8. **Procedure-pointer verification (E13, E14) — verify FIRST, change only on
   failure.** Run the E13 resolution experiment before opening any template
   file; the experiment's outcome selects branch 2 (comment only) or branch 3
   (absolute render + test). Annotate CER-122 to match. This item lands last
   so its template diff (if any) cannot entangle the E8 revert-assertion work
   in the same files.

9. **Ideology note (Step 4a — resolved inline, no conflict).** Two entries shaped this
   spec. *"Never silently pass contradictions"* (no silent bypass permitted) is why E3/E4
   choose exit 2 over a silent exit 0 for an unresolvable story ID: a scan that cannot
   locate its subject must not report as clean, because a false clean is worse than a
   loud refusal. The same conviction is why E7/E10 refuse the backlog row's prescribed
   inversion and record *why* instead of quietly complying — a test asserting a false
   property of the system is a contradiction passed silently. *"Rationale-bearing
   decisions over bare rules"* is why every doc edit in step 4 states the reason for the
   narrowed contract, and why the corrected skip reason in E7 says what happened rather
   than just naming a story. The *"Python everywhere"* fingerprint is unaffected — stdlib
   plus the already-present `click`, no new dependency. Nothing here touches the
   hook–pipe–sidebar boundary.

## Tests

Run from the story worktree root. Targeted first:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_spec_preflight.py \
  tests/pairmode/test_flex_build.py \
  tests/pairmode/test_templates.py \
  tests/pairmode/test_procedure_skills.py \
  tests/pairmode/test_docs.py -q 2>&1 | tail -30
```

Then the full suite, **without `-x`** so a known failure cannot mask a new one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Machine-checkable assertions the reviewer may run directly:

```bash
grep -c 'docs" / "stories"' skills/pairmode/scripts/spec_preflight.py   # must print 0
grep -c 'split("-"' skills/pairmode/scripts/spec_preflight.py           # must print 0
grep -c 'story_path_checked' skills/pairmode/scripts/spec_preflight.py  # must be >= 1
grep -c 'story_path_checked' skills/pairmode/scripts/flex_build.py      # must be >= 2
grep -c 'git ' skills/pairmode/templates/agents/reviewer.md.j2          # must print 0
git diff --stat -- skills/pairmode/scripts/flex_build.py                # ~25 changed lines or fewer
```

Manual parity check (both lines must print the same text and the same exit code `2`):

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/spec_preflight.py \
  --story-id '../../../etc/passwd' --project-dir . ; echo "exit=$?"
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/flex_build.py \
  spec-preflight --story-id '../../../etc/passwd' --project-dir . ; echo "exit=$?"
```

Acceptance:

- the CER-064-named parity test (E6) and both new procedure/template tests (E8) pass;
- the pre-existing cases in `test_spec_preflight.py` and the `spec-preflight (INFRA-191)`
  block of `test_flex_build.py` pass **unmodified** (E5);
- `test_templates.py` collects the same number of skipped cases as before — the skip-reason
  edit must not unskip anything;
- the full suite is green except
  `test_observability_ui.py::test_ui_build_emits_dist_index_html` (CER-090); if it appears,
  state that it reproduces on clean `HEAD` and is unrelated, and that the worktree payload
  was repaired by rsync from the main checkout, never by `pnpm install`.

Documentation-only assertions (E9, E10) are verified by the reviewer from the diff.

Note for `spec-preflight`: `story_path_checked` does not exist in the codebase yet — it is
created by this story, so a preflight finding naming it is expected. `_STORY_ID_RE` and
`_story_path` do exist (`flex_build.py:122`, `:129`).

## Out of scope

- **A shared story-path module.** Four other call sites build
  `docs/stories/<RAIL>/<ID>.md` by hand — `story_resolver.py:63`,
  `subagent_transcript.py:1506`, `story_context.py:250`, and
  `flex_build.generate_permissions_artifact:538-545` (which duplicates the containment
  check inline). Extracting a stdlib-only `story_paths.py` and rewiring all of them is the
  right eventual shape, but it is a wide refactor across modules three phase-113 stories
  are already editing, and it would turn a LOW-severity parity fix into a rebase hazard.
  This story keeps `flex_build` as the single definition and makes `spec_preflight` a
  consumer; the wider extraction belongs in the backlog, not here.
- **Widening `story_path_checked` to the other 11 `_story_path` call sites.** Those
  commands have their own validation and error-reporting conventions (several already call
  `_STORY_ID_RE.match` themselves); changing them all is a behaviour change to commands
  this story does not own.
- **Making `spec-preflight` blocking.** It remains informational: warnings never change
  the exit code. Exit 2 is an input-validation refusal, not a gate verdict. Turning the
  scan into a gate would change the build loop's contract and is not asked for by either
  row.
- **Pruning retired skipped test classes.** `TestReviewerAgentTemplate`,
  `TestLoopBreakerAgentTemplate` and the `TestBuilderAgentTemplate` family all carry
  HARNESS-001/002 skips. Deleting them is a coherent cleanup, but doing it for one class
  and not its siblings is worse than leaving all three; propose it as a backlog item
  instead.
- **Changing the revert behaviour itself.** Neither the declared-scope revert nor its
  legacy whole-tree fallback is modified. This story adds a test for the contract and
  corrects where the docs say it lives; if the fallback should go, that is a reviewer
  procedure change with its own spec.
- **The other doc-currency rows.** CER-078/079/084/085/086/100/112 are INFRA-305's sweep;
  the only doc edits here are the ones this story's own code and disposition make false
  (E4, E9).
- **Backlog truth pass.** Only the two rows named in E10 are annotated. Enumerating and
  closing the remaining un-annotated rows, and refreshing the file's "Last updated:" line,
  is INFRA-310.

## Evidence

**E13 resolution experiment (run before any template was touched).**

Method: bootstrapped a fixture "consuming repo" from this checkout's own
`bootstrap.py`, then checked whether the rendered `.claude/agents/reviewer.md`'s
bare relative pointer (`skills/pairmode/skills/reviewer/procedure.md`) exists
relative to the fixture project's own directory tree — the same relation a
spawned worker's cwd (its per-story worktree) would have to a genuinely
separate downstream project.

```
$ uv run python skills/pairmode/scripts/bootstrap.py \
    --project-dir <scratch>/myapp --project-name myapp --stack Python \
    --what "test app" --why testing --build-command pytest --test-dir tests \
    --phase-title "Phase 1" --phase-goal goal --yes
  ...
  wrote: <scratch>/myapp/.claude/agents/reviewer.md
  ...

$ ls -la <scratch>/myapp/skills
ls: cannot access '<scratch>/myapp/skills': No such file or directory

$ cd <scratch>/myapp && test -f skills/pairmode/skills/reviewer/procedure.md \
    && echo RESOLVES || echo "DOES NOT RESOLVE (file not found relative to project cwd)"
DOES NOT RESOLVE (file not found relative to project cwd)
```

Supporting evidence that no other runtime mechanism substitutes for this at
render time: `bootstrap.py` and `pairmode_sync.py` never `shutil.copy`/vendor
the `skills/pairmode/` tree into a target project (`grep -rn "shutil\|copytree"
skills/pairmode/scripts/bootstrap.py skills/pairmode/scripts/sync.py
skills/pairmode/scripts/pairmode_sync.py` — no output). The only documented
plugin-root path-substitution mechanism in this codebase is
`${CLAUDE_PLUGIN_ROOT}`, and it is scoped exclusively to `hooks.json` command
strings (interpolated by the Claude Code hook runner before exec, per
`hook_view.py:203,258,269` and `hooks/hooks.json`); it does not apply to prose
paths inside an agent's rendered markdown body, which a subagent can only act
on via its own `Read` tool (which requires an absolute path).

**Verdict: does not resolve.** Branch 3 (E13 step 3) applies: the pointer is
now rendered absolute in all six affected templates (`builder`, `reviewer`,
`intent-reviewer`, `loop-breaker`, `security-auditor`, `gate-worker`), anchored
on the existing `pairmode_scripts_dir` context variable (already populated
identically by both `bootstrap.py` and `pairmode_sync.py` — no new context
variable was added, despite an initial `permissions-widen` grant for
`skills/pairmode/scripts/bootstrap.py` recorded in `## Scope widenings` above;
on finding the existing variable sufficient, `bootstrap.py` was left
unmodified). `reconstruction-agent.md.j2` was checked and carries no procedure
pointer at all — confirmed no equivalent, no change needed. A parametrised
test in `tests/pairmode/test_procedure_skills.py`
(`TestAgentShellProcedurePointerIsAbsolute`) pins the resolvable-absolute
shape for all six templates, plus an end-to-end check that the real
`pairmode_scripts_dir` this repo runs from resolves to the actual
`reviewer/procedure.md` file on disk.
