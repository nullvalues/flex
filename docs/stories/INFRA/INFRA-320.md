---
id: INFRA-320
rail: INFRA
title: "Mid-build scope relief: standing shared surfaces, audited permissions-widen, scope-implication preflight — hard block preserved"
status: draft
phase: "113"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/scope_guard.py
  - skills/pairmode/scripts/flex_build.py
touches:
  - skills/pairmode/scripts/spec_preflight.py
  - skills/pairmode/skills/builder/procedure.md
  - skills/pairmode/skills/reviewer/procedure.md
  - skills/pairmode/skills/spec-writer/procedure.md
  - tests/pairmode/test_scope_guard.py
  - tests/pairmode/test_pre_tool_use_scope_guard.py
  - tests/pairmode/test_flex_build.py
  - tests/pairmode/test_flex_build_permissions_create.py
  - tests/pairmode/test_flex_build_check_story_scope.py
  - tests/pairmode/test_flex_build_permissions_widen.py
  - tests/pairmode/test_spec_preflight.py
  - docs/architecture.md
  - docs/cer/backlog.md
  - docs/stories/INFRA/INFRA-320.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

**Pulled from CER-128** (`docs/cer/backlog.md`, operator-flagged 2026-07-29,
"scope friction"), a mid-phase addition to Phase 113 by operator direction rather
than from the era-004 closeout reconciliation.

`scope_guard.check_path` is a flat allow-list matcher: `candidate in
allowed_paths` (`scope_guard.py:149-151`), where `allowed_paths` is the exact,
literal concatenation of the story's `primary_files` + `touches` frontmatter plus
the story's own spec path (`flex_build.py:577-584`). There are no globs, no
prefixes, and — this is the defect — **no path from a deny back to an allow that
does not require a human**. When a build discovers mid-loop that it must touch a
file nobody predicted at spec time, the only remedies are: an operator hand-edits
`touches:` and re-runs `permissions-create`, or the operator toggles auto-mode off
so the permission prompt surfaces, or the builder falls back to shell writes. All
three are human interventions in what is otherwise a headless loop.

**The observed downstream consequence is worse than the stall itself.** On a
fresh 0.3.0-bootstrapped repo, teams respond to the friction by over-declaring
`touches:` at spec time to pre-empt later prompts — which converts a scope
*guard* into a scope *fiction*: a story whose declared surface is wide enough that
the guard no longer says anything about it. The observed churn shape is CERs filed
per build loop and then pulled back into existing specs.

**Same-session evidence inside flex itself.** INFRA-297 and INFRA-298 both edited
`docs/cer/backlog.md` without declaring it, and both drew reviewer MEDIUM findings
under § 9 RAIL SCOPE (`reviewer/procedure.md:292-305`) for an undeclared file —
self-disclosed as a spec-preflight gap. Meanwhile INFRA-319's spec-writer was
scope-blocked writing planning docs and fell back to shell writes (the CER-087
workaround). Three interventions, one week, one repo, on files that essentially
every story touches.

**Why the existing mechanisms do not cover this.** 0.3.0's spec-elaboration step
(`spec-writer/procedure.md` Step 7 → `spec-preflight`) only helps an
under-specified stub *before* the build starts; it scans for unverifiable route
and constant references (`spec_preflight.py:63-95`) and says nothing about
`touches:`. `check-story-scope` (`flex_build.py::cmd_check_story_scope`) does
apply two touches-implication heuristics — test co-location and `*.j2`/rendered
pair — but is not reachable from the spec-writer's self-check and has no rule for
paths the story body itself names. And `spec_exception.py` — flex's existing
override-audit-trail module — is reachable only through the companion sidebar's
interactive keypress (`sidebar.py:1283-1320`), so a headless builder subagent
cannot use it.

**The shape of the fix.** Three layers, none of which weakens the guard for an
arbitrary path:

- **A — standing shared surfaces.** A short, central, *exact-path* list of
  surfaces nearly every story legitimately touches, declared once in the
  enforcement module rather than copy-pasted into every story's `touches:`. This
  is not a new idea in the codebase — `generate_permissions_artifact` already
  appends the story's own spec path unconditionally (`flex_build.py:583-584`);
  this story generalises that one hard-coded case into a named, tested,
  documented constant.
- **B — an audited widening command.** `permissions-widen` turns the manual
  hand-edit into one self-service CLI call that writes the declaration into the
  story's `touches:` (so the spec stays the single source of truth), records the
  reason and timestamp in the story body, regenerates the artifact, and leaves a
  trail the reviewer is required to check. **This is not an auto-widen** — the
  builder must name the path and state a reason; nothing is granted implicitly by
  attempting a write.
- **C — prediction at spec time.** A third `check-story-scope` rule that warns
  when the story's own `## Ensures`/`## Instructions` name a repo path that is
  absent from the declared scope, wired into the spec-writer's Step 7 self-check
  so it actually fires on new specs.

The hard block itself is untouched. Protected paths stay fail-closed, out-of-root
stays denied, and an undeclared code file still blocks until someone declares it —
the change is that declaring it is now one auditable command instead of an
operator round-trip.

## Requires

Re-verified against the working tree at spec time (2026-07-29, `main` @
`2586ad4c`). A builder finding an anchor moved should re-locate by symbol name,
not line number, and note the drift in its report.

- `scope_guard.py::check_path` (`:44-151`) — the decision function. Its final
  comparison is exact string membership: `if candidate in allowed_paths: return
  True, "allowed"` (`:149-151`). `candidate` is `_strip_worktree_prefix(normalise
  (file_path, project), story_id)` (`:113-115`). No glob, no prefix matching.
- `scope_guard.py::PROTECTED_GLOBS` (`:31-39`) — `hooks/**`,
  `.claude-plugin/**`, `skills/seed/**`, `skills/companion/**`, `lessons/**`,
  `.claude/settings.json`, `.claude/settings.local.json`. Every protected branch
  in `check_path` (`:96-108`, `:121-147`) fails **closed**.
- `scope_guard.py::_read_allowed_paths` (`:579-597`) — returns
  `(paths, status)` with status `missing` / `malformed` / `ok`; on `ok` it
  normalises each entry through `_norm_str`.
- `scope_guard.py` is **stdlib-only** and is imported by `hooks/pre_tool_use.py`
  (`:187-192`) inside a bare `try/except → sys.exit(0)`. No third-party import may
  be added to it, and no code path in it may become slow (the hook is on every
  Edit/Write).
- `flex_build.py::generate_permissions_artifact` (`:525-612`) — reads
  frontmatter, refuses non-list `primary_files`/`touches` (INFRA-296 B1,
  `:570-575`), dedupes into `allowed`, appends `story_spec_rel` when absent
  (`:583-584`), short-circuits when `existing_allowed == allowed` (`:602-603`),
  and writes `{story_id, story_spec, allowed_paths, generated_at}` (`:606-611`).
  Raises `PermissionsCreateError`, never `sys.exit`, so non-CLI callers
  (`create-story-worktree`) can handle it.
- `flex_build.py::cmd_check_story_scope` — two rules today (test co-location;
  `*.j2`/rendered pair), always exits 0, prints nothing when clean. Tested by
  `tests/pairmode/test_flex_build_check_story_scope.py`.
- `flex_build.py` already imports from `scope_guard` (`:74`:
  `from scope_guard import entry_is_fresh, STATE_STORY_MAX_AGE_HOURS`) — the
  import direction for § A's shared constant already exists and must be reused,
  not reversed.
- `spec_preflight.py::run_preflight` (`:97-111`) returns a list of warning
  strings; the CLI always exits 0. `flex_build.py:2117-2136` wraps it as
  `spec-preflight`.
- `spec-writer/procedure.md` Step 7 (`:188-200`) invokes `flex_build.py
  spec-preflight --story-id <scalar>` as the spec-writer's self-check and states
  it is informational and never blocks.
- `reviewer/procedure.md` § 9 RAIL SCOPE (`:292-305`) is what fires MEDIUM on an
  undeclared file; § 7 PROTECTED FILES (`:275-283`) is the protected-path item.
- `builder/procedure.md` § *Before writing anything* item 3 (`:71-79`) is the only
  place the builder is told what to do about a scope obstruction today, and it
  covers **protected** files only (`BUILDER BLOCKED — …`). There is no instruction
  for an ordinary undeclared file.
- `docs/architecture.md:68` is the `scope_guard.py` inventory line;
  `:352-383` is the "Permission pre-write — two layers" narrative;
  `:744-770` is the INFRA-253/INFRA-255 fail-closed + input-normalisation
  contract. `:3675+` is § Protected files — `docs/architecture.md` and
  `docs/cer/backlog.md` are **not** on that list, which is what makes § A's
  standing allowance legitimate.
- Baseline: `main`'s suite is green — 4116 passed, 211 skipped. A
  `test_observability_ui` failure inside a story worktree is the known CER-090
  vendored-payload gap: fix by `rsync`-ing the payload from the main checkout,
  **never** by `pnpm install`.

**Sibling-story coordination inside Phase 113.** INFRA-299 is unmerged at spec
time and its permissions artifact
(`docs/phases/permissions/INFRA-299.json`) declares `docs/architecture.md` and
`docs/cer/backlog.md`. This story edits both. On `docs/cer/backlog.md`, edit
**only** the CER-128 row — INFRA-299 owns rows CER-105, CER-106 and CER-113 and
must not be touched. In `docs/architecture.md`, this story's edits land at the
scope-enforcement material (`:68`, `:352-383`, `:744-770`); INFRA-299's land at
the recording/attribution material. If INFRA-299 has already merged when this
builds, re-read both files before editing. INFRA-299 also edits
`hooks/pre_tool_use.py`; **this story must not** — see § Out of scope.

## Ensures

### A — standing shared surfaces: declared once, centrally, never per story

**A1.** `scope_guard.py` gains a module-level constant — `STANDING_SURFACES`
(name indicative) — holding the exact repo-relative paths every story may write
without declaring them:

| path | why it is standing |
|---|---|
| `docs/cer/backlog.md` | any story may file or annotate a CER; the reviewer checklist and closeout process both assume it |
| `docs/architecture.md` | reviewer § 11 DOCUMENTATION CURRENCY makes a doc update mandatory for code that any doc describes — the obligation and the permission must not disagree |

It is a `tuple[str, ...]` (immutable), stdlib-only, and carries a docstring
stating the admission rule: **a path may join this list only if it is (i) a
documentation or record surface, never code; (ii) not matched by
`PROTECTED_GLOBS`; and (iii) one that a majority of stories legitimately touch.**
Adding a code path to it is a CRITICAL review finding.

**A2.** `scope_guard.py` gains a pure helper — `standing_paths_for(story_id,
story_phase=None)` (name indicative) — returning `STANDING_SURFACES` plus the two
**per-story derived** surfaces:

- `docs/stories/<RAIL>/<story_id>.md` — the story's own spec (today hard-coded in
  `flex_build.py:583-584`; this becomes its single definition);
- `docs/phases/phase-<phase>.md` — **only** when a phase key is supplied, and only
  that one phase doc. No other phase doc is ever standing.

The helper is **total**: a malformed story ID or an absent phase key returns the
static surfaces alone and never raises. It performs no file I/O.

**A3.** `check_path`'s `status == "ok"` branch admits a candidate that is in the
standing set for the resolved story, with the reason string
`"allowed (standing shared surface)"` — distinguishable from the plain
`"allowed"` so the decision is legible in a hook transcript. The phase key used
comes from the permissions artifact (§ A5), never from re-reading the story file
inside the hook — `check_path` must not gain a frontmatter parse.

**A4.** The standing allowance **never** overrides a protected path. A path
matched by `PROTECTED_GLOBS` is denied even if it were somehow listed in
`STANDING_SURFACES`; the protected check runs first and its result is final. A
test asserts this against a synthetic standing entry pointing at a protected glob.

**A5.** `generate_permissions_artifact` writes standing surfaces into the artifact
as a **separate top-level key** — `standing_paths` — not merged into
`allowed_paths`, and also records `story_phase` (from frontmatter `phase:`, or
omitted when absent). `allowed_paths` therefore continues to mean *exactly what
this story declared*, which is what makes reviewer § 9 still able to tell a
declaration from a standing allowance. The `story_spec_rel` append at `:583-584`
is removed from `allowed_paths` and delivered through `standing_paths` instead.

**A6.** The `existing_allowed == allowed` short-circuit (`:602-603`) is widened to
compare the full computed payload minus `generated_at` — otherwise a change to
`standing_paths` or `story_phase` alone would leave a stale artifact on disk with
an unchanged `allowed_paths`. A test pins that changing only `phase:` in
frontmatter rewrites the artifact.

**A7.** `check_path` computes the effective set as `allowed_paths ∪ standing`,
where `standing` is the artifact's `standing_paths` when present and well-formed,
**union** `standing_paths_for(...)` computed live. The live union is what makes an
artifact generated by an older flex still grant the standing surfaces — a
migration-free upgrade. A malformed or absent `standing_paths` key degrades to the
live computation, never to an exception; the `"malformed"` artifact status branch
(`:129-136`) is unchanged and still fail-closed for protected paths.

**A8.** No behaviour change for any path outside the standing set. The
`"not in story scope for <story_id>: <path>"` deny (`:151`) is byte-identical for
an undeclared code file, and `_normalise`/`_out_of_root_decision` are untouched.

### B — `permissions-widen`: an audited mid-build declaration, not an auto-widen

**B1.** `flex_build.py` gains a `permissions-widen` command:

```
permissions-widen STORY_ID --path <repo-relative path> --reason <text>
                  [--project-dir .] [--dry-run]
```

`--path` and `--reason` are both **required**. A missing or empty `--reason` is a
usage error (exit 2), not a defaulted value — an untraceable widening is the thing
this command exists to prevent.

**B2.** Refusal policy — the command exits non-zero and writes **nothing** when:

- `STORY_ID` does not match `_STORY_ID_RE`, or its spec file does not exist;
- `--path` resolves outside the project root (same containment semantics
  `_safe_path`/`_normalise` already use — resolve, then `relative_to`, never a
  string `startswith`);
- `--path` is matched by `scope_guard.PROTECTED_GLOBS`. The message names the
  matched glob and points at the `BUILDER BLOCKED` protected-file path in
  `builder/procedure.md`. **A protected path is never widenable by this command
  under any flag.**

**B3.** On success the command performs exactly three writes, in this order,
and is atomic in intent — if the frontmatter edit fails, nothing else is written:

1. appends `--path` to the story file's `touches:` **block-style** YAML list
   (never flow style — INFRA-296 made flow style a parse refusal), preserving
   existing entries and their order, and creating the `touches:` key immediately
   after `primary_files:` when absent;
2. appends a row to a `## Scope widenings` table in the story body (created after
   `## Requires` when absent) with columns `path | reason | widened_at` (UTC,
   `%Y-%m-%dT%H:%M:%SZ`, matching `generated_at`'s format);
3. calls `generate_permissions_artifact` so the artifact and the frontmatter can
   never disagree — the frontmatter stays the single source of truth and the
   artifact stays derived.

**B4.** Idempotent: widening an already-declared path (present in `primary_files`
or `touches`) is a **no-op success** — one line of output saying so, no duplicate
`touches:` entry, no second `## Scope widenings` row, exit 0.

**B5.** `--dry-run` echoes exactly what each of the three writes would do and
changes no byte of any file. Asserted by byte-comparing the story file and the
artifact before and after.

**B6.** A path that is already **standing** (§ A) is reported as such and is a
no-op success — the command does not add `docs/cer/backlog.md` to a story's
`touches:`, because doing so would re-introduce exactly the per-story
copy-pasting § A removes.

**B7.** `permissions-widen` never touches `.claude/settings.json`,
`.claude/settings.local.json`, `state.json`, or any file other than the named
story spec and that story's permissions artifact.

### C — prediction at spec time

**C1.** `cmd_check_story_scope` gains **rule 3 — body-named paths**: it extracts
repo-relative path tokens from the story's `## Ensures` and `## Instructions`
sections (tokens inside inline code or fenced code, matching a path-like shape
with a known source or doc extension), keeps only those that **exist in the
working tree**, and warns for each that is absent from `primary_files ∪ touches ∪
standing_paths_for(...)`. Non-existent paths are silently dropped — a spec may
legitimately name a file it is about to create, and warning on those would make
the rule noise.

**C2.** The rule reuses `scope_guard.standing_paths_for` rather than
re-listing the standing surfaces, so a path added to `STANDING_SURFACES` stops
producing spec-time warnings in the same commit that stops producing deny
decisions. One definition, two consumers.

**C3.** `check-story-scope` still **always exits 0** and still prints nothing when
clean. Rules 1 and 2 are byte-identical in output.

**C4.** `spec_preflight.run_preflight` appends the `check-story-scope` warnings to
its returned list, prefixed so their origin is legible (e.g.
`scope: docs/architecture.md is named in Ensures but is not in declared scope`).
The `spec-preflight` CLI still always exits 0. This is what makes the spec-writer's
Step 7 self-check actually surface a `touches:` gap on a story it has just written
— the gap INFRA-297/298 self-disclosed.

**C5.** `spec-writer/procedure.md` Step 7 is amended to say the scan now also
reports declared-scope gaps and that the spec-writer should fix `touches:` before
returning, rather than treating every warning as route/constant noise.

### D — the loop knows what to do

**D1.** `builder/procedure.md` § *Before writing anything* gains an item covering
the **ordinary undeclared file** case, which today has no instruction: when a
write is denied with `not in story scope for <story_id>`, the builder runs
`permissions-widen` with a one-sentence reason and continues — it does **not**
stop, does **not** shell out around the guard, and does **not** silently drop the
change. The existing protected-file `BUILDER BLOCKED` instruction is unchanged and
explicitly named as the case that still stops.

**D2.** The builder return format gains a line for widenings performed (path +
reason, or "none"), so the orchestrator sees a widening without reading the story
file.

**D3.** `reviewer/procedure.md` § 9 RAIL SCOPE gains a scope-widening item: an
undeclared file in the diff that carries a `## Scope widenings` row is **not** a
MEDIUM finding — the reviewer instead judges whether the recorded reason is
legitimate, flagging MEDIUM when the reason is absent, empty or boilerplate, and
HIGH when the widening reaches a different rail's primary domain (the existing
HIGH rail-violation rule still applies to a widened path). An undeclared file with
**no** widening row remains MEDIUM exactly as today. A standing surface is never a
finding.

**D4.** § 7 PROTECTED FILES is unchanged: `permissions-widen` cannot reach a
protected path (§ B2), so a protected path in a diff is still an unexplained
modification unless the story states a reason.

### E — documentation

**E1.** `docs/architecture.md:68`'s `scope_guard.py` inventory line is extended
with the standing-surface layer, naming `STANDING_SURFACES`,
`standing_paths_for`, the "documentation/record surfaces only, never code, never
protected" admission rule, and the artifact-`standing_paths` ∪ live-computation
degradation (§ A7).

**E2.** The § *Permission pre-write* narrative (`:352-383`) records the third
layer: `permissions-widen` as the audited mid-build declaration path, its refusal
policy, and the invariant that **the frontmatter remains the source of truth and
the artifact remains derived** — a widening that edited only the artifact would
make the story spec lie.

**E3.** The INFRA-253 fail-closed material (`:744-770`) is amended to state
explicitly that standing surfaces do not weaken the protected-path contract, and
that no path in `PROTECTED_GLOBS` is reachable by any standing or widening
mechanism.

**E4.** The rejected directions (§ Out of scope R1–R5) are recorded in the
architecture note with their reasons — particularly R1 (auto-widen on deny) and R2
(`permissionDecision: "ask"`), because both read as the obvious fix and both
destroy the property the guard exists to hold.

**E5.** No new persistent schema object is introduced; `schema_introduces` stays
`false` and Phase 113's § Schema delivery table owes this story no row. The
permissions artifact is a pre-existing derived file, not a new persistent store,
and its human management surface is the story frontmatter it is derived from.

### F — backlog

**F1.** The CER-128 row in `docs/cer/backlog.md` is annotated
`**RESOLVED INFRA-320 (Phase 113)**` with a short statement of what landed:
standing shared surfaces (A), `permissions-widen` (B), spec-time prediction (C),
loop-procedure wiring (D).

**F2.** The annotation states plainly that the hard block was **preserved** — no
auto-widen, protected paths unreachable — so the record cannot be read as "the
guard was relaxed".

**F3.** No other backlog row is edited and no row is deleted. `git diff
docs/cer/backlog.md` touches exactly one row. Rows CER-105, CER-106 and CER-113
are owned by the unmerged INFRA-299 branch and must be left byte-identical.

### G — tests and suite

**G1.** New tests exist for each of: A3 (standing surface allowed, reason string),
A4 (protected beats standing), A5 (artifact key separation), A6 (phase-only change
rewrites the artifact), A7 (legacy artifact with no `standing_paths` still grants
them; malformed `standing_paths` degrades without raising), A8 (undeclared code
file still denied, deny string unchanged), B2 (each refusal arm), B3 (block-style
`touches:` append + `## Scope widenings` row + artifact regenerated), B4
(idempotent), B5 (dry run writes nothing), B6 (standing path is a no-op), C1
(warns on a body-named existing undeclared path; silent on a not-yet-created one),
C3 (still exits 0, clean output unchanged), C4 (preflight surfaces the scope
warning).

**G2.** `tests/pairmode/test_pre_tool_use_scope_guard.py` gains a case asserting
the hook allows a standing surface end-to-end and still blocks an undeclared code
file — the guard is only real at the hook boundary.

**G3.** Existing `test_scope_guard.py`,
`test_flex_build_permissions_create.py` and `test_flex_build_check_story_scope.py`
tests are **retargeted, not deleted**. In particular
`test_permissions_create_includes_story_spec_in_allowed_paths` asserts today's
`:583-584` behaviour that § A5 moves — update it to assert the spec path now
arrives via `standing_paths`, with a docstring line naming INFRA-320.

**G4.** Full suite green, run **once without `-x`** so a pre-existing failure
cannot mask a new one, against the `main` baseline of 4116 passed / 211 skipped
plus this story's additions.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Build in order **A → B → C → D → E → F**, running the focused suites after each of
A, B and C, then the full suite without `-x` at the end.

**A — scope_guard.** Put `STANDING_SURFACES` and `standing_paths_for` in
`scope_guard.py`, next to `PROTECTED_GLOBS`, so the permission model reads as one
block: what is never writable, and what is always writable. Keep the module
stdlib-only and keep both additions pure — `standing_paths_for` must not touch the
filesystem, because `check_path` runs on every Edit/Write through the hook. In
`check_path`, add the standing union **inside** the `status == "ok"` branch, after
the protected check, never before it; the protected branches at `:96-108` and
`:121-147` must be reachable and unchanged. `flex_build.py` already imports from
`scope_guard` (`:74`) — extend that import; do not create a reverse dependency.

**A5/A6 in `generate_permissions_artifact`.** Remove the `story_spec_rel` append
into `allowed`, add `standing_paths` and `story_phase` to the payload, and widen
the unchanged-short-circuit to compare the payload minus `generated_at`. Read the
phase key with the same frontmatter reader already in use; treat an absent or
non-string `phase:` as "no phase doc is standing", never as an error.

**B — `permissions-widen`.** Model the command on `cmd_permissions_create`
(`:632-649`): resolve `--project-dir`, do the work in a helper that raises
`PermissionsCreateError` (or a sibling error type) so a future non-CLI caller can
use it, and let the command translate that to `echo(err=True)` + `sys.exit(1)`.
Reuse `scope_guard._is_protected` for B2's protected refusal rather than
re-listing the globs. Do the frontmatter edit textually against the `touches:`
block — do **not** round-trip the whole file through a YAML dumper, which would
reformat unrelated frontmatter and lose comments.

**C — check-story-scope + preflight.** Add rule 3 alongside the existing two, in
the same shape (build the normalised scope set once, warn per miss). The
path-token regex should be conservative: require a `/` and a known extension
(`.py`, `.md`, `.json`, `.j2`, `.ts`, `.tsx`, `.js`, `.jsx`, `.toml`, `.yaml`,
`.yml`) and require the file to exist. Then have `run_preflight` call
`check-story-scope`'s **pure warning function** — extract one if the logic
currently lives inside the Click command — never shell out to the CLI from inside
another Python process.

**D — procedures.** Three small doc edits. Keep the builder instruction short and
imperative; the builder reads it cold at the top of every story.

**E/F — docs and backlog.** Amend the three architecture anchors named in E1–E4
and annotate exactly the CER-128 row. Append the annotation to the existing
Finding cell as sibling rows do; do not reword the original finding text. Do not
touch rows CER-105/106/113 (§ Requires, INFRA-299 coordination).

**Ideology-alignment note (Step 4a, resolved inline).** `docs/ideology.md`
§ Accepted constraints — *"Never silently pass contradictions"* — reads directly on
§ B1's required `--reason` and on § D3: a widening must leave a legible trace and
a reviewer obligation, never a quiet grant. § Core convictions —
*"rationale-bearing decisions over bare rules"* — is why § A1 ships an admission
rule in the constant's docstring rather than a bare tuple, and why § E4 records the
rejected directions: a later reader who does not know why auto-widen was rejected
will propose it again.

## Tests

```bash
# Focused — the guard and its hook boundary
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_scope_guard.py \
  tests/pairmode/test_pre_tool_use_scope_guard.py -q

# Focused — artifact generation, widening, scope prediction
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_flex_build_permissions_create.py \
  tests/pairmode/test_flex_build_permissions_widen.py \
  tests/pairmode/test_flex_build_check_story_scope.py \
  tests/pairmode/test_spec_preflight.py -q

# Full suite — once, WITHOUT -x, so a pre-existing failure cannot mask a new one
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

**Acceptance:**

- Both focused runs green, including every new test named in G1/G2.
- Full suite green against the `main` baseline of 4116 passed / 211 skipped plus
  this story's new tests. No new failures.
- A `test_observability_ui` failure is worktree-only (CER-090). Fix by `rsync`-ing
  the vendored payload from the main checkout; never `pnpm install`. State in the
  build report that it does not reproduce on a clean `main` checkout.

**New tests required** (names indicative):

- `test_standing_surface_allowed_with_distinct_reason`
- `test_protected_glob_denied_even_when_listed_standing`
- `test_undeclared_code_file_still_denied_with_unchanged_message`
- `test_permissions_artifact_separates_allowed_from_standing_paths`
- `test_permissions_artifact_rewritten_when_only_phase_changes`
- `test_legacy_artifact_without_standing_paths_still_grants_them`
- `test_malformed_standing_paths_degrades_to_live_computation`
- `test_hook_allows_standing_surface_and_blocks_undeclared_code_file`
- `test_permissions_widen_requires_reason`
- `test_permissions_widen_refuses_protected_path_naming_the_glob`
- `test_permissions_widen_refuses_out_of_root_path`
- `test_permissions_widen_appends_block_style_touches_and_widening_row`
- `test_permissions_widen_regenerates_artifact`
- `test_permissions_widen_is_idempotent_for_declared_path`
- `test_permissions_widen_noop_for_standing_path`
- `test_permissions_widen_dry_run_writes_nothing`
- `test_check_story_scope_warns_on_body_named_undeclared_existing_path`
- `test_check_story_scope_silent_on_body_named_nonexistent_path`
- `test_check_story_scope_silent_on_standing_surface`
- `test_spec_preflight_surfaces_scope_warnings`

## Out of scope

- **R1 — auto-widening on deny (implicit grant on first attempted write).
  Rejected, not deferred.** It converts the allow-list into a log: any path a
  builder attempts becomes allowed, which is precisely the property `check_path`
  exists to deny. § B keeps the grant explicit — a named path and a stated reason —
  which costs one CLI call and preserves the guarantee.
- **R2 — turning the deny into a `hookSpecificOutput.permissionDecision: "ask"`
  prompt instead of a block. Rejected.** A prompt *is* the human intervention
  CER-128 reports; it moves the friction rather than removing it, and it makes the
  guard's outcome depend on operator attention rather than on the declared scope.
- **R3 — routing the widening audit trail through `spec_exception.py` /
  the companion sidebar pipe. Rejected.** `record_spec_exception` is reached only
  through an interactive sidebar keypress (`sidebar.py:1283-1320`); a headless
  builder subagent cannot invoke it, which is the exact population that needs the
  path. The trail therefore lives in the story file, which every reviewer already
  reads.
- **R4 — glob or prefix matching in `allowed_paths`. Rejected for this story.**
  `docs/**` in a `touches:` list would silently re-create the over-declaration
  CER-128 describes. Exact paths keep the declaration meaningful. If a directory
  grant is ever wanted it should be a separate, named mechanism with its own
  review rule, not a quiet change to the matcher.
- **R5 — a warn-only / advisory scope mode. Rejected.** A guard that only warns is
  a guard nobody reads.
- **Editing `hooks/pre_tool_use.py`.** The hook's Edit/Write dispatch
  (`:186-198`) already calls `scope_guard.check_path` and needs no change for any
  of A–D; INFRA-299 (same phase, unmerged) owns that file. Only the hook's
  **test** file is touched (§ G2).
- **Widening `PROTECTED_GLOBS` or changing any protected-path branch.** The
  fail-closed contract (INFRA-253) is preserved verbatim.
- **`harness_owned_prefixes` / out-of-root writes (CER-087).** The spec-writer's
  shell-write workaround named in § Context is the *symptom* that motivated this
  story, but its cause is out-of-root containment, which is a separate mechanism
  with its own row. Planning-doc writes from inside the project root are fixed
  here; writes outside the project root are not.
- **Retro-fitting `touches:` across existing story specs.** Standing surfaces make
  the existing over-declarations harmless, not wrong; no historical spec is
  rewritten.
- **A management UI for permissions artifacts.** The artifact is derived from
  story frontmatter (§ E5); its management surface is the story file, and
  `permissions-widen` is the write path.
