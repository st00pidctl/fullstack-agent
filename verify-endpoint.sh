#!/usr/bin/env bash
# End-to-end remote endpoint verification without VM audio hardware.
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

ROOT="$HOME/universal-agent"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root) ROOT="${2:?missing path}"; shift 2 ;;
    -h|--help) echo "Usage: ./verify-endpoint.sh [--root PATH]"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
ROOT="${ROOT/#\~/$HOME}"
PY="$ROOT/backtalk/.venv/bin/python"

pass() { printf 'PASS  %s\n' "$1"; }
bad() { printf 'FAIL  %s\n' "$1"; exit 1; }

[ -x "$PY" ] || bad "Backtalk virtual environment missing"
command -v curl >/dev/null 2>&1 || bad "curl missing"
command -v ffmpeg >/dev/null 2>&1 || bad "ffmpeg missing"

if (cd "$ROOT/backtalk" && "$PY" -m backtalk.endpoint_server --self-test); then
  pass "endpoint server and PWA assets present"
else
  bad "endpoint self-test failed"
fi

PORT="$($PY - <<'PY'
import socket
s = socket.socket()
s.bind(('127.0.0.1', 0))
print(s.getsockname()[1])
s.close()
PY
)"
TMP="$(mktemp -d)"
LOG="$TMP/endpoint.log"
START_TS="$(date +%s)"

(
  cd "$ROOT/backtalk"
  "$PY" -m backtalk.endpoint_server --host 127.0.0.1 --port "$PORT" --no-warm >"$LOG" 2>&1
) &
PID=$!
cleanup() {
  kill "$PID" >/dev/null 2>&1 || true
  wait "$PID" >/dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap cleanup EXIT

ready=0
for _ in $(seq 1 150); do
  if curl -fsS "http://127.0.0.1:$PORT/api/health" >"$TMP/health.json" 2>/dev/null; then
    ready=1
    break
  fi
  if ! kill -0 "$PID" 2>/dev/null; then break; fi
  sleep 0.2
done
if [ "$ready" -ne 1 ]; then
  cat "$LOG" >&2 || true
  bad "endpoint server did not become healthy"
fi
pass "loopback endpoint healthy"

if curl -fsS "http://127.0.0.1:$PORT/" | grep -q 'HOLD TO TALK'; then
  pass "mobile PWA served"
else
  bad "mobile PWA did not load"
fi

if python3 - "$TMP/health.json" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
assert s['ok'] is True
assert s.get('provider')
mem = s.get('memory_system') or {}
print(f"ENDPOINT_STATUS provider={s.get('provider')} state={s.get('state')} available_mb={mem.get('available_mb')}")
PY
then
  pass "endpoint reports core and host status"
else
  bad "endpoint health payload invalid"
fi

printf '\n== text -> core -> TTS test ==\n'
TEXT_START="$(date +%s)"
curl -fsS \
  -H 'Content-Type: application/json' \
  --data '{"text":"Reply with exactly REMOTE READY."}' \
  "http://127.0.0.1:$PORT/api/text" > "$TMP/text-turn.json" || {
    cat "$LOG" >&2 || true
    bad "endpoint text turn failed"
  }

AUDIO_URL="$(python3 - "$TMP/text-turn.json" <<'PY'
import json, sys
p = json.load(open(sys.argv[1]))
assert p.get('reply')
assert p.get('audio_url')
print(p['audio_url'])
PY
)" || bad "text turn returned invalid JSON"
pass "core reply returned through endpoint"

curl -fsS "http://127.0.0.1:$PORT$AUDIO_URL" -o "$TMP/first.wav" || bad "reply audio fetch failed"
[ "$(head -c 4 "$TMP/first.wav")" = "RIFF" ] || bad "reply audio is not WAV"
pass "Peter synthesized remote reply audio"
TEXT_END="$(date +%s)"
printf 'INFO  text+core+TTS elapsed=%ss\n' "$((TEXT_END - TEXT_START))"

printf '\n== synthetic phone audio -> STT -> core -> TTS test ==\n'
curl -fsS \
  -H 'Content-Type: audio/wav' \
  --data-binary "@$TMP/first.wav" \
  "http://127.0.0.1:$PORT/api/turn" > "$TMP/voice-turn.json" || {
    cat "$LOG" >&2 || true
    bad "remote voice turn failed"
  }

SECOND_AUDIO_URL="$(python3 - "$TMP/voice-turn.json" <<'PY'
import json, sys
p = json.load(open(sys.argv[1]))
transcript = (p.get('transcript') or '').strip()
reply = (p.get('reply') or '').strip()
assert transcript, p
assert reply, p
assert p.get('audio_url'), p
print(p['audio_url'])
print(f"TRANSCRIPT={transcript}", file=sys.stderr)
print(f"REPLY={reply}", file=sys.stderr)
PY
)" || bad "voice turn returned invalid JSON"
pass "Whisper transcribed endpoint audio"
pass "transcript reached selected core"

curl -fsS "http://127.0.0.1:$PORT$SECOND_AUDIO_URL" -o "$TMP/second.wav" || bad "second reply audio fetch failed"
[ "$(head -c 4 "$TMP/second.wav")" = "RIFF" ] || bad "second reply audio is not WAV"
pass "full remote voice round trip completed"

END_TS="$(date +%s)"
printf '\nREMOTE_ENDPOINT_VERIFIED: no VM microphone or speaker required.\n'
printf 'INFO  full verification elapsed=%ss\n' "$((END_TS - START_TS))"

if command -v free >/dev/null 2>&1; then
  free -h | sed 's/^/INFO  /'
fi

cleanup
trap - EXIT
