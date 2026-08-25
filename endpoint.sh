#!/usr/bin/env bash
# Manage the headless remote browser endpoint.
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

ROOT="$HOME/universal-agent"
PORT=8787
TAILSCALE=0
ACTION="${1:-status}"
[ "$#" -gt 0 ] && shift || true

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root) ROOT="${2:?missing path}"; shift 2 ;;
    --port) PORT="${2:?missing port}"; shift 2 ;;
    --tailscale) TAILSCALE=1; shift ;;
    -h|--help)
      cat <<'EOF'
Usage: ./endpoint.sh <start|foreground|stop|status|logs|install-user-service> [options]

Options:
  --root PATH     Agent home. Default: ~/universal-agent
  --port PORT     Loopback endpoint port. Default: 8787
  --tailscale     Configure Tailscale Serve after start
EOF
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

ROOT="${ROOT/#\~/$HOME}"
PY="$ROOT/backtalk/.venv/bin/python"
PIDFILE="$ROOT/.remote-endpoint.pid"
LOGDIR="$ROOT/logs"
LOGFILE="$LOGDIR/remote-endpoint.log"
mkdir -p "$LOGDIR"

require_runtime() {
  if [ ! -x "$PY" ]; then
    echo "Backtalk virtual environment missing: $PY" >&2
    exit 1
  fi
}

running_pid() {
  [ -f "$PIDFILE" ] || return 1
  local pid
  pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && printf '%s' "$pid"
}

wait_health() {
  local i
  for i in $(seq 1 100); do
    if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.2
  done
  return 1
}

configure_tailscale() {
  if ! command -v tailscale >/dev/null 2>&1; then
    echo "Tailscale CLI not found; endpoint remains loopback-only." >&2
    return 1
  fi
  echo "== configuring private HTTPS through Tailscale Serve =="
  tailscale serve --bg "$PORT"
  echo
  tailscale serve status || true
}

case "$ACTION" in
  start)
    require_runtime
    if pid="$(running_pid)"; then
      echo "Remote endpoint already running (pid $pid)."
    else
      echo "== starting remote endpoint on 127.0.0.1:$PORT =="
      (
        cd "$ROOT/backtalk"
        nohup "$PY" -m backtalk.endpoint_server --host 127.0.0.1 --port "$PORT" \
          >>"$LOGFILE" 2>&1 &
        echo $! > "$PIDFILE"
      )
      if ! wait_health; then
        echo "Endpoint did not become healthy. Recent log:" >&2
        tail -80 "$LOGFILE" >&2 || true
        exit 1
      fi
      echo "Endpoint healthy."
    fi
    [ "$TAILSCALE" -eq 1 ] && configure_tailscale
    ;;
  foreground)
    require_runtime
    cd "$ROOT/backtalk"
    exec "$PY" -m backtalk.endpoint_server --host 127.0.0.1 --port "$PORT"
    ;;
  stop)
    if pid="$(running_pid)"; then
      echo "Stopping remote endpoint (pid $pid)..."
      kill "$pid"
      for _ in $(seq 1 30); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.1
      done
      kill -9 "$pid" 2>/dev/null || true
    else
      echo "Remote endpoint is not running."
    fi
    rm -f "$PIDFILE"
    ;;
  status)
    if pid="$(running_pid)"; then
      echo "Remote endpoint running (pid $pid)."
      curl -fsS "http://127.0.0.1:$PORT/api/status" | python3 -m json.tool || true
    else
      echo "Remote endpoint is not running."
    fi
    if command -v tailscale >/dev/null 2>&1; then
      echo
      tailscale serve status 2>/dev/null || true
    fi
    ;;
  logs)
    touch "$LOGFILE"
    exec tail -f "$LOGFILE"
    ;;
  install-user-service)
    require_runtime
    UNIT_DIR="$HOME/.config/systemd/user"
    UNIT="$UNIT_DIR/universal-agent-endpoint.service"
    mkdir -p "$UNIT_DIR"
    cat > "$UNIT" <<EOF
[Unit]
Description=Universal Fullstack Agent remote endpoint
After=network-online.target tailscaled.service

[Service]
Type=simple
WorkingDirectory=$ROOT/backtalk
ExecStart=$PY -m backtalk.endpoint_server --host 127.0.0.1 --port $PORT
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable --now universal-agent-endpoint.service
    echo "Installed and started: $UNIT"
    echo "For start at boot before login, enable lingering once: sudo loginctl enable-linger $USER"
    [ "$TAILSCALE" -eq 1 ] && configure_tailscale
    ;;
  *)
    echo "Unknown action: $ACTION" >&2
    exit 2
    ;;
esac
