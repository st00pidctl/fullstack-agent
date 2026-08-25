# Cores

Each directory under `cores/` represents an interchangeable agent runtime adapter.

A core is responsible only for translating the universal shell contract into a provider or harness API.

Initial targets:

- `claude`: compatibility with the original Claude Agent SDK implementation
- `codex`: OpenAI Codex runtime
- `cursor`: Cursor agent/CLI integration where supported
- `opencode`: OpenCode integration
- `generic-cli`: fallback adapter for stream-capable command-line agents

Do not place memory, voice, visualizer, or Barehands logic in a core.
