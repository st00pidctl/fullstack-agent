# Universalization status

The universal branch has moved past architecture-only work. The shell now has a concrete fresh-VM path and the matching Backtalk fork has a provider registry with working adapter implementations.

## Ownership model

The shell owns:

- canonical identity in `AGENTS.md`
- portable memory wiring
- voice input/output
- visual state and state bus
- Barehands integration
- component lifecycle
- portable permission vocabulary

A replaceable core owns:

- connection to the reasoning runtime
- provider session lifecycle
- provider-native tools
- provider-native permission mapping
- model and effort mapping where available

## Implemented

### Shell

- canonical `AGENTS.md`
- provider-neutral configuration model
- compatibility-only `CLAUDE.md`
- core contract and portability docs
- fresh Ubuntu/Debian VM bootstrap
- headless VM verifier
- shell-owned `memory/`

### Backtalk fork

Repository: `st00pidctl/backtalk`
Stable branch: `main`

Implemented adapters:

- Claude Code
- OpenAI Codex CLI
- generic CLI wrapper

Backtalk's existing audio, Whisper STT, TTS, PTT, signaling, visualizer bus, and voice loop remain outside provider-specific code.

The Codex adapter uses `codex exec --json`, stores the thread ID emitted by Codex, and resumes the thread on later turns. The generic adapter accepts any executable wrapper that reads a prompt from stdin and writes assistant text to stdout.

## Fresh VM milestone

`bootstrap-vm.sh` and `verify-vm.sh` are the current integration gate. A new VM should be able to:

1. install dependencies
2. clone the shell and component repositories
3. configure a selected core
4. authenticate the runtime
5. complete one headless agent turn
6. serve a valid visualizer mock state
7. launch the normal stack when guest audio devices are available

See `FRESH_VM.md`.

## Remaining work

The next tranche is compatibility depth rather than basic portability:

- exercise the fresh-VM path and fix runtime defects found by the verifier
- improve Codex response streaming when the CLI exposes a suitable assistant delta/event
- add first-class OpenCode and Cursor adapters where their runtime interfaces justify it
- improve provider-specific voice-console capability handling
- progressively decouple memory tooling from Claude-era setup assumptions
- add automated integration tests that do not require paid/authenticated model calls

## Rule going forward

Do not add provider conditionals to the visualizer, speech recognition, TTS, Barehands, or memory ownership layers. New runtime-specific behavior belongs in an adapter. If a runtime cannot satisfy an optional capability, report that capability as unsupported and keep the shell operational.
