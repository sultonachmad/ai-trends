#!/usr/bin/env bash
# Run the app in the background for a test session, with readable logs.
#
#   scripts/devtest.sh start     migrate the database, start backend + frontend, wait until both answer
#   scripts/devtest.sh stop      stop both
#   scripts/devtest.sh restart   stop, then start
#   scripts/devtest.sh status    are they running / answering?
#   scripts/devtest.sh errors    show errors, tracebacks and 5xx responses from the logs
#   scripts/devtest.sh tail      follow the combined log
#
# Logs (git-ignored) live in .ttest/log/:
#   backend.log, frontend.log   one service each
#   dev.log                     both, interleaved
# Every line is `2026-11-20T10:15:02+0700 [backend] <original line>`; stderr is included,
# so Python tracebacks are captured, and terminal colour codes are stripped.
# The logs of the previous run are kept as *.prev.log.
#
# For an interactive foreground session use scripts/dev.sh instead.

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/.ttest/log"
RUN_DIR="$LOG_DIR/run"
READY_TIMEOUT_SECONDS=90
SERVICES=(backend frontend)

export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
# shellcheck disable=SC1091
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

BE_PORT=8000
FE_PORT=3100
if [ -f "$ROOT/.ttest/config.yaml" ]; then
  read -r BE_PORT FE_PORT < <(python3 - "$ROOT/.ttest/config.yaml" <<'PY' 2>/dev/null || echo "8000 3100"
import sys, yaml
services = yaml.safe_load(open(sys.argv[1])).get("run", {}).get("services", [])
port = lambda name, default: next((s["port"] for s in services if s.get("name") == name), default)
print(port("backend", 8000), port("frontend", 3100))
PY
  )
fi
BACKEND_URL="http://localhost:$BE_PORT/api/health"
FRONTEND_URL="http://localhost:$FE_PORT/login"

# Prefix each line with a timestamp and the service name; drop ANSI colour codes.
stamp() {
  sed -u 's/\x1b\[[0-9;?]*[a-zA-Z]//g' |
    awk -v svc="$1" '{ print strftime("%Y-%m-%dT%H:%M:%S%z"), "[" svc "]", $0; fflush() }'
}

log_to() { stamp "$1" | tee -a "$LOG_DIR/$1.log" >>"$LOG_DIR/dev.log"; }

port_in_use() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

answers() { curl -s -o /dev/null --max-time 3 "$1"; }

pid_of() { cat "$RUN_DIR/$1.pid" 2>/dev/null; }

is_running() { local pid; pid="$(pid_of "$1")"; [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; }

start_service() { # name, working dir, command...
  local name="$1" dir="$2"
  shift 2
  # setsid: own process group, so `stop` can end the whole tree (reloader, workers).
  # The log writer gets its own stdout/stderr, so it never holds the caller's pipe
  # open: `devtest.sh start | tail` must return as soon as the servers are ready.
  PYTHONUNBUFFERED=1 FORCE_COLOR=0 setsid bash -c '
    cd "$1" || exit 1
    shift
    exec "$@" 2>&1
  ' _ "$dir" "$@" > >(
    exec >/dev/null 2>&1 # permanent: a redirection on the function call would keep a saved copy
    log_to "$name"
  ) 2>&1 </dev/null &
  echo $! >"$RUN_DIR/$name.pid"
}

cmd_start() {
  mkdir -p "$RUN_DIR"
  for name in "${SERVICES[@]}"; do
    if is_running "$name"; then
      echo "$name is already running (pid $(pid_of "$name")). Use: scripts/devtest.sh restart"
      return 1
    fi
  done
  for port in "$BE_PORT" "$FE_PORT"; do
    if port_in_use "$port"; then
      echo "Port $port is already in use (another dev server?). Stop it first."
      return 1
    fi
  done
  for file in backend frontend dev; do
    [ -f "$LOG_DIR/$file.log" ] && mv -f "$LOG_DIR/$file.log" "$LOG_DIR/$file.prev.log"
  done

  local python="$ROOT/backend/.venv/bin/python"
  if [ ! -x "$python" ] || [ ! -x "$ROOT/frontend/node_modules/.bin/next" ]; then
    echo "Dependencies are missing. Run scripts/dev.sh once (it installs them), then retry."
    return 1
  fi

  echo "Applying database migrations..."
  local migrate_output migrate_status
  migrate_output="$(cd "$ROOT/backend" && "$python" -m alembic upgrade head 2>&1)"
  migrate_status=$?
  printf '%s\n' "$migrate_output" | stamp migrate | tee -a "$LOG_DIR/backend.log" >>"$LOG_DIR/dev.log"
  if [ "$migrate_status" -ne 0 ]; then
    echo "Migration failed — see $LOG_DIR/backend.log"
    tail -n 15 "$LOG_DIR/backend.log"
    return 1
  fi

  start_service backend "$ROOT/backend" "$python" -m uvicorn app.main:app \
    --host 127.0.0.1 --port "$BE_PORT" --reload
  start_service frontend "$ROOT/frontend" npm run dev -- -p "$FE_PORT"

  echo "Waiting for both servers (up to ${READY_TIMEOUT_SECONDS}s)..."
  local waited=0
  until answers "$BACKEND_URL" && answers "$FRONTEND_URL"; do
    for name in "${SERVICES[@]}"; do
      if ! is_running "$name"; then
        echo "$name stopped during startup. Last log lines:"
        tail -n 25 "$LOG_DIR/$name.log"
        cmd_stop >/dev/null
        return 1
      fi
    done
    if [ "$waited" -ge "$READY_TIMEOUT_SECONDS" ]; then
      echo "Not ready after ${READY_TIMEOUT_SECONDS}s. Last log lines:"
      tail -n 25 "$LOG_DIR/dev.log"
      cmd_stop >/dev/null
      return 1
    fi
    sleep 1
    waited=$((waited + 1))
  done
  echo "Ready.  Backend: http://localhost:$BE_PORT   Frontend: http://localhost:$FE_PORT"
  echo "Logs:   $LOG_DIR/{backend,frontend,dev}.log"
}

cmd_stop() {
  local name pid
  for name in "${SERVICES[@]}"; do
    pid="$(pid_of "$name")"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
      for _ in 1 2 3 4 5 6 7 8 9 10; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
      done
      kill -KILL -- "-$pid" 2>/dev/null
      echo "Stopped $name."
    else
      echo "$name was not running."
    fi
    rm -f "$RUN_DIR/$name.pid"
  done
}

cmd_status() {
  local name
  for name in "${SERVICES[@]}"; do
    if is_running "$name"; then echo "$name: running (pid $(pid_of "$name"))"; else echo "$name: stopped"; fi
  done
  if answers "$BACKEND_URL"; then echo "backend answers at $BACKEND_URL"; else echo "backend does not answer"; fi
  if answers "$FRONTEND_URL"; then echo "frontend answers at $FRONTEND_URL"; else echo "frontend does not answer"; fi
}

cmd_errors() {
  if [ ! -f "$LOG_DIR/dev.log" ]; then
    echo "No log yet. Run: scripts/devtest.sh start"
    return 0
  fi
  # Python tracebacks and log errors, uvicorn 5xx access lines, Next.js failures.
  if ! grep -nE 'Traceback|ERROR|CRITICAL|Exception|Error:|" 5[0-9]{2} | 5[0-9]{2} in [0-9]+ms|⨯|Failed to compile|Unhandled' \
    -A 12 "$LOG_DIR/dev.log"; then
    echo "No errors in $LOG_DIR/dev.log"
  fi
}

case "${1:-}" in
  start) cmd_start ;;
  stop) cmd_stop ;;
  restart) cmd_stop && cmd_start ;;
  status) cmd_status ;;
  errors) cmd_errors ;;
  tail) tail -n 40 -F "$LOG_DIR/dev.log" ;;
  *)
    sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
