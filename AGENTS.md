# Universal Fullstack Agent

This repository is the shell and integration layer for a portable personal agent system.

## Canonical model

The shell owns identity, memory integration, voice, visual state, launch/update behavior, and safety policy. The AI runtime is a replaceable core selected through configuration.

Never make a provider-specific instruction file the source of truth. `AGENTS.md` is the portable constitution. Runtime identity lives under `identity/`, durable knowledge lives under `memory/`, and provider files such as `CLAUDE.md` are compatibility shims only.

## State hierarchy

Keep these layers distinct:

1. `AGENTS.md`: portable constitution and startup protocol.
2. `identity/`: name, role, self-description, and operating principles.
3. `memory/`: durable facts, decisions, lessons, project state, and the shell-owned memory graph.
4. Provider session state: disposable conversation acceleration only.
5. Core: replaceable reasoning/tool runtime.
6. Host: replaceable compute location.
7. Endpoint: replaceable human I/O device.

Provider-session loss must never imply identity or memory loss.

## Evidence based memory

`architecture/MEMORY_CONTRACT.md` is the canonical behavioral contract for durable memory.

Memory rules include:

- canonical memory units are atomic claims
- evidence and provenance are retained separately from the claim
- confidence, relevance, freshness, and domain confidence are separate values
- every verified durable claim has exactly one primary domain
- every stored relationship has exactly one primary domain
- domains are explicit configuration and are never silently invented
- assumptions and inferred relationships remain visibly unverified until confirmed
- corrections preserve history by superseding rather than silently rewriting old claims
- creation-time verification and point-of-use verification are both required
- audits include candidates, contradictions, stale claims, domain questions, and inferred relationships
- periodic review occurs weekly, with additional quantity triggers at 20 unresolved candidates or 5 high-impact or contradictory items
- consequential actions must not rely silently on unresolved memory

Graph connectivity can affect relevance and retrieval, but graph density must never be treated as proof.

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

Do not couple identity, the visualizer, speech recognition, TTS, Barehands, memory layout, or the state bus to a specific model vendor or harness.

Provider-specific code belongs under `cores/<provider>/` or in a component-level adapter package.

Codex is the active core for the current customization phase. Future core portability remains an architectural requirement, not a current milestone.

## Compatibility

Preserve upstream Jared Rhodenizer components where possible. Prefer adapters and generated configuration over invasive forks so upstream updates remain mergeable.
