#!/usr/bin/env python3
"""Verify the shell-owned memory graph and explicit domain configuration."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def configured_domains(path: Path) -> set[str]:
    return {
        value
        for line in path.read_text(encoding="utf-8").splitlines()
        if (value := line.split("#", 1)[0].strip())
    }


def verify(root: str | Path) -> dict:
    agent_root = Path(root).expanduser().resolve()
    domain_file = agent_root / "config/memory-domains.txt"
    database = agent_root / "memory/memory.db"
    configured = configured_domains(domain_file)
    if not configured:
        raise ValueError("memory domains have not been explicitly configured")

    with sqlite3.connect(database) as conn:
        schema = conn.execute(
            "SELECT value FROM engine_state WHERE key = 'schema_version'"
        ).fetchone()
        if not schema or schema[0] != "1":
            raise ValueError("memory graph schema is not initialized")
        active = {
            row[0] for row in conn.execute("SELECT name FROM domains WHERE active = 1")
        }
        if active != configured:
            raise ValueError("active domains differ from operator configuration")
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("memory graph foreign key check failed")

    return {
        "database": str(database),
        "domains_file": str(domain_file),
        "active_domains": sorted(active, key=str.casefold),
        "schema_version": schema[0],
        "verified": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path.home() / "universal-agent"))
    args = parser.parse_args()
    try:
        result = verify(args.root)
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(f"MEMORY_GRAPH_NOT_READY: {exc}")
        return 1
    print(json.dumps(result, indent=2))
    print("MEMORY_GRAPH_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
