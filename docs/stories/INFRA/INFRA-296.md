---
id: INFRA-296
rail: INFRA
title: Flow-style frontmatter sequences: parse or refuse; never leave a half-created worktree
status: draft
phase: "113"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/schema_validator.py
  - skills/pairmode/scripts/flex_build.py
touches:
  - tests/pairmode/test_schema_validator.py
  - tests/pairmode/test_flex_build.py
  - tests/pairmode/test_flex_build_permissions_create.py
  - docs/architecture.md
  - docs/cer/backlog.md
  - docs/stories/INFRA/INFRA-296.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

`schema_validator._parse_frontmatter` is the project's canonical frontmatter
parser (`docs/architecture.md:1156-1159` makes importing it a non-negotiable —
ten sibling scripts do). It implements a deliberately minimal YAML subset:
`key: value` scalars and `  - item` block sequences, with one shared
inline-comment rule. It has no notion of a **flow sequence** — YAML's
single-line `key: [a, b]` form. A story written that way does not fail; it
parses to the *string* `"[a, b]"`, and the failure surfaces far downstream:

```
primary_files: [a.html, b.html]   →   fm["primary_files"] == "[a.html, b.html]"
```

`generate_permissions_artifact` then evaluates `for p in primary_files + touches`
(`flex_build.py:561`) with a `str` on the left and a `list` on the right and
raises `TypeError: can only concatenate str (not "list") to str`. That
`TypeError` is **not** a `PermissionsCreateError`, so the `except
PermissionsCreateError` at `flex_build.py:3562` does not catch it — it escapes
`cmd_create_story_worktree` as an unhandled traceback *after* `git worktree add`
has already succeeded (`flex_build.py:3536-3546`). The operator is left with a
worktree directory and a `pairmode/<ID>` branch that both exist, no permissions
artifact, and a command that never printed a path. Because
`.pairmode-worktrees/<ID>/` **is** the in-flight claim (`claimed_story_ids`,
INFRA-280), the story is now pinned as claimed; the next
`create-story-worktree` for it exits 1 with `error: branch already exists`, and
recovery requires a manual `discard-story-worktree`. That is exactly what
CER-115 reports from RELEASE-066 E12.

Two things are wrong, and this story fixes both:

1. **The parser fails open.** A value it does not understand is silently
   returned as a scalar. The ideology's first accepted constraint — *never
   silently pass contradictions* — reads directly on this: a parser that
   answers "string" when the truth is "I cannot parse this" gives false
   confidence to every one of its ten callers. Flow style is legitimate,
   widely-written YAML; the parser should either understand it or refuse it,
   and today it does neither.

2. **The worktree command is not atomic.** `create-story-worktree` performs a
   durable, claim-establishing side effect (`git worktree add -b`) and then
   runs two best-effort follow-ups. When the second one dies, nothing walks the
   first one back. `_teardown_story_worktree` (INFRA-286, `flex_build.py:215`)
   already exists and is exactly the right primitive — the create path simply
   never learned to call it.

This is the first story of Phase 113 because the parser sits under every rail:
`story_resolver`, `permission_scope`, `story_context`, `record_attempt`,
`index_integrity`, `model_selector`, `story_update`, `phase_new` and
`flex_build` all read frontmatter through it. It also carries a **campaign
edge**: the in-flight phase-106 migration campaign runs its CLIs from
`/mnt/work/flex-harness`, not from this checkout, so the fix is invisible to
the campaign until it is promoted to that channel (§ Ensures D, modelled on
INFRA-293's F3/F4).

## Requires

- **Phase 112 is complete and merged.** This story's worktree is cut from a
  `HEAD` containing `INFRA-293`/`INFRA-294`/`INFRA-295` (`git log --oneline -1`
  at spec time: `610af2a3`).
- `skills/pairmode/scripts/schema_validator.py` defines, at module level:
  `_YAML_SCALAR_RE` (`:25`), `_YAML_LIST_ITEM_RE` (`:26`),
  `_strip_inline_comment` (`:34`) and `_parse_frontmatter` (`:77`). Inside
  `_parse_frontmatter`'s scalar branch, the **CER-092 ordering comment**
  occupies `:116-120` and is immediately followed by
  `value_raw = _strip_inline_comment(scalar_m.group(2))` (`:121`) and
  `if value_raw in ("", "[]") or value_raw is None:` (`:123`). The scalar
  fall-through assigns `result[key] = value_raw` (`:133`).
- `validate_story_file` checks `isinstance(fm["primary_files"], list)` in both
  arms of its `status in ("draft", "backlog")` branch
  (`schema_validator.py:205-206` and `:208-209` — the two checks are textually
  identical) and applies **no** list check to `touches` at all.
- `skills/pairmode/scripts/flex_build.py` defines `_STORY_ID_RE` (`:122`),
  `_read_story_frontmatter` (`:147`), `_worktree_paths` (`:203`),
  `_teardown_story_worktree` (`:215`), `_residue_lines` (`:250`),
  `PermissionsCreateError` (`:520`) and `generate_permissions_artifact`
  (`:524`), whose concatenation site is `for p in primary_files + touches:`
  (`:561`).
- `cmd_create_story_worktree` (`:3504`) calls `_stamp_active_story` inside a
  `try/except Exception` that warns (`:3556-3559`) and then
  `generate_permissions_artifact` inside a `try/except PermissionsCreateError`
  that **also only warns** (`:3560-3563`), before echoing the worktree path
  (`:3565`).
- `tests/pairmode/test_flex_build_permissions_create.py` exists with the
  module-level helper `_make_story(tmp_path, story_id, primary_files=None,
  touches=None)` (`:20`) and the CER-092 regression tests
  `test_permissions_artifact_fresh_stub_does_not_raise` (`:277`) and
  `test_permissions_artifact_legacy_buggy_touches_line_does_not_raise`
  (`:298`). `tests/pairmode/test_flex_build.py` contains
  `class TestStoryWorktreeLifecycle` and the helpers `_run`, `_init_git_repo`,
  `_git`, `_commit_in`. `tests/pairmode/test_schema_validator.py` is a flat
  function-per-test module.
- **Suite baseline, measured on `610af2a3` in the main checkout on 2026-07-29:**
  `uv run pytest tests/pairmode/ -q` → `4116 passed, 211 skipped` in ~166 s.
  There is **no** known failing test on main. (The closeout plan's "known
  `test_observability_ui` failure" does not reproduce here — that file passes
  37/37 on main. It is a *worktree-only* symptom of the incomplete vendored
  `node_modules` payload, CER-090; see § Tests.)
- No hook script imports `schema_validator` or `_parse_frontmatter`
  (`grep -n '_parse_frontmatter\|schema_validator' hooks/*.py` → no output).
  This is load-bearing for § Ensures A7's fail-closed decision and must be
  re-verified before building.

## Ensures

Grouped by item. Every assertion is checkable from the diff, by running the
command given, or by running the named test. § Ensures D is the one deliberate
exception and states its own verification path.

### A — the parser understands flow sequences, and refuses what it cannot parse

**A1. A named flow-sequence parser exists.** `schema_validator.py` defines a
module-level `_parse_flow_sequence(value_raw: str) -> list[str] | None`. It
returns `None` when `value_raw` does not begin with `[` (i.e. "not a flow
sequence, not my business"), a `list[str]` when `value_raw` is a well-formed
single-line flow sequence, and raises `FrontmatterError` otherwise. Its
docstring states the fail-closed rule and cites `CER-115`.
(`_parse_flow_sequence` and `FrontmatterError` do not exist in the tree today;
`spec-preflight` flagging them as unverifiable is expected and intentional —
this story creates them.)

**A2. `FrontmatterError` is a public, `ValueError`-derived exception.**
`schema_validator.FrontmatterError` subclasses `ValueError`. The subclassing is
deliberate and must be commented: several existing callers already funnel
parse problems through `ValueError` (`model_selector.py:446` raises
`ValueError` for missing frontmatter) or through a bare `except Exception`
(`flex_build.py:546-548`, `flex_build.py:2004-2008`, `model_selector.py:401-405`),
so an existing loud handler stays loud and no caller silently swallows it as an
unrelated type.

**A3. Well-formed flow sequences parse to lists.** `_parse_frontmatter` routes
every non-empty scalar value through `_parse_flow_sequence` **after**
`_strip_inline_comment` and **after** the existing `value_raw in ("", "[]")`
branch, assigning the returned list to `result[key]` when it is not `None`.
These inputs produce these outputs (one test case each):

| frontmatter line | parsed value |
|---|---|
| `primary_files: [a.html, b.html]` | `["a.html", "b.html"]` |
| `primary_files: [a.html]` | `["a.html"]` |
| `touches: [ "a.html" , 'b/c.html' ]` | `["a.html", "b/c.html"]` |
| `touches: [a.html, b.html]  # note` | `["a.html", "b.html"]` |
| `touches: [a.html, ]` | `["a.html"]` |
| `touches: [a.html,, b.html]` | `["a.html", "b.html"]` |

Elements are split on top-level commas, then stripped of surrounding
whitespace, then of one matching pair of surrounding `"` or `'`; empty elements
are dropped.

**A4. The `[]` branch is untouched and its ordering is re-proven.** The
`value_raw in ("", "[]") or value_raw is None` test and the CER-092 ordering
comment above it (`schema_validator.py:116-123`) are byte-identical in the
diff. `touches: []`, bare `touches:`, and `touches:  # note` each still parse
to `[]`, pinned by three assertions in `tests/pairmode/test_schema_validator.py`
that name CER-092 in their test names or docstrings. A test asserting the
comment block is still present (`grep` for
`comment strip must` in the source) is acceptable but not required; the three
behavioural assertions are.

**A5. Nested structures are refused, not half-parsed.** A value that begins
with `[` and contains a further `[`, `]` (other than the terminating one) or
`{` raises `FrontmatterError`. `_parse_flow_sequence` does not implement
nesting, and must not silently discard it.

**A6. Malformed flow sequences raise, naming key and value.**
`_parse_frontmatter` propagates `FrontmatterError` (it does **not** catch it)
for a value that begins with `[` and is not well-formed. The exception message
contains the key name and the offending raw value. Cases pinned by test:
`primary_files: [a, b` (unbalanced open), `touches: [a, b]]` (trailing junk
after the close), `touches: [a, [b]]` (nested, per A5). This is the "do not
fail open" decision CER-115 asks for, taken at the parser rather than at
`validate_story_file`, because `generate_permissions_artifact` — the crash site
— never calls `validate_story_file`.

**A7. A value that does not begin with `[` is byte-identical to today.**
`_parse_flow_sequence` returns `None` immediately unless
`value_raw.startswith("[")`, so a `]`-containing title, a value with commas, a
quoted scalar and a numeric-looking value are all unchanged. Pinned by tests
for `title: Fix the [thing], loudly` (→ the string, unchanged),
`title: "a, b"` (→ `a, b`), `phase: "113"` (→ `113`). A single regression here
would break every consumer of the parser, which is why the guard is a
`startswith` and not a regex over the whole value.

**A8. No existing `test_schema_validator.py` test is renamed, weakened or
deleted.** The file's existing tests all pass unchanged.

### B — `generate_permissions_artifact` never raises a bare `TypeError`

**B1. Types are checked before the concatenation.**
`generate_permissions_artifact` validates that both `fm.get("primary_files")`
and `fm.get("touches")`, when present and not falsy, are `list` instances
**before** `for p in primary_files + touches:` (`flex_build.py:561`). A
non-list value raises `PermissionsCreateError` whose message names the
offending key, the observed type, and the story spec path. A test constructs a
story file whose `primary_files` is a plain string and asserts
`pytest.raises(PermissionsCreateError)` with the key name in `str(exc.value)`.

**B2. `TypeError` cannot escape the function.** A test that drives
`generate_permissions_artifact` against a story file containing
`primary_files: [a.html, b.html]` asserts it **succeeds** (A3 made it a list)
and, separately, a test against a story whose frontmatter is malformed
(`primary_files: [a, b`) asserts `PermissionsCreateError` — never
`TypeError`, never `FrontmatterError` — because
`_read_story_frontmatter`'s caller already wraps parse failures
(`flex_build.py:545-548`).

**B3. The parse-failure message names the story file.**
`generate_permissions_artifact`'s existing `raise PermissionsCreateError(f"failed
to parse frontmatter: {exc}")` (`flex_build.py:546-548`) is extended so the
message also contains the story spec path (`docs/stories/<RAIL>/<ID>.md`).
Asserted by the B2 malformed-frontmatter test.

**B4. `cmd_check_story_scope` behaves identically.** The second
`_read_story_frontmatter` consumer (`flex_build.py:2004-2011`) is not edited;
its existing `except Exception` already converts a `FrontmatterError` into
`check-story-scope: failed to parse frontmatter: …` and `sys.exit(1)`. A test
pins that a malformed-frontmatter story makes `check-story-scope` exit 1 with
that prefix and no traceback.

**B5. The duplicated `primary_files` list check is not "cleaned up".**
`schema_validator.py:205-206` and `:208-209` stay as they are. They are
textually identical in both branches, which looks redundant, but collapsing
them is a separate refactor with its own regression surface and is out of scope
(§ Out of scope). Add a one-line comment noting the duplication is known and
deliberate for now.

### C — `create-story-worktree` is all-or-nothing

**C1. A permissions failure tears the worktree down and exits non-zero.** In
`cmd_create_story_worktree`, the `except PermissionsCreateError` block
(`flex_build.py:3560-3563`) no longer merely warns. It:
echoes `error: failed to generate permissions for <story_id>: <exc>` to stderr;
calls `_teardown_story_worktree(project_path, story_id)`; echoes any residue
via `_residue_lines(story_id, residue)` to stderr; and `sys.exit(1)`. It does
**not** echo the worktree path to stdout.

**C2. The change of severity is deliberate and commented.** The comment above
the block states why a missing permissions artifact is fatal where a failed
`current_story` stamp is not: the artifact **is** the Layer 1 allow-list
`scope_guard.py` reads (`docs/architecture.md:310-325`), so a worktree without
one is a worktree in which every scoped write is unenforced — handing that to a
builder is worse than handing back an error. This is a behaviour change from
INFRA-238's best-effort wording and must be recorded in `docs/architecture.md`
(E1).

**C3. `_stamp_active_story` stays a warning.** The `try/except Exception`
around `_stamp_active_story` (`flex_build.py:3555-3559`) is unchanged: a
missing stamp degrades scope resolution but leaves the artifact-based
enforcement intact, and INFRA-281's story-keyed `current_stories` tolerates it.
Do not "unify" the two handlers — the asymmetry is the point and needs the
comment saying so.

**C4. Git state is byte-identical across a failed create.** A test captures
`git worktree list --porcelain` and `git branch --list 'pairmode/*'` before and
after a `create-story-worktree` invocation for a story whose frontmatter is
malformed, and asserts both outputs are unchanged, that the exit code is `1`,
that stderr names the story spec path, that
`.pairmode-worktrees/<ID>/` does not exist, and that stdout is empty (no path
printed).

**C5. A second attempt after the failure succeeds.** The same test, after
repairing the story's frontmatter to block style, re-runs
`create-story-worktree` and asserts exit `0` and a printed path — i.e. the
failure left no residue requiring a manual `discard-story-worktree`. This is
the operator-visible symptom CER-115 actually reports.

**C6. Flow-style frontmatter works end to end.** A test creates a story whose
frontmatter is `primary_files: [skills/pairmode/scripts/a.py, docs/architecture.md]`
and `touches: [tests/pairmode/test_a.py]`, runs `create-story-worktree`,
asserts exit `0`, and asserts `docs/phases/permissions/<ID>.json`'s
`allowed_paths` contains all three declared paths **plus** the story spec path,
in declaration order.

**C7. The success path is otherwise unchanged.** Every test in
`tests/pairmode/test_flex_build.py::TestStoryWorktreeLifecycle` passes under its
original name. `tests/pairmode/test_cli_surface_freeze.py` passes with no edit:
no new subcommand, option or exit code is introduced; the only exit codes
`create-story-worktree` produces remain `0` and `1`.

### D — channel promotion (operator-run, post-merge)

The phase-106 campaign runs its CLIs from `/mnt/work/flex-harness`
(`docs/harness-cutover-runbook.md:84-85`, `:121`, `:139`), so this fix does not
reach the campaign by landing on `main`. This item follows the INFRA-293 F3/F4
pattern (`docs/phases/phase-112.md:177-185`).

**D1 (operator-run, post-merge, before the next campaign proving cycle).**
After this story merges to `main`, the change is promoted to
`/mnt/work/flex-harness` by an **ff-only** merge, and the promotion is verified
from the channel — not from this checkout:

```bash
# promote
git -C /mnt/work/flex-harness merge --ff-only <main-sha>

# verify the parser on the channel
PATH=$HOME/.local/bin:$PATH uv run python -c "
import sys; sys.path.insert(0, '/mnt/work/flex-harness/skills/pairmode/scripts')
from schema_validator import _parse_frontmatter, FrontmatterError
print(_parse_frontmatter('---\nid: X-001\nprimary_files: [a.md, b.md]\n---\n'))
try:
    _parse_frontmatter('---\nid: X-001\nprimary_files: [a, b\n---\n')
except FrontmatterError as e:
    print('refused:', e)
"
```

The first line must print a dict whose `primary_files` is `['a.md', 'b.md']`;
the second must print a `refused:` line. Both outputs are pasted into the
record.

**D2. The result is recorded in the phase doc's CP-113 cold-eyes checklist**
(orchestrator-filled, per project convention) with the date it was run, the
promoted SHA, and both command outputs. **Phase 113 cannot be checkpointed with
D1 unrun.** If a campaign proving cycle (RELEASE-068 or later) is dispatched
before D1 is run, that cycle inherits the CER-115 defect — record that as a
FAIL of this item, not as a skip, and do not retro-fit the record afterwards.

**D3. D1/D2 are not builder work.** They are the operator's post-merge step and
the CP-113 gate. The builder states in its `BUILD-RESULT` reason that D1 remains
outstanding, so it is not lost between the merge and the checkpoint.

### E — the record

**E1. The architecture doc states the supported subset and the fail-closed
rule.** `docs/architecture.md`'s **Inline-comment rule (minimal YAML subset)**
passage (≈ `:1161-1170`) is followed by a short paragraph — no new `##`-level
heading — recording that (a) single-line flow sequences `key: [a, b]` are
parsed into lists, (b) nesting is not supported and a value that opens with `[`
but is not a well-formed flat flow sequence raises `FrontmatterError` rather
than degrading to a string, and (c) the rationale: the parser has ten callers
and a silently-wrong type surfaces as a `TypeError` in whichever of them
happens to concatenate first (CER-115). The passage cites `INFRA-296, CER-115`.

**E2. The permissions/worktree severity change is documented.**
`docs/architecture.md`'s Layer 1 paragraph (`:312-325`) records that a
`PermissionsCreateError` during `create-story-worktree` is now fatal and tears
the worktree down (INFRA-296), while a failed `current_story` stamp remains a
warning, and gives the reason from C2. The historical INFRA-238 sentence is
extended, not deleted.

**E3. CER-115 carries a RESOLVED note.** `docs/cer/backlog.md`'s `CER-115` row
(`:188`) gains a bolded `**RESOLVED Phase 113 — INFRA-296 …**` note appended to
its Finding cell, naming both halves of the fix (flow-sequence parsing with a
fail-closed refusal; teardown-and-exit-1 on a permissions failure during
create). It must not claim that the parser now supports general YAML — it
supports one more flat form and refuses the rest loudly. The row is not
deleted or moved (`docs/cer/backlog.md:6-7`).

### F — cross-cutting

**F1. No other module is edited.** The diff contains no change to
`permission_scope.py`, `story_resolver.py`, `story_context.py`,
`record_attempt.py`, `index_integrity.py`, `story_update.py`, `phase_new.py`,
`model_selector.py`, `scope_guard.py`, any hook, or any template. Their
exposure to `FrontmatterError` is deliberate and argued in § Out of scope.

**F2. `schema_introduces` stays `false`.** No new persistent state; no
management-surface row is owed in `docs/phases/phase-113.md` § Schema delivery.

**F3. The full test suite is green**, run once **without `-x`**
(`tests/pairmode/`), against the § Requires baseline of `4116 passed, 211
skipped`. The new tests raise the passed count; the skipped count must not
rise. If any test fails, verify it reproduces on clean `HEAD` **in the same
worktree** before attributing it elsewhere, and say so explicitly in the build
result.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Build in order A → B → C → E, running the suite after A and after C. E is prose
and should be written last, against what actually shipped.

**0. Re-read before you write.** The line numbers in this spec are anchors, not
coordinates. Read, as they exist *now*:
`skills/pairmode/scripts/schema_validator.py` lines 20-140 (the regexes,
`_strip_inline_comment`, and the whole of `_parse_frontmatter`);
`skills/pairmode/scripts/flex_build.py` `generate_permissions_artifact`
(≈ `:524-600`), `_teardown_story_worktree`/`_residue_lines` (≈ `:215-270`) and
`cmd_create_story_worktree` (≈ `:3504-3566`). Re-run the two § Requires
verification greps (no hook imports the parser; the CER-092 comment is intact)
before touching anything.

**1. (A) The parser.** Add `FrontmatterError(ValueError)` near the top of
`schema_validator.py`, beside the regex constants, with a docstring giving A2's
reason for the base class. Add `_parse_flow_sequence` next to
`_strip_inline_comment`. Shape:

```python
def _parse_flow_sequence(value_raw: str) -> list[str] | None:
    """Parse a single-line YAML flow sequence into a list of strings.

    Returns None when *value_raw* is not a flow sequence at all (it does not
    begin with "["), so the caller falls through to its existing scalar
    handling unchanged. Raises FrontmatterError when it begins with "[" but
    is not a well-formed *flat* flow sequence — nesting is not supported, and
    guessing is worse than refusing (CER-115): the parser has ten callers and
    a silently-wrong type surfaces as a TypeError in whichever of them
    concatenates first.
    """
```

Insert its call in `_parse_frontmatter`'s scalar branch **after** the
`value_raw in ("", "[]")` test, in the `else:` arm, immediately before
`result[key] = value_raw`. Do **not** move, reword or reorder the CER-092
comment block or the `_strip_inline_comment` call above it — that ordering is
itself a fixed bug (A4), and `[]` must keep reaching the empty-list branch
rather than the new parser.

Element splitting: split the inner text on `,`, strip whitespace, strip one
matching pair of surrounding quotes, drop empties. There is no escaping rule
and none is being invented — a path containing a literal comma is not
expressible in flow style and must be written in block style; say so in the
docstring.

**2. (B) The permissions guard.** Add the `isinstance` checks immediately
before `flex_build.py:561`'s concatenation, raising `PermissionsCreateError`
with key, observed type and story path. Extend the existing parse-failure
message (`:546-548`) to include the story path. Leave
`cmd_check_story_scope`'s copy of the pattern (`:2010-2022`) alone — it is
already guarded, and B4 only pins that.

**3. (C) The worktree.** Rewrite the `except PermissionsCreateError` block per
C1, reusing `_teardown_story_worktree` and `_residue_lines` — do not open-code
`git worktree remove` / `git branch -D`; INFRA-286 extracted that function
precisely so there is one implementation. Write C2's comment **before** you
write the code: if you cannot state plainly why this failure is fatal and the
stamp failure is not, the change is wrong. Do not add a new subcommand, option,
flag or exit code, and do not touch `merge-story-worktree` or
`discard-story-worktree`.

**4. Tests.**

- `tests/pairmode/test_schema_validator.py` — add A3's six parse cases, A4's
  three CER-092 re-assertions, A5's nesting refusal, A6's three malformed
  cases (`pytest.raises(FrontmatterError)`, asserting the key name appears in
  the message), A7's three unchanged-scalar cases, and one assertion that
  `FrontmatterError` is a subclass of `ValueError`. Follow the file's flat
  function-per-test style; do not introduce a class.
- `tests/pairmode/test_flex_build_permissions_create.py` — add B1, B2 and B3.
  Reuse the module-level `_make_story` helper (`:20`); if it cannot express a
  raw frontmatter body, add a sibling helper rather than changing `_make_story`'s
  signature (existing tests depend on it).
- `tests/pairmode/test_flex_build.py` — add a new class
  `TestCreateStoryWorktreeAtomicity` alongside `TestStoryWorktreeLifecycle`
  rather than growing the existing one, covering C4, C5, C6 and B4. Use the
  file's existing `_init_git_repo` / `_commit_in` / `_git` / `_run` fixtures.
  C4's before/after comparison must capture both `git worktree list
  --porcelain` and `git branch --list 'pairmode/*'` and compare the strings.

**5. (E) The prose.** Write E1 and E2 against the shipped code, then E3's CER
row note. For CER-115, resist overclaiming: the note says "one more flat form,
plus a loud refusal", never "the parser now handles YAML".

**6. Sequencing note — INFRA-302 (phase 114).** INFRA-302 will later add
optional `worktree_provision` symlinking to **the same function**,
`cmd_create_story_worktree`. This story lands first (closeout plan § C.7).
Keep the edit surface here confined to the `except PermissionsCreateError`
block and its comment — do not restructure the function, rename its locals, or
extract helpers from it — so INFRA-302 layers on cleanly rather than
conflicting. INFRA-302's spec must be written against this story's post-merge
version of the function.

**7. Ideology note (Step 4a — resolved inline, no conflict).** Two entries
shaped this spec. *"Never silently pass contradictions"* (`docs/ideology.md:102-110`)
is the whole of item A: a parser returning `"[a, b]"` when it cannot parse
`[a, b]` is precisely the false confidence that constraint protects against,
which is why A6 raises rather than routing the problem into
`validate_story_file` — the crash site never calls the validator, so a
validator-only fix would leave the constraint violated on the live path.
*"Rationale-bearing decisions over bare rules"* is why C2, C3, B5 and the
`_parse_flow_sequence` docstring are Ensures rather than niceties: the
merge-path/stamp-path severity asymmetry and the deliberate duplicate
`isinstance` checks both read as oversights to someone who does not know the
reason, and the obvious "cleanup" of either is a regression. *"Hooks are thin
relays only"* was checked and does **not** bind: no hook imports this parser
(§ Requires), which is exactly why F1's fail-closed propagation is safe.

## Tests

Run from the story worktree root. After item A, and again after item C:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_schema_validator.py \
  tests/pairmode/test_flex_build_permissions_create.py \
  tests/pairmode/test_flex_build.py \
  tests/pairmode/test_cli_surface_freeze.py \
  -q 2>&1 | tail -30
```

Then the parser's other consumers, to catch collateral damage:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_permission_scope.py \
  tests/pairmode/test_story_resolver.py \
  tests/pairmode/test_story_context.py \
  tests/pairmode/test_record_attempt.py \
  tests/pairmode/test_index_integrity.py \
  tests/pairmode/test_story_update.py \
  tests/pairmode/test_model_selector.py \
  tests/pairmode/test_phase_new.py \
  -q 2>&1 | tail -30
```

(Skip any of the above that does not exist in the tree; do not create it.)

Then the full suite **without `-x`**, so nothing is masked:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Machine-checkable Ensures:

```bash
# A1/A2 — the new symbols exist
grep -n 'class FrontmatterError\|def _parse_flow_sequence' \
  skills/pairmode/scripts/schema_validator.py

# A4 — the CER-092 ordering comment survived
grep -c 'comment strip must' skills/pairmode/scripts/schema_validator.py   # 1

# C1 — the create path tears down
grep -n '_teardown_story_worktree' skills/pairmode/scripts/flex_build.py   # >= 3 sites

# F1 — no other module was touched
git diff --name-only | sort

# E3 — the CER row is closed
grep 'CER-115' docs/cer/backlog.md | grep -c 'RESOLVED Phase 113'          # 1
```

Acceptance:

- every new test from A1-A8, B1-B5, C1-C7, E1-E3 passes;
- every pre-existing test in `TestStoryWorktreeLifecycle` and in
  `tests/pairmode/test_schema_validator.py` passes under its original name
  (A8, C7);
- `tests/pairmode/test_cli_surface_freeze.py` passes with no edit (C7);
- the full suite is green against the § Requires baseline (`4116 passed, 211
  skipped` on `610af2a3`), with the passed count higher and the skipped count
  unchanged.

**On the "known failure".** There is no failing test on main as of
2026-07-29 — the closeout plan's note about `test_observability_ui` was
measured in a *worktree*, not in the main checkout, and is the CER-090 vendored
`node_modules` gap. If `tests/pairmode/test_observability_ui.py` fails in your
worktree, do **not** run `pnpm install`; rsync the payload from the main
checkout per the documented remedy, re-run, and record what you did. Do not
weaken or skip the test, and do not report a worktree-provisioning failure as a
code failure. (Making worktree provisioning automatic is INFRA-302's job, not
this story's.)

## Out of scope

- **Converting the other eight `_parse_frontmatter` call sites to per-site
  error handling.** `permission_scope.py:35`, `story_resolver.py:70`,
  `story_context.py:274`, `record_attempt.py:233`, `index_integrity.py:214`
  (and `:257`, `:326`, `:350`), `story_update.py:146`, `phase_new.py:104`/`:155`
  and `model_selector.py:444` do not currently guard against a raising parser,
  so a `FrontmatterError` will surface there as an uncaught `ValueError`. That
  is the **intended** behaviour for this story: all of them are CLI or script
  entry points (no hook imports the parser — § Requires), the input that
  triggers it is genuinely malformed frontmatter that today produces silently
  wrong data, and a loud failure naming the key is strictly better than the
  status quo. Prettier per-site messages are cosmetics and belong in their own
  story.
- **A general YAML parser, or any dependency on PyYAML.** The minimal-subset
  parser is a deliberate architectural choice (`docs/architecture.md:1156-1170`);
  this story widens the subset by exactly one flat form and refuses everything
  else. Nested flow sequences, flow mappings (`{a: b}`), multi-line flow
  sequences, block scalars (`|`, `>`) and anchors remain unsupported and
  unparsed.
- **An escaping rule for commas inside flow-sequence elements.** Not invented
  here (step 1). Block style already expresses it.
- **Collapsing the duplicated `primary_files` `isinstance` check** at
  `schema_validator.py:205-206`/`:208-209`, or adding the missing `touches`
  list check to `validate_story_file`. Both are real, both are one line, and
  both change what `validate-schema` reports across every existing story file —
  a validator-tightening story with its own full-tree re-validation evidence,
  not a clause here. B5 pins that this story leaves them alone.
- **Making `_stamp_active_story` failures fatal.** C3 explicitly preserves the
  warning.
- **Worktree provisioning (`node_modules` symlinking, `worktree_provision`
  config) and the `tsconfig.tsbuildinfo` tracking residue.** INFRA-302,
  phase 114 — which edits the same function and lands after this story
  (step 6).
- **Any change to `merge-story-worktree` or `discard-story-worktree`,** or to
  `_teardown_story_worktree`/`_residue_lines` themselves (INFRA-286
  semantics). This story only adds a third caller.
- **Retroactive repair of any residue currently in `.pairmode-worktrees/`.**
  The new atomicity applies from the next `create-story-worktree` onward.
- **Rewriting flow-style frontmatter in existing story files.** Once the parser
  understands the form, existing files are correct as written; no migration
  sweep is owed.
- **Any further `docs/cer/backlog.md` grooming** beyond the CER-115 row named
  in E3. The era's remaining rows are closed by their own stories, and the
  backlog truth pass is INFRA-310.
