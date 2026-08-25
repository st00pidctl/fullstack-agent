#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Operator control plane for shell-owned agent state.

This intentionally edits only shell/component configuration. Provider session
state is not identity and is never used as the source of truth for the name.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import socket
import sys


def root_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def identity_file(root: Path) -> Path:
    return root / "identity" / "IDENTITY.md"


def current_name(root: Path) -> str:
    path = identity_file(root)
    if path.exists():
        match = re.search(r"(?m)^Name:\s*(.+?)\s*$", path.read_text())
        if match:
            return match.group(1).strip()
    cfg = read_json(root / "backtalk" / "backtalk.json")
    return str(cfg.get("name") or "Assistant")


def set_identity_name(root: Path, name: str) -> None:
    name = name.strip()
    if not name:
        raise SystemExit("Name cannot be empty")
    if "\n" in name or "\r" in name:
        raise SystemExit("Name must be one line")

    path = identity_file(root)
    if not path.exists():
        raise SystemExit(f"Missing identity file: {path}. Run repair-vm.sh first.")
    text = path.read_text()
    if re.search(r"(?m)^Name:\s*.*$", text):
        text = re.sub(r"(?m)^Name:\s*.*$", f"Name: {name}", text, count=1)
    else:
        text = text.replace("# Agent Identity", f"# Agent Identity\n\nName: {name}", 1)
    path.write_text(text)

    backtalk_path = root / "backtalk" / "backtalk.json"
    backtalk = read_json(backtalk_path)
    backtalk["name"] = name
    write_json(backtalk_path, backtalk)

    visualizer_path = root / "ai-visualizer" / "ai-visualizer.json"
    visualizer = read_json(visualizer_path)
    visualizer["name"] = name
    write_json(visualizer_path, visualizer)

    barehands_path = root / "barehands" / "barehands.json"
    barehands = read_json(barehands_path)
    barehands["name"] = name
    write_json(barehands_path, barehands)

    shell_path = root / "fullstack-agent.json"
    shell = read_json(shell_path)
    identity = dict(shell.get("identity") or {})
    identity["name"] = name
    identity["file"] = "identity/IDENTITY.md"
    shell["identity"] = identity
    write_json(shell_path, shell)


def show_status(root: Path) -> int:
    shell = read_json(root / "fullstack-agent.json")
    backtalk = read_json(root / "backtalk" / "backtalk.json")
    core = backtalk.get("core") or shell.get("core") or {}
    print(f"name:     {current_name(root)}")
    print(f"host:     {socket.gethostname()}")
    print(f"core:     {core.get('provider') or 'unknown'}")
    print(f"identity: {identity_file(root)}")
    print(f"memory:   {root / 'memory'}")
    print("model:    provider default" if not core.get("model") else f"model:    {core.get('model')}")
    return 0


def show_identity(root: Path) -> int:
    files = [
        root / "identity" / "IDENTITY.md",
        root / "identity" / "OPERATING_PRINCIPLES.md",
    ]
    for path in files:
        if not path.exists():
            print(f"missing: {path}", file=sys.stderr)
            return 1
        print(f"===== {path.name} =====")
        print(path.read_text().rstrip())
        print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Universal Fullstack Agent operator control")
    parser.add_argument("--root", default="~/universal-agent", help="agent home")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="show shell-owned agent status")

    identity = sub.add_parser("identity", help="inspect or change shell-owned identity")
    identity_sub = identity.add_subparsers(dest="identity_command", required=True)
    identity_sub.add_parser("show", help="print portable identity documents")
    rename = identity_sub.add_parser("set-name", help="change the agent display name everywhere")
    rename.add_argument("name")

    args = parser.parse_args()
    root = root_path(args.root)

    if args.command == "status":
        return show_status(root)
    if args.command == "identity" and args.identity_command == "show":
        return show_identity(root)
    if args.command == "identity" and args.identity_command == "set-name":
        old = current_name(root)
        set_identity_name(root, args.name)
        print(f"Renamed agent: {old} -> {args.name.strip()}")
        print("Restart the endpoint service so every component reloads the new identity.")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
