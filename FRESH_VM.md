# Fresh VM bring-up

This is the clean-room test path for the universal branch. It is designed for a new Ubuntu or Debian VM and uses Codex as the default non-Claude core.

## VM recommendation

For a headless validation VM, start with roughly:

- 4 vCPU
- 8 GB RAM minimum, 12 GB preferred if preloading local speech models
- 30 GB disk minimum
- Ubuntu 24.04 LTS is the primary tested target
- network access for package and model downloads

The bootstrap installs a managed Python 3.12 with `uv` for Backtalk, so the voice environment does not depend on the distro's default Python version.

For the complete voice experience, the guest must also see a microphone and audio output device. A normal server VM without audio passthrough can still validate the core, memory layout, state bus, and visualizer.

## One clean install

```bash
mkdir -p ~/universal-agent
cd ~/universal-agent
git clone --branch universal-core-architecture https://github.com/st00pidctl/fullstack-agent.git
cd fullstack-agent
./bootstrap-vm.sh --provider codex --name Assistant
```

The bootstrap:

1. installs Linux packages needed by the voice stack
2. installs `uv` and a managed Python 3.12
3. installs Codex CLI when selected
4. clones the universal Backtalk fork
5. clones upstream ai-memory-vault, ai-visualizer, and Barehands
6. creates portable `AGENTS.md` and a Claude compatibility shim
7. creates shell-owned `memory/`
8. writes component configuration and state-bus paths
9. installs Backtalk and preloads local speech models

The script is safe to re-run. Existing Git repositories are updated instead of replaced, an existing canonical `AGENTS.md` is not overwritten, and the bootstrap does not update the script underneath itself while it is running.

## Authenticate the selected core

For a headless Codex VM, use device authentication:

```bash
codex login --device-auth
```

For a VM with a usable desktop and browser, plain `codex login` is also fine.

Then verify the VM:

```bash
cd ~/universal-agent
./fullstack-agent/verify-vm.sh
```

The verifier does not require a microphone. It checks configuration, provider startup, one headless agent turn, and the visualizer mock state endpoint.

## Start the stack

```bash
cd ~/universal-agent
./fullstack-agent/start.sh
```

The existing launcher starts the visualizer, Barehands server, and Backtalk. Backtalk reads `core.provider` and loads the matching adapter.

## Headless visualizer access

The upstream visualizer intentionally binds to loopback. From another machine, tunnel it through SSH:

```bash
ssh -L 8790:127.0.0.1:8790 user@vm-address
```

Then open `http://127.0.0.1:8790/` locally while the visualizer is running.

## Core choices

### Codex

This is the primary fresh VM validation path. The adapter uses `codex exec --json`, captures Codex thread IDs, and resumes them for later voice turns.

### Claude

Run bootstrap with:

```bash
./bootstrap-vm.sh --provider claude
```

Claude remains an adapter, not the owner of identity or memory. Authentication and install steps remain provider-specific.

### Generic CLI

Run:

```bash
./bootstrap-vm.sh --provider generic-cli
```

The bootstrap creates `~/universal-agent/core-wrapper`. Replace that executable with a wrapper for any harness. Backtalk sends prompts on stdin and consumes assistant text on stdout. The wrapper can maintain whatever provider-specific session state it needs internally.

## What is intentionally not universal yet

- Codex JSONL currently provides completed agent-message items rather than token-by-token assistant text, so TTS begins after Codex has produced the final agent message for that turn.
- Codex does not currently use Backtalk's Claude-style spoken per-tool approval callback. The adapter stays in Codex's sandboxed automatic-review lane.
- Some voice-console operations are provider-specific. Capability negotiation is the authority; unsupported operations must report that they are unsupported.
- Upstream ai-memory-vault still contains Claude-era setup assumptions. The universal shell therefore owns `AGENTS.md` and `memory/` independently, and the upstream vault remains an optional memory tool rather than the source of identity.

## Success criteria

A fresh VM is considered software-ready when `verify-vm.sh` reports VERIFIED. Full voice readiness additionally requires working guest microphone and speaker devices.
