---
era: "003"
---

# flex — Phase 93: Wire Edit/Write/Read matchers into pre_tool_use.py's PreToolUse registration

← [Phase 92: Fix cross-phase status leakage in story_update.py](phase-92.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

hooks/pre_tool_use.py has full dispatch logic for three tool types (Task/Agent -> context_budget.py; Edit/Write -> scope_guard.py, Phase 55; Read -> cold_read_guard.py, INFRA-196), but hooks/hooks.json PreToolUse array registers only one matcher block, Task|Agent -- no Edit|Write or Read block, unlike the PostToolUse array in the same file which correctly carries two separate matcher blocks. Result: Claude Code never invokes pre_tool_use.py for Edit, Write, or Read tool calls, so the scope_guard.py and cold_read_guard.py branches are unreachable dead code in every project using this plugin, including flex itself. bootstrap.py _register_pretooluse_hook is further behind: it only registers a bare Task matcher (predates even the CER-049 Agent rename) for non-plugin bootstrapped projects, and never an Edit|Write or Read block either. Root cause: two separate stories (INFRA-139, INFRA-196) each added a new dispatch branch to pre_tool_use.py Python source without touching the registration manifest, and no test asserted that hooks.json matchers are a superset of the tool_name branches pre_tool_use.py actually dispatches on. This phase (CER-065) wires the missing matchers into both hooks/hooks.json and bootstrap.py, and adds a regression test enforcing matcher/dispatch consistency so a future new branch fails a test instead of shipping silently dead.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-205 | Register the Edit\|Write and Read PreToolUse matchers in hooks/hooks.json so scope_guard and cold_read_guard dispatch branches fire, plus a regression test asserting hooks.json PreToolUse matchers are a superset of pre_tool_use.py's dispatched tool_name values | planned |
| INFRA-206 | Widen bootstrap.py's _register_pretooluse_hook to register the full Task\|Agent + Edit\|Write + Read matcher set into downstream projects' .claude/settings.json, migrating the stale "Task"-only block in place while preserving idempotency | planned |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-93 Cold-eyes checklist

— developer fills in after phase completion —
