#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$HOME/universal-agent}"
DB="$(mktemp)"
trap 'rm -f "$DB" "$DB-wal" "$DB-shm"' EXIT

cd "$ROOT/fullstack-agent"
python3 -m unittest tests.test_memory_engine tests.test_memory_runtime

python3 memory_runtime.py pre --db "$DB" --utterance "What does CTS remember about memory?" >/tmp/live-memory-pre.json
python3 memory_runtime.py post --db "$DB" --utterance "For CTS, I prefer atomic memory claims." --response "Understood." >/tmp/live-memory-post.json
python3 - "$DB" <<'PY'
import sqlite3, sys
conn=sqlite3.connect(sys.argv[1])
row=conn.execute("select status, primary_domain, domain_verified from memories limit 1").fetchone()
assert row == ('candidate','CTS',0), row
print('MEMORY_RUNTIME_OK candidate=queued domain=CTS verified=false')
PY

cd "$ROOT/backtalk"
.venv/bin/python - <<'PY'
from backtalk.memory_bridge import pre_turn, post_turn
pre=pre_turn('What does CTS remember?')
assert pre.get('enabled') is True, pre
post=post_turn('For CTS, I prefer evidence gated memory.', 'Acknowledged.')
assert post.get('enabled') is True, post
print('BACKTALK_MEMORY_BRIDGE_OK')
PY

echo "LIVE_MEMORY_INTEGRATION_VERIFIED"
