# Design note — shadow handshake and warm attempts

Investigated 2026-08-07 against nullvalues/flex@main (post-CER-174/175/180
hardening). Two findings, two different landing eras.

## 1. The intra-attempt gap (lands 0.4.1 — proposed phase shadow-handshake)

**Confirmed.** The shadow procedure's stop condition is "a story-<ID> commit
appears" — the shadow's final read of the finished diff happens at or after
the moment the build is sealed. Findings from that last pass can only save
attempt N+1, never attempt N. Mid-build polls help only with mid-build misses;
the highest-value review moment (the complete diff) is structurally wasted.

**Design: a three-artifact handshake (operator-ruled, 2026-08-07).**

- **Builder-owned marker** (.pairmode-review-request): written after the
  builder's last file write, before the story commit. Gitignored, never
  committed, never shadow-writable.
- **Shadow-owned lck** (.pairmode-review.lck): a discrete liveness ack. The
  marker is itself a file change, so it wakes the shadow's event-driven poll;
  the shadow writes OPEN immediately, reviews, then writes CLOSED. (Content
  transitions, not presence/absence — the shadow holds Write only and cannot
  delete.) Widening scope_guard's shadow confinement from one literal path to
  exactly two keeps the CER-174/175 default-deny pattern intact; it changes an
  allowlist's length, not its class.
- **Dead-shadow detection is structural, not tuned**: no OPEN within one poll
  cycle means the shadow never woke — the builder proceeds immediately. This
  kills both the per-story latency tax and the timeout-tuning loop a fixed
  wait would invite. Once OPEN is seen, the builder waits for CLOSED under a
  generous runaway ceiling (mid-review death is the rare case; era-005
  heartbeats give the orchestrator that watch properly).
- **Typed findings**: the shadow self-classifies every entry — mechanical,
  ensures-gap, intent-deviation, taste. No explicit ignore rules for the
  builder: suggestions stay advisory, and intent-typed findings flow to the
  intent reviewer to reinforce or correct regardless of adoption.
- **Builder dispositions**: the builder appends a one-line answer per finding
  (adopted / declined + outcome + reason). The log stops being shadow-owned
  and becomes the exchange record; append-only discipline holds for both
  writers. The OSPA shadow lane's adopted/ignored markers become real signals
  instead of diff inference, and the reviewer procedure names the exchange
  record (typed findings + dispositions) as a bounded input — declined
  ensures-gap findings are re-examined at review, so a wrong decline costs
  a verdict finding, not a silent miss. In-scope for INFRA-438, not a
  follow-up.
- **Ideology line (ruled)**: feedback on its own build is within context-free
  scope — the builder may know everything about its own attempt, and nothing
  about anyone else's.

Payoff: simple misses (the story's own Ensures edge cases, staged-suggestions,
scope drift) get fixed inside the attempt — whole build loops saved for the
cost of one marker file and two log entry types.

## 2. Warm attempts (lands era 005 — KERNEL-007, proposed phase ts-kernel)

**Confirmed, with precedent.** The tree already walked this direction twice:
BUILD-038 dropped git clean -fd from the FAIL-revert, and INFRA-223 scoped the
reviewer FAIL-path revert to the story's declared primary_files/touches after
RELEASE-022's blanket revert deleted two unrelated directories. What remains
wholesale is the attempt restart itself: every retry cold-starts the worktree,
so a scope-expansion retry rebuilds work the reviewer already verified.

**Design: salvage manifest on the verdict.**

- A FAIL verdict gains a per-file disposition over the story's declared file
  set: keep / revert / rebuild. The reviewer proposes it; cause-class (the
  D1 column landing in proposed phase measurement-columns) informs it.
- Attempt N+1 applies the manifest — scoped revert of only revert/rebuild
  files — and the builder receives the manifest as a bounded input naming
  what stands and what failed.
- **Cold stays cold where it matters**: wrong-approach and architecture
  cause-classes force the full reset unchanged. Cold agents were always the
  ideology; cold trees were only ever its blunt instrument.
- Landing in the TS kernel's worktree-lifecycle module (KERNEL-003's phase)
  rather than in Python first — building it twice on both sides of the
  cutover would violate the port-nothing-twice posture. The handshake (above)
  covers the cheap wins in 0.4.1 meanwhile.

## Sequencing note

proposed phase measurement-columns's cause-class column now does double duty: era-006 measurement AND
the salvage-manifest trigger data. It should land exactly as specced.
