#!/usr/bin/env bash
# Prove the same shell-owned agent survives a real reasoning-core swap.
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

ROOT="$HOME/universal-agent"
TARGET=""

usage() {
  cat <<'EOF'
Usage: ./verify-core-swap.sh --target PROVIDER [--root PATH]

The target runtime must already be installed and authenticated.
The test leaves TARGET active on success and restores the previous core on
failure.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root) ROOT="${2:?missing path}"; shift 2 ;;
    --target) TARGET="${2:?missing provider}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

ROOT="${ROOT/#\~/$HOME}"
if [ -z "$TARGET" ]; then
  echo "--target is required" >&2
  usage >&2
  exit 2
fi

CORECTL="$ROOT/fullstack-agent/corectl.py"
MEMORY_VERIFY="$ROOT/fullstack-agent/verify-memory.sh"
if [ ! -x "$CORECTL" ]; then
  echo "FAIL corectl missing or not executable: $CORECTL" >&2
  exit 1
fi
if [ ! -x "$MEMORY_VERIFY" ]; then
  echo "FAIL memory verifier missing or not executable: $MEMORY_VERIFY" >&2
  exit 1
fi

CURRENT="$($CORECTL --root "$ROOT" status --json | python3 -c \
  'import json,sys; print(json.load(sys.stdin).get("voice_core") or "")')"
if [ -z "$CURRENT" ]; then
  echo "FAIL current core is not configured" >&2
  exit 1
fi
if [ "$CURRENT" = "$TARGET" ]; then
  echo "FAIL target core is already active: $TARGET" >&2
  exit 1
fi

identity_hash() {
  sha256sum \
    "$ROOT/identity/IDENTITY.md" \
    "$ROOT/identity/OPERATING_PRINCIPLES.md" | sha256sum | awk '{print $1}'
}

IDENTITY_BEFORE="$(identity_hash)"
ROLLED_BACK=0

rollback() {
  if [ "$ROLLED_BACK" -eq 1 ]; then
    return
  fi
  ROLLED_BACK=1
  echo "== rolling back to $CURRENT ==" >&2
  if ! "$CORECTL" --root "$ROOT" use "$CURRENT" --restart --verify; then
    echo "CRITICAL: automatic rollback to $CURRENT failed" >&2
    echo "Run: $CORECTL --root $ROOT use $CURRENT --restart --verify" >&2
  fi
}

fail_after_switch() {
  echo "FAIL $1" >&2
  rollback
  exit 1
}

echo "== core swap proof =="
echo "from: $CURRENT"
echo "to:   $TARGET"
echo "identity hash: $IDENTITY_BEFORE"

echo "== target runtime preflight =="
if ! "$CORECTL" --root "$ROOT" prepare "$TARGET"; then
  echo "FAIL target runtime is not ready: $TARGET" >&2
  exit 1
fi

echo "== transactional switch and real inference =="
if ! "$CORECTL" --root "$ROOT" use "$TARGET" --restart --verify; then
  echo "FAIL transactional switch did not commit" >&2
  exit 1
fi

IDENTITY_AFTER_SWITCH="$(identity_hash)"
if [ "$IDENTITY_AFTER_SWITCH" != "$IDENTITY_BEFORE" ]; then
  fail_after_switch "identity files changed during core switch"
fi
echo "PASS shell-owned identity unchanged"

echo "== fresh-session memory recovery on target core =="
if ! "$MEMORY_VERIFY" --root "$ROOT"; then
  fail_after_switch "target core could not recover shell-owned memory"
fi

echo "== endpoint provider check =="
HEALTH="$(curl -fsS http://127.0.0.1:8787/api/health 2>/dev/null || true)"
if [ -z "$HEALTH" ]; then
  fail_after_switch "endpoint health API did not answer"
fi
PROVIDER="$(printf '%s' "$HEALTH" | python3 -c \
  'import json,sys; print(json.load(sys.stdin).get("provider") or "")' 2>/dev/null || true)"
if [ "$PROVIDER" != "$TARGET" ]; then
  fail_after_switch "endpoint reports provider '$PROVIDER', expected '$TARGET'"
fi
echo "PASS endpoint now reports provider=$TARGET"

IDENTITY_FINAL="$(identity_hash)"
if [ "$IDENTITY_FINAL" != "$IDENTITY_BEFORE" ]; then
  fail_after_switch "identity files changed during memory verification"
fi

echo
echo "CORE_SWAP_VERIFIED: $CURRENT -> $TARGET"
echo "Identity unchanged. Portable memory recovered. Endpoint unchanged."
echo "Target core remains active for the physical phone test."
