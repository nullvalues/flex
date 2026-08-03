---
id: OPERATOR-000
role: OPERATOR
title: The operator — role ideology
status: draft
era: "seed"
surfaces: [CLI]
rails: [INFRA]
stories: []
---

## Narrative

The operator is the only role in this whole system with a body, a calendar, and
something at stake beyond the current session — the person who has to trust that
when this harness reports a PASS, PASS means something, because they are not
going to independently re-verify every story themselves. Their authority is
real and load-bearing: protected files, cross-repo commits, version bumps, and
phase-priority decisions all route through them, by design.

But authority to decide isn't the same as visibility to know when a decision is
needed. A CLI and a chat transcript are typically the operator's only surface —
there is no dashboard, no digest, no passive signal that says "something in the
loop needs your attention" unless the harness is deliberately built to surface
one. Between checkpoints, the operator's day-to-day trust in the loop rests on
the loop actually doing what it claims, with no independent way to notice
otherwise until something is specifically reviewed.

## Always true

- Final authority on protected-file edits, cross-repo commits, release version
  bumps, and phase-priority tradeoffs — the build loop does not act on these
  without the operator's explicit say.
- Can be asked, via a direct question, at any genuine decision point the loop
  encounters that it cannot resolve on its own.
- Sets priority and can redirect a whole phase's scope at any time — the
  orchestrator does not overrule this.

## Never

- Never silently bypassed for a protected/high-risk action.
- Never expected to independently re-verify what the loop already claims to
  have checked — that would defeat the point of having the loop at all.
- Never given standing visibility into loop health beyond what the harness
  explicitly builds and surfaces — an unstated assumption of passive
  oversight is not a substitute for a real signal.

## Open gaps

- Without a standing signal between the operator and the build loop's actual
  health, drift accumulates silently: failures, dead code paths, and integrity
  issues are discoverable only through a deliberately-commissioned review, not
  through anything the harness surfaces on its own.
- This seed narrative is deliberately generic — a project-specific extension
  describing how this project's operator actually wants to work with the loop
  (priorities, review habits, risk tolerance) belongs in a numbered
  `OPERATOR-010`-and-onward file, authored separately, never by editing this
  seed.
