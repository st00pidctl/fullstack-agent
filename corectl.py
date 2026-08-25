#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Switch Fullstack Agent reasoning cores without moving shell-owned state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import sys

BUILT_INS = ("claude", "codex", "generic-cli")


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing configuration: {path}") from exc
    except ValueError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def root_from_args(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def status(root: Path) -> int:
    shell_path = root / "fullstack-agent.json"
    backtalk_path = root / "backtalk" / "backtalk.json"
    shell = load_json(shell_path)
    backtalk = load_json(backtalk_path)
    shell_provider = shell.get("core", {}).get("provider")
    voice_provider = backtalk.get("core", {}).get("provider")
    print(f"agent home: {root}")
    print(f"shell core: {shell_provider or '(unset)'}")
    print(f"voice core: {voice_provider or '(unset)'}")
    if shell_provider != voice_provider:
        print("status: MISMATCH")
        return 1
    print("status: aligned")
    if voice_provider == "codex":
        core = backtalk.get("core", {})
        print(f"binary: {core.get('binary') or 'codex'}")
        print(f"model: {core.get('model') or '(Codex default)'}")
    elif voice_provider == "generic-cli":
        command = backtalk.get("core", {}).get("command") or []
        print("command: " + (" ".join(map(str, command)) if command else "(unset)"))
    return 0


def switch(root: Path, provider: str, command: list[str] | None) -> int:
    if provider not in BUILT_INS:
        raise SystemExit(
            f"Unknown built-in core {provider!r}. Use generic-cli for an arbitrary runtime."
        )

    shell_path = root / "fullstack-agent.json"
    backtalk_path = root / "backtalk" / "backtalk.json"
    shell = load_json(shell_path)
    backtalk = load_json(backtalk_path)

    shell_core = dict(shell.get("core") or {})
    shell_core["provider"] = provider
    shell["core"] = shell_core

    old_core = dict(backtalk.get("core") or {})
    if provider == "claude":
        new_core = {"provider": "claude"}
        # Removing provider-specific overrides lets Backtalk's upstream
        # defaults choose the current Claude models.
        backtalk.pop("model", None)
        backtalk.pop("deep_model", None)
    elif provider == "codex":
        new_core = {
            "provider": "codex",
            "binary": old_core.get("binary") or "codex",
            "model": old_core.get("model") if old_core.get("provider") == "codex" else "",
            "extra_args": old_core.get("extra_args") if old_core.get("provider") == "codex" else [],
        }
        # Do not leak Claude model IDs into Codex voice-console requests.
        backtalk["model"] = ""
        backtalk["deep_model"] = ""
    else:
        if command:
            argv = command
        elif old_core.get("provider") == "generic-cli" and old_core.get("command"):
            argv = list(old_core["command"])
        else:
            argv = [str(root / "core-wrapper")]
        new_core = {
            "provider": "generic-cli",
            "command": argv,
            "timeout_seconds": int(old_core.get("timeout_seconds") or 300),
        }
        backtalk["model"] = ""
        backtalk["deep_model"] = ""

    backtalk["core"] = new_core
    write_json(shell_path, shell)
    write_json(backtalk_path, backtalk)

    print(f"core switched to: {provider}")
    print("identity unchanged: AGENTS.md")
    print("memory unchanged: memory/")
    print("provider sessions remain isolated in their provider-specific state files")
    print(f"verify: {root}/fullstack-agent/verify-vm.sh --root {shlex.quote(str(root))}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect or switch the replaceable Fullstack Agent reasoning core."
    )
    parser.add_argument(
        "--root", default="~/universal-agent", help="agent home directory"
    )
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list", help="list built-in core adapters")
    sub.add_parser("status", help="show configured shell and voice core")
    use = sub.add_parser("use", help="switch to a core without changing shell state")
    use.add_argument("provider", choices=BUILT_INS)
    use.add_argument(
        "--command",
        nargs=argparse.REMAINDER,
        help="generic-cli wrapper argv; everything after --command is preserved",
    )

    args = parser.parse_args()
    root = root_from_args(args.root)

    if args.action == "list":
        print("Built-in core adapters:")
        print("  claude       Claude Agent SDK")
        print("  codex        OpenAI Codex CLI")
        print("  generic-cli  any wrapper that reads stdin and writes assistant text to stdout")
        return 0
    if args.action == "status":
        return status(root)
    if args.action == "use":
        return switch(root, args.provider, args.command)
    return 2


if __name__ == "__main__":
    sys.exit(main())
