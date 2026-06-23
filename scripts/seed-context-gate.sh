#!/usr/bin/env bash
# Seed context gate state.json keys for repos missing context_current_tokens
# or context_session_reset_at. Run from the project root.
# Safe to re-run: only writes if keys are missing.
set -euo pipefail

STATE=".companion/state.json"

if [ ! -d ".companion" ]; then
  mkdir -p .companion
fi

python3 - <<'PYEOF'
import json, pathlib, sys
from datetime import datetime, timezone

p = pathlib.Path(".companion/state.json")
s = json.loads(p.read_text()) if p.exists() else {}

needs_seed = "context_current_tokens" not in s or "context_session_reset_at" not in s
if not needs_seed:
    print("state.json already has context gate keys — no changes made.")
    sys.exit(0)

now = datetime.now(timezone.utc).isoformat()
s.setdefault("context_current_tokens", 25000)
s.setdefault("context_current_tokens_recorded_at", now)
s.setdefault("context_session_reset_at", now)
# If we just seeded current_tokens, align recorded_at to reset_at so it reads as fresh
if "context_current_tokens_recorded_at" not in s or s["context_current_tokens_recorded_at"] < s["context_session_reset_at"]:
    s["context_current_tokens_recorded_at"] = s["context_session_reset_at"]

p.write_text(json.dumps(s, indent=2))
print(f"seeded: context_current_tokens={s['context_current_tokens']}, reset_at={s['context_session_reset_at']}")
PYEOF
