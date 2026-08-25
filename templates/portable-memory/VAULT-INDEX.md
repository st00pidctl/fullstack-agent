---
status: active
project: meta
type: index
---
# Vault Index

This directory is the portable memory owned by the Fullstack Agent shell. It must remain usable when the reasoning core changes.

## Startup sequence

At the start of a new agent session:

1. Read the agent home's `AGENTS.md`.
2. Read this file.
3. Read `[[Active Priorities]]`.
4. Retrieve other notes only when they are relevant to the current task.

Do not load the entire vault into context by default. The index and searchability are the memory system.

## Structure

```text
00 - Inbox             capture first, organize later
01 - Daily Notes       dated work logs and the daily-note template
90 - Archive           completed or retired material
99 - Resources         cross-project references and reusable material
Active Priorities.md   current open work across projects
VAULT-INDEX.md         this map and the memory rules
```

Project folders can be added between Daily Notes and Archive as needed. Give substantial project folders their own index file.

## Memory rules

- The shell owns this memory. Never move canonical memory into a provider-specific directory.
- Durable decisions, constraints, lessons, and state that a future session needs belong here.
- Do not store passwords, API keys, recovery codes, private keys, or other secrets in the vault.
- Prefer updating an existing relevant note before creating a new thin note.
- Use Markdown and YAML frontmatter for durable notes.
- Keep `[[Active Priorities]]` current when work starts, changes state, or finishes.
- When a folder grows large enough that its contents are hard to discover, create an index in that folder.
- Archive only when the user explicitly decides material is complete or retired.
- Provider session IDs, caches, model settings, and harness-specific runtime state do not belong here.

## Frontmatter defaults

Use these fields when creating a durable note:

```yaml
---
status: active
project: meta
type: reference
---
```

Valid status values: `active`, `completed`, `parked`, `idea`, `archived`.

Useful type values: `index`, `reference`, `guide`, `plan`, `log`.

## Daily notes

Daily notes live in `01 - Daily Notes/` and use filename `YYYY-MM-DD.md`. Use `Daily Note Template.md` as the shape. Add another session section when the same date already exists rather than overwriting earlier work.

## Human ownership

These files are ordinary Markdown. They can be opened in Obsidian or another editor, synced independently, backed up with normal file tools, and read by any core that has filesystem access to the agent home.
