#!/usr/bin/env bash
# Prove shell-owned memory survives provider-session loss.
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

ROOT="$HOME/universal-agent"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --root) ROOT="${2:?missing path}"; shift 2 ;;
    -h|--help)
      echo "Usage: ./verify-memory.sh [--root PATH]"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
ROOT="${ROOT/#\~/$HOME}"

PY="$ROOT/backtalk/.venv/bin/python"
PROBE="$ROOT/memory/99 - Resources/.memory-durability-probe.md"
BACKUP_DIR="$(mktemp -d)"
PROBE_BACKUP="$BACKUP_DIR/probe.previous"
SESSION_DIR="$ROOT/backtalk"
TOKEN="$($PY - <<'PY'
import secrets
print('MEM-' + secrets.token_hex(8).upper())
PY
)"

if [ ! -x "$PY" ]; then
  echo "FAIL Backtalk Python missing: $PY" >&2
  exit 1
fi
if [ ! -d "$ROOT/memory" ]; then
  echo "FAIL portable memory missing: $ROOT/memory" >&2
  exit 1
fi

had_probe=0
if [ -f "$PROBE" ]; then
  cp "$PROBE" "$PROBE_BACKUP"
  had_probe=1
fi

restore() {
  rm -f "$PROBE"
  if [ "$had_probe" -eq 1 ]; then
    cp "$PROBE_BACKUP" "$PROBE"
  fi

  # Remove any provider session tokens created by the isolated probe and
  # restore the tokens that existed before the test.
  find "$SESSION_DIR" -maxdepth 1 -type f -name '.backtalk_session*' -delete 2>/dev/null || true
  if [ -d "$BACKUP_DIR/sessions" ]; then
    cp -a "$BACKUP_DIR/sessions/." "$SESSION_DIR/" 2>/dev/null || true
  fi
  rm -rf "$BACKUP_DIR"
}
trap restore EXIT

mkdir -p "$(dirname "$PROBE")" "$BACKUP_DIR/sessions"
cat > "$PROBE" <<EOF
# Memory Durability Probe

Probe-Token: $TOKEN

This note exists only for the automated durability verification and may be removed after the test.
EOF

# Provider thread/session IDs are acceleration state, not memory. Move them
# aside so the test begins with no resumable provider conversation.
while IFS= read -r -d '' file; do
  mv "$file" "$BACKUP_DIR/sessions/"
done < <(find "$SESSION_DIR" -maxdepth 1 -type f -name '.backtalk_session*' -print0)

echo "== portable memory durability test =="
echo "provider session tokens temporarily removed"
echo "probe written to shell-owned memory"

set +e
OUTPUT="$({
  cd "$ROOT/backtalk"
  "$PY" -m backtalk.core_smoke \
    --prompt 'Start as a fresh provider session. Follow AGENTS.md. Read memory/99 - Resources/.memory-durability-probe.md and reply with exactly the value after Probe-Token:, with no other words.' \
    --second-prompt ''
} 2>&1)"
RC=$?
set -e

printf '%s\n' "$OUTPUT"
if [ "$RC" -ne 0 ]; then
  echo "FAIL core could not complete a fresh-session memory lookup" >&2
  exit 1
fi
if ! grep -Fq "$TOKEN" <<<"$OUTPUT"; then
  echo "FAIL core response did not recover the shell-owned probe token" >&2
  exit 1
fi

echo "PASS fresh provider session recovered shell-owned memory token"
echo "MEMORY_DURABILITY_VERIFIED: provider session state is disposable; portable memory survived."
