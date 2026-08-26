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

echo "== updating stable Backtalk main =="
# Older Universal Agent installs cloned only the development branch with
# --single-branch. Their remote.origin.fetch refspec therefore tracks only
# that one branch. Merely creating refs/remotes/origin/main is insufficient:
# Git still refuses to treat origin/main as an upstream branch. Normalize the
# origin refspec to a normal all-branches mapping first, then fetch and migrate.
git -C "$ROOT/backtalk" config --replace-all \
  remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*'
git -C "$ROOT/backtalk" fetch --prune origin
if git -C "$ROOT/backtalk" show-ref --verify --quiet refs/heads/main; then
  git -C "$ROOT/backtalk" checkout main
else
  git -C "$ROOT/backtalk" checkout -b main --track origin/main
fi
git -C "$ROOT/backtalk" branch --set-upstream-to=origin/main main >/dev/null
git -C "$ROOT/backtalk" merge --ff-only origin/main

AGENTS="$ROOT/AGENTS.md"
if [ ! -f "$AGENTS" ]; then
  echo "Missing canonical instruction file: $AGENTS" >&2
  exit 1
fi

if grep -q 'identity/IDENTITY.md' "$AGENTS" && \
   grep -q 'identity/OPERATING_PRINCIPLES.md' "$AGENTS"; then
  echo "== portable identity protocol already present =="
else
  echo "== adding portable identity protocol to AGENTS.md =="
  cat >> "$AGENTS" <<'EOF'

## Portable identity protocol

At the start of a new provider session, read `identity/IDENTITY.md` and `identity/OPERATING_PRINCIPLES.md` before treating provider session context as authoritative. Identity is shell-owned and must not be inferred from the active model, provider, host, or endpoint.

Provider session IDs are disposable acceleration state. If provider-session resume fails, recover from shell-owned identity and portable memory instead of treating the agent as a new identity.
EOF
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

IDENTITY_DIR="$ROOT/identity"
IDENTITY_TEMPLATES="$ROOT/fullstack-agent/templates/identity"
mkdir -p "$IDENTITY_DIR"

CURRENT_NAME="$(python3 - "$ROOT" <<'PY'
import json
import sys
from pathlib import Path
root = Path(sys.argv[1])
try:
    cfg = json.loads((root / 'backtalk' / 'backtalk.json').read_text())
except Exception:
    cfg = {}
print(str(cfg.get('name') or 'Assistant'))
PY
)"

if [ ! -f "$IDENTITY_DIR/IDENTITY.md" ]; then
  echo "== provisioning portable identity =="
  cp "$IDENTITY_TEMPLATES/IDENTITY.md" "$IDENTITY_DIR/IDENTITY.md"
  python3 - "$IDENTITY_DIR/IDENTITY.md" "$CURRENT_NAME" <<'PY'
import re
import sys
from pathlib import Path
path = Path(sys.argv[1])
name = sys.argv[2]
text = path.read_text()
text = re.sub(r'(?m)^Name:\s*.*$', f'Name: {name}', text, count=1)
path.write_text(text)
PY
fi
if [ ! -f "$IDENTITY_DIR/OPERATING_PRINCIPLES.md" ]; then
  cp "$IDENTITY_TEMPLATES/OPERATING_PRINCIPLES.md" "$IDENTITY_DIR/OPERATING_PRINCIPLES.md"
fi

# Ensure components can see shell-owned portable memory and record identity
# metadata without replacing user configuration.
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

shell_path = root / "fullstack-agent.json"
try:
    shell = json.loads(shell_path.read_text())
except FileNotFoundError:
    shell = {}
identity = dict(shell.get("identity") or {})
identity.setdefault("name", cfg.get("name") or "Assistant")
identity["file"] = "identity/IDENTITY.md"
identity["principles_file"] = "identity/OPERATING_PRINCIPLES.md"
shell["identity"] = identity
shell_path.write_text(json.dumps(shell, indent=2) + "\n")
PY

echo "== repair complete =="
echo "Identity: $ROOT/identity/IDENTITY.md"
echo "Status:   $ROOT/fullstack-agent/agentctl.py --root $ROOT status"
echo "Verify:   $ROOT/fullstack-agent/verify-vm.sh --root $ROOT"
echo "Memory:   $ROOT/fullstack-agent/verify-memory.sh --root $ROOT"
