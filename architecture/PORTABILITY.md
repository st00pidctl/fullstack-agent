# Portability Strategy

## Goal

Make the fullstack-agent shell accept any compatible AI core with minimal integration work.

## Keep upstream wherever possible

These subsystems are intended to remain provider-neutral:

- ai-visualizer
- Barehands
- speech-to-text
- text-to-speech
- push-to-talk
- audio ducking
- state/signaling bus
- launcher/update orchestration
- persistent Markdown memory

The principal provider lock currently lives in Backtalk's brain/runtime integration and in Claude-specific setup conventions.

## Adapter-first rule

Do not copy provider conditionals throughout the codebase. One adapter owns each runtime.

Preferred layout:

```text
cores/
  claude/
  codex/
  cursor/
  opencode/
  generic-cli/
```

A future core can be added without editing the visualizer, Barehands, memory vault, TTS, STT, or shell launchers.

## Canonical instructions

`AGENTS.md` is the portable source of truth. Compatibility generators may create or update:

- `CLAUDE.md`
- Cursor rules/instructions
- OpenCode instructions/config
- other harness-specific instruction files

Generated files should clearly identify themselves as compatibility projections.

## Generic CLI adapter

A generic CLI adapter is encouraged as an escape hatch for runtimes that can:

1. receive a prompt on stdin or argv,
2. stream text to stdout,
3. run with a configured working directory,
4. terminate on signal.

It will not expose every advanced feature, but gives new runtimes a low-friction path into the shell.

## Capability negotiation

Adapters advertise capabilities rather than forcing every provider to emulate Claude-specific behavior.

Example:

```json
{
  "streaming": true,
  "interrupt": true,
  "resume": false,
  "permissions": true,
  "context_usage": false,
  "model_switch": true,
  "effort": false
}
```

The UI and voice command layer hide or gracefully reject unsupported functions.
