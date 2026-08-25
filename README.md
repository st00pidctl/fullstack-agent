# fullstack-agent universal fork

A portable agent shell with memory, voice, visual state, optional hands, and a replaceable reasoning core.

This fork is based on Jared Rhodenizer's `fullstack-agent`, but its architectural goal is different: **the agent belongs to the shell, not to Claude Code or any other single harness.** A compatible core should be swappable without rebuilding identity, memory, TTS, STT, visualizer, Barehands, launchers, or user workflow.

## Design goal

Think of the system as:

```text
identity + memory + shell
          |
      core adapter
          |
  any compatible runtime
          |
 voice / face / hands
```

A core may be Claude Code, Codex, Cursor, OpenCode, another agent harness, or a generic stream-capable CLI. Provider-specific behavior is isolated behind the core adapter contract in `architecture/CORE_CONTRACT.md`.

## Canonical instructions

`AGENTS.md` is the source of truth for this fork. Runtime-specific files such as `CLAUDE.md` are compatibility shims, not canonical identity.

## Components

The original stack remains valuable and is preserved wherever possible:

- **Memory:** Jared Rhodenizer's `ai-memory-vault`, adapted conceptually toward provider-neutral Markdown memory.
- **Voice:** `backtalk`, whose STT, TTS, push-to-talk, audio and signaling layers are largely reusable. Its Claude-specific brain is the main runtime seam that must be extracted behind an adapter.
- **Face:** `ai-visualizer`, intended to remain core-neutral.
- **Hands:** `barehands`, intended to remain core-neutral.

## Universal core architecture

See:

- `architecture/CORE_CONTRACT.md`
- `architecture/PORTABILITY.md`
- `cores/README.md`
- `UNIVERSALIZATION.md`

Canonical configuration is modeled in `config/fullstack-agent.example.json`.

Portable permission vocabulary:

- `ask`
- `trusted`
- `read-only`

Adapters translate those semantics into provider-native controls.

## Current status

The shell architecture and compatibility rules are now provider-neutral on the `universal-core-architecture` branch.

The major remaining implementation seam is Backtalk itself. Upstream Backtalk directly imports the Claude Agent SDK, so true drag-and-drop cores require extracting that runtime into a provider adapter or maintaining a universal Backtalk fork.

Planned initial adapters:

```text
cores/
  claude/
  codex/
  cursor/
  opencode/
  generic-cli/
```

The generic CLI adapter is intentionally important: a new runtime should have a low-friction path into the system even when it cannot expose advanced features such as resumable sessions, permission callbacks or context accounting.

## Upstream compatibility

This fork should avoid unnecessary duplication. Provider-neutral upstream pieces should stay close to Jared's repositories so fixes can continue to be merged. Prefer adapter layers and generated compatibility configuration over invasive rewrites.

## Original project

Original project and concept by Jared Rhodenizer:

`https://github.com/jaredrhod/fullstack-agent`

The original project is AGPL-3.0-or-later. This fork retains the upstream licensing obligations. Review `LICENSE` before distribution, hosted service use, or commercial derivative use.
