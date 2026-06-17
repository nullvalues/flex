---
era: "002"
---

# flex — Phase 73: Per-story context token dict; revert Phase 72 JSONL gate

← [Phase 72: Restore JSONL-based context gate](phase-72.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Replace the mutable context_current_tokens scalar with a per-story-ID dict (context_story_tokens) whose entries are validated against a session-boundary timestamp (context_session_reset_at) written by the SessionStart hook. This makes the hook gate story-ID-aware — a token count recorded for a different story, or before the last /clear, is treated as missing and prompts CONTEXT CHECK REQUIRED. Simultaneously reverts the Phase 72 JSONL enforcement path, which was unreliable (JSONL lags the live window) and undermined the gate by providing a silent fallback that bypassed CONTEXT CHECK REQUIRED.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-180 | Replace context_current_tokens scalar with per-story-ID dict; add session-boundary staleness gate | planned |
| INFRA-181 | Revert Phase 72 JSONL additions; restore /context + set-context-tokens Context gate | planned |
| BUILD-031 | Context gate flow diagram; README tooling update | planned |

## Schema delivery

| Object | Management surface | Exception |
|---|---|---|
| — | — | — |

---

### CP-73 Cold-eyes checklist

— developer fills in after phase completion —
