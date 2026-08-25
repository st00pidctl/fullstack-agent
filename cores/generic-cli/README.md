# Generic CLI Core

This is the portability escape hatch.

A generic command-line agent can join the shell if it can be launched in the agent directory, accept prompts, stream plain text, and stop on signal.

Suggested configuration:

```json
{
  "provider": "generic-cli",
  "options": {
    "command": ["my-agent", "--stream"],
    "prompt_transport": "stdin"
  }
}
```

Advanced functionality such as resumable sessions, tool approval callbacks, context usage, model switching, and effort switching is capability-dependent.
