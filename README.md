# fullstack-agent universal fork

A portable agent shell with persistent identity, memory, voice, visual state, optional hands, replaceable reasoning cores, and replaceable endpoint devices.

This fork is based on Jared Rhodenizer's `fullstack-agent`, but the ownership model is intentionally different: **the agent belongs to the shell, not to Claude Code, Codex, a particular VM, or a particular microphone.** Swap the core or the endpoint without rebuilding identity, memory, STT, TTS, visualizer, or operator workflow.

## Architecture

```text
AGENTS.md + shell-owned memory
            |
      stable core contract
            |
   replaceable runtime adapter
            |
      headless agent host
            |
   replaceable endpoint device
```

`AGENTS.md` is canonical. Provider-specific files such as `CLAUDE.md` are compatibility shims only.

The current reference deployment separates three things explicitly:

```text
CORE != AGENT != ENDPOINT
```

The core reasons and uses tools. The shell owns identity and durable state. The endpoint owns local human I/O such as microphone, speaker, and touch controls.

## Core integration lanes

The matching `st00pidctl/backtalk` universal branch supports three ways to attach a core:

1. Built-in adapters for Claude Code and OpenAI Codex CLI.
2. `generic-cli` for any wrapper that reads prompts from stdin and writes assistant text to stdout.
3. A native drop-in Python adapter selected by file path or import path, with no Backtalk registry edit required.

This means a future runtime can join at the simplest level first, then gain a native adapter later without changing the shell.

## Fresh VM quickstart

Ubuntu 24.04 LTS is the primary clean-room target. The bootstrap uses a managed Python 3.12 for Backtalk and defaults to Codex as the first non-Claude validation core.

```bash
mkdir -p ~/universal-agent
cd ~/universal-agent
git clone --branch main https://github.com/st00pidctl/fullstack-agent.git
cd fullstack-agent
./bootstrap-vm.sh --provider codex --name Assistant \
  --memory-domains "Personal,Work,Project Name"
```

On a headless VM, authenticate Codex with:

```bash
codex login --device-auth
```

Then run the software/core verifier:

```bash
cd ~/universal-agent
./fullstack-agent/verify-vm.sh
```

The verifier checks repository layout, portable memory, JSON and cross-component wiring, Backtalk's Python version, selected-core startup, real multi-turn core resume, and the visualizer state endpoint.

See `FRESH_VM.md` for VM sizing and clean-room success criteria.

## Remote voice endpoint

The VM no longer needs microphone or speaker passthrough for full voice operation.

The matching Backtalk branch includes a mobile-first browser/PWA endpoint. The phone provides microphone capture and speaker playback. Peter keeps Whisper STT, TTS, memory, session state, and the selected reasoning core.

First verify the complete synthetic remote voice loop:

```bash
cd ~/universal-agent
./fullstack-agent/verify-endpoint.sh
```

A successful run ends with:

```text
REMOTE_ENDPOINT_VERIFIED: no VM microphone or speaker required.
```

Then start the private endpoint and expose it over tailnet-only HTTPS:

```bash
./fullstack-agent/endpoint.sh start --tailscale
./fullstack-agent/endpoint.sh status
```

Open the HTTPS Tailscale Serve address on the phone. The PWA provides hold-to-talk, transcript, reply text, endpoint state, interrupt, and phone audio playback.

See `REMOTE_ENDPOINT.md` for lifecycle, systemd, security, and capacity details.

## Portable memory

The bootstrap provisions a provider-neutral Markdown vault and a shell-owned SQLite memory graph under `memory/`:

```text
memory/
  VAULT-INDEX.md
  Active Priorities.md
  00 - Inbox/
  01 - Daily Notes/
    Daily Note Template.md
  90 - Archive/
  99 - Resources/
  memory.db
```

`AGENTS.md` tells every core to read the vault index and active priorities at session start, then retrieve other notes only when relevant. The memory directory can also be opened directly as an Obsidian vault, but Obsidian is not required for the agent to use it.

The upstream `ai-memory-vault` repository is still cloned as reference and optional tooling, but its Claude-era bootstrap is no longer allowed to own canonical identity or memory.

Structured memory is governed by `architecture/MEMORY_CONTRACT.md`. Domains are explicit operator configuration in `config/memory-domains.txt`; there is no invented or catch-all domain. Bootstrap accepts `--memory-domains` for a deliberate initial set. Later edits are synchronized with:

```bash
python3 fullstack-agent/memoryctl.py runtime-init --root ~/universal-agent
python3 fullstack-agent/memoryctl.py domain sync config/memory-domains.txt
python3 fullstack-agent/memoryctl.py domain list
python3 fullstack-agent/memoryctl.py audit status
```

Claims remain candidates until verified with exactly one active primary domain. Consequential use must pass `memoryctl.py gate` first. Corrections supersede prior claims without erasing history, and audits cover candidates, contradictions, stale claims, domain questions, and inferred relationships.

To adopt the graph on an existing VM without replacing identity or Markdown memory:

```bash
cd ~/universal-agent/fullstack-agent
git pull --ff-only
./repair-vm.sh --root ~/universal-agent \
  --memory-domains "Personal,Work,Project Name"
./verify-memory-graph.py --root ~/universal-agent
```

Replace the example names with the exact domains you intend to enforce. A successful independent check ends with `MEMORY_GRAPH_VERIFIED`.

## Switch cores

`corectl.py` changes the reasoning runtime while leaving identity and memory alone.

```bash
cd ~/universal-agent
./fullstack-agent/corectl.py status
./fullstack-agent/corectl.py list
./fullstack-agent/corectl.py use codex
./fullstack-agent/corectl.py use claude
```

Use any command-line harness through a wrapper:

```bash
./fullstack-agent/corectl.py use generic-cli --command /path/to/my-wrapper
```

Use a native Python drop-in adapter:

```bash
./fullstack-agent/corectl.py use-custom my-runtime /path/to/my_core.py:MyRuntimeBrain
```

Backtalk includes `examples/custom_core.py` as the reference contract.

## Components

- **Shell and lifecycle:** this repository
- **Voice, endpoint server, and core adapter layer:** `st00pidctl/backtalk`, branch `main`
- **Portable memory:** shell-owned `memory/`
- **Memory reference/tooling:** Jared Rhodenizer's `ai-memory-vault`
- **Face:** Jared Rhodenizer's `ai-visualizer`, core-neutral
- **Hands:** Jared Rhodenizer's `barehands`, core-neutral
- **Endpoint hardware:** phone/browser first, designed to be replaceable

## Core contract

See:

- `architecture/CORE_CONTRACT.md`
- `architecture/PORTABILITY.md`
- `cores/README.md`
- `UNIVERSALIZATION.md`
- `FRESH_VM.md`
- `REMOTE_ENDPOINT.md`

Canonical shell configuration is modeled in `config/fullstack-agent.example.json`.

Portable permission vocabulary:

- `ask`
- `trusted`
- `read-only`

Each adapter maps those semantics to the safest compatible provider behavior and reports unsupported capabilities instead of pretending feature parity.

## Current limitations

- Codex `exec --json` currently emits completed agent-message items rather than token-by-token assistant text, so spoken output begins after the completed message is available.
- Codex does not currently expose the same spoken per-tool approval callback used by the Claude SDK adapter. The Codex path remains sandboxed and noninteractive for remote voice turns.
- Some voice-console operations are provider-specific. Capability negotiation is authoritative.
- The first browser endpoint serializes turns through one agent session. It is intentionally not a multi-user concurrent service yet.
- The first endpoint relies on Tailscale as the private HTTPS and network identity boundary. Future multi-user/customer use should add explicit endpoint pairing and per-device authorization.
- Automated CI validates code shape and assets. Authenticated core inference and local speech models are validated on the clean VM through `verify-vm.sh` and `verify-endpoint.sh`.

## Upstream compatibility

Keep provider-neutral upstream pieces close to Jared's repositories so fixes remain mergeable. Prefer adapters and generated configuration over invasive rewrites.

Original project and concept:

`https://github.com/jaredrhod/fullstack-agent`

The original project is AGPL-3.0-or-later. This fork retains the upstream licensing obligations. Review `LICENSE` before distribution, hosted service use, or commercial derivative use.
