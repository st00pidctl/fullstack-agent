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

## Implemented cores

The matching `st00pidctl/backtalk` universal branch now provides:

- Claude Code adapter
- OpenAI Codex CLI adapter with JSONL events and resumable thread IDs
- generic CLI adapter for arbitrary wrappers and future harnesses

The generic adapter is the escape hatch that keeps the architecture open. A new runtime can be wrapped without teaching the rest of the stack what vendor or harness it is.

## Fresh VM quickstart

The current clean-room validation path targets Ubuntu or Debian and defaults to Codex:

```bash
mkdir -p ~/universal-agent
cd ~/universal-agent
git clone --branch universal-core-architecture https://github.com/st00pidctl/fullstack-agent.git
cd fullstack-agent
./bootstrap-vm.sh --provider codex --name Assistant
```

Authenticate the core:

```bash
codex login
```

Then run the microphone-free verifier:

```bash
cd ~/universal-agent
./fullstack-agent/verify-vm.sh
```

See `FRESH_VM.md` for VM sizing, headless access, audio requirements, and success criteria.

## Components

- **Shell and lifecycle:** this repository
- **Voice and core adapter layer:** `st00pidctl/backtalk`, branch `universal-core-architecture`
- **Memory tooling:** Jared Rhodenizer's `ai-memory-vault`, kept optional because its setup still carries Claude-era assumptions
- **Face:** Jared Rhodenizer's `ai-visualizer`, core-neutral
- **Hands:** Jared Rhodenizer's `barehands`, core-neutral
- **Portable memory:** shell-owned `memory/` directory that survives provider swaps

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

## Upstream compatibility

Keep provider-neutral upstream pieces close to Jared's repositories so fixes remain mergeable. Prefer adapters and generated configuration over invasive rewrites.

Original project and concept:

`https://github.com/jaredrhod/fullstack-agent`

The original project is AGPL-3.0-or-later. This fork retains the upstream licensing obligations. Review `LICENSE` before distribution, hosted service use, or commercial derivative use.
