#!/usr/bin/env bash
# Universal Fullstack Agent fresh VM bootstrap
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

ROOT="$HOME/universal-agent"
PROVIDER="codex"
AGENT_NAME="Assistant"
INSTALL_MODELS=1
INSTALL_SYSTEM=1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHELL_BRANCH="${FULLSTACK_AGENT_BRANCH:-main}"
BACKTALK_BRANCH="${BACKTALK_BRANCH:-main}"

usage() {
  cat <<'EOF'
Usage: ./bootstrap-vm.sh [options]

Options:
  --root PATH             Agent home. Default: ~/universal-agent
  --provider NAME         codex, claude, or generic-cli. Default: codex
  --name NAME             Agent display name. Default: Assistant
  --no-models             Skip Whisper/Kokoro model prefetch
  --skip-system-packages  Do not run apt-get
  -h, --help              Show this help

Stable installs use main for Fullstack Agent and Backtalk. Developers may
override FULLSTACK_AGENT_BRANCH or BACKTALK_BRANCH in the environment.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root) ROOT="${2:?missing path}"; shift 2 ;;
    --provider) PROVIDER="${2:?missing provider}"; shift 2 ;;
    --name) AGENT_NAME="${2:?missing name}"; shift 2 ;;
    --no-models) INSTALL_MODELS=0; shift ;;
    --skip-system-packages) INSTALL_SYSTEM=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$PROVIDER" in
  codex|claude|generic-cli) ;;
  *) echo "Unsupported provider: $PROVIDER" >&2; exit 2 ;;
esac

ROOT="${ROOT/#\~/$HOME}"
mkdir -p "$ROOT"

if [ "$INSTALL_SYSTEM" -eq 1 ]; then
  if command -v apt-get >/dev/null 2>&1; then
    echo "== installing VM packages =="
    sudo apt-get update
    sudo apt-get install -y \
      ca-certificates curl git bubblewrap \
      python3 python3-venv python3-pip python3-dev build-essential \
      ffmpeg espeak-ng libportaudio2 portaudio19-dev libsndfile1
  else
    echo "No apt-get detected. Install git, curl, Python 3, ffmpeg, espeak-ng, PortAudio, and bubblewrap manually."
  fi
fi

# User-local official binaries must win over distro or snap shims.
export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "== installing uv =="
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "== ensuring managed Python 3.12 for Backtalk =="
uv python install 3.12

sync_repo() {
  local url="$1" dir="$2" branch="$3"
  if [ -d "$dir/.git" ]; then
    echo "== updating $(basename "$dir") [$branch] =="
    git -C "$dir" fetch origin "$branch"
    git -C "$dir" checkout "$branch"
    git -C "$dir" pull --ff-only origin "$branch"
  elif [ -e "$dir" ]; then
    echo "Refusing to replace non-git path: $dir" >&2
    exit 1
  else
    echo "== cloning $(basename "$dir") [$branch] =="
    git clone --branch "$branch" --single-branch "$url" "$dir"
  fi
}

# Do not update the script underneath itself. A fresh external invocation gets
# the stable shell checkout under ROOT; an invocation from that checkout uses
# the currently checked out shell revision.
if [ "$SCRIPT_DIR" = "$ROOT/fullstack-agent" ]; then
  echo "== fullstack-agent: using current checkout =="
else
  sync_repo "https://github.com/st00pidctl/fullstack-agent.git" \
    "$ROOT/fullstack-agent" "$SHELL_BRANCH"
fi

sync_repo "https://github.com/st00pidctl/backtalk.git" \
  "$ROOT/backtalk" "$BACKTALK_BRANCH"
sync_repo "https://github.com/jaredrhod/ai-memory-vault.git" \
  "$ROOT/ai-memory-vault" "main"
sync_repo "https://github.com/jaredrhod/ai-visualizer.git" \
  "$ROOT/ai-visualizer" "main"
sync_repo "https://github.com/jaredrhod/barehands.git" \
  "$ROOT/barehands" "main"

if [ "$PROVIDER" = "codex" ]; then
  echo "== installing/updating official OpenAI Codex CLI =="
  curl -fsSL https://chatgpt.com/codex/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  if [ ! -x "$HOME/.local/bin/codex" ]; then
    echo "Official Codex installer did not create $HOME/.local/bin/codex" >&2
    exit 1
  fi
  CODEX_BIN="$(command -v codex)"
  if [ "$CODEX_BIN" != "$HOME/.local/bin/codex" ]; then
    echo "Codex provenance check failed: expected $HOME/.local/bin/codex, got $CODEX_BIN" >&2
    exit 1
  fi
  codex --version
elif [ "$PROVIDER" = "claude" ]; then
  echo "== installing/updating official Anthropic Claude Code =="
  curl -fsSL https://claude.ai/install.sh | bash
  export PATH="$HOME/.local/bin:$PATH"
  if [ ! -x "$HOME/.local/bin/claude" ]; then
    echo "Official Claude installer did not create $HOME/.local/bin/claude" >&2
    exit 1
  fi
  CLAUDE_BIN="$(command -v claude)"
  if [ "$CLAUDE_BIN" != "$HOME/.local/bin/claude" ]; then
    echo "Claude provenance check failed: expected $HOME/.local/bin/claude, got $CLAUDE_BIN" >&2
    exit 1
  fi
  claude --version
fi

if [ ! -f "$ROOT/AGENTS.md" ]; then
  cat > "$ROOT/AGENTS.md" <<EOF
# ${AGENT_NAME}

This directory is the canonical home of the agent.

## Ownership model

The shell owns identity, durable memory, voice integration, endpoint state, and lifecycle. Provider-specific instruction files are compatibility shims only. The reasoning core is replaceable and must never become the source of truth for identity.

## Portable identity protocol

At the start of a new provider session, read \`identity/IDENTITY.md\` and \`identity/OPERATING_PRINCIPLES.md\`. Identity is shell-owned and must not be inferred from the active model, provider, host, or endpoint.

Provider session IDs are disposable acceleration state. If provider-session resume fails, recover from shell-owned identity and portable memory instead of treating the agent as a new identity.

## Portable memory protocol

At the start of a new provider session, read \`memory/VAULT-INDEX.md\`, then \`memory/Active Priorities.md\`. Retrieve other memory only when relevant to the task.

Persist durable decisions, constraints, lessons, and project state under \`memory/\`. Never move canonical memory into a provider-specific directory and never store secrets in portable Markdown memory.

## Operating model

- Work from this directory unless the user explicitly selects another workspace.
- Prefer reversible actions and inspect before mutating.
- Keep provider-specific behavior behind adapters when a portable abstraction exists.
- Preserve shell-owned identity and memory when cores, endpoints, or hosts change.
EOF
fi

if [ ! -f "$ROOT/CLAUDE.md" ]; then
  cat > "$ROOT/CLAUDE.md" <<'EOF'
Read and follow ./AGENTS.md. AGENTS.md is canonical. This file exists only for Claude Code compatibility.
EOF
fi

echo "== provisioning portable memory =="
mkdir -p \
  "$ROOT/memory/00 - Inbox" \
  "$ROOT/memory/01 - Daily Notes" \
  "$ROOT/memory/90 - Archive" \
  "$ROOT/memory/99 - Resources"
MEMORY_TEMPLATES="$ROOT/fullstack-agent/templates/portable-memory"
[ -f "$ROOT/memory/VAULT-INDEX.md" ] || cp "$MEMORY_TEMPLATES/VAULT-INDEX.md" "$ROOT/memory/VAULT-INDEX.md"
[ -f "$ROOT/memory/Active Priorities.md" ] || cp "$MEMORY_TEMPLATES/Active Priorities.md" "$ROOT/memory/Active Priorities.md"
[ -f "$ROOT/memory/01 - Daily Notes/Daily Note Template.md" ] || \
  cp "$MEMORY_TEMPLATES/Daily Note Template.md" "$ROOT/memory/01 - Daily Notes/Daily Note Template.md"
if [ ! -f "$ROOT/memory/README.md" ]; then
  cat > "$ROOT/memory/README.md" <<'EOF'
# Portable memory

This directory belongs to the agent shell, not to any model provider. `VAULT-INDEX.md` is the map and memory policy. The directory is ordinary Markdown and can also be opened as an Obsidian vault.
EOF
fi

echo "== provisioning portable identity =="
mkdir -p "$ROOT/identity"
IDENTITY_TEMPLATES="$ROOT/fullstack-agent/templates/identity"
if [ ! -f "$ROOT/identity/IDENTITY.md" ]; then
  cp "$IDENTITY_TEMPLATES/IDENTITY.md" "$ROOT/identity/IDENTITY.md"
  python3 - "$ROOT/identity/IDENTITY.md" "$AGENT_NAME" <<'PY'
import re
import sys
from pathlib import Path
path = Path(sys.argv[1])
name = sys.argv[2]
path.write_text(re.sub(r'(?m)^Name:\s*.*$', f'Name: {name}', path.read_text(), count=1))
PY
fi
[ -f "$ROOT/identity/OPERATING_PRINCIPLES.md" ] || \
  cp "$IDENTITY_TEMPLATES/OPERATING_PRINCIPLES.md" "$ROOT/identity/OPERATING_PRINCIPLES.md"

python3 - "$ROOT" "$PROVIDER" "$AGENT_NAME" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).expanduser().resolve()
provider = sys.argv[2]
name = sys.argv[3]

backtalk = root / "backtalk" / "backtalk.json"
try:
    cfg = json.loads(backtalk.read_text())
except FileNotFoundError:
    cfg = {}
except ValueError:
    raise SystemExit(f"Refusing to overwrite invalid JSON: {backtalk}")

cfg.update({
    "agent_dir": str(root),
    "name": name,
    "permission_mode": "ask",
    "resume_last_session": True,
    "signals_dir": str(root / "backtalk"),
    "barehands_state_dir": str(root / "barehands" / "state"),
    "extra_dirs": [str(root / "memory")],
    "greeting": f"Hello. {name} is online. Hold {{ptt_key}} and talk to me.",
})
core = dict(cfg.get("core") or {})
core["provider"] = provider
if provider == "codex":
    core["binary"] = str(Path.home() / ".local/bin/codex")
    core.setdefault("model", "")
    core.setdefault("extra_args", [])
    cfg["model"] = ""
    cfg["deep_model"] = ""
elif provider == "claude":
    core["binary"] = str(Path.home() / ".local/bin/claude")
    core.setdefault("model", "")
    cfg["model"] = ""
    cfg["deep_model"] = ""
elif provider == "generic-cli":
    core.setdefault("command", [str(root / "core-wrapper")])
    core.setdefault("timeout_seconds", 300)
cfg["core"] = core
backtalk.write_text(json.dumps(cfg, indent=2) + "\n")

visualizer = root / "ai-visualizer" / "ai-visualizer.json"
visualizer.write_text(json.dumps({
    "name": name,
    "face": "board",
    "bus_dir": str(root / "backtalk"),
}, indent=2) + "\n")

barehands = root / "barehands" / "barehands.json"
try:
    bh = json.loads(barehands.read_text())
except (FileNotFoundError, ValueError):
    bh = {}
bh["name"] = name
barehands.write_text(json.dumps(bh, indent=2) + "\n")

shell_cfg = root / "fullstack-agent.json"
shell_cfg.write_text(json.dumps({
    "version": 3,
    "agent_dir": str(root),
    "identity": {
        "name": name,
        "file": "identity/IDENTITY.md",
        "principles_file": "identity/OPERATING_PRINCIPLES.md",
    },
    "memory_dir": str(root / "memory"),
    "core": {"provider": provider},
    "core_profiles": {provider: core},
    "permissions": {"mode": "ask"},
    "components": {
        "memory": True,
        "voice": True,
        "visualizer": True,
        "barehands": True,
        "remote_endpoint": True,
    },
}, indent=2) + "\n")
PY

if [ "$PROVIDER" = "generic-cli" ] && [ ! -e "$ROOT/core-wrapper" ]; then
  cat > "$ROOT/core-wrapper" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cat >/tmp/fullstack-agent-last-prompt.txt
echo "Generic core wrapper is not configured yet. Replace core-wrapper with your runtime bridge."
EOF
  chmod +x "$ROOT/core-wrapper"
fi

echo "== preparing Backtalk Python 3.12 environment =="
cd "$ROOT/backtalk"
if [ -x .venv/bin/python ]; then
  if ! .venv/bin/python -c 'import sys; assert (3, 11) <= sys.version_info[:2] < (3, 13)' >/dev/null 2>&1; then
    echo "Existing backtalk/.venv uses an unsupported Python version." >&2
    echo "Move that environment aside and rerun bootstrap; no files were deleted automatically." >&2
    exit 1
  fi
else
  uv venv --python 3.12 .venv
fi
export UV_PYTHON=3.12

if [ "$INSTALL_MODELS" -eq 1 ]; then
  ./install.sh
else
  ./install.sh --no-models
fi

printf '\n== bootstrap complete ==\n'
printf 'agent home: %s\n' "$ROOT"
printf 'provider:   %s\n' "$PROVIDER"
printf 'identity:   %s/identity/IDENTITY.md\n' "$ROOT"
printf 'memory:     %s/memory/VAULT-INDEX.md\n' "$ROOT"
printf '\nNext:\n'
if [ "$PROVIDER" = "codex" ]; then
  echo "  1. Authenticate the official CLI: codex login --device-auth"
elif [ "$PROVIDER" = "claude" ]; then
  echo "  1. Authenticate the official CLI: claude auth login"
fi
printf '  2. Verify: %s/fullstack-agent/verify-vm.sh --root %q\n' "$ROOT" "$ROOT"
printf '  3. Verify remote voice: %s/fullstack-agent/verify-endpoint.sh --root %q\n' "$ROOT" "$ROOT"
printf '  4. Start private endpoint: cd %q && ./fullstack-agent/endpoint.sh start --tailscale\n' "$ROOT"
printf '\nHeadless mode is first-class: the browser endpoint supplies microphone and speaker hardware.\n'
