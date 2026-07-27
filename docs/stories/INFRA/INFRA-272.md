---
id: INFRA-272
rail: INFRA
title: "Context-state hygiene: surface context_budget fail-open, clear token-staleness residue (CER-040, CER-041)"
status: draft
phase: "105"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/context_budget.py
touches:
  - hooks/pre_tool_use.py
  - skills/pairmode/scripts/session_state.py
  - skills/pairmode/scripts/story_context.py
  - skills/observability/api/src/routes/context.ts
  - docs/architecture.md
  - docs/cer/backlog.md
  - tests/pairmode/test_context_budget.py
  - tests/pairmode/test_pre_tool_use_hook.py
  - tests/pairmode/test_session_state.py
  - tests/pairmode/test_session_reset.py
  - tests/pairmode/test_story_context.py
  - tests/pairmode/test_observability_context_api.py
  - docs/stories/INFRA/INFRA-272.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase 105 de-risks the fleet campaign: every project that gets migrated in
Phase 106 inherits whatever the context gate does today, on eight-plus
checkouts at once, with no operator watching each one. Two of the phase's
named CERs are the gate's own hygiene, and both are in the same
awkward half-state — the *mechanism* each one asked for shipped years of
phases ago, the *finding* was never closed, and what is left behind is
residue that actively misleads a reader.

**CER-040 — the fail-open is no longer wrong, but it is still silent.**
The finding is that `decide()` passes through with "no operator signal" when
state is missing or broken. Phase 59 (INFRA-150) and Phase 74/75 (INFRA-182)
closed the two loudest holes: `_read_state()` now returns `{}` rather than
`None` for a malformed file (`context_budget.py:618-637`), and a
`.companion/` directory with no `state.json` returns a hard CONTEXT CHECK
REQUIRED block (`:749-762`). What nobody went back and did is the second half
of the sentence. Four pass-through paths remain, and every one of them
produces a gate that is *not enforcing* while looking exactly like a gate
that decided you were within budget:

1. `_is_stale()` returns `False` when `context_session_reset_at` is absent
   (`:653-655`). The session-invalidation anchor the whole CER-047 fix rests
   on is simply not there, and the gate proceeds on an unanchored number.
2. `_is_stale()` returns `False` when either timestamp is unparseable
   (`:660-664`) — documented as "fail-open for backwards compatibility",
   which is a defensible decision and an indefensible silence.
3. `_import_session_state()` (`:668-682`) raises `ImportError` if neither
   import style resolves. That propagates out of `decide()` into
   `pre_tool_use.py`'s blanket `except Exception: sys.exit(0)`
   (`hooks/pre_tool_use.py:135-136`), and the gate is dead for the rest of
   the session with nothing printed anywhere.
4. That blanket `except` swallows *any* `decide()` failure the same way. It
   is correctly non-blocking — a hook bug must never wedge a build — but
   "never block" and "never mention it" are different properties, and only
   the first one was designed.

The module already has the right precedent for the fix and does not follow
it: the `flex_factor` clamps three lines up print a named, prefixed line to
stderr and carry on (`:729-747`). This story makes every remaining fail-open
branch behave the way the clamps already do. The one path that must stay
silent is a project with no `.companion/` directory at all — the hook fires
on every allowlisted spawn in every repo, non-pairmode projects
intentionally have no `state.json`, and CER-040 states outright that the fix
must not break that case.

**CER-041 — the fix shipped twice, and the first copy is still in the tree.**
The finding asked for session invalidation on `context_current_tokens`.
Phase 59 (INFRA-151) shipped a 60-minute TTL inside
`read_context_tokens_from_state` (`:267-320`). CER-047 then demonstrated in
production that a TTL cannot answer the question — an operator who clears
after twenty minutes is inside the TTL and gets the phantom number anyway —
and Phase 68/74 replaced it with the `context_session_reset_at` comparison
(`_is_stale`, `:640-665`) that `decide()` actually uses today. `decide()`
reads `context_current_tokens` inline and says so in a comment: *"bypass
TTL; session-reset check below"* (`:780`).

So the TTL is dead, and the corpse is load-bearing in the wrong direction:

- `read_context_tokens_from_state` has **zero production callers** — only
  tests and doc prose reference it — yet it is the module's most
  authoritative-looking public reader, and it applies a staleness rule the
  enforcement path deliberately does not.
- `story_context.py:130-135` tells the next reader that cross-session
  staleness "is handled by the TTL check in
  `context_budget.read_context_tokens_from_state`". It is not. That sentence
  is why the two token keys survive a story clear, so a reader who checks the
  claim and finds it false has no idea whether the retention is still
  correct. (It is — `_is_stale` covers it — but nothing says so.)
- `session_state.py:88-99` and `docs/architecture.md:350-352` both define
  `SESSION_LIVE_TTL_MINUTES` (180) by contrast with
  `context_budget._CONTEXT_TOKEN_STALE_MINUTES` (60), pinning a live,
  well-reasoned constant to a dead one.
- `skills/observability/api/src/routes/context.ts` still advertises
  `context_current_tokens_ttl_minutes` as one of six tunable thresholds
  (`:57-63`) — a knob the operator can see, that tunes nothing, because
  `architecture.md:2036-2038` already records the key as "legacy … no longer
  used". Worse, `buildCurrentField` (`:126-162`) computes the SPA's `stale`
  badge from that TTL, so the one operator surface that reports on gate
  freshness answers a different question from the gate, using a number no
  writer maintains.

The badge itself is not the residue and must survive: CER-045/CER-054's
resolution note leans on it explicitly ("the SPA's staleness badge already
surfaces it") to distinguish a genuinely idle project from a broken writer.
"Is this number old?" is a real question. It is just not the gate's question,
and the fix is to say which is which rather than to delete either.

Both CER rows sit unannotated in `## Do Later` (`docs/cer/backlog.md:104`,
`:106`) while the phase Goal claims to close them; the resolution notes are
part of this story's deliverable, not bookkeeping after it.

## Requires

- `skills/pairmode/scripts/context_budget.py` defines `_CONTEXT_CHECK_REQUIRED_MSG`,
  `_CONTEXT_TOKEN_STALE_MINUTES`, `read_context_tokens_from_state`,
  `_read_state`, `_is_stale`, `_import_session_state`, and `decide`. Verify:
  `grep -n 'def _is_stale\|_CONTEXT_TOKEN_STALE_MINUTES\|def read_context_tokens_from_state' skills/pairmode/scripts/context_budget.py`
  prints at least four lines.
- `read_context_tokens_from_state` has **no** caller under `hooks/` or
  `skills/` other than its own definition. Verify before deleting anything:
  `grep -rn 'read_context_tokens_from_state' hooks/ skills/ --include='*.py' | grep -v 'def read_context_tokens_from_state'`
  prints only `skills/pairmode/scripts/story_context.py` (a docstring
  reference, item B4). If that command prints a real call site, **stop and
  report `FAIL-CAUSE`** — item B's premise is wrong and the deletion is not
  safe.
- `hooks/pre_tool_use.py`'s `Task`/`Agent` branch calls
  `context_budget.decide(project_dir=..., flex_factor=..., session_id=...)`
  inside a `try` whose `except Exception:` body is exactly `sys.exit(0)`
  (`:130-136`).
- `skills/observability/api/src/routes/context.ts` defines the `CurrentOut`
  interface (`:89-96`), a `THRESHOLD`-style definition list containing an
  entry named `context_current_tokens_ttl_minutes`, and
  `buildCurrentField(state, ttlMinutes, resolverState)`.
- `docs/cer/backlog.md` contains a `CER-040` row and a `CER-041` row, both
  under `## Do Later`, neither carrying a `**RESOLVED` note.
- `docs/architecture.md` contains the string
  `context_budget`'s 60-minute token` (≈ line 350) and a bullet beginning
  `- \`context_current_tokens_ttl_minutes\`` (≈ line 2036).
- No prior story in Phase 105 is a prerequisite — `## Ordering` in
  `docs/phases/phase-105.md` names INFRA-272 as independent.

## Ensures

Grouped by item. Every assertion is checkable from the diff or by running a
command. Line numbers throughout are anchors, not coordinates.

### A — CER-040: every fail-open branch emits an operator signal

**A1. One prefix, one emitter.** `context_budget.py` defines a module-level
constant `_FAIL_OPEN_PREFIX = "context_budget: gate not enforced — "` and a
function `_warn_fail_open(reason: str) -> None` that writes exactly one line
(`_FAIL_OPEN_PREFIX + reason`) to `sys.stderr` and returns `None`. It never
raises (its body is wrapped so that a closed/replaced stderr cannot propagate
an exception into the hook path), never writes state, and never blocks.
(`_FAIL_OPEN_PREFIX` and `_warn_fail_open` are created by this story;
`spec-preflight` flagging them as unverifiable is expected.)

**A2. The staleness-check fail-opens are named, not just taken.**
`context_budget.py` defines a pure helper
`_staleness_unverifiable_reason(state: dict) -> str | None` returning a
human-readable reason string when `_is_stale()` will fail open without
having compared anything — specifically when `context_session_reset_at` is
absent, and when either `context_session_reset_at` or
`context_current_tokens_recorded_at` is present but not parseable by
`datetime.fromisoformat` — and `None` when the comparison is genuinely
performable. It does not duplicate `_is_stale`'s verdict and does not call it.

**A3. `_is_stale`'s signature and verdicts are unchanged.**
`_is_stale(state: dict) -> bool` still returns `False` for absent
`context_session_reset_at`, `False` for unparseable timestamps, `True` for a
missing `context_current_tokens_recorded_at` alongside a present
`context_session_reset_at`, and `recorded_dt < reset_dt` otherwise. This
story adds observability to the fail-open, **not** a new blocking condition:
a project mid-upgrade that lacks `context_session_reset_at` must keep
building.

**A4. `decide()` warns on the two staleness fail-opens.** After the
`_is_stale(state)` check at `:800-807`, `decide()` calls
`_staleness_unverifiable_reason(state)` and, when it returns a string, calls
`_warn_fail_open` with it before continuing to the threshold arithmetic. The
warning fires on the pass-through path only; a state that produces a
CONTEXT CHECK REQUIRED block does not additionally warn (the block is already
the signal).

**A5. A missing `session_state` module warns and degrades, instead of killing
the gate.** `_import_session_state()` returns `None` rather than propagating
`ImportError` when neither import style resolves. `decide()`'s
`if session_id:` branch calls `_warn_fail_open` with a reason naming
`session_state` and the fact that the session-keyed read was skipped, then
proceeds using the flat project-global state exactly as it does when
`session_id` is falsy. No exception escapes `decide()` on this path.

**A6. A non-pairmode project stays silent.** When `_read_state()` returns
`None` and `project_dir / ".companion"` is not a directory, `decide()`
returns `None` and writes **nothing** to stderr. Asserted by a `capsys` test
that runs `decide(tmp_path)` on an empty directory and requires
`capsys.readouterr().err == ""`.

**A7. The hook reports what it swallows.** `hooks/pre_tool_use.py`'s
`except Exception:` around the `decide()` call (`:135-136`) prints one line
to `sys.stderr` — beginning with the literal `context_budget: gate not
enforced — ` and including `repr()` of the caught exception — before
`sys.exit(0)`. The exit code stays `0`, no `{"decision": "block"}` is
emitted, and the print is itself wrapped so a failure to print cannot change
the exit code. The blanket `except` is **not** narrowed and no other hook
branch is touched.

**A8. Warnings are tested at each branch.** `tests/pairmode/test_context_budget.py`
gains a class `TestFailOpenSignals` with one test per branch (A4 × 2 reasons,
A5, A6), each asserting on `capsys.readouterr().err` — presence and the
`_FAIL_OPEN_PREFIX` substring for the warning cases, exact emptiness for A6 —
and asserting the return value of `decide()` is unchanged from today's
behaviour on that input.

**A9. `decide()` is still read-only and still non-throwing.** The diff adds
no write to `state.json`, no `effort.db` access, and no new `raise` inside
`decide()` (D11, `docs/architecture.md` § hook architecture). A test calls
`decide()` against a directory whose `.companion/state.json` is a directory
rather than a file and asserts it returns a dict or `None` without raising.

**A10. No new block reason string.** `grep -c '_CONTEXT_CHECK_REQUIRED_MSG'`
counts may change only by branch reuse; no second CONTEXT-CHECK-style message
constant is introduced, and `render_alert_prompt`'s output is byte-identical
for unchanged inputs.

### B — CER-041: the dead scalar TTL is removed

**B1. The TTL branch leaves `read_context_tokens_from_state`.** The function
signature becomes `read_context_tokens_from_state(state: dict) -> int | None`
— the `_now` parameter is gone — and its body performs only the value
validation it already does (non-dict → `None`; key absent → `None`;
non-numeric → `None`; `<= 0` → `None`; otherwise the int). The docstring
states that staleness is **not** this function's job, names `_is_stale` /
`context_session_reset_at` as the single staleness authority, and cites
CER-041 → CER-047 for why the TTL was retired rather than kept as a second
opinion.

**B2. The constant is gone.**
`grep -c '_CONTEXT_TOKEN_STALE_MINUTES' skills/pairmode/scripts/context_budget.py`
returns `0`, and the same grep across `skills/`, `hooks/` and `tests/`
returns `0`.

**B3. `context_current_tokens_ttl_minutes` is read by nothing.**
`grep -rn 'context_current_tokens_ttl_minutes' skills/ hooks/` returns no
line that reads the key for a decision — the only surviving mentions are
documentation of the key as inert (item B5) and, in TS, none at all (item C).

**B4. The false docstring claim is corrected.**
`skills/pairmode/scripts/story_context.py`'s `clear_current_story` docstring
no longer contains the string
`by the TTL check in ``context_budget.read_context_tokens_from_state``` and
instead states that the two token keys are retained deliberately and that
cross-session staleness is handled by `context_budget._is_stale`'s
`context_current_tokens_recorded_at` vs `context_session_reset_at`
comparison, written by `session_start.py` on `clear`/`startup`. The
retention behaviour itself does not change.

**B5. The contrast constants are re-anchored.**
`skills/pairmode/scripts/session_state.py`'s `SESSION_LIVE_TTL_MINUTES`
comment (`:88-99`) no longer names `context_budget._CONTEXT_TOKEN_STALE_MINUTES`.
Its two-questions explanation survives verbatim in substance — "might that
other *process* still be running?" versus the counter's own freshness — but
the counterpart it contrasts against is stated as the SPA's display staleness
heuristic (item C2) rather than a deleted constant. The value stays `180`.
`docs/architecture.md:350-352` gets the same correction.

**B6. Existing tests are migrated, not deleted.** Every test in
`tests/pairmode/test_context_budget.py` that exercised the TTL
(`test_read_context_tokens_from_state_*` staleness cases ≈ `:460-520` and
≈ `:1665-1695`) is either retained with the TTL assertion replaced by the
equivalent `_is_stale`/`decide()` assertion, or removed **with** a
replacement test in `TestFailOpenSignals` or the `_is_stale` coverage that
covers the same operator-visible outcome. The value-validation tests
(`present_int`, `present_numeric_string`, `absent`, `zero`, `negative`,
`non_numeric`, `non_dict`) keep their names and pass unmodified except for
dropping any `_now=` argument. `tests/pairmode/test_session_reset.py:386`
and `:555` and `tests/pairmode/test_session_state.py:69` are updated for the
new signature and the removed constant.

**B7. `_is_stale` gains direct coverage.** `tests/pairmode/test_context_budget.py`
gains a class `TestIsStale` with one test per documented branch of A3, so the
staleness authority is no longer tested only indirectly through `decide()`.

### C — the observability surface stops advertising a dead knob

**C1. The threshold entry is removed.**
`skills/observability/api/src/routes/context.ts`'s threshold definition list
no longer contains an entry whose `name` is
`context_current_tokens_ttl_minutes`. The list has five entries. The
`ContextOut` payload's other fields are unchanged.

**C2. Display staleness is a named local constant with a stated scope.**
`context.ts` defines a module-level
`const DISPLAY_STALE_SECONDS = 3600;` with a comment stating that it is a
**display heuristic answering "is this number old?"**, that it is
deliberately not the gate's rule (`context_budget._is_stale`, which compares
`context_current_tokens_recorded_at` against `context_session_reset_at`),
and that it is the badge CER-054's resolution relies on to distinguish an
idle project from a broken writer. (`DISPLAY_STALE_SECONDS` is created by this
story; `spec-preflight` flags it as an unverifiable constant, which is
expected.) `buildContextPayload` no longer derives
`ttlMinutes` from state, and `buildCurrentField`'s signature drops the
`ttlMinutes` parameter.

**C3. The gate's own verdict is exposed.** `CurrentOut` gains
`gate_stale: boolean`, computed by `buildCurrentField` with the same rule as
`_is_stale`: `false` when `context_session_reset_at` is absent or either
timestamp is unparseable; `true` when `context_current_tokens_recorded_at` is
absent while `context_session_reset_at` is present; otherwise
`recorded < reset`. The existing `stale`, `age_seconds`, `recorded_at`,
`tokens`, `story_id` and `phase` fields keep their names, types and
(for `stale`) their age-based meaning.

**C4. The source-assertion tests follow.**
`tests/pairmode/test_observability_context_api.py`'s threshold test is
updated: the expected name list loses `context_current_tokens_ttl_minutes`,
the docstring/assert message says five, and a new assertion requires that
`'context_current_tokens_ttl_minutes'` does **not** appear in `context.ts` at
all. A further assertion requires `gate_stale` and `DISPLAY_STALE_SECONDS`
to appear in `context.ts`.

**C5. No SPA render change is required.** `gate_stale` is additive; no file
under `skills/observability/` other than `api/src/routes/context.ts` is
edited, and no `pnpm`/`npm` install or build is run as part of this story
(see `## Out of scope`).

### D — the record is closed

**D1. `docs/architecture.md`'s legacy-key bullet is final.** The
`- \`context_current_tokens_ttl_minutes\`` bullet (≈ `:2036-2038`) states that
the key is now read by **no** code path — Python or TypeScript — names
INFRA-272 as the story that removed the last reader, and keeps its "safe to
leave in state.json" guidance (no migration, no state rewrite).

**D2. The fail-open contract is documented where the gate is documented.**
`docs/architecture.md`'s `Task`/`Agent` → `context_budget.py` hook bullet
(≈ `:2206-2225`) gains a sentence recording that every remaining pass-through
branch emits a single `context_budget: gate not enforced — ` line on stderr,
that a project with no `.companion/` directory is the one deliberate silent
pass-through, and that the hook's blanket `except` now reports before exiting
`0`. It cites `INFRA-272, CER-040`. No new `##`-level heading is added.

**D3. CER-040 carries a RESOLVED note.** `docs/cer/backlog.md`'s `CER-040`
row's Finding cell gains a bolded `**RESOLVED Phase 105 — INFRA-272 …**` note
recording that option (b) was taken (soft, observable pass-through) on top of
the INFRA-150/INFRA-182 blocks that already implement option (a) for the
missing- and malformed-state cases, and stating explicitly that non-pairmode
projects remain silent by design. The row keeps its `Phase` cell and its
quadrant; no row is deleted or moved.

**D4. CER-041 carries a RESOLVED note.** The `CER-041` row gains a bolded
`**RESOLVED Phase 105 — INFRA-272 …**` note recording that the TTL shipped in
Phase 59 (INFRA-151) was superseded by the `context_session_reset_at`
comparison (CER-047, INFRA-175/182) and that this story removed the
now-unreachable TTL, its constant, its state key's last reader, and the three
prose claims that still described it. The note must not claim a new
invalidation mechanism was built — none was.

### Cross-cutting

**E1. No behaviour change outside the fail-open signalling.** For any state
that produces a block or a pass today, the diff produces the same block or
pass — the only difference is stderr. Assert by keeping every existing
`decide()` test in `tests/pairmode/test_context_budget.py` passing under its
original name.

**E2. Nothing outside the named files changes.** No edit to
`hooks/post_tool_use.py`, `hooks/session_start.py`,
`skills/pairmode/scripts/session_reset.py`, `flex_build.py`,
`scope_guard.py`, `next_action.py`, or `hooks/hooks.json`.

**E3. `schema_introduces` stays `false`.** No new state key, table or file is
created; one state key (`context_current_tokens_ttl_minutes`) becomes fully
inert and is documented as such (D1). No Schema-delivery row is owed in
`docs/phases/phase-105.md`.

**E4. The full test suite is green** (`tests/pairmode/`), run once **without**
`-x`.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Build in order **B → A → C → D**: B is a deletion that shrinks the surface A
has to instrument, A is the behaviour change, C is the surface that mirrors
both, and D is prose written last against what actually shipped. Run the
context-budget tests after B and again after A.

**0. Verify the deletion premise.** Run the `## Requires` grep for
`read_context_tokens_from_state` call sites *before* touching anything. If a
production caller exists, stop and report `FAIL-CAUSE`. Read the current
bodies of `decide`, `_is_stale`, `_read_state`, `_import_session_state` and
`read_context_tokens_from_state` as they exist now.

**1. (B) Remove the TTL.** Delete the `_now` parameter, the
`_CONTEXT_TOKEN_STALE_MINUTES` constant, and the whole
`recorded_at` / `ttl_minutes` / `age_minutes` block from
`read_context_tokens_from_state`, leaving only the value validation. Rewrite
the docstring per B1 — say what the function does *not* do and where the
staleness rule actually lives, because the next reader's first instinct on
finding a token reader with no staleness check will be to add one back. Fix
the `story_context.py` docstring (B4) and the two contrast comments (B5).
Then migrate the tests (B6) and add `TestIsStale` (B7). Do **not** delete
`read_context_tokens_from_state` itself: it is the module's documented scalar
reader, it is referenced from `docs/pairmode/context-gate-flow.md`, and
removing a public function is a larger blast radius than this story's
premise supports.

**2. (A) Add the emitter.** Put `_FAIL_OPEN_PREFIX` next to
`_CONTEXT_CHECK_REQUIRED_MSG` (`:86`) and `_warn_fail_open` immediately after
it. Model it on the `flex_factor` clamp warnings at `:729-747` — same
`print(..., file=sys.stderr)` shape, same "say it and carry on" posture — and
say in its docstring that it exists because a gate that fails open silently
is indistinguishable from a gate that passed you, which is the exact false
confidence `docs/ideology.md` § *Never silently pass contradictions*
forbids.

**3. (A) Instrument the four branches.** Add
`_staleness_unverifiable_reason` next to `_is_stale`, keeping `_is_stale`'s
signature and verdicts untouched (A3) — the two functions answer different
questions and merging them into a `tuple[bool, str | None]` would force every
existing caller and test to change for no gain. Call it from `decide()` after
the `_is_stale` block. Make `_import_session_state` return `None` instead of
raising, and handle the `None` in `decide()`'s `if session_id:` branch by
warning and falling through to the flat read (A5) — the CER-097 fail-safe
block stays exactly as it is when the module *does* import. Then add the
hook-side print (A7): keep `except Exception:` broad, wrap the print itself
in its own `try/except Exception: pass`, and leave `sys.exit(0)` as the last
statement.

Do **not** turn any of these four branches into a block. Every one of them
fires on a state a mid-upgrade fleet project can legitimately be in, and
Phase 106 migrates eight of them; converting a silent pass into a hard stop
during the campaign this phase exists to de-risk would be the opposite of the
goal. Loud pass-through is the deliberate choice — record it in the comment
above `_warn_fail_open`'s call sites.

**4. (C) Fix the observability surface.** Remove the threshold entry (C1),
add `DISPLAY_STALE_SECONDS` with the comment C2 demands, drop the
`ttlMinutes` plumbing from `buildContextPayload`/`buildCurrentField`, and add
`gate_stale` to `CurrentOut` and its computation. Keep `stale` age-based:
CER-045/CER-054's resolution note depends on that badge answering "is this
number old?", and silently redefining it to the gate's rule would retire a
signal another CER is closed against. The TS is verified by Python
source-assertion tests (`tests/pairmode/test_observability_context_api.py`);
do not run a Node build or install.

**5. (D) The prose.** Write D1, D2, D3, D4. For both CER rows, amend — never
delete the original finding text; the row is the record of what was true in
Phase 58. For CER-041, resist writing the note as though invalidation were
built here: it was built in Phase 68/74, and what this story did is remove
the earlier, weaker mechanism that was still lying to readers.

**6. Ideology note (Step 4a — resolved inline, no conflict).** Three entries
shaped this spec. *"Never silently pass contradictions"* is the whole of item
A, almost literally: its rationale — "a system that misses contradictions
provides false confidence, which is worse than no system" — is the argument
for warning on every pass-through, and its override path ("a developer may
explicitly acknowledge … silent bypass is never permitted") is why A6's
non-pairmode silence is scoped to *projects that never opted in* rather than
to *pairmode projects with broken state*. *"Rationale-bearing decisions over
bare rules"* is why B1's docstring, C2's comment and B5's re-anchoring are
Ensures rather than niceties: a token reader with no staleness check and a
display badge with a hardcoded hour both look like bugs to a reader who does
not know the reason, and the obvious "fix" for either re-creates the residue
this story removes. *"Hooks are thin relays only"* binds directly — item A7
touches the hook path, so the fix is a `print` to stderr and nothing else: no
state write, no retry, no API call, and `decide()` stays read-only (A9, D11).
The one place the constraint pushed the design is the rejected alternative of
recording the fail-open into `state.json` so the SPA could show it; that
would have made a read-only hook path a writer, so item C reads the same
facts from the state the writers already maintain instead.

## Tests

Run from the story worktree root. After item B, and again after item A:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_context_budget.py \
  tests/pairmode/test_pre_tool_use_hook.py \
  -q 2>&1 | tail -30
```

Then the adjacent surface — everything that reads the keys or constants this
story moved:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_session_state.py \
  tests/pairmode/test_session_reset.py \
  tests/pairmode/test_session_start_hook.py \
  tests/pairmode/test_story_context.py \
  tests/pairmode/test_context_token_writer.py \
  tests/pairmode/test_post_tool_use_hook.py \
  tests/pairmode/test_observability_context_api.py \
  -q 2>&1 | tail -30
```

(Skip any of the above that does not exist in the tree; do not create it.)

Then the full suite **without `-x`**, so a known failure cannot mask a new one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Machine-checkable Ensures:

```bash
# B2 — the dead constant is gone everywhere
grep -rn '_CONTEXT_TOKEN_STALE_MINUTES' skills/ hooks/ tests/            # no output

# B3/C1 — the dead state key has no reader left
grep -rn 'context_current_tokens_ttl_minutes' skills/ hooks/             # no output

# A1 — the emitter exists
grep -n '_FAIL_OPEN_PREFIX\|_warn_fail_open\|_staleness_unverifiable_reason' \
  skills/pairmode/scripts/context_budget.py

# A7 — the hook reports what it swallows
grep -n 'gate not enforced' hooks/pre_tool_use.py                        # >= 1

# C2/C3 — the two staleness questions are both present and distinct
grep -n 'DISPLAY_STALE_SECONDS\|gate_stale' \
  skills/observability/api/src/routes/context.ts

# D3/D4 — both CER rows are closed
grep 'CER-040' docs/cer/backlog.md | grep -c 'RESOLVED Phase 105'        # 1
grep 'CER-041' docs/cer/backlog.md | grep -c 'RESOLVED Phase 105'        # 1
```

Acceptance:

- every new test from A8, A9, B6, B7, C4 passes;
- every pre-existing `decide()` test passes under its original name (E1);
- the full suite is green. If a failure appears, verify it reproduces on
  clean `HEAD` before attributing it elsewhere, and say so explicitly in the
  build result.

## Out of scope

- **Converting any fail-open branch into a block.** Explicitly rejected in
  step 3: Phase 106 migrates projects that will legitimately be missing
  `context_session_reset_at` mid-upgrade, and this phase exists to de-risk
  that campaign, not to add a new way for it to stop. If field evidence later
  shows an unanchored gate passing a genuinely over-budget spawn, that is a
  new CER with its own severity argument.
- **Deleting `read_context_tokens_from_state`.** The TTL inside it is dead;
  the function is the module's documented scalar reader and is named in
  `docs/pairmode/context-gate-flow.md`. Removing a public function is a
  separate deprecation with its own consumer check.
- **Re-keying the flat `context_current_tokens` mirror for the observability
  API.** `docs/architecture.md:344-347` records that re-keying the SPA's
  session-less read is OBS-rail work; this story reads the same mirror the
  route already reads and only corrects what it *reports*.
- **Any SPA (front-end) rendering of `gate_stale`.** The field is added to
  the API payload; surfacing it in the UI, and any `pnpm install` / Node
  build needed to do so, is OBS-rail work (and would collide with CER-090's
  vendored `node_modules` problem inside a worktree).
- **`systemMessage`-style hook output.** Making hook warnings appear in the
  operator's main transcript rather than stderr would introduce a new hook
  output contract across every hook in the project; stderr matches the
  existing `flex_factor` clamp precedent and is what this story uses.
- **`compact` handling in the SessionStart reset.** Deliberately out of scope
  since CER-047; unchanged here.
- **Any further `docs/cer/backlog.md` grooming** beyond the CER-040 and
  CER-041 rows named in D3/D4. CER-045/CER-047/CER-054 are already annotated
  and are only *cited* by this story, not edited.
