#!/usr/bin/env bash
# Repair or upgrade an existing Universal Fullstack Agent VM in place.
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

ROOT="$HOME/universal-agent"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root) ROOT="${2:?missing path}"; shift 2 ;;
    -h|--help)
      echo "Usage: ./repair-vm.sh [--root PATH]"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

ROOT="${ROOT/#\~/$HOME}"

for repo in fullstack-agent backtalk; do
  if [ ! -d "$ROOT/$repo/.git" ]; then
    echo "Missing Git checkout: $ROOT/$repo" >&2
    exit 1
  fi
done

echo "== updating universal branches =="
git -C "$ROOT/backtalk" fetch origin universal-core-architecture
git -C "$ROOT/backtalk" checkout universal-core-architecture
git -C "$ROOT/backtalk" pull --ff-only origin universal-core-architecture

AGENTS="$ROOT/AGENTS.md"
if [ ! -f "$AGENTS" ]; then
  echo "Missing canonical identity file: $AGENTS" >&2
  exit 1
fi

if grep -q 'memory/VAULT-INDEX.md' "$AGENTS" && \
   grep -q 'memory/Active Priorities.md' "$AGENTS"; then
  echo "== portable memory protocol already present =="
else
  echo "== adding portable memory protocol to AGENTS.md =="
  cat >> "$AGENTS" <<'EOF'

## Portable memory protocol

At the start of a new session, read `memory/VAULT-INDEX.md`, then `memory/Active Priorities.md`. Retrieve other memory only when it is relevant to the task.

Persist durable decisions, constraints, lessons, and project state to the appropriate file under `memory/`. Update an existing note before creating a thin new one when practical. Never move canonical memory into a provider-specific directory, and never store secrets in the memory vault.
EOF
fi

if [ ! -d "$ROOT/memory" ]; then
  echo "Missing portable memory directory: $ROOT/memory" >&2
  exit 1
fi

# Ensure Backtalk can see shell-owned portable memory without replacing any
# other user configuration.
python3 - "$ROOT" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).expanduser().resolve()
path = root / "backtalk" / "backtalk.json"
cfg = json.loads(path.read_text())
extra = [str(Path(p).expanduser()) for p in cfg.get("extra_dirs", [])]
mem = str(root / "memory")
if mem not in extra:
    extra.append(mem)
cfg["extra_dirs"] = extra
cfg["agent_dir"] = str(root)
cfg["signals_dir"] = str(root / "backtalk")
path.write_text(json.dumps(cfg, indent=2) + "\n")
PY

echo "== repair complete =="
echo "Run: $ROOT/fullstack-agent/verify-vm.sh --root $ROOT"
