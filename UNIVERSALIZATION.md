# Universalization Status

This fork is transitioning the original fullstack-agent from a Claude Code-specific assembly into a provider-neutral shell.

## Architectural decision

The shell owns:

- identity
- memory wiring
- voice input/output
- visual state
- Barehands integration
- component lifecycle
- canonical permissions vocabulary

A replaceable core owns:

- reasoning runtime connection
- provider session lifecycle
- provider-native tool execution
- provider-native permission mapping
- model/effort mapping

## Why this model

Swapping a core should not change the rest of the system. A new runtime should be installable by dropping in an adapter that satisfies `architecture/CORE_CONTRACT.md` and selecting it in configuration.

## Current upstream constraints

The original Backtalk implementation directly depends on `claude_agent_sdk`. That code belongs behind the Claude adapter in the universal architecture.

The original setup wizard also treats `CLAUDE.md` and `~/.claude/...` as canonical. In this fork, those become compatibility and migration paths rather than the source of truth.

## Next implementation tranche

The next code-level work is to fork or vendor the Backtalk runtime layer and extract its existing `WarmBrain` into `claude`, then add a provider registry and generic CLI implementation. Once that seam exists, Codex, Cursor, and OpenCode can be added independently.
