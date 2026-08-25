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
      ca-certificates curl git \
      python3 python3-venv python3-pip python3-dev build-essential \
      ffmpeg espeak-ng libportaudio2 portaudio19-dev libsndfile1
  else
    echo "No apt-get detected. Install git, curl, Python 3, ffmpeg, espeak-ng, and PortAudio manually."
  fi
fi

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
    echo "== updating $(basename "$dir") =="
    git -C "$dir" fetch origin "$branch"
    git -C "$dir" checkout "$branch"
    git -C "$dir" pull --ff-only origin "$branch"
  elif [ -e "$dir" ]; then
    echo "Refusing to replace non-git path: $dir" >&2
    exit 1
  else
    echo "== cloning $(basename "$dir") =="
    git clone --branch "$branch" --single-branch "$url" "$dir"
  fi
}

# Avoid updating the script underneath itself. If bootstrap is being run from
# the intended checkout, use it as-is. If it was launched from another clone,
# create or update the working checkout under ROOT.
if [ "$SCRIPT_DIR" = "$ROOT/fullstack-agent" ]; then
  echo "== fullstack-agent: using current checkout =="
else
  sync_repo "https://github.com/st00pidctl/fullstack-agent.git" \
    "$ROOT/fullstack-agent" "universal-core-architecture"
fi

sync_repo "https://github.com/st00pidctl/backtalk.git" \
  "$ROOT/backtalk" "universal-core-architecture"
sync_repo "https://github.com/jaredrhod/ai-memory-vault.git" \
  "$ROOT/ai-memory-vault" "main"
sync_repo "https://github.com/jaredrhod/ai-visualizer.git" \
  "$ROOT/ai-visualizer" "main"
sync_repo "https://github.com/jaredrhod/barehands.git" \
  "$ROOT/barehands" "main"

if [ "$PROVIDER" = "codex" ] && ! command -v codex >/dev/null 2>&1; then
  echo "== installing OpenAI Codex CLI =="
  curl -fsSL https://chatgpt.com/codex/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

if [ ! -f "$ROOT/AGENTS.md" ]; then
  cat > "$ROOT/AGENTS.md" <<EOF
# ${AGENT_NAME}

This directory is the canonical home of ${AGENT_NAME}.

## Identity ownership

AGENTS.md is the portable source of truth for identity and operating rules. Provider-specific instruction files are compatibility shims only.

## Operating model

- Work from this directory unless the user explicitly selects another workspace.
- Use the memory directory for durable cross-session notes that are useful later.
- Do not make a provider, model vendor, or harness part of the agent's identity.
- The reasoning core is replaceable. Preserve shell-owned memory, voice, UI, and configuration when the core changes.
- Prefer reversible actions and inspect before mutating.

## Components

- fullstack-agent: shell, lifecycle, bootstrap, and integration
- backtalk: voice, speech recognition, TTS, and pluggable reasoning core adapter
- ai-memory-vault: optional structured memory tooling
- ai-visualizer: local face and state viewer
- barehands: optional camera-driven visual workspace
- memory: portable shell-owned durable notes
EOF
fi

if [ ! -f "$ROOT/CLAUDE.md" ]; then
  cat > "$ROOT/CLAUDE.md" <<'EOF'
Read and follow ./AGENTS.md. AGENTS.md is canonical. This file exists only for Claude Code compatibility.
EOF
fi

mkdir -p "$ROOT/memory"
if [ ! -f "$ROOT/memory/README.md" ]; then
  cat > "$ROOT/memory/README.md" <<'EOF'
# Portable memory

This directory belongs to the agent shell, not to any model provider. Store durable Markdown notes here when they should survive core changes.
EOF
fi

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
    "greeting": f"Hello. {name} is online. Hold {{ptt_key}} and talk to me.",
})
core = dict(cfg.get("core") or {})
core["provider"] = provider
if provider == "codex":
    core.setdefault("binary", "codex")
    core.setdefault("model", "")
    core.setdefault("extra_args", [])
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
    "version": 2,
    "agent_dir": str(root),
    "identity_file": "AGENTS.md",
    "core": {"provider": provider},
    "permissions": {"mode": "ask"},
    "components": {
        "memory": True,
        "voice": True,
        "visualizer": True,
        "barehands": True,
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
printf 'identity:   %s/AGENTS.md\n' "$ROOT"
printf '\nNext:\n'
if [ "$PROVIDER" = "codex" ]; then
  echo "  1. On a headless VM, run: codex login --device-auth"
  echo "     On a desktop VM, plain codex login is also fine."
  echo "  2. Run the verifier after authentication."
fi
printf '  Run: %s/fullstack-agent/verify-vm.sh --root %q\n' "$ROOT" "$ROOT"
printf '  Then: cd %q && ./fullstack-agent/start.sh\n' "$ROOT"
printf '\nVM note: full voice needs a microphone and audio output visible inside the VM.\n'
printf 'A headless VM can still run the core smoke test and visualizer through an SSH tunnel.\n'
