#!/usr/bin/env bash
# Verify a fresh VM install without requiring microphone input.
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

ROOT="$HOME/universal-agent"
SKIP_CORE=0

usage() {
  cat <<'EOF'
Usage: ./verify-vm.sh [--root PATH] [--skip-core]

Checks repository layout, portable identity and memory, cross-component
configuration, Backtalk core selection, a headless agent turn, remote endpoint
assets, and the visualizer state endpoint. No VM audio hardware is required.
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

for d in \
  fullstack-agent \
  backtalk \
  ai-memory-vault \
  ai-visualizer \
  barehands \
  identity \
  memory \
  "memory/00 - Inbox" \
  "memory/01 - Daily Notes" \
  "memory/90 - Archive" \
  "memory/99 - Resources"; do
  if [ -d "$ROOT/$d" ]; then pass "$d present"; else bad "$d missing"; fi
done

for f in \
  AGENTS.md \
  CLAUDE.md \
  fullstack-agent.json \
  backtalk/backtalk.json \
  ai-visualizer/ai-visualizer.json \
  identity/IDENTITY.md \
  identity/OPERATING_PRINCIPLES.md \
  memory/VAULT-INDEX.md \
  "memory/Active Priorities.md" \
  "memory/01 - Daily Notes/Daily Note Template.md"; do
  if [ -f "$ROOT/$f" ]; then pass "$f present"; else bad "$f missing"; fi
done

if python3 - "$ROOT" <<'PY'
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1]).expanduser().resolve()
shell = json.loads((root / "fullstack-agent.json").read_text())
backtalk = json.loads((root / "backtalk/backtalk.json").read_text())
visualizer = json.loads((root / "ai-visualizer/ai-visualizer.json").read_text())
identity_text = (root / "identity/IDENTITY.md").read_text()

provider = shell.get("core", {}).get("provider")
assert provider, "fullstack-agent.json has no core.provider"
assert backtalk.get("core", {}).get("provider") == provider, \
    "shell and Backtalk provider differ"
assert Path(shell["agent_dir"]).resolve() == root, "shell agent_dir is wrong"
assert Path(shell["memory_dir"]).resolve() == root / "memory", \
    "shell memory_dir is wrong"
identity = shell.get("identity") or {}
assert identity.get("file") == "identity/IDENTITY.md", \
    "portable identity file is not configured"
assert identity.get("principles_file") == "identity/OPERATING_PRINCIPLES.md", \
    "portable operating principles are not configured"
match = re.search(r"(?m)^Name:\s*(.+?)\s*$", identity_text)
assert match, "identity file has no Name field"
name = match.group(1).strip()
assert backtalk.get("name") == name, "Backtalk name differs from portable identity"
assert visualizer.get("name") == name, "visualizer name differs from portable identity"
assert Path(backtalk["agent_dir"]).resolve() == root, "Backtalk agent_dir is wrong"
assert Path(backtalk["signals_dir"]).resolve() == root / "backtalk", \
    "Backtalk signals_dir is wrong"
assert str(root / "memory") in backtalk.get("extra_dirs", []), \
    "portable memory is not exposed to Backtalk core"
assert Path(visualizer["bus_dir"]).resolve() == root / "backtalk", \
    "visualizer bus_dir is wrong"
print(f"WIRING_OK name={name} provider={provider}")
PY
then
  pass "identity, configuration, and cross-component wiring"
else
  bad "identity or cross-component wiring invalid"
fi

if grep -q 'identity/IDENTITY.md' "$ROOT/AGENTS.md" && \
   grep -q 'identity/OPERATING_PRINCIPLES.md' "$ROOT/AGENTS.md"; then
  pass "AGENTS.md contains portable identity startup protocol"
else
  bad "AGENTS.md does not contain portable identity startup protocol"
fi

if grep -q 'memory/VAULT-INDEX.md' "$ROOT/AGENTS.md" && \
   grep -q 'memory/Active Priorities.md' "$ROOT/AGENTS.md"; then
  pass "AGENTS.md contains portable memory startup protocol"
else
  bad "AGENTS.md does not contain portable memory startup protocol"
fi

if [ -x "$ROOT/backtalk/.venv/bin/python" ]; then
  pass "Backtalk virtual environment present"
  if "$ROOT/backtalk/.venv/bin/python" -c \
      'import sys; assert (3, 11) <= sys.version_info[:2] < (3, 13)' >/dev/null 2>&1; then
    pass "Backtalk Python version supported"
  else
    bad "Backtalk Python version unsupported"
  fi
else
  bad "Backtalk virtual environment missing"
fi

CPU_OK=1
if bash "$ROOT/fullstack-agent/cpu-preflight.sh"; then
  pass "VM CPU feature baseline supported"
else
  bad "VM CPU feature baseline too old for current voice dependencies"
  CPU_OK=0
fi

if [ "$CPU_OK" -eq 1 ]; then
  if (cd "$ROOT/backtalk" && .venv/bin/python -m backtalk.endpoint_headless --self-test); then
    pass "headless remote endpoint server and PWA assets ready"
  else
    bad "headless remote endpoint self-test failed"
  fi
else
  warn "remote endpoint self-test skipped until VM CPU model is corrected"
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
  echo "VERIFIED: identity, software stack, memory wiring, selected core, and headless endpoint assets are ready."
  echo "Run verify-memory.sh to prove portable memory survives provider-session loss."
  exit 0
else
  echo "NOT READY: one or more checks failed."
  exit 1
fi
