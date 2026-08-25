# Universal Fullstack Agent

This repository is the shell and integration layer for a portable personal agent system.

## Canonical model

The shell owns identity, memory integration, voice, visual state, launch/update behavior, and safety policy. The AI runtime is a replaceable core selected through configuration.

Never make a provider-specific instruction file the source of truth. `AGENTS.md` is canonical. Provider files such as `CLAUDE.md` are compatibility shims only.

## Core contract

A core adapter MUST provide these semantic capabilities where supported:

- start a session in the configured agent directory
- stream assistant text
- interrupt an in-flight turn
- stop cleanly
- expose optional session resume
- expose optional usage/context information
- map portable permission modes to provider-native controls
- map portable model/effort requests when supported

Unsupported optional capabilities must degrade gracefully, never prevent the shell from launching.

## Portable permission modes

Use only these canonical modes in shell configuration:

- `ask`: request approval for consequential tool actions
- `trusted`: allow the configured core to act without interactive approval within its own safety boundary
- `read-only`: permit reading/reasoning while prohibiting mutations where the provider can enforce it

Adapters translate these into provider-specific values.

## Core independence

Do not couple the visualizer, speech recognition, TTS, Barehands, memory layout, or state bus to a specific model vendor or harness.

Provider-specific code belongs under `cores/<provider>/` or in a component-level adapter package.

## Compatibility

Preserve upstream Jared Rhodenizer components where possible. Prefer adapters and generated configuration over invasive forks so upstream updates remain mergeable.
