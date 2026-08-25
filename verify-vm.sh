#!/usr/bin/env bash
# Verify a fresh VM install without requiring microphone input.
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

ROOT="$HOME/universal-agent"
SKIP_CORE=0

usage() {
  cat <<'EOF'
Usage: ./verify-vm.sh [--root PATH] [--skip-core]

Checks repository layout, JSON config, Backtalk core selection, a headless
agent turn, and the visualizer state endpoint. The headless core test requires
provider authentication but does not require audio hardware.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root) ROOT="${2:?missing path}"; shift 2 ;;
    --skip-core) SKIP_CORE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done
ROOT="${ROOT/#\~/$HOME}"

fail=0
pass() { printf 'PASS  %s\n' "$1"; }
warn() { printf 'WARN  %s\n' "$1"; }
bad() { printf 'FAIL  %s\n' "$1"; fail=1; }

for d in fullstack-agent backtalk ai-memory-vault ai-visualizer barehands memory; do
  if [ -d "$ROOT/$d" ]; then pass "$d present"; else bad "$d missing"; fi
done

for f in AGENTS.md CLAUDE.md fullstack-agent.json backtalk/backtalk.json ai-visualizer/ai-visualizer.json; do
  if [ -f "$ROOT/$f" ]; then pass "$f present"; else bad "$f missing"; fi
done

if python3 - "$ROOT" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
for rel in (
    "fullstack-agent.json",
    "backtalk/backtalk.json",
    "ai-visualizer/ai-visualizer.json",
):
    json.loads((root / rel).read_text())
print("JSON_OK")
PY
then
  pass "configuration JSON parses"
else
  bad "configuration JSON invalid"
fi

if [ -x "$ROOT/backtalk/.venv/bin/python" ]; then
  pass "Backtalk virtual environment present"
else
  bad "Backtalk virtual environment missing"
fi

if (cd "$ROOT/backtalk" && .venv/bin/python -m backtalk.core_probe --check); then
  pass "selected core starts"
else
  bad "selected core could not start"
fi

if [ "$SKIP_CORE" -eq 0 ]; then
  if (cd "$ROOT/backtalk" && .venv/bin/python -m backtalk.core_smoke); then
    pass "headless core turn returned text"
  else
    bad "headless core turn failed"
  fi
else
  warn "headless core turn skipped"
fi

VIS_LOG="$(mktemp)"
(
  cd "$ROOT/ai-visualizer"
  python3 server.py --no-open --mock thinking >"$VIS_LOG" 2>&1
) &
VIS_PID=$!
cleanup() {
  kill "$VIS_PID" >/dev/null 2>&1 || true
  wait "$VIS_PID" >/dev/null 2>&1 || true
  rm -f "$VIS_LOG"
}
trap cleanup EXIT

ok=0
for _ in $(seq 1 30); do
  if command -v curl >/dev/null 2>&1 && \
     curl -fsS http://127.0.0.1:8790/state 2>/dev/null | \
     python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["state"] == "thinking"' 2>/dev/null; then
    ok=1
    break
  fi
  sleep 0.2
done
if [ "$ok" -eq 1 ]; then
  pass "visualizer mock state endpoint"
else
  bad "visualizer did not answer on 127.0.0.1:8790"
  cat "$VIS_LOG" >&2 || true
fi
cleanup
trap - EXIT

printf '\n'
if [ "$fail" -eq 0 ]; then
  echo "VERIFIED: software stack and selected core are ready."
  echo "Full voice still requires microphone and speaker devices inside the VM."
  exit 0
else
  echo "NOT READY: one or more checks failed."
  exit 1
fi
