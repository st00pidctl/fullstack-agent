# fullstack-agent universal fork

A portable agent shell with persistent identity, memory, voice, visual state, optional hands, and a replaceable reasoning core.

This fork is based on Jared Rhodenizer's `fullstack-agent`, but the ownership model is intentionally different: **the agent belongs to the shell, not to Claude Code, Codex, or any other single harness.** Swap the core without rebuilding identity, memory, STT, TTS, visualizer, Barehands, or the operator workflow.

## Architecture

```text
AGENTS.md + shell-owned memory
            |
      stable core contract
            |
   replaceable runtime adapter
            |
 voice + face + hands + lifecycle
```

`AGENTS.md` is canonical. Provider-specific files such as `CLAUDE.md` are compatibility shims only.

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
git clone --branch universal-core-architecture https://github.com/st00pidctl/fullstack-agent.git
cd fullstack-agent
./bootstrap-vm.sh --provider codex --name Assistant
```

On a headless VM, authenticate Codex with:

```bash
codex login --device-auth
```

Then run the microphone-free verifier:

```bash
cd ~/universal-agent
./fullstack-agent/verify-vm.sh
```

The verifier checks repository layout, portable memory, JSON and cross-component wiring, Backtalk's Python version, selected-core startup, one real headless agent turn, and the visualizer state endpoint.

See `FRESH_VM.md` for VM sizing, audio requirements, SSH tunneling, and success criteria.

## Portable memory

The bootstrap provisions a provider-neutral Markdown vault under `memory/`:

```text
memory/
  VAULT-INDEX.md
  Active Priorities.md
  00 - Inbox/
  01 - Daily Notes/
    Daily Note Template.md
  90 - Archive/
  99 - Resources/
```

`AGENTS.md` tells every core to read the vault index and active priorities at session start, then retrieve other notes only when relevant. The memory directory can also be opened directly as an Obsidian vault, but Obsidian is not required for the agent to use it.

The upstream `ai-memory-vault` repository is still cloned as reference and optional tooling, but its Claude-era bootstrap is no longer allowed to own canonical identity or memory.

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
- **Voice and core adapter layer:** `st00pidctl/backtalk`, branch `universal-core-architecture`
- **Portable memory:** shell-owned `memory/`
- **Memory reference/tooling:** Jared Rhodenizer's `ai-memory-vault`
- **Face:** Jared Rhodenizer's `ai-visualizer`, core-neutral
- **Hands:** Jared Rhodenizer's `barehands`, core-neutral

## Core contract

See:

- `architecture/CORE_CONTRACT.md`
- `architecture/PORTABILITY.md`
- `cores/README.md`
- `UNIVERSALIZATION.md`
- `FRESH_VM.md`

Canonical shell configuration is modeled in `config/fullstack-agent.example.json`.

Portable permission vocabulary:

- `ask`
- `trusted`
- `read-only`

Each adapter maps those semantics to the safest compatible provider behavior and reports unsupported capabilities instead of pretending feature parity.

## Current limitations

- Codex `exec --json` currently emits completed agent-message items rather than token-by-token assistant text, so spoken output begins after the completed message is available.
- Codex does not currently expose the same spoken per-tool approval callback used by the Claude SDK adapter. The Codex path remains sandboxed and uses its automatic review lane.
- Some voice-console operations are provider-specific. Capability negotiation is authoritative.
- Full voice inside a VM requires guest-visible microphone and speaker devices. A headless VM can still validate the core, memory layout, state bus, and visualizer.
- The automated checks validate syntax, configuration shape, and the drop-in loader. The authenticated clean-VM runtime test is intentionally performed by `verify-vm.sh` after you log the selected provider in on the VM.

## Upstream compatibility

Keep provider-neutral upstream pieces close to Jared's repositories so fixes remain mergeable. Prefer adapters and generated configuration over invasive rewrites.

Original project and concept:

`https://github.com/jaredrhod/fullstack-agent`

The original project is AGPL-3.0-or-later. This fork retains the upstream licensing obligations. Review `LICENSE` before distribution, hosted service use, or commercial derivative use.
