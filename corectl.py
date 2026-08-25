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


def config_paths(root: Path) -> tuple[Path, Path]:
    return root / "fullstack-agent.json", root / "backtalk" / "backtalk.json"


def status(root: Path) -> int:
    shell_path, backtalk_path = config_paths(root)
    shell = load_json(shell_path)
    backtalk = load_json(backtalk_path)
    shell_provider = shell.get("core", {}).get("provider")
    voice_core = backtalk.get("core", {})
    voice_provider = voice_core.get("provider")
    print(f"agent home: {root}")
    print(f"shell core: {shell_provider or '(unset)'}")
    print(f"voice core: {voice_provider or '(unset)'}")
    if shell_provider != voice_provider:
        print("status: MISMATCH")
        return 1
    print("status: aligned")
    if voice_core.get("adapter"):
        print(f"adapter: {voice_core['adapter']}")
    elif voice_provider == "codex":
        print(f"binary: {voice_core.get('binary') or 'codex'}")
        print(f"model: {voice_core.get('model') or '(Codex default)'}")
    elif voice_provider == "generic-cli":
        command = voice_core.get("command") or []
        print("command: " + (" ".join(map(str, command)) if command else "(unset)"))
    return 0


def save_provider(root: Path, provider: str, backtalk_core: dict,
                  clear_provider_models: bool) -> int:
    shell_path, backtalk_path = config_paths(root)
    shell = load_json(shell_path)
    backtalk = load_json(backtalk_path)

    shell_core = dict(shell.get("core") or {})
    shell_core["provider"] = provider
    shell["core"] = shell_core

    if clear_provider_models:
        backtalk["model"] = ""
        backtalk["deep_model"] = ""
    else:
        backtalk.pop("model", None)
        backtalk.pop("deep_model", None)

    backtalk["core"] = backtalk_core
    write_json(shell_path, shell)
    write_json(backtalk_path, backtalk)

    print(f"core switched to: {provider}")
    print("identity unchanged: AGENTS.md")
    print("memory unchanged: memory/")
    print("provider sessions remain isolated in provider-specific state files")
    print(f"verify: {root}/fullstack-agent/verify-vm.sh --root {shlex.quote(str(root))}")
    return 0


def switch_builtin(root: Path, provider: str, command: list[str] | None) -> int:
    if provider not in BUILT_INS:
        raise SystemExit(f"Unknown built-in core {provider!r}")
    _, backtalk_path = config_paths(root)
    backtalk = load_json(backtalk_path)
    old_core = dict(backtalk.get("core") or {})

    if provider == "claude":
        new_core = {"provider": "claude"}
        clear_models = False
    elif provider == "codex":
        new_core = {
            "provider": "codex",
            "binary": old_core.get("binary") or "codex",
            "model": old_core.get("model") if old_core.get("provider") == "codex" else "",
            "extra_args": old_core.get("extra_args") if old_core.get("provider") == "codex" else [],
        }
        clear_models = True
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
        clear_models = True

    return save_provider(root, provider, new_core, clear_models)


def switch_custom(root: Path, provider: str, adapter: str) -> int:
    if ":" not in adapter:
        raise SystemExit(
            "adapter must be '/path/to/file.py:ClassName' or 'python.module:ClassName'"
        )
    source = adapter.rsplit(":", 1)[0]
    if source.endswith(".py"):
        path = Path(source).expanduser()
        if not path.is_file():
            raise SystemExit(f"adapter file not found: {path}")
        adapter = f"{path.resolve()}:{adapter.rsplit(':', 1)[1]}"
    return save_provider(
        root,
        provider,
        {"provider": provider, "adapter": adapter},
        clear_provider_models=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect or switch the replaceable Fullstack Agent reasoning core."
    )
    parser.add_argument("--root", default="~/universal-agent", help="agent home directory")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list", help="list built-in core adapters")
    sub.add_parser("status", help="show configured shell and voice core")

    use = sub.add_parser("use", help="switch to a built-in core")
    use.add_argument("provider", choices=BUILT_INS)
    use.add_argument(
        "--command",
        nargs=argparse.REMAINDER,
        help="generic-cli wrapper argv; everything after --command is preserved",
    )

    custom = sub.add_parser("use-custom", help="select a drop-in Python core adapter")
    custom.add_argument("provider", help="local name for this runtime")
    custom.add_argument(
        "adapter",
        help="/path/to/file.py:ClassName or python.module:ClassName",
    )

    args = parser.parse_args()
    root = root_from_args(args.root)

    if args.action == "list":
        print("Built-in core adapters:")
        print("  claude       Claude Agent SDK")
        print("  codex        OpenAI Codex CLI")
        print("  generic-cli  any wrapper that reads stdin and writes assistant text to stdout")
        print("Custom native adapters: corectl.py use-custom NAME FILE.py:ClassName")
        return 0
    if args.action == "status":
        return status(root)
    if args.action == "use":
        return switch_builtin(root, args.provider, args.command)
    if args.action == "use-custom":
        return switch_custom(root, args.provider, args.adapter)
    return 2


if __name__ == "__main__":
    sys.exit(main())
