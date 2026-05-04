# anchor — Cold-Eyes Review (CER) Backlog

*Last updated: 2026-04-22*

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
| CER-001 | reconstruct.py `parse_ideology()` compat wrapper uses NamedTemporaryFile round-trip; on SIGKILL leaves ideology.md copy in /tmp. Fix: add `parse_ideology_text(text: str)` to ideology_parser.py to eliminate temp file. reconstruct.py:33-50 | Security audit cp12 | 2026-04-24 | 12 |


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

