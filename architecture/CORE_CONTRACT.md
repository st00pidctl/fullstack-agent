# Core Adapter Contract

A **core** is the replaceable reasoning and tool-execution runtime behind the fullstack-agent shell.

The shell must be able to accept a new core without changing voice, memory, visualizer, Barehands, launcher, or user identity.

## Required interface

Conceptually, every adapter exposes:

```python
class AgentCore:
    async def start(self): ...
    async def ask_stream(self, prompt: str): ...
    async def interrupt(self): ...
    async def stop(self): ...
```

`ask_stream` yields human-readable text chunks suitable for sentence-oriented TTS.

## Optional capabilities

Adapters may additionally implement:

```python
async def resume(self, session_id: str | None = None): ...
async def reset_turn(self): ...
async def context_usage(self): ...
async def usage(self): ...
async def set_permission_mode(self, mode: str): ...
async def set_model(self, model: str): ...
async def set_effort(self, effort: str): ...
async def clear(self): ...
async def compact(self): ...
```

The shell feature-detects optional capabilities. Missing capabilities return a clear unsupported result instead of failing the session.

## Configuration

Canonical shell configuration should use provider-neutral keys:

```json
{
  "core": {
    "provider": "codex",
    "model": "default",
    "effort": "default",
    "resume_last_session": true
  },
  "permissions": {
    "mode": "ask"
  }
}
```

Provider-specific settings live under `core.options` and must not leak into other components.

## Events

The core reports semantic lifecycle events to the shell:

- `idle`
- `listening`
- `thinking`
- `tool`
- `speaking`
- `error`

The shell owns translation of these events into state files or a future event bus.

## Identity

A core does not own identity. The shell's canonical identity and operating instructions live in `AGENTS.md` plus the configured memory system. Provider-specific instruction files are generated compatibility projections.

## Tool permissions

Canonical modes are `ask`, `trusted`, and `read-only`. Each adapter translates these into the closest provider-native controls and documents any semantic mismatch.

## Session storage

Store provider session metadata under a provider-neutral directory, for example:

```text
.state/sessions/<provider>.json
```

Never bake provider session identifiers into unrelated component configuration.
