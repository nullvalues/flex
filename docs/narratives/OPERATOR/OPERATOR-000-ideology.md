---
id: OPERATOR-000
role: OPERATOR
title: The operator — role ideology
status: draft
era: "004"
surfaces: [CLI]
rails: [INFRA]
stories: []
---

## Narrative

The operator is the only role in this whole system with a body, a calendar, and
something at stake beyond the current session — the person who has to trust that
when this harness says PASS, PASS means something, because they are not going to
independently re-verify every story themselves. Their authority is real and
load-bearing: protected files, cross-repo commits, version bumps, and
phase-priority decisions all route through them, by design, and this era's own
transcripts show that gate holding — every one of those actions paused for a real
confirmation, not a rubber stamp.

But authority to decide isn't the same as visibility to know when a decision is
needed. This era's own cold-eyes review found the harness's core promise —
reliable escalation on failure — silently broken roughly half the time,
discoverable only by mining a log file few would think to read proactively. It
found two Phase-116 features, reviewer-PASSed and merged, that had never actually
run once. None of this reached the operator through any surface the harness
offers today; it reached them because this era went looking, on request, at real
cost. A CLI and a chat transcript are the operator's only surface — there is no
dashboard, no digest, no passive signal that says "something in the loop needs
your attention" between the moments someone thinks to ask.

## Always true

- Final authority on protected-file edits, cross-repo commits, release version
  bumps, and phase-priority tradeoffs.
- Can be asked, via a direct question, at any genuine decision point — and this
  era shows that channel gets used for real decisions (a version bump, a
  divergent-branch merge strategy, a scope tradeoff), not performative ones.
- Sets priority and can redirect a whole phase's scope (as happened this era,
  folding backlog findings into a closeout phase rather than deferring them) —
  the orchestrator does not overrule this.

## Never

- Never silently bypassed for a protected/high-risk action — verified working
  this era, not merely asserted.
- Never expected to independently re-verify what the loop already claims to
  have checked — that would defeat the point of having the loop at all.

## Open gaps

- The single clearest operator-UX gap this whole exercise surfaced: there is no
  standing signal, of any kind, between the operator and the build loop's
  actual health. Every finding this era produced — the escalation-ladder
  failure rate, the dead features, the CER-corruption bug — was discoverable
  only through an expensive, deliberately-commissioned review, never through
  anything the harness surfaces on its own. An operator who trusts the loop day
  to day has no way to notice drift before it accumulates into something this
  large.
- No narrative-of-record existed until this era for the operator to check the
  loop's behavior against, even though the operator is the one role whose whole
  relationship to this system is "does this actually serve what I need it to
  serve" — exactly the question a narrative answers and a technical spec does
  not.
