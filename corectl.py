#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Prepare, inspect, and transactionally switch Fullstack Agent cores."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

BUILT_INS = ("claude", "codex", "generic-cli")
SERVICE = "universal-agent-endpoint.service"


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing configuration: {path}") from exc
    except ValueError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def root_from_args(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def config_paths(root: Path) -> tuple[Path, Path]:
    return root / "fullstack-agent.json", root / "backtalk" / "backtalk.json"


def provider_default(root: Path, provider: str) -> dict:
    if provider == "codex":
        preferred = Path.home() / ".local/bin/codex"
        return {
            "provider": "codex",
            "binary": str(preferred if preferred.exists() else Path("codex")),
            "model": "",
            "extra_args": [],
        }
    if provider == "claude":
        preferred = Path.home() / ".local/bin/claude"
        profile = {"provider": "claude", "model": ""}
        if preferred.exists():
            profile["binary"] = str(preferred)
        return profile
    return {
        "provider": "generic-cli",
        "command": [str(root / "core-wrapper")],
        "timeout_seconds": 300,
    }


def normalized_profiles(root: Path, shell: dict, backtalk: dict) -> dict:
    profiles = copy.deepcopy(shell.get("core_profiles") or {})
    active = str((backtalk.get("core") or {}).get("provider") or "").strip()
    if active:
        profiles[active] = copy.deepcopy(backtalk.get("core") or {})
    return profiles


def status_data(root: Path) -> tuple[dict, int]:
    shell_path, backtalk_path = config_paths(root)
    shell = load_json(shell_path)
    backtalk = load_json(backtalk_path)
    shell_provider = shell.get("core", {}).get("provider")
    voice_core = backtalk.get("core", {})
    voice_provider = voice_core.get("provider")
    data = {
        "agent_home": str(root),
        "shell_core": shell_provider,
        "voice_core": voice_provider,
        "aligned": shell_provider == voice_provider,
        "active_profile": voice_core,
        "saved_profiles": sorted((shell.get("core_profiles") or {}).keys()),
    }
    return data, 0 if data["aligned"] else 1


def status(root: Path, as_json: bool = False) -> int:
    data, rc = status_data(root)
    if as_json:
        print(json.dumps(data, indent=2))
        return rc
    print(f"agent home: {data['agent_home']}")
    print(f"shell core: {data['shell_core'] or '(unset)'}")
    print(f"voice core: {data['voice_core'] or '(unset)'}")
    print("status: aligned" if data["aligned"] else "status: MISMATCH")
    core = data["active_profile"] or {}
    if core.get("adapter"):
        print(f"adapter: {core['adapter']}")
    if core.get("binary"):
        print(f"binary: {core['binary']}")
    if "model" in core:
        print(f"model: {core.get('model') or '(provider default)'}")
    if core.get("command"):
        print("command: " + " ".join(map(str, core["command"])))
    profiles = data["saved_profiles"]
    print("saved profiles: " + (", ".join(profiles) if profiles else "(none yet)"))
    return rc


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = False,
        capture: bool = False, timeout: int | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PATH"] = f"{Path.home() / '.local/bin'}:{env.get('PATH', '')}"
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        check=check,
        capture_output=capture,
        timeout=timeout,
    )


def prepare(root: Path, provider: str, install: bool) -> int:
    if provider == "claude":
        binary = Path.home() / ".local/bin/claude"
        if not binary.exists() and install:
            print("== installing official Anthropic Claude Code ==")
            run([
                "bash", "-lc",
                "curl -fsSL https://claude.ai/install.sh | bash",
            ], check=True)
        if not binary.exists():
            print(f"Claude Code not installed at {binary}", file=sys.stderr)
            print("Run: corectl.py prepare claude --install", file=sys.stderr)
            return 1
        version = run([str(binary), "--version"], capture=True)
        print((version.stdout or version.stderr).strip())
        auth = run([str(binary), "auth", "status", "--text"], capture=True)
        if auth.returncode != 0:
            print("Claude Code is installed but not authenticated.")
            print("Run: claude auth login")
            return 2
        print((auth.stdout or "Claude authentication: ready").strip())
        print("CLAUDE_CORE_READY")
        return 0

    if provider == "codex":
        binary = Path.home() / ".local/bin/codex"
        if not binary.exists() and install:
            print("== installing official OpenAI Codex CLI ==")
            run([
                "bash", "-lc",
                "curl -fsSL https://chatgpt.com/codex/install.sh | sh",
            ], check=True)
        if not binary.exists():
            print(f"Codex not installed at {binary}", file=sys.stderr)
            return 1
        result = run([str(binary), "--version"], capture=True)
        print((result.stdout or result.stderr).strip())
        print("Codex authentication is verified by a real core turn during switch.")
        return 0

    wrapper = root / "core-wrapper"
    if wrapper.exists() and os.access(wrapper, os.X_OK):
        print(f"generic core wrapper: {wrapper}")
        return 0
    print(f"Generic core wrapper missing or not executable: {wrapper}", file=sys.stderr)
    return 1


def target_profile(root: Path, provider: str, profiles: dict,
                   command: list[str] | None = None) -> dict:
    existing = copy.deepcopy(profiles.get(provider) or {})
    if not existing:
        existing = provider_default(root, provider)
    existing["provider"] = provider
    if provider == "claude":
        preferred = Path.home() / ".local/bin/claude"
        if preferred.exists():
            existing["binary"] = str(preferred)
        existing.setdefault("model", "")
    elif provider == "codex":
        preferred = Path.home() / ".local/bin/codex"
        if preferred.exists():
            existing["binary"] = str(preferred)
        existing.setdefault("model", "")
        existing.setdefault("extra_args", [])
    elif provider == "generic-cli":
        if command:
            existing["command"] = command
        existing.setdefault("command", [str(root / "core-wrapper")])
        existing.setdefault("timeout_seconds", 300)
    return existing


def apply_provider(root: Path, provider: str, profile: dict) -> None:
    shell_path, backtalk_path = config_paths(root)
    shell = load_json(shell_path)
    backtalk = load_json(backtalk_path)
    profiles = normalized_profiles(root, shell, backtalk)
    profiles[provider] = copy.deepcopy(profile)
    shell["core_profiles"] = profiles
    shell_core = dict(shell.get("core") or {})
    shell_core["provider"] = provider
    shell["core"] = shell_core
    backtalk["core"] = copy.deepcopy(profile)
    # Provider default model selection belongs in the provider profile.
    # Keep legacy top-level model slots empty so one provider cannot leak a
    # model choice into another provider.
    backtalk["model"] = ""
    backtalk["deep_model"] = ""
    atomic_write_json(shell_path, shell)
    atomic_write_json(backtalk_path, backtalk)


def restart_endpoint(root: Path) -> None:
    result = run(["systemctl", "--user", "restart", SERVICE], capture=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"could not restart {SERVICE}: {detail}")


def real_turn(root: Path) -> tuple[bool, str]:
    py = root / "backtalk/.venv/bin/python"
    if not py.exists():
        return False, f"Backtalk Python missing: {py}"
    result = run(
        [
            str(py), "-m", "backtalk.core_smoke",
            "--prompt", "Reply with exactly CORE_READY.",
            "--second-prompt", "",
        ],
        cwd=root / "backtalk",
        capture=True,
        timeout=240,
    )
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    ok = result.returncode == 0 and "CORE_READY" in output
    return ok, output


def switch_builtin(root: Path, provider: str, command: list[str] | None,
                   restart: bool, verify: bool) -> int:
    if provider not in BUILT_INS:
        raise SystemExit(f"Unknown built-in core {provider!r}")
    shell_path, backtalk_path = config_paths(root)
    shell_before = shell_path.read_bytes()
    backtalk_before = backtalk_path.read_bytes()
    shell = load_json(shell_path)
    backtalk = load_json(backtalk_path)
    old_provider = str((backtalk.get("core") or {}).get("provider") or "unknown")
    profiles = normalized_profiles(root, shell, backtalk)
    profile = target_profile(root, provider, profiles, command)

    print(f"switching core: {old_provider} -> {provider}")
    print("identity owner: shell")
    print("memory owner: shell")
    apply_provider(root, provider, profile)

    try:
        if restart:
            restart_endpoint(root)
            print(f"restarted: {SERVICE}")
        if verify:
            print("== real inference verification ==")
            ok, output = real_turn(root)
            if output:
                print(output)
            if not ok:
                raise RuntimeError("target core did not complete the CORE_READY turn")
    except Exception as exc:
        print(f"SWITCH_FAILED: {exc}", file=sys.stderr)
        shell_path.write_bytes(shell_before)
        backtalk_path.write_bytes(backtalk_before)
        print(f"rolled back core to: {old_provider}", file=sys.stderr)
        if restart:
            try:
                restart_endpoint(root)
                print(f"restarted previous core: {SERVICE}", file=sys.stderr)
            except Exception as restart_exc:
                print(f"rollback restart also failed: {restart_exc}", file=sys.stderr)
        return 1

    print(f"CORE_SWITCH_COMMITTED: {old_provider} -> {provider}")
    print("identity unchanged: identity/")
    print("memory unchanged: memory/")
    print("provider sessions remain isolated in provider-specific state files")
    return 0


def switch_custom(root: Path, provider: str, adapter: str,
                  restart: bool, verify: bool) -> int:
    if ":" not in adapter:
        raise SystemExit(
            "adapter must be '/path/to/file.py:ClassName' or 'python.module:ClassName'"
        )
    source, class_name = adapter.rsplit(":", 1)
    if source.endswith(".py"):
        path = Path(source).expanduser()
        if not path.is_file():
            raise SystemExit(f"adapter file not found: {path}")
        adapter = f"{path.resolve()}:{class_name}"

    shell_path, backtalk_path = config_paths(root)
    shell_before = shell_path.read_bytes()
    backtalk_before = backtalk_path.read_bytes()
    old = load_json(backtalk_path).get("core", {}).get("provider") or "unknown"
    profile = {"provider": provider, "adapter": adapter}
    apply_provider(root, provider, profile)
    try:
        if restart:
            restart_endpoint(root)
        if verify:
            ok, output = real_turn(root)
            if output:
                print(output)
            if not ok:
                raise RuntimeError("custom core did not complete the CORE_READY turn")
    except Exception as exc:
        print(f"SWITCH_FAILED: {exc}", file=sys.stderr)
        shell_path.write_bytes(shell_before)
        backtalk_path.write_bytes(backtalk_before)
        if restart:
            try:
                restart_endpoint(root)
            except Exception:
                pass
        return 1
    print(f"CORE_SWITCH_COMMITTED: {old} -> {provider}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare, inspect, or transactionally switch the replaceable reasoning core."
    )
    parser.add_argument("--root", default="~/universal-agent", help="agent home directory")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list", help="list built-in core adapters")
    status_p = sub.add_parser("status", help="show configured shell and voice core")
    status_p.add_argument("--json", action="store_true")

    prep = sub.add_parser("prepare", help="check or install a provider runtime")
    prep.add_argument("provider", choices=BUILT_INS)
    prep.add_argument("--install", action="store_true",
                      help="install the provider's official native runtime if missing")

    use = sub.add_parser("use", help="switch to a built-in core")
    use.add_argument("provider", choices=BUILT_INS)
    use.add_argument("--restart", action="store_true",
                     help=f"restart {SERVICE} after changing configuration")
    use.add_argument("--verify", action="store_true",
                     help="require a real inference turn or automatically roll back")
    use.add_argument(
        "--command",
        nargs=argparse.REMAINDER,
        help="generic-cli wrapper argv; everything after --command is preserved",
    )

    custom = sub.add_parser("use-custom", help="select a drop-in Python core adapter")
    custom.add_argument("provider", help="local name for this runtime")
    custom.add_argument("adapter", help="/path/to/file.py:ClassName or python.module:ClassName")
    custom.add_argument("--restart", action="store_true")
    custom.add_argument("--verify", action="store_true")

    args = parser.parse_args()
    root = root_from_args(args.root)

    if args.action == "list":
        print("Built-in core adapters:")
        print("  claude       Claude Agent SDK / Claude Code")
        print("  codex        OpenAI Codex CLI")
        print("  generic-cli  any wrapper that reads stdin and writes assistant text to stdout")
        print("Custom native adapters: corectl.py use-custom NAME FILE.py:ClassName")
        return 0
    if args.action == "status":
        return status(root, args.json)
    if args.action == "prepare":
        return prepare(root, args.provider, args.install)
    if args.action == "use":
        return switch_builtin(root, args.provider, args.command, args.restart, args.verify)
    if args.action == "use-custom":
        return switch_custom(root, args.provider, args.adapter, args.restart, args.verify)
    return 2


if __name__ == "__main__":
    sys.exit(main())
